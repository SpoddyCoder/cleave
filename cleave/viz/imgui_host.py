"""ImGui context, font, renderer, and raw mouse queue for the live window.

The shell decides which events reach this host. Keyboard stays in
``input_dispatch``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import pygame
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_ARRAY_BUFFER_BINDING,
    GL_BACK,
    GL_CULL_FACE,
    GL_CURRENT_PROGRAM,
    GL_FRONT,
    GL_POLYGON_MODE,
    glBindBuffer,
    glDisable,
    glEnable,
    glGetIntegerv,
    glIsEnabled,
    glPolygonMode,
    glUseProgram,
)
from imgui_bundle import imgui
from imgui_bundle.python_backends.opengl_backend import ProgrammablePipelineRenderer

from cleave.gl_state import restore_gl_state, save_gl_state
from cleave.viz.overlay_primitives import overlay_font_path
from cleave.viz.row_sections import INSPECTOR_GROUP_EXPANDED
from cleave.viz.theme import (
    BACKGROUND,
    BORDER_COLOR,
    DISABLED,
    FOCUS_ROW_BG_ALPHA,
    HIGHLIGHT,
    HOVER,
    HOVER_BG_ALPHA,
    VALUE,
    tuning_ui_metrics,
)

RENDERER_CLASS = ProgrammablePipelineRenderer

PLAY_GLYPH = "\u25b6"
PAUSE_GLYPH = "\u275a\u275a"

_IMGUI_BUTTON = {1: 0, 2: 2, 3: 1}
_GL_LIBS: list[Any] = []
_ContextGetter = Callable[[], int | None]


class _HeadlessRenderer:
    """No GL device objects. Used only when ``create`` has no current context."""

    def shutdown(self) -> None:
        return None

    def render(self, _draw_data: Any) -> None:
        return None


def mouse_button(event: pygame.event.Event) -> int | None:
    """ImGui button index for a pygame mouse button event, or None."""
    return _IMGUI_BUTTON.get(getattr(event, "button", 0))


def rgba(rgb: tuple[int, int, int], alpha: float = 1.0) -> imgui.ImVec4:
    return imgui.ImVec4(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, alpha)


def _context_pointer(getter: _ContextGetter) -> int:
    try:
        handle = getter()
    except Exception:
        return 0
    if not handle:
        return 0
    return int(handle)


def _dlopen_mode(*, resident_only: bool) -> int | None:
    lazy = getattr(os, "RTLD_LAZY", None)
    if resident_only:
        noload = getattr(os, "RTLD_NOLOAD", None)
        if lazy is None or noload is None:
            return None
        return lazy | noload
    glob = getattr(os, "RTLD_GLOBAL", None)
    if glob is None:
        return None
    if lazy is None:
        return glob
    return lazy | glob


def _open_gl_lib(name: str, *, resident_only: bool) -> Any | None:
    import ctypes

    mode = _dlopen_mode(resident_only=resident_only)
    if mode is None:
        return None
    try:
        return ctypes.CDLL(name, mode=mode)
    except OSError:
        return None


def _live_getter(
    names: tuple[str, ...], symbol: str, *, resident_only: bool
) -> _ContextGetter | None:
    """Load *symbol* and return it only when it reports a current context."""
    import ctypes

    for name in names:
        lib = _open_gl_lib(name, resident_only=resident_only)
        if lib is None:
            continue
        fn = getattr(lib, symbol, None)
        if fn is None:
            continue
        fn.restype = ctypes.c_void_p
        fn.argtypes = ()
        _GL_LIBS.append(lib)
        if _context_pointer(fn):
            return fn
    return None


def _native_context_getter() -> _ContextGetter | None:
    """``glXGetCurrentContext`` or ``eglGetCurrentContext``, whichever is current.

    ``WAYLAND_DISPLAY`` makes PyOpenGL install ``EGLPlatform``, whose
    ``GetCurrentContext`` is ``eglGetCurrentContext`` and stays null for the
    GLX context pygame already made current. moderngl shares that context but
    does not expose the native pointer. Already-resident libraries are tried
    first so a second ``libGL`` does not hide pygame's context.
    """
    probes = (
        (("libGLX.so.0", "libGL.so.1"), "glXGetCurrentContext"),
        (("libEGL.so.1",), "eglGetCurrentContext"),
    )
    for resident_only in (True, False):
        for names, symbol in probes:
            getter = _live_getter(names, symbol, resident_only=resident_only)
            if getter is not None:
                return getter
    return None


def _install_pyopengl_context(getter: _ContextGetter) -> None:
    """Point PyOpenGL's context lookup at *getter*. OpenGL is already imported."""
    import OpenGL.platform as gl_platform

    gl_platform.GetCurrentContext = getter
    gl_platform.CurrentContextIsValid = getter
    plat = gl_platform.PLATFORM
    if plat is None:
        return
    plat.GetCurrentContext = getter
    plat.CurrentContextIsValid = getter


