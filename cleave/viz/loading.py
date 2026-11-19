"""The pre-project window, its splash, and its progress dialog.

``LoadingWindow`` is the pre-project pygame/GL handle: open the window,
show the splash (:func:`show_splash`), show each phase as a progress dialog
(the same panel the editor uses, under the full logo), then hand the same
display to ``continue_launch``. A job that reports a fraction gets a bar; a
named wait has none.
"""

from __future__ import annotations

import functools
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame
from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    GL_FRAMEBUFFER,
    glBindFramebuffer,
    glClear,
    glClearColor,
    glViewport,
)

from cleave.config_schema.window import (
    WindowGeometry,
    fit_window_to_desktop,
    window_minimum_size,
)
from cleave.gl_color_format import RGBA8
from cleave.gl_compositor import GlCompositor
from cleave.paths import themes_dir
from cleave.viz.theme import (
    palette,
    palette_for_theme,
    set_palette,
    set_ui_scale_percent,
    ui_scale_percent,
)
from cleave.viz import sdl_window
from cleave.viz.user_themes import install_user_themes

if TYPE_CHECKING:
    from imgui_bundle import imgui

    from cleave.viz.imgui_host import ImGuiHost


@functools.cache
def _imgui():
    from imgui_bundle import imgui as imgui_mod

    return imgui_mod


@functools.cache
def _scrim_flags() -> int:
    imgui = _imgui()
    return (
        int(imgui.WindowFlags_.no_title_bar)
        | int(imgui.WindowFlags_.no_resize)
        | int(imgui.WindowFlags_.no_move)
        | int(imgui.WindowFlags_.no_saved_settings)
        | int(imgui.WindowFlags_.no_focus_on_appearing)
        | int(imgui.WindowFlags_.no_nav)
        | int(imgui.WindowFlags_.no_bring_to_front_on_focus)
        | int(imgui.WindowFlags_.no_scrollbar)
        | int(imgui.WindowFlags_.no_scroll_with_mouse)
    )


_SCRIM_WINDOW = "##loading-scrim"


def _style_color(slot: imgui.Col_) -> imgui.ImVec4:
    imgui = _imgui()
    color = imgui.get_style().color_(slot)
    return imgui.ImVec4(color.x, color.y, color.z, color.w)


def _raise_window(name: str) -> None:
    imgui = _imgui()
    imgui.internal.bring_window_to_display_front(
        imgui.internal.find_window_by_name(name)
    )


def _draw_scrim() -> None:
    imgui = _imgui()
    display = imgui.get_io().display_size
    imgui.set_next_window_pos(imgui.ImVec2(0.0, 0.0), imgui.Cond_.always)
    imgui.set_next_window_size(
        imgui.ImVec2(display.x, display.y), imgui.Cond_.always
    )
    imgui.push_style_color(
        imgui.Col_.window_bg,
        _style_color(imgui.Col_.modal_window_dim_bg),
    )
    imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
    try:
        imgui.begin(_SCRIM_WINDOW, None, _scrim_flags())
        try:
            _raise_window(_SCRIM_WINDOW)
        finally:
            imgui.end()
    finally:
        imgui.pop_style_var()
        imgui.pop_style_color()


def _clear_display(width: int, height: int) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    glViewport(0, 0, width, height)
    red, green, blue = palette().background
    glClearColor(red / 255.0, green / 255.0, blue / 255.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT)


def present_frame(
    window: LoadingWindow,
    draw: Callable[[], None],
    *,
    scrim: bool = False,
    dt: float = 1.0 / 60.0,
) -> None:
    """Clear the framebuffer, run one ImGui frame, and flip.

    ``draw`` runs inside the frame, after the scrim when ``scrim`` is set.
    No ImGui host skips the clear, the frame, and the callback.
    """
    window.apply_pending_resize()
    host = window.imgui
    if host is None:
        return
    _clear_display(window.display_width, window.display_height)
    host.begin_frame(dt)
    try:
        if scrim:
            _draw_scrim()
        draw()
    finally:
        host.end_frame()
    pygame.display.flip()


