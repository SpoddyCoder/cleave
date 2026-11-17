"""Determinate progress bar shared by the loading screen and the progress modal.

A ``SURFACE_EDGE`` border, a background gap, then a fill that runs from
``ACCENT_FROM`` blue toward ``ACCENT_TO`` violet as it grows. Geometry is pure;
``draw_progress_bar`` needs a live ImGui frame.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.viz.theme import (
    ACCENT_FROM,
    ACCENT_TO,
    PROGRESS_BAR_BORDER_WIDTH,
    PROGRESS_BAR_FILL_GAP,
    SURFACE_EDGE,
    ui_px,
)

if TYPE_CHECKING:
    from imgui_bundle import imgui

Rect = tuple[int, int, int, int]

# Fill height at 100% UI scale. Border and gap are added outside it.
_FILL_HEIGHT_BASE = 6


def progress_bar_inset() -> int:
    """Pixels from the bar's outer edge to the fill."""
    return PROGRESS_BAR_BORDER_WIDTH + PROGRESS_BAR_FILL_GAP


def progress_bar_height() -> int:
    return ui_px(_FILL_HEIGHT_BASE) + 2 * progress_bar_inset()


def clamp_fraction(fraction: float) -> float:
    return max(0.0, min(1.0, float(fraction)))


def progress_fill_rect(bar: Rect, fraction: float) -> Rect | None:
    """Fill inside the border and gap, or None when nothing is filled."""
    x, y, width, height = bar
    inset = progress_bar_inset()
    inner_w = width - 2 * inset
    inner_h = height - 2 * inset
    if inner_w <= 0 or inner_h <= 0:
        return None
    fill_w = min(inner_w, int(round(inner_w * clamp_fraction(fraction))))
    if fill_w <= 0:
        return None
    return (x + inset, y + inset, fill_w, inner_h)


def accent_at(fraction: float) -> tuple[int, int, int]:
    """The accent gradient's colour *fraction* of the way from blue to violet."""
    t = clamp_fraction(fraction)
    return (
        round(ACCENT_FROM[0] + (ACCENT_TO[0] - ACCENT_FROM[0]) * t),
        round(ACCENT_FROM[1] + (ACCENT_TO[1] - ACCENT_FROM[1]) * t),
        round(ACCENT_FROM[2] + (ACCENT_TO[2] - ACCENT_FROM[2]) * t),
    )


def _packed(role: tuple[int, int, int]) -> int:
    from imgui_bundle import imgui as imgui_mod

    from cleave.viz.imgui_theme import rgba

    return int(imgui_mod.get_color_u32(rgba(role)))


def _fill(draw: imgui.ImDrawList, rect: Rect, color: int) -> None:
    from imgui_bundle import imgui as imgui_mod

    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    draw.add_rect_filled(
        imgui_mod.ImVec2(float(x), float(y)),
        imgui_mod.ImVec2(float(x + w), float(y + h)),
        color,
    )


def draw_progress_bar(
    draw: imgui.ImDrawList,
    bar: Rect,
    fraction: float,
    *,
    background: tuple[int, int, int] | None = None,
) -> None:
    """Draw track, fill, and border. ``background`` paints the whole track first."""
    x, y, width, height = bar
    if width <= 0 or height <= 0:
        return
    if background is not None:
        _fill(draw, bar, _packed(background))
    fill = progress_fill_rect(bar, fraction)
    if fill is not None:
        from imgui_bundle import imgui as imgui_mod

        fx, fy, fw, fh = fill
        start, end = _packed(ACCENT_FROM), _packed(accent_at(fraction))
        draw.add_rect_filled_multi_color(
            imgui_mod.ImVec2(float(fx), float(fy)),
            imgui_mod.ImVec2(float(fx + fw), float(fy + fh)),
            start,
            end,
            end,
            start,
        )
    border = _packed(SURFACE_EDGE)
    t = min(PROGRESS_BAR_BORDER_WIDTH, width // 2, height // 2)
    _fill(draw, (x, y, width, t), border)
    _fill(draw, (x, y + height - t, width, t), border)
    _fill(draw, (x, y + t, t, height - 2 * t), border)
    _fill(draw, (x + width - t, y + t, t, height - 2 * t), border)