def _gl_context_current() -> bool:
    """True when PyOpenGL's ``GetCurrentContext`` sees the current context.

    ``glGetString`` is not enough: it skips ``contextdata.getContext``, and
    ``glVertexAttribPointer`` does not.
    """
    import OpenGL.platform as gl_platform

    if _context_pointer(gl_platform.GetCurrentContext):
        return True
    getter = _native_context_getter()
    if getter is None:
        return False
    _install_pyopengl_context(getter)
    return bool(_context_pointer(gl_platform.GetCurrentContext))


def _select_renderer_class() -> type[ProgrammablePipelineRenderer] | type[_HeadlessRenderer]:
    if _gl_context_current():
        return RENDERER_CLASS
    return _HeadlessRenderer


def _shell_glyph_ranges() -> list[int]:
    """Default Latin plus the glyphs the shell draws outside that range.

    Dear ImGui stops the default range at U+00FF. Disclosure triangles, the
    transport play and pause marks, and the menu check then rasterize as "?".
    """
    ranges = list(imgui.get_io().fonts.get_glyph_ranges_default())
    if ranges and ranges[-1] == 0:
        ranges = ranges[:-1]
    ranges.extend(
        (
            ord(PLAY_GLYPH),
            ord(INSPECTOR_GROUP_EXPANDED),
            ord("✓"),
            ord("✓"),
            ord(PAUSE_GLYPH[0]),
            ord(PAUSE_GLYPH[0]),
            0,
        )
    )
    return ranges


def _ensure_font_atlas() -> None:
    """Build the atlas before ``imgui.new_frame``.

    ``ProgrammablePipelineRenderer`` does this while uploading the font
    texture. The headless renderer never uploads, and ``new_frame`` asserts
    if ``GetTexDataAsRGBA32`` has not run.
    """
    fonts = imgui.get_io().fonts
    if fonts.is_built():
        return
    fonts.get_tex_data_as_rgba32()
    fonts.clear_tex_data()


def _keep_keyboard_nav_off() -> None:
    nav = int(imgui.ConfigFlags_.nav_enable_keyboard)
    io = imgui.get_io()
    io.config_flags = int(io.config_flags) & ~nav


def _apply_theme() -> None:
    """Map overlay roles onto ImGui, including the hover wash."""
    style = imgui.get_style()
    style.window_rounding = 0.0
    style.frame_rounding = 0.0
    style.popup_rounding = 0.0
    style.scrollbar_rounding = 0.0
    highlight = rgba(HIGHLIGHT, FOCUS_ROW_BG_ALPHA / 255.0)
    hover = rgba(HOVER, HOVER_BG_ALPHA / 255.0)
    background = rgba(BACKGROUND)
    text = rgba(VALUE)
    disabled = rgba(DISABLED)
    assignments = {
        imgui.Col_.text: text,
        imgui.Col_.text_disabled: disabled,
        imgui.Col_.window_bg: background,
        imgui.Col_.child_bg: background,
        imgui.Col_.popup_bg: background,
        imgui.Col_.menu_bar_bg: background,
        imgui.Col_.border: rgba(BORDER_COLOR),
        imgui.Col_.header: highlight,
        imgui.Col_.header_hovered: hover,
        imgui.Col_.header_active: hover,
        imgui.Col_.button: background,
        imgui.Col_.button_hovered: highlight,
        imgui.Col_.button_active: highlight,
        imgui.Col_.frame_bg: background,
        imgui.Col_.title_bg: background,
        imgui.Col_.title_bg_active: background,
        imgui.Col_.title_bg_collapsed: background,
        imgui.Col_.check_mark: text,
        imgui.Col_.separator: disabled,
        imgui.Col_.text_selected_bg: highlight,
        imgui.Col_.nav_highlight: rgba(HIGHLIGHT),
    }
    for column, color in assignments.items():
        style.set_color_(int(column), color)


def _gl_int(param: int) -> int:
    value = glGetIntegerv(param)
    try:
        return int(value[0])
    except (TypeError, IndexError):
        return int(value)


class _ExtraGlState:
    __slots__ = ("program", "array_buffer", "cull", "polygon_front", "polygon_back")

    def __init__(self) -> None:
        self.program = _gl_int(GL_CURRENT_PROGRAM)
        self.array_buffer = _gl_int(GL_ARRAY_BUFFER_BINDING)
        self.cull = bool(glIsEnabled(GL_CULL_FACE))
        polygon = glGetIntegerv(GL_POLYGON_MODE)
        try:
            self.polygon_front = int(polygon[0])
            self.polygon_back = int(polygon[1])
        except (TypeError, IndexError):
            self.polygon_front = int(polygon)
            self.polygon_back = self.polygon_front

    def restore(self) -> None:
        glUseProgram(self.program)
        glBindBuffer(GL_ARRAY_BUFFER, self.array_buffer)
        if self.cull:
            glEnable(GL_CULL_FACE)
        else:
            glDisable(GL_CULL_FACE)
        glPolygonMode(GL_FRONT, self.polygon_front)
        glPolygonMode(GL_BACK, self.polygon_back)