@dataclass(frozen=True)
class _ProgressDraw:
    title: str
    body: str | None
    fraction: float | None

    def __call__(self) -> None:
        from cleave.viz.brand import Logo
        from cleave.viz.modal import ModalKind, ModalViewState
        from cleave.viz.modal_surface import ImGuiTextMeasure, ModalSurface
        from cleave.viz.top_layer import TopLayer

        view = ModalViewState(
            kind=ModalKind.PROGRESS,
            message=self.title,
            options=(),
            focus_index=0,
            body=self.body,
            progress_fraction=(
                None if self.fraction is None else max(0.0, min(1.0, self.fraction))
            ),
            banner=Logo.FULL,
        )
        layer = TopLayer()
        layer.push(ModalSurface(view, ImGuiTextMeasure()))
        layer.draw()


_SPLASH_FADE_IN_SEC = 0.6
_SPLASH_HOLD_SEC = 2.95
_SPLASH_FADE_OUT_SEC = 0.3

SPLASH_SEC = _SPLASH_FADE_IN_SEC + _SPLASH_HOLD_SEC + _SPLASH_FADE_OUT_SEC
"""How long the launch splash shows unless a key or click ends it."""

# Splash logo size as a fraction of the window: the smaller fit wins.
_SPLASH_WIDTH_FRACTION = 0.45
_SPLASH_HEIGHT_FRACTION = 0.4
# Splash logo centre as a fraction of the window height, a little above middle.
_SPLASH_CENTRE_Y = 0.45
_SPLASH_FPS = 60
# Splash summary and credit sizes over the shell font size.
_SPLASH_SUMMARY_SCALE = 2.0
_SPLASH_CREDIT_SCALE = 1.125


def splash_alpha(elapsed: float) -> float:
    """Opacity of the splash *elapsed* seconds in: fade in, hold, fade out."""
    fade_in = elapsed / _SPLASH_FADE_IN_SEC
    fade_out = (SPLASH_SEC - elapsed) / _SPLASH_FADE_OUT_SEC
    return max(0.0, min(1.0, fade_in, fade_out))


