"""Stepper geometry for form dialogs. No GL window."""

from __future__ import annotations

from cleave.viz.choice_layout import (
    stepper_arrow_box,
    stepper_arrow_rects,
    stepper_slot_width,
    stepper_width,
)


class _Measure:
    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * 8, 16)


def test_stepper_is_two_square_slots_and_the_widest_option() -> None:
    width = stepper_width(_Measure(), ("Off", "Bars"), side=22)
    assert width == stepper_slot_width(22) * 2 + 32


def test_arrow_slots_sit_at_each_end_with_square_boxes_outside() -> None:
    rect = (100, 50, 120, 22)
    back, forward = stepper_arrow_rects(rect)
    slot = stepper_slot_width(22)
    assert back == (100, 50, slot, 22)
    assert forward == (220 - slot, 50, slot, 22)
    assert stepper_arrow_box(back, forward=False) == (100, 50, 22, 22)
    assert stepper_arrow_box(forward, forward=True) == (198, 50, 22, 22)
