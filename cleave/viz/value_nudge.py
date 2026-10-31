"""Side arrows on an adjustable inspector value.

The glyphs are draw-list text. Hit tests use the painted glyph widths, and a
hold repeats with the same clock as Left/Right.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cleave.viz.key_repeat import RepeatClock
from cleave.viz.row_kinds import RowDescriptor
from cleave.viz.row_spec import apply_field_horizontal
from cleave.viz.theme import DISABLED

if TYPE_CHECKING:
    from imgui_bundle import imgui

NUDGE_BACK_GLYPH = "< "
NUDGE_FORWARD_GLYPH = " >"


def value_parts(
    value: str, color: imgui.ImVec4, *, stepped: bool
) -> list[tuple[str, imgui.ImVec4]]:
    """``< `` / value / `` >`` when the row steps. Otherwise the value alone."""
    if not stepped:
        return [(value, color)]
    # imgui_theme imports imgui_bundle, whose package init loads matplotlib.
    # Stay off the play-path import graph until a stepped value is drawn.
    from cleave.viz.imgui_theme import rgba

    bracket = rgba(DISABLED)
    return [
        (NUDGE_BACK_GLYPH, bracket),
        (value, color),
        (NUDGE_FORWARD_GLYPH, bracket),
    ]


def selectable_text_y(
    item_min_y: float,
    item_spacing_y: float,
    *,
    selectable_text_align_y: float = 0.0,
    text_box_height: float = 0.0,
    text_height: float = 0.0,
) -> float:
    """Screen y of a Selectable label, given the item-rect top.

    Selectable grows the highlight by ``trunc(ItemSpacing / 2)`` above the
    cursor and draws the label at that cursor. Inspector rows submit
    Selectable with the default size, so the text box is the line height.
    ``SelectableTextAlign`` only drops the line when that box is taller than
    the text. Frame padding is not added to this box, so it is not an input.
    """
    y = float(item_min_y) + float(math.trunc(float(item_spacing_y) * 0.5))
    if selectable_text_align_y > 0.0:
        slack = float(text_box_height) - float(text_height)
        if slack > 0.0:
            y += slack * float(selectable_text_align_y)
    return y


def nudge_cluster_origin_x(
    row_max_x: float,
    part_widths: Sequence[float],
    frame_pad_x: float,
) -> float:
    """Left edge of the value cluster, matching the aligned draw."""
    return row_max_x - sum(part_widths) - frame_pad_x


@dataclass(frozen=True)
class NudgeRect:
    """Axis-aligned hit rect. Max edges are exclusive."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def contains(self, x: float, y: float) -> bool:
        return self.min_x <= x < self.max_x and self.min_y <= y < self.max_y


def nudge_arrow_rects(
    row_min_x: float,
    row_min_y: float,
    row_max_x: float,
    row_max_y: float,
    part_widths: Sequence[float],
    *,
    frame_pad_x: float,
) -> tuple[NudgeRect, NudgeRect]:
    """Left and right glyph hit rects.

    *part_widths* is the painted cluster: back glyph, value, forward glyph.
    Glyph width includes the gap space. Height is the row item rect. The
    value string is the span between the two rects and is not a hit.
    """
    back_w, value_w, forward_w = part_widths
    x = nudge_cluster_origin_x(
        row_max_x, (back_w, value_w, forward_w), frame_pad_x
    )
    back = NudgeRect(x, row_min_y, x + back_w, row_max_y)
    forward_x = back.max_x + value_w
    forward = NudgeRect(
        forward_x, row_min_y, forward_x + forward_w, row_max_y
    )
    return back, forward


def nudge_hover_fill_rect(
    hit: NudgeRect,
    *,
    forward: bool,
    arrow_width: float,
    space_width: float,
) -> NudgeRect:
    """Hover wash centered on the arrow character.

    The hit rect covers the painted glyph, including the gap space in
    ``< `` or `` >``. The wash keeps that width and the row's vertical
    edges, and shifts by half the space so the character sits in the middle.
    """
    width = hit.max_x - hit.min_x
    if forward:
        char_center = hit.min_x + space_width + arrow_width * 0.5
    else:
        char_center = hit.min_x + arrow_width * 0.5
    min_x = char_center - width * 0.5
    return NudgeRect(min_x, hit.min_y, min_x + width, hit.max_y)


@dataclass(frozen=True)
class NudgeHit:
    """Pointer is on a side arrow. ``forward`` is the right glyph."""

    forward: bool


def nudge_hit_at(
    x: float,
    y: float,
    back: NudgeRect,
    forward: NudgeRect,
) -> NudgeHit | None:
    """Arrow under the pointer. The value body and the rest of the row miss."""
    if back.contains(x, y):
        return NudgeHit(forward=False)
    if forward.contains(x, y):
        return NudgeHit(forward=True)
    return None


def nudge_press_skips_row(hit: NudgeHit | None) -> bool:
    """An arrow press skips the value drag and the row action.

    A miss, including the value string, leaves the row click alone.
    """
    return hit is not None


class ValueNudgeHold:
    """Pointer capture on one side arrow.

    ``press`` does not step. The caller steps once, then ``tick`` repeats
    while the clock is armed. A non-repeatable press stays captured so the
    row click and the drag stay suppressed, and ``tick`` does not step.
    """

    def __init__(self, controls: Any) -> None:
        self._controls = controls
        self._desc: RowDescriptor | None = None
        self._forward = False
        self._clock: RepeatClock | None = None

    def press(
        self, desc: RowDescriptor, forward: bool, repeatable: bool
    ) -> None:
        self._desc = desc
        self._forward = forward
        self._clock = RepeatClock() if repeatable else None

    def release(self) -> None:
        self._desc = None
        self._forward = False
        self._clock = None

    @property
    def armed(self) -> bool:
        return self._desc is not None

    @property
    def desc(self) -> RowDescriptor | None:
        return self._desc

    @property
    def forward(self) -> bool:
        return self._forward

    def tick(self, dt_sec: float) -> None:
        clock = self._clock
        desc = self._desc
        if clock is None or desc is None:
            return
        for _ in range(clock.tick(dt_sec)):
            apply_field_horizontal(self._controls, desc, self._forward, False)
