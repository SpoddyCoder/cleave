"""Drawing primitives shared by the tuning, timeline, help, and modal overlays."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from cleave.viz.overlay_upload import UploadPlan, UploadSignature
from cleave.viz.theme import (
    BACKGROUND,
    BACKGROUND_ALPHA,
    BORDER_COLOR,
    BORDER_WIDTH,
)

_font_cache: dict[tuple[int, bool], pygame.font.Font] = {}


def overlay_font(size: int, *, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont("monospace", size, bold=bold)
    return _font_cache[key]


def clip_rect_to_surface(
    rect: tuple[int, int, int, int],
    surface: pygame.Surface,
) -> tuple[int, int, int, int] | None:
    """Intersection of rect with surface bounds (for subsurface-safe panel_rect)."""
    return clip_rect_to_bounds(rect, surface.get_width(), surface.get_height())


def clip_rect_to_bounds(
    rect: tuple[int, int, int, int],
    bounds_w: int,
    bounds_h: int,
) -> tuple[int, int, int, int] | None:
    """Intersection of rect with a width/height viewport."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return None
    left = max(x, 0)
    top = max(y, 0)
    right = min(x + w, bounds_w)
    bottom = min(y + h, bounds_h)
    clip_w = right - left
    clip_h = bottom - top
    if clip_w <= 0 or clip_h <= 0:
        return None
    return (left, top, clip_w, clip_h)


def overlay_panel_surface(
    size: tuple[int, int],
    *,
    fill_alpha: int | None = None,
) -> pygame.Surface:
    """Panel-sized SRCALPHA surface filled with the overlay background."""
    panel = pygame.Surface(size, pygame.SRCALPHA)
    panel.fill((*BACKGROUND, BACKGROUND_ALPHA if fill_alpha is None else fill_alpha))
    return panel


def draw_panel_border(surface: pygame.Surface, *, alpha: int = 255) -> None:
    if alpha < 2 or BORDER_WIDTH <= 0:
        return
    pygame.draw.rect(
        surface,
        (*BORDER_COLOR, alpha),
        surface.get_rect(),
        width=BORDER_WIDTH,
    )


def visibility_bucket(visibility: float) -> int:
    if visibility <= 0.01:
        return 0
    return min(255, int(visibility * 255))


@dataclass(frozen=True)
class ComposedPanel:
    upload_surface: pygame.Surface
    panel_size: tuple[int, int]
    screen_rect: tuple[int, int, int, int]
    upload_plan: UploadPlan
    upload_signature: UploadSignature
    capacity: tuple[int, int]
