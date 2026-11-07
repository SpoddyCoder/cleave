"""Scroll a list just enough to keep the focused row in view.

The pure helpers work in content pixels and are shared by the file picker and
the shell panels. ``ScrollFollow`` applies them to the current ImGui window.
ImGui loads on the first follow, not at import.
"""

from __future__ import annotations

from collections.abc import Hashable


def reveal_span(
    scroll_y: float,
    top: float,
    bottom: float,
    *,
    view_height: float,
) -> float:
    """Move *scroll_y* the least amount that puts [*top*, *bottom*] in the view.

    A span taller than the view keeps its top in view. The result is never
    negative. The caller clamps the far end.
    """
    if view_height <= 0:
        return 0.0
    if bottom > scroll_y + view_height:
        scroll_y = bottom - view_height
    if top < scroll_y:
        scroll_y = top
    return max(0.0, scroll_y)


def clamp_scroll(
    scroll_y: float,
    *,
    row_stride: int,
    view_height: float,
    row_count: int,
) -> float:
    """Clamp a list scroll offset so the last row can sit at the bottom."""
    if row_stride <= 0 or view_height <= 0 or row_count <= 0:
        return 0.0
    limit = max(0.0, row_count * row_stride - view_height)
    return min(max(0.0, scroll_y), limit)


def scroll_to_reveal(
    scroll_y: float,
    row: int,
    *,
    row_stride: int,
    view_height: float,
    row_count: int,
) -> float:
    """Move *scroll_y* the least amount that puts uniform *row* fully in view."""
    if row_stride <= 0 or view_height <= 0 or row_count <= 0:
        return 0.0
    row = min(max(0, row), row_count - 1)
    top = float(row * row_stride)
    return clamp_scroll(
        reveal_span(scroll_y, top, top + float(row_stride), view_height=view_height),
        row_stride=row_stride,
        view_height=view_height,
        row_count=row_count,
    )


class ScrollFollow:
    """Keeps one panel's focused item in view when the focus changes.

    Call ``follow`` right after drawing the focused item, inside its window.
    It scrolls only when *key* differs from the last one, so the wheel and the
    scrollbar stay free between focus moves.
    """

    def __init__(self) -> None:
        self._key: Hashable | None = None

    def follow(self, key: Hashable) -> None:
        if key == self._key:
            return
        self._key = key
        from imgui_bundle import imgui

        rect_min = imgui.get_item_rect_min()
        rect_max = imgui.get_item_rect_max()
        window_y = float(imgui.get_window_pos().y)
        scroll_y = float(imgui.get_scroll_y())
        pad_y = float(imgui.get_style().window_padding.y)
        # Window-local content coordinates, with the padding kept around the row.
        top = float(rect_min.y) - window_y + scroll_y - pad_y
        bottom = float(rect_max.y) - window_y + scroll_y + pad_y
        target = reveal_span(
            scroll_y, top, bottom, view_height=float(imgui.get_window_height())
        )
        # Moving up to within one row of the top shows the top, so a title
        # above the first row comes back into view.
        if target < scroll_y and target < bottom - top:
            target = 0.0
        if abs(target - scroll_y) > 0.01:
            imgui.set_scroll_y(target)