@dataclass(frozen=True)
class _SplashDraw:
    """The full logo, then the summary, the credit, and the version under it."""

    summary: str
    credit: str
    version: str
    alpha: float

    def __call__(self) -> None:
        from cleave.viz.brand import Logo, draw_logo, logo_size

        imgui = _imgui()
        display = imgui.get_io().display_size
        width, height = logo_size(
            Logo.FULL,
            display.y * _SPLASH_HEIGHT_FRACTION,
            display.x * _SPLASH_WIDTH_FRACTION,
        )
        x = int(display.x - width) // 2
        y = int(display.y * _SPLASH_CENTRE_Y - height / 2)
        draw = imgui.get_background_draw_list()
        draw_logo(
            draw,
            Logo.FULL,
            (x, y, width, height),
            backdrop=palette().background,
            alpha=self.alpha,
        )
        text_y = float(y + height + height // 6)
        lines = (
            (self.summary, palette().value, _SPLASH_SUMMARY_SCALE),
            (self.credit, palette().muted, _SPLASH_CREDIT_SCALE),
        )
        base = imgui.get_style().font_size_base
        for text, colour, scale in lines:
            imgui.push_font(None, base * scale)
            try:
                text_y = self._centred_line(draw, text, colour, text_y)
            finally:
                imgui.pop_font()
        text_y += imgui.get_text_line_height_with_spacing()
        self._centred_line(draw, self.version, palette().muted, text_y)

    def _centred_line(
        self, draw: imgui.ImDrawList, text: str, colour: tuple[int, int, int], y: float
    ) -> float:
        """One line centred across the window in the current font. Returns the next y."""
        from cleave.viz.imgui_theme import rgba

        imgui = _imgui()
        display = imgui.get_io().display_size
        text_w = imgui.calc_text_size(text).x
        draw.add_text(
            imgui.get_font(),
            imgui.get_font_size(),
            imgui.ImVec2(float(int((display.x - text_w) / 2)), y),
            imgui.get_color_u32(rgba(colour, self.alpha)),
            text,
        )
        return y + imgui.get_text_line_height_with_spacing()


def show_splash(window: LoadingWindow) -> None:
    """Show the full logo and version on the open window for a moment.

    The summary, credit, and version sit under the logo. It fades in, holds,
    and fades out over :data:`SPLASH_SEC`. A key or click
    ends it at once; closing the window ends it and sets ``quit_requested``.
    """
    from cleave.about import ABOUT_SUMMARY, about_credit
    from cleave.build_version import display_version

    splash = functools.partial(
        _SplashDraw, ABOUT_SUMMARY, about_credit(), display_version()
    )
    clock = pygame.time.Clock()
    elapsed = 0.0
    while elapsed < SPLASH_SEC:
        for event in pygame.event.get():
            window.note_event(event)
            if event.type == pygame.QUIT:
                window.quit_requested = True
                return
            if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                window.clear()
                return
        dt = clock.tick(_SPLASH_FPS) / 1000.0
        elapsed += dt
        present_frame(window, splash(splash_alpha(elapsed)), dt=dt)
    window.clear()


_GL_DISPLAY_FLAGS = pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE
_LOADING_CAPTION = "Cleave"


def _set_gl_mode(width: int, height: int) -> None:
    try:
        pygame.display.set_mode((width, height), _GL_DISPLAY_FLAGS)
    except pygame.error as exc:
        pygame.quit()
        from cleave.viz import LaunchError

        raise LaunchError(f"failed to open OpenGL window: {exc}") from exc


@dataclass
class LoadingWindow:
    """OpenGL display and ImGui host for boot and stem-split progress."""

    compositor: GlCompositor
    display_width: int
    display_height: int
    overlay_surface: pygame.Surface
    quit_requested: bool = field(default=False)
    video_quit: bool = field(default=False)
    imgui: ImGuiHost | None = None
    # Latest size from a drag or maximise, applied once before the next draw.
    pending_size: tuple[int, int] | None = None
    # Size to reopen at: the last size while neither maximised nor fullscreen.
    restored_size: tuple[int, int] | None = None
    maximised: bool = False
    fullscreen: bool = False
    # UI scale percent the minimum window size was last set for.
    minimum_size_scale: int | None = None

    def note_event(self, event: pygame.event.Event) -> None:
        """Track window size and maximised state. The last size in a burst wins."""
        if event.type == pygame.WINDOWMAXIMIZED:
            self.maximised = True
            return
        if event.type == pygame.WINDOWRESTORED:
            self.maximised = False
            return
        if event.type != pygame.WINDOWSIZECHANGED:
            return
        width = int(event.x)
        height = int(event.y)
        if width <= 0 or height <= 0:
            return
        self.pending_size = (width, height)
        if not self._size_is_transient():
            self.restored_size = (width, height)

    def _size_is_transient(self) -> bool:
        """True while maximised, fullscreen, or minimised, so the size is not kept.

        Reads SDL's live flags when they are available, because SDL may send
        the size change before or after the maximise event.
        """
        flags = sdl_window.window_flags()
        if flags is None:
            return self.maximised or self.fullscreen
        self.maximised = bool(flags & sdl_window.SDL_WINDOW_MAXIMIZED)
        transient = (
            sdl_window.SDL_WINDOW_MAXIMIZED
            | sdl_window.SDL_WINDOW_FULLSCREEN
            | sdl_window.SDL_WINDOW_MINIMIZED
        )
        return bool(flags & transient) or self.fullscreen

    def geometry(self) -> WindowGeometry:
        """Size and maximised state to reopen with."""
        width, height = self.restored_size or (self.display_width, self.display_height)
        return WindowGeometry(width=width, height=height, maximised=self.maximised)

    def sync_minimum_size(self) -> None:
        """Set the minimum window size for the live UI scale. No-op when unchanged."""
        percent = ui_scale_percent()
        if percent == self.minimum_size_scale:
            return
        self.minimum_size_scale = percent
        width, height = window_minimum_size(percent / 100.0, _desktop_size())
        sdl_window.set_minimum_size(width, height)

    def toggle_fullscreen(self) -> None:
        """Switch between borderless desktop fullscreen and the windowed state.

        Leaving fullscreen returns to the earlier size or maximised state.
        The size change arrives as a normal resize event.
        """
        from pygame._sdl2.video import Window

        try:
            window = Window.from_display_module()
            if self.fullscreen:
                window.set_windowed()
            else:
                window.set_fullscreen(desktop=True)
        except pygame.error:
            return
        self.fullscreen = not self.fullscreen

    def apply_pending_resize(self) -> bool:
        """Resize the display viewport, overlay surface, and ImGui in place.

        Keeps the GL context: the window is never reopened with ``set_mode``.
        True when the size changed.
        """
        size = self.pending_size
        self.pending_size = None
        if size is None:
            return False
        width, height = size
        if width == self.display_width and height == self.display_height:
            return False
        self.compositor.set_display_size(width, height)
        self.overlay_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        self.display_width = width
        self.display_height = height
        if self.imgui is not None:
            self.imgui.set_display_size(width, height)
        return True

    def update(
        self,
        title: str,
        body: str | None = None,
        fraction: float | None = None,
    ) -> bool:
        """Show *title* over *body* in a progress dialog and pump events.

        *fraction* draws a bar; None is a named wait. False if the user quit.
        """
        if not self._pump():
            return False
        present_frame(self, _ProgressDraw(title, body, fraction))
        return True

    def clear(self) -> bool:
        """Paint the empty window and pump events. False if the user quit."""
        if not self._pump():
            return False
        present_frame(self, lambda: None)
        return True

    def _pump(self) -> bool:
        for event in pygame.event.get():
            self.note_event(event)
            if event.type == pygame.QUIT:
                self.quit_requested = True
                return False
        return not self.quit_requested

    def release_imgui(self) -> None:
        """Destroy the ImGui host. A second call is a no-op."""
        host = self.imgui
        if host is None:
            return
        host.destroy()
        self.imgui = None

    def ensure_imgui(self) -> None:
        """Recreate the ImGui host after :meth:`release_imgui`.

        No-op when a host is already attached.
        """
        if self.imgui is not None:
            return
        from cleave.viz.imgui_host import ImGuiHost

        self.imgui = ImGuiHost.create()
        self.imgui.set_display_size(self.display_width, self.display_height)

    def close(self) -> None:
        if not self.video_quit:
            _persist_geometry(self.geometry())
        self.release_imgui()
        self.compositor.destroy()
        self.video_quit = True
        pygame.quit()


def _desktop_size() -> tuple[int, int] | None:
    try:
        sizes = pygame.display.get_desktop_sizes()
    except pygame.error:
        return None
    if not sizes:
        return None
    width, height = sizes[0]
    if width <= 0 or height <= 0:
        return None
    return (int(width), int(height))


def _persist_geometry(geometry: WindowGeometry) -> None:
    """Save the window geometry. A bad user config is reported when it loads."""
    import yaml

    from cleave.user_config import persist_window_geometry

    try:
        persist_window_geometry(geometry)
    except (OSError, ValueError, yaml.YAMLError):
        return


def _set_window_icon() -> None:
    """The C mark on the title bar and taskbar. Set before the window opens."""
    from cleave.viz.brand import window_icon

    try:
        pygame.display.set_icon(window_icon())
    except (OSError, pygame.error):
        return


def _maximise() -> None:
    from pygame._sdl2.video import Window

    try:
        Window.from_display_module().maximize()
    except pygame.error:
        return


def open_loading_window() -> LoadingWindow:
    """Open the GL window at the saved size and draw ``Loading...``.

    The window opens centred. A saved maximised state, or a saved size bigger
    than the desktop, opens maximised. Does not import torch.
    """
    from cleave.user_config import saved_editor_settings, saved_window_geometry
    from cleave.viz.imgui_host import ImGuiHost

    os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
    pygame.init()
    _set_window_icon()
    geometry = fit_window_to_desktop(saved_window_geometry(), _desktop_size())
    width, height = geometry.width, geometry.height
    _set_gl_mode(width, height)
    pygame.display.set_caption(_LOADING_CAPTION)
    compositor = GlCompositor(
        width,
        height,
        display_width=width,
        display_height=height,
        color_format=RGBA8,
    )
    compositor.init()
    editor = saved_editor_settings()
    set_ui_scale_percent(editor.ui_scale)
    install_user_themes(themes_dir())
    set_palette(palette_for_theme(editor.theme))
    imgui_host = ImGuiHost.create()
    imgui_host.set_display_size(width, height)
    overlay_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    window = LoadingWindow(
        compositor=compositor,
        display_width=width,
        display_height=height,
        overlay_surface=overlay_surface,
        imgui=imgui_host,
        restored_size=(width, height),
    )
    window.sync_minimum_size()
    if geometry.maximised:
        _maximise()
        window.maximised = True
    window.clear()
    return window
