"""Shared semi-transparent focus and accent tint drawing."""

from __future__ import annotations

import pygame

from cleave.viz.theme import FOCUS_ROW_BG_ALPHA


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