class ImGuiHost:
    """One ImGui context, font atlas, and renderer for the editor window."""

    def __init__(
        self,
        context: Any,
        renderer: Any,
        display_size: tuple[int, int],
    ) -> None:
        self._context = context
        self.renderer = renderer
        self.display_size = display_size
        self._mouse_pos: tuple[float, float] | None = None
        self._buttons: list[tuple[int, bool]] = []
        self._held: set[int] = set()
        self._wheel_x = 0.0
        self._wheel_y = 0.0

    @classmethod
    def create(cls) -> ImGuiHost:
        """Build the context, font, theme, and renderer. Call with the live GL window."""
        context = imgui.create_context()
        try:
            io = imgui.get_io()
            _keep_keyboard_nav_off()
            io.set_ini_filename(os.devnull)
            font_size = float(tuning_ui_metrics().font_size)
            font = io.fonts.add_font_from_file_ttf(
                str(overlay_font_path()),
                font_size,
                None,
                _shell_glyph_ranges(),
            )
            io.font_default = font
            _apply_theme()
            renderer = _select_renderer_class()()
        except Exception:
            imgui.destroy_context(context)
            raise
        surface = pygame.display.get_surface()
        if surface is None:
            display_size = (1, 1)
        else:
            display_size = surface.get_size()
        return cls(context, renderer, display_size)

    @property
    def mouse_pos(self) -> tuple[float, float] | None:
        return self._mouse_pos

    @property
    def queued_buttons(self) -> list[tuple[int, bool]]:
        """Button events waiting for the next frame, as ``(imgui_button, down)``."""
        return list(self._buttons)

    def button_held(self, button: int) -> bool:
        return button in self._held

    def press_button(self, button: int) -> None:
        self._held.add(button)

    def release_button(self, button: int) -> None:
        self._held.discard(button)

    def process_mouse_event(self, event: pygame.event.Event) -> None:
        """Record position, a button edge, or wheel. No shell policy."""
        if event.type == pygame.MOUSEMOTION:
            self._mouse_pos = (float(event.pos[0]), float(event.pos[1]))
            return
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            button = mouse_button(event)
            if button is None:
                return
            down = event.type == pygame.MOUSEBUTTONDOWN
            self._buttons.append((button, down))
            return
        if event.type == pygame.MOUSEWHEEL:
            self._wheel_x += float(event.x)
            self._wheel_y += float(event.y)

    def begin_frame(self, dt: float) -> None:
        self._submit_input(dt)
        _keep_keyboard_nav_off()
        _ensure_font_atlas()
        _apply_theme()
        imgui.new_frame()

    def end_frame(self) -> None:
        imgui.render()
        self._render_draw_data()

    def discard_input(self) -> None:
        self._buttons.clear()
        self._held.clear()
        self._wheel_x = 0.0
        self._wheel_y = 0.0

    def destroy(self) -> None:
        renderer = self.renderer
        self.renderer = None
        if renderer is not None:
            renderer.shutdown()
        context = self._context
        self._context = None
        if context is not None:
            imgui.destroy_context(context)

    def _submit_input(self, dt: float) -> None:
        io = imgui.get_io()
        width, height = self.display_size
        surface = pygame.display.get_surface()
        if surface is not None:
            width, height = surface.get_size()
            self.display_size = (width, height)
        io.display_size = imgui.ImVec2(float(width), float(height))
        io.display_framebuffer_scale = imgui.ImVec2(1.0, 1.0)
        io.delta_time = dt if dt > 0.0 else 1.0 / 60.0
        mouse_x, mouse_y = self._mouse_xy()
        io.add_mouse_pos_event(mouse_x, mouse_y)
        for button, down in self._buttons:
            io.add_mouse_button_event(button, down)
        self._buttons.clear()
        if self._wheel_x or self._wheel_y:
            io.add_mouse_wheel_event(self._wheel_x, self._wheel_y)
            self._wheel_x = 0.0
            self._wheel_y = 0.0

    def _mouse_xy(self) -> tuple[float, float]:
        if self._mouse_pos is not None:
            return self._mouse_pos
        pos = pygame.mouse.get_pos()
        return (float(pos[0]), float(pos[1]))

    def _render_draw_data(self) -> None:
        renderer = self.renderer
        if not isinstance(renderer, ProgrammablePipelineRenderer):
            return
        saved = save_gl_state()
        extra = _ExtraGlState()
        try:
            renderer.render(imgui.get_draw_data())
        finally:
            restore_gl_state(saved)
            extra.restore()
