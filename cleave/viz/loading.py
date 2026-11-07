"""Centered loading message during visualizer boot.

Optional detail line and determinate progress bar when a job reports a
fraction. Indeterminate waits stay message-only.

``LoadingWindow`` is the pre-project pygame/GL handle: open the window,
draw phase messages with ImGui, then hand the same display to
``continue_launch``.
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
from cleave.viz.text_fit import TextSizer, fit_text_to_width
from cleave.viz.theme import (
    BACKGROUND,
    BORDER_COLOR,
    BORDER_WIDTH,
    LABEL,
    VALUE,
    set_ui_scale_percent,
    ui_px,
    ui_scale_percent,
)
from cleave.viz import sdl_window

if TYPE_CHECKING:
    from imgui_bundle import imgui

    from cleave.viz.imgui_host import ImGuiHost


@functools.cache
def _imgui():
    from imgui_bundle import imgui as imgui_mod

    return imgui_mod


@functools.cache
def _loading_flags() -> int:
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
        | int(imgui.WindowFlags_.no_background)
    )


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


_BAR_WIDTH_FRACTION = 0.4
_TEXT_MAX_WIDTH_FRACTION = 0.8
# Base px at 100% UI scale; read through ui_px at layout time.
_BAR_HEIGHT_BASE = 10
_LINE_GAP_BASE = 8
_BAR_GAP_BASE = 16
_LOADING_WINDOW = "##loading"
_SCRIM_WINDOW = "##loading-scrim"

# Future separate/download hook: (message, fraction). fraction None = named wait, no bar.
LoadingProgress = Callable[[str, float | None], None]


@dataclass(frozen=True)
class LoadingContentLayout:
    """Centered stack of message, optional detail, and optional progress bar."""

    message_xy: tuple[int, int]
    detail_xy: tuple[int, int] | None
    bar_rect: tuple[int, int, int, int] | None
    fill_rect: tuple[int, int, int, int] | None


def clamp_loading_fraction(fraction: float) -> float:
    return max(0.0, min(1.0, float(fraction)))


def loading_bar_width(display_width: int) -> int:
    return max(1, int(round(display_width * _BAR_WIDTH_FRACTION)))


def loading_content_layout(
    display_width: int,
    display_height: int,
    message_size: tuple[int, int],
    *,
    detail_size: tuple[int, int] | None = None,
    fraction: float | None = None,
    line_gap: int | None = None,
    bar_gap: int | None = None,
    bar_width: int | None = None,
    bar_height: int | None = None,
    border_width: int = BORDER_WIDTH,
) -> LoadingContentLayout:
    """Vertically stack message, detail, and bar; center the block in the viewport."""
    if line_gap is None:
        line_gap = ui_px(_LINE_GAP_BASE)
    if bar_gap is None:
        bar_gap = ui_px(_BAR_GAP_BASE)
    if bar_height is None:
        bar_height = ui_px(_BAR_HEIGHT_BASE)
    message_w, message_h = message_size
    stack_h = message_h
    if detail_size is not None:
        stack_h += line_gap + detail_size[1]
    show_bar = fraction is not None
    if show_bar:
        stack_h += bar_gap + bar_height

    top = (display_height - stack_h) // 2
    message_xy = ((display_width - message_w) // 2, top)
    y = top + message_h

    detail_xy: tuple[int, int] | None = None
    if detail_size is not None:
        y += line_gap
        detail_xy = ((display_width - detail_size[0]) // 2, y)
        y += detail_size[1]

    bar_rect: tuple[int, int, int, int] | None = None
    fill_rect: tuple[int, int, int, int] | None = None
    if show_bar:
        y += bar_gap
        width = loading_bar_width(display_width) if bar_width is None else bar_width
        bar_x = (display_width - width) // 2
        bar_rect = (bar_x, y, width, bar_height)
        inner_w = width - 2 * border_width
        inner_h = bar_height - 2 * border_width
        if inner_w > 0 and inner_h > 0:
            fill_w = min(inner_w, int(round(inner_w * clamp_loading_fraction(fraction))))
            if fill_w > 0:
                fill_rect = (
                    bar_x + border_width,
                    y + border_width,
                    fill_w,
                    inner_h,
                )

    return LoadingContentLayout(
        message_xy=message_xy,
        detail_xy=detail_xy,
        bar_rect=bar_rect,
        fill_rect=fill_rect,
    )


class _ImGuiTextSize:
    """``TextSizer`` for the current ImGui font. Valid only inside a frame."""

    def size(self, text: str) -> tuple[int, int]:
        imgui = _imgui()
        measured = imgui.calc_text_size(text)
        return (int(measured.x), int(measured.y))


def _packed(role: tuple[int, int, int]) -> int:
    # imgui_theme imports imgui_bundle, whose package init loads matplotlib
    # when that package is installed. Keep it off the play-path import graph.
    from cleave.viz.imgui_theme import rgba

    imgui = _imgui()
    return int(imgui.get_color_u32(rgba(role)))


def _style_color(slot: imgui.Col_) -> imgui.ImVec4:
    imgui = _imgui()
    color = imgui.get_style().color_(slot)
    return imgui.ImVec4(color.x, color.y, color.z, color.w)


def _raise_window(name: str) -> None:
    imgui = _imgui()
    imgui.internal.bring_window_to_display_front(
        imgui.internal.find_window_by_name(name)
    )


def _text(
    draw: imgui.ImDrawList,
    x: int,
    y: int,
    text: str,
    role: tuple[int, int, int],
) -> None:
    if not text:
        return
    imgui = _imgui()
    draw.add_text(imgui.ImVec2(float(x), float(y)), _packed(role), text)


def _draw_loading_bar(
    draw: imgui.ImDrawList,
    bar_rect: tuple[int, int, int, int],
    fill_rect: tuple[int, int, int, int] | None,
) -> None:
    imgui = _imgui()
    x, y, width, height = bar_rect
    draw.add_rect_filled(
        imgui.ImVec2(float(x), float(y)),
        imgui.ImVec2(float(x + width), float(y + height)),
        _packed(BACKGROUND),
    )
    if fill_rect is not None:
        fill_x, fill_y, fill_w, fill_h = fill_rect
        draw.add_rect_filled(
            imgui.ImVec2(float(fill_x), float(fill_y)),
            imgui.ImVec2(float(fill_x + fill_w), float(fill_y + fill_h)),
            _packed(VALUE),
        )
    draw.add_rect(
        imgui.ImVec2(float(x), float(y)),
        imgui.ImVec2(float(x + width), float(y + height)),
        _packed(BORDER_COLOR),
        0.0,
        0,
        float(BORDER_WIDTH),
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


def _fitted_detail(detail: str, display_width: int, measure: TextSizer) -> str:
    max_w = max(1, int(display_width * _TEXT_MAX_WIDTH_FRACTION))
    return fit_text_to_width(measure, detail, max_w)


def draw_loading_content(
    message: str,
    display_width: int,
    display_height: int,
    *,
    fraction: float | None = None,
    detail: str | None = None,
) -> None:
    """Draw the centred loading block into the current ImGui frame."""
    imgui = _imgui()
    measure = _ImGuiTextSize()
    message_size = measure.size(message) if message else (0, 0)
    fitted = ""
    detail_size: tuple[int, int] | None = None
    if detail:
        fitted = _fitted_detail(detail, display_width, measure)
        if fitted:
            detail_size = measure.size(fitted)
    layout = loading_content_layout(
        display_width,
        display_height,
        message_size,
        detail_size=detail_size,
        fraction=fraction,
    )

    imgui.set_next_window_pos(imgui.ImVec2(0.0, 0.0), imgui.Cond_.always)
    imgui.set_next_window_size(
        imgui.ImVec2(float(display_width), float(display_height)),
        imgui.Cond_.always,
    )
    pushed = 0
    begun = False
    try:
        imgui.push_style_var(imgui.StyleVar_.window_padding, imgui.ImVec2(0.0, 0.0))
        pushed += 1
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
        pushed += 1
        imgui.begin(_LOADING_WINDOW, None, _loading_flags())
        begun = True
        _raise_window(_LOADING_WINDOW)
        draw = imgui.get_window_draw_list()
        _text(draw, layout.message_xy[0], layout.message_xy[1], message, VALUE)
        if fitted and layout.detail_xy is not None:
            _text(draw, layout.detail_xy[0], layout.detail_xy[1], fitted, LABEL)
        if layout.bar_rect is not None:
            _draw_loading_bar(draw, layout.bar_rect, layout.fill_rect)
    finally:
        if begun:
            imgui.end()
        if pushed:
            imgui.pop_style_var(pushed)


def _clear_display(width: int, height: int) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    glViewport(0, 0, width, height)
    red, green, blue = BACKGROUND
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


@dataclass
class _LoadingDraw:
    message: str
    display_width: int
    display_height: int
    fraction: float | None = None
    detail: str | None = None

    def __call__(self) -> None:
        draw_loading_content(
            self.message,
            self.display_width,
            self.display_height,
            fraction=self.fraction,
            detail=self.detail,
        )


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
        message: str,
        fraction: float | None = None,
        detail: str | None = None,
    ) -> bool:
        """Draw the loading screen and pump events. False if the user quit."""
        for event in pygame.event.get():
            self.note_event(event)
            if event.type == pygame.QUIT:
                self.quit_requested = True
                return False
        if self.quit_requested:
            return False
        present_frame(
            self,
            _LoadingDraw(
                message,
                self.display_width,
                self.display_height,
                fraction,
                detail,
            ),
            scrim=False,
        )
        return True

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
    from cleave.user_config import saved_ui_scale, saved_window_geometry
    from cleave.viz.imgui_host import ImGuiHost

    os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
    pygame.init()
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
    set_ui_scale_percent(saved_ui_scale())
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
    window.update("Loading...")
    return window
