"""Shared focus and accent tint drawing with opaque GL-safe compositing."""

from __future__ import annotations

import pygame

from cleave.viz.theme import FOCUS_ROW_BG_ALPHA


def composite_row_background(
    background: tuple[int, int, int],
    background_alpha: int,
    tint: tuple[int, int, int],
    tint_alpha: int,
) -> tuple[tuple[int, int, int], int]:
    """Straight RGBA after compositing *tint* over *background* (Porter-Duff over)."""
    if tint_alpha < 2:
        return background, background_alpha
    if background_alpha < 2:
        return tint, tint_alpha
    ba = background_alpha / 255.0
    ta = tint_alpha / 255.0
    out_a = ta + ba * (1.0 - ta)
    if out_a <= 0.0:
        return background, 0
    inv_out_a = 1.0 / out_a
    out_rgb = tuple(
        int(round((tint[i] * ta + background[i] * ba * (1.0 - ta)) * inv_out_a))
        for i in range(3)
    )
    return out_rgb, int(round(out_a * 255))


def draw_opaque_row_background(
    surface: pygame.Surface,
    rect: tuple[int, int, int, int] | pygame.Rect,
    background: tuple[int, int, int],
    background_alpha: int,
    tint: tuple[int, int, int] | None = None,
    *,
    tint_alpha: int = FOCUS_ROW_BG_ALPHA,
) -> None:
    """Draw a row background opaque enough for GL SRC_ALPHA overlay present."""
    if isinstance(rect, pygame.Rect):
        x, y, w, h = rect.x, rect.y, rect.w, rect.h
    else:
        x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    if tint is not None and tint_alpha >= 2:
        rgb, alpha = composite_row_background(
            background, background_alpha, tint, tint_alpha
        )
    else:
        rgb, alpha = background, background_alpha
    if alpha < 2:
        return
    pygame.draw.rect(surface, (*rgb, alpha), (x, y, w, h))


def blit_tint(
    surface: pygame.Surface,
    rect: tuple[int, int, int, int] | pygame.Rect,
    color: tuple[int, int, int],
    *,
    alpha: int = FOCUS_ROW_BG_ALPHA,
) -> None:
    if isinstance(rect, pygame.Rect):
        x, y, w, h = rect.x, rect.y, rect.w, rect.h
    else:
        x, y, w, h = rect
    if w <= 0 or h <= 0 or alpha < 2:
        return
    tint = pygame.Surface((w, h), pygame.SRCALPHA)
    tint.fill((*color, alpha))
    surface.blit(tint, (x, y))
