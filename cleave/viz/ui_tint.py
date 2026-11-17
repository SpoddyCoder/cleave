"""Shared tint, hover, and row band drawing on pygame surfaces (the timeline strip)."""

from __future__ import annotations

import pygame

from cleave.viz.row_paint import RowLook
from cleave.viz.theme import (
    ICON_HOVER_BG,
    ICON_HOVER_BG_ALPHA,
    ICON_HOVER_EDGE,
)


def blit_tint(
    surface: pygame.Surface,
    rect: tuple[int, int, int, int] | pygame.Rect,
    color: tuple[int, int, int],
    *,
    alpha: int,
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


def blit_hover(
    surface: pygame.Surface, rect: tuple[int, int, int, int] | pygame.Rect
) -> None:
    """The shell's icon hover on the strip: violet wash and its 1px outline."""
    blit_tint(surface, rect, ICON_HOVER_BG, alpha=ICON_HOVER_BG_ALPHA)
    r = pygame.Rect(rect)
    if r.w > 0 and r.h > 0:
        pygame.draw.rect(surface, ICON_HOVER_EDGE, r, 1)


def _rgba8(color: tuple[tuple[int, int, int], float]) -> tuple[int, int, int, int]:
    rgb, alpha = color
    return (*rgb, max(0, min(255, round(alpha * 255))))


def blit_row_band(
    surface: pygame.Surface, rect: pygame.Rect, look: RowLook, *, bar_px: int
) -> None:
    """A row look's band and marker bar, as ``row_paint.paint_look`` draws them.

    The edge is left to ``draw_row_edge``, so it can go over the row's content.
    """
    if rect.w <= 0 or rect.h <= 0:
        return
    ramp = pygame.Surface((2, 1) if not look.vertical else (1, 2), pygame.SRCALPHA)
    ramp.set_at((0, 0), _rgba8(look.start))
    ramp.set_at((1, 0) if not look.vertical else (0, 1), _rgba8(look.end))
    surface.blit(pygame.transform.smoothscale(ramp, rect.size), rect.topleft)
    if look.bar is not None:
        surface.fill(look.bar, pygame.Rect(rect.x, rect.y, min(rect.w, bar_px), rect.h))


def draw_row_edge(surface: pygame.Surface, rect: pygame.Rect, look: RowLook) -> None:
    """A row look's 1px edge, if it has one."""
    if look.edge is None or rect.w <= 0 or rect.h <= 0:
        return
    pygame.draw.rect(surface, look.edge, rect, 1)
