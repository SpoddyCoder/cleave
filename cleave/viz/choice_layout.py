"""Sizes and hit rects for choice controls: segments, combos, and their list.

Pure geometry shared by the inspector and form dialogs. Every control is as
wide as its widest option, so its parts hold still while the value changes.
"""

from __future__ import annotations

from collections.abc import Sequence

from cleave.choice import ChoiceKind, choice_kind
from cleave.viz.text_fit import TextSizer
from cleave.viz.theme import ui_px

Rect = tuple[int, int, int, int]

# In the shell glyph ranges (the navigator's open twisty).
COMBO_CARET = "▾"


def segment_pad_x() -> int:
    return ui_px(8)


def combo_pad_x() -> int:
    return ui_px(6)


def choice_list_pad_y() -> int:
    return ui_px(2)


def segment_widths(measure: TextSizer, labels: Sequence[str]) -> tuple[int, ...]:
    pad = segment_pad_x() * 2
    return tuple(measure.size(label)[0] + pad for label in labels)


def segment_rects(
    measure: TextSizer, labels: Sequence[str], *, x: int, y: int, height: int
) -> tuple[Rect, ...]:
    """Segments left to right from ``x``, sharing edges."""
    rects: list[Rect] = []
    for width in segment_widths(measure, labels):
        rects.append((x, y, width, height))
        x += width
    return tuple(rects)


def combo_width(measure: TextSizer, labels: Sequence[str]) -> int:
    """Widest option, a gap, the caret, and padding either side."""
    widest = max((measure.size(label)[0] for label in labels), default=0)
    caret = measure.size(f" {COMBO_CARET}")[0]
    return widest + caret + combo_pad_x() * 2


def choice_width(measure: TextSizer, labels: Sequence[str]) -> int:
    if choice_kind(len(labels)) is ChoiceKind.SEGMENT:
        return sum(segment_widths(measure, labels))
    return combo_width(measure, labels)


def choice_list_rects(
    *, x: int, y: int, width: int, line_h: int, count: int
) -> tuple[Rect, ...]:
    """One row per option, top to bottom from ``y``."""
    row_h = line_h + choice_list_pad_y() * 2
    return tuple((x, y + i * row_h, width, row_h) for i in range(count))


def rect_contains(rect: Rect, x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rx <= x < rx + rw and ry <= y < ry + rh


def rect_index_at(rects: Sequence[Rect], x: float, y: float) -> int | None:
    for index, rect in enumerate(rects):
        if rect_contains(rect, x, y):
            return index
    return None
