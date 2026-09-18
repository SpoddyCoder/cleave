"""Centered loading message during visualizer boot.

Optional detail line and determinate progress bar when a job reports a
fraction. Indeterminate waits stay message-only.

``LoadingWindow`` is the pre-project pygame/GL handle: open the window,
draw phase messages, then hand the same display to ``continue_launch``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pygame
from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    GL_FRAMEBUFFER,
    glBindFramebuffer,
    glClear,
    glClearColor,
    glViewport,
)

from cleave.config_schema.editor import editor_display_size
from cleave.gl_color_format import RGBA8
from cleave.gl_compositor import GlCompositor
from cleave.viz.overlay_primitives import (
    draw_panel_border,
    overlay_font,
    overlay_panel_surface,
)
from cleave.viz.text_fit import fit_text_to_width
from cleave.viz.theme import (
    BACKGROUND,
    BORDER_WIDTH,
    LABEL,
    UI_SCALE,
    VALUE,
    scale_px,
)

_FONT_SIZE = 28
_DETAIL_FONT_SIZE = 18
_BAR_WIDTH_FRACTION = 0.4
_TEXT_MAX_WIDTH_FRACTION = 0.8
_BAR_HEIGHT = scale_px(10, scale=UI_SCALE)
_LINE_GAP = scale_px(8, scale=UI_SCALE)
_BAR_GAP = scale_px(16, scale=UI_SCALE)

_loading_font: pygame.font.Font | None = None

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
    line_gap: int = _LINE_GAP,
    bar_gap: int = _BAR_GAP,
    bar_width: int | None = None,
    bar_height: int = _BAR_HEIGHT,
    border_width: int = BORDER_WIDTH,
) -> LoadingContentLayout:
    """Vertically stack message, detail, and bar; center the block in the viewport."""
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


def _loading_font_get() -> pygame.font.Font:
    global _loading_font
    if _loading_font is None:
        _loading_font = overlay_font(_FONT_SIZE)
    return _loading_font


def _detail_font_get() -> pygame.font.Font:
    return overlay_font(_DETAIL_FONT_SIZE)


def _draw_loading_bar(
    surface: pygame.Surface,
    bar_rect: tuple[int, int, int, int],
    fill_rect: tuple[int, int, int, int] | None,
) -> None:
    x, y, w, h = bar_rect
    bar = overlay_panel_surface((w, h), fill_alpha=255)
    if fill_rect is not None:
        fx, fy, fw, fh = fill_rect
        pygame.draw.rect(bar, VALUE, (fx - x, fy - y, fw, fh))
    draw_panel_border(bar)
    surface.blit(bar, (x, y))


def compose_loading_surface(
    message: str,
    display_width: int,
    display_height: int,
    *,
    fraction: float | None = None,
    detail: str | None = None,
) -> pygame.Surface:
    """Blit message, optional detail, and optional bar onto an overlay surface."""
    message_surface = _loading_font_get().render(message, True, VALUE)

    detail_surface: pygame.Surface | None = None
    if detail:
        max_w = max(1, int(display_width * _TEXT_MAX_WIDTH_FRACTION))
        fitted = fit_text_to_width(_detail_font_get(), detail, max_w)
        if fitted:
            detail_surface = _detail_font_get().render(fitted, True, LABEL)

    layout = loading_content_layout(
        display_width,
        display_height,
        message_surface.get_size(),
        detail_size=None if detail_surface is None else detail_surface.get_size(),
        fraction=fraction,
    )

    surface = pygame.Surface((display_width, display_height), pygame.SRCALPHA)
    surface.blit(message_surface, layout.message_xy)
    if detail_surface is not None and layout.detail_xy is not None:
        surface.blit(detail_surface, layout.detail_xy)
    if layout.bar_rect is not None:
        _draw_loading_bar(surface, layout.bar_rect, layout.fill_rect)
    return surface


def draw_loading_screen(
    compositor: GlCompositor,
    message: str,
    display_width: int,
    display_height: int,
    *,
    fraction: float | None = None,
    detail: str | None = None,
) -> None:
    surface = compose_loading_surface(
        message,
        display_width,
        display_height,
        fraction=fraction,
        detail=detail,
    )
    texture_id = compositor.upload_overlay_texture(surface)

    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    glViewport(0, 0, display_width, display_height)
    r, g, b = BACKGROUND
    glClearColor(r / 255.0, g / 255.0, b / 255.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT)

    compositor.draw_overlay(texture_id, 0, 0, display_width, display_height)
    pygame.display.flip()


_GL_DISPLAY_FLAGS = pygame.OPENGL | pygame.DOUBLEBUF
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
    """OpenGL display plus overlay compositor for boot and stem-split progress."""

    compositor: GlCompositor
    display_width: int
    display_height: int
    overlay_surface: pygame.Surface
    quit_requested: bool = field(default=False)

    def update(
        self,
        message: str,
        fraction: float | None = None,
        detail: str | None = None,
    ) -> bool:
        """Draw the loading screen and pump events. False if the user quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit_requested = True
                return False
        if self.quit_requested:
            return False
        draw_loading_screen(
            self.compositor,
            message,
            self.display_width,
            self.display_height,
            fraction=fraction,
            detail=detail,
        )
        return True

    def adopt_display_size(self, width: int, height: int) -> None:
        """Resize the pygame window when the project display size differs."""
        if width == self.display_width and height == self.display_height:
            return
        _set_gl_mode(width, height)
        self.display_width = width
        self.display_height = height
        self.overlay_surface = pygame.Surface((width, height), pygame.SRCALPHA)

    def close(self) -> None:
        self.compositor.destroy()
        pygame.quit()


def open_loading_window(
    *,
    width: int | None = None,
    height: int | None = None,
) -> LoadingWindow:
    """Create the pygame/GL window and draw ``Loading...``. Does not import torch."""
    if width is None or height is None:
        width, height = editor_display_size()
    pygame.init()
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
    overlay_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    window = LoadingWindow(
        compositor=compositor,
        display_width=width,
        display_height=height,
        overlay_surface=overlay_surface,
    )
    window.update("Loading...")
    return window
