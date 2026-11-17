"""The accent bar behind a heading: help column section titles and modal titles.

It is the inspector title's settled band: the accent gradient, blue into
violet, across the full width, with the heading in ``value`` on it.
"""

from __future__ import annotations

from imgui_bundle import imgui

from cleave.viz.imgui_theme import rgba
from cleave.viz.progress_bar import accent_at


def paint_title_bar(
    draw: imgui.ImDrawList, x0: float, y0: float, x1: float, y1: float
) -> None:
    """Fill (*x0*, *y0*) to (*x1*, *y1*) with the accent gradient, left to right."""
    if x1 <= x0 or y1 <= y0:
        return
    left = int(imgui.get_color_u32(rgba(accent_at(0.0))))
    right = int(imgui.get_color_u32(rgba(accent_at(1.0))))
    draw.add_rect_filled_multi_color(
        imgui.ImVec2(x0, y0), imgui.ImVec2(x1, y1), left, right, right, left
    )
