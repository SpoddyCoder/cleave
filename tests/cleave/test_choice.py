"""Choosing from a fixed list: clamped steps and the segment/combo rule."""

from __future__ import annotations

from cleave.choice import (
    ChoiceKind,
    at_end,
    at_start,
    choice_index,
    choice_kind,
    step_choice,
    step_index,
)

_OPTIONS = ("low", "mid", "high")


def test_step_choice_moves_one_option() -> None:
    assert step_choice(_OPTIONS, "low", 1) == "mid"
    assert step_choice(_OPTIONS, "high", -1) == "mid"


def test_step_choice_stops_at_either_end() -> None:
    assert step_choice(_OPTIONS, "high", 1) == "high"
    assert step_choice(_OPTIONS, "low", -1) == "low"
    assert step_choice(_OPTIONS, "low", 10) == "high"


def test_unknown_value_counts_as_first_option() -> None:
    assert choice_index(_OPTIONS, "missing") == 0
    assert step_choice(_OPTIONS, "missing", 1) == "mid"


def test_step_index_clamps_and_handles_empty() -> None:
    assert step_index(2, 3, 1) == 2
    assert step_index(0, 3, -1) == 0
    assert step_index(0, 0, 1) == 0


def test_ends() -> None:
    assert at_start(_OPTIONS, "low") and not at_end(_OPTIONS, "low")
    assert at_end(_OPTIONS, "high") and not at_start(_OPTIONS, "high")


def test_three_or_fewer_options_are_segments() -> None:
    assert choice_kind(2) is ChoiceKind.SEGMENT
    assert choice_kind(3) is ChoiceKind.SEGMENT
    assert choice_kind(4) is ChoiceKind.COMBO
