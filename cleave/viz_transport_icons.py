"""Vector transport icons for the live tuning overlay."""

from __future__ import annotations

import pygame


def _bar_width(h: int) -> int:
    return max(2, (h + 4) // 7)


def _triangle_width(h: int) -> int:
    return (h * 3) // 4


def _draw_play(surf: pygame.Surface, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
    tri_w = _triangle_width(h)
    start_x = x + (w - tri_w) // 2
    pygame.draw.polygon(
        surf,
        color,
        [(start_x, y), (start_x, y + h), (start_x + tri_w, y + h // 2)],
    )


def _draw_pause(surf: pygame.Surface, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
    bar_w = _bar_width(h)
    inner_gap = max(1, bar_w // 2)
    total_w = 2 * bar_w + inner_gap
    start_x = x + (w - total_w) // 2
    pygame.draw.rect(surf, color, (start_x, y, bar_w, h))
    pygame.draw.rect(surf, color, (start_x + bar_w + inner_gap, y, bar_w, h))


def _draw_skip_back(
    surf: pygame.Surface, x: int, y: int, w: int, h: int, color: tuple[int, int, int]
) -> None:
    bar_w = _bar_width(h)
    tri_w = _triangle_width(h)
    inner_gap = max(1, bar_w // 2)
    total_w = bar_w + inner_gap + tri_w
    start_x = x + (w - total_w) // 2
    pygame.draw.rect(surf, color, (start_x, y, bar_w, h))
    tip_x = start_x + bar_w + inner_gap
    base_x = tip_x + tri_w
    pygame.draw.polygon(
        surf,
        color,
        [(tip_x, y + h // 2), (base_x, y), (base_x, y + h)],
    )


def _draw_skip_forward(
    surf: pygame.Surface, x: int, y: int, w: int, h: int, color: tuple[int, int, int]
) -> None:
    bar_w = _bar_width(h)
    tri_w = _triangle_width(h)
    inner_gap = max(1, bar_w // 2)
    total_w = tri_w + inner_gap + bar_w
    start_x = x + (w - total_w) // 2
    pygame.draw.polygon(
        surf,
        color,
        [(start_x, y), (start_x, y + h), (start_x + tri_w, y + h // 2)],
    )
    pygame.draw.rect(surf, color, (start_x + tri_w + inner_gap, y, bar_w, h))


def render_transport_icons(
    *,
    color: tuple[int, int, int],
    line_height: int,
    paused: bool,
) -> pygame.Surface:
    icon_h = line_height - 4
    bar_w = _bar_width(icon_h)
    gap = max(8, line_height // 2)
    inner_gap = max(1, bar_w // 2)
    tri_w = _triangle_width(icon_h)
    slot_w = max(tri_w, 2 * bar_w + inner_gap, bar_w + inner_gap + tri_w)
    total_w = 3 * slot_w + 2 * gap
    surf = pygame.Surface((total_w, line_height), pygame.SRCALPHA)
    y = (line_height - icon_h) // 2

    _draw_skip_back(surf, 0, y, slot_w, icon_h, color)
    center_x = slot_w + gap
    if paused:
        _draw_pause(surf, center_x, y, slot_w, icon_h, color)
    else:
        _draw_play(surf, center_x, y, slot_w, icon_h, color)
    _draw_skip_forward(surf, 2 * (slot_w + gap), y, slot_w, icon_h, color)
    return surf
