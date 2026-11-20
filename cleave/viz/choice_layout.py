"""Sizes and hit rects for choice controls: segments, combos, steppers, and lists.

Pure geometry shared by the inspector and form dialogs. Every control is as
wide as its widest option, so its parts hold still while the value changes.
"""

from __future__ import annotations

from collections.abc import Sequence

from cleave.choice import ChoiceKind, choice_kind
from cleave.viz.icon_button import icon_gap
from cleave.viz.text_fit import TextSizer
from cleave.viz.theme import ui_px

Rect = tuple[int, int, int, int]
# x, y, width, height in unrounded pixels, for rects built from ImGui sizes.
FRect = tuple[float, float, float, float]

# In the shell glyph ranges (the navigator's open twisty).
COMBO_CARET = "▾"
# A stepper's arrows as inspector value parts. Each paints as a square box
# the row tall, with an icon gap to the value that belongs to its hit area.
STEPPER_BACK = "< "
STEPPER_FORWARD = " >"
# A vertical list's radio buttons, then a space before the option.
RADIO_ON = "● "
RADIO_OFF = "○ "


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


def choice_width(
    measure: TextSizer, labels: Sequence[str], *, combo: bool = False
) -> int:
    if choice_kind(len(labels), combo=combo) is ChoiceKind.SEGMENT:
        return sum(segment_widths(measure, labels))
    return combo_width(measure, labels)


def stepper_slot_width(side: int) -> int:
    """An arrow's square box of *side*, and the gap before the value."""
    return side + round(icon_gap())


def stepper_width(measure: TextSizer, labels: Sequence[str], *, side: int) -> int:
    """``< value >`` wide enough for the widest option, with arrows *side* square."""
    widest = max((measure.size(label)[0] for label in labels), default=0)
    return stepper_slot_width(side) * 2 + widest


def radio_width(measure: TextSizer, labels: Sequence[str]) -> int:
    """A radio button and the widest option beside it."""
    widest = max((measure.size(label)[0] for label in labels), default=0)
    return measure.size(RADIO_OFF)[0] + widest


def stepper_arrow_rects(rect: Rect) -> tuple[Rect, Rect]:
    """The back and forward arrow slots at either end of a stepper ``rect``.

    Each is a square box ``rect`` tall plus the gap before the value.
    """
    x, y, w, h = rect
    slot = stepper_slot_width(h)
    return (x, y, slot, h), (x + w - slot, y, slot, h)


def stepper_arrow_box(slot: Rect, *, forward: bool) -> Rect:
    """The square box painted on the outer edge of an arrow ``slot``."""
    x, y, w, h = slot
    return (x + w - h if forward else x), y, h, h


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
