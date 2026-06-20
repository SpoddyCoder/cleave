"""Tests for timeline cue evaluation and editing."""

from __future__ import annotations

import pytest

from cleave.config_schema import LAYER_SLOTS
from cleave.timeline import (
    RECORD_DEBOUNCE_SEC,
    TimelineCue,
    layer_visible_at,
    punch_replace,
    should_accept_toggle,
    stem_abbreviation,
    visible_state_at,
)


def _defaults(**overrides: bool) -> dict[str, bool]:
    base = {slot: True for slot in LAYER_SLOTS}
    base.update(overrides)
    return base


def test_stem_abbreviation_maps_known_stems() -> None:
    assert stem_abbreviation("drums") == "D"
    assert stem_abbreviation("bass") == "B"
    assert stem_abbreviation("vocals") == "V"
    assert stem_abbreviation("other") == "O"


def test_stem_abbreviation_full_mix() -> None:
    assert stem_abbreviation("full_mix") == "M"


def test_stem_abbreviation_rejects_unknown_stem() -> None:
    with pytest.raises(ValueError, match="unknown stem"):
        stem_abbreviation("synth")  # type: ignore[arg-type]


def test_layer_visible_at_uses_defaults_when_no_cues() -> None:
    defaults = _defaults(layer_1=False, layer_2=True)
    assert layer_visible_at([], defaults, "layer_1", 10.0) is False
    assert layer_visible_at([], defaults, "layer_2", 10.0) is True


def test_layer_visible_at_applies_cues_up_to_t_sec() -> None:
    defaults = _defaults()
    cues = [
        TimelineCue(t=5.0, layers={"layer_1": False}),
        TimelineCue(t=10.0, layers={"layer_1": True}),
        TimelineCue(t=15.0, layers={"layer_1": False}),
    ]
    assert layer_visible_at(cues, defaults, "layer_1", 4.9) is True
    assert layer_visible_at(cues, defaults, "layer_1", 5.0) is False
    assert layer_visible_at(cues, defaults, "layer_1", 12.0) is True
    assert layer_visible_at(cues, defaults, "layer_1", 14.9) is True
    assert layer_visible_at(cues, defaults, "layer_1", 20.0) is False


def test_layer_visible_at_last_write_wins_per_slot() -> None:
    defaults = _defaults()
    cues = [
        TimelineCue(t=1.0, layers={"layer_1": False, "layer_2": False}),
        TimelineCue(t=1.0, layers={"layer_1": True}),
    ]
    assert layer_visible_at(cues, defaults, "layer_1", 2.0) is True
    assert layer_visible_at(cues, defaults, "layer_2", 2.0) is False


def test_visible_state_at_returns_all_slots() -> None:
    defaults = _defaults(layer_1=False)
    cues = [TimelineCue(t=1.0, layers={"layer_2": False})]
    state = visible_state_at(cues, defaults, 2.0)
    assert set(state) == set(LAYER_SLOTS)
    assert state["layer_1"] is False
    assert state["layer_2"] is False
    assert state["layer_3"] is True
    assert state["layer_4"] is True


def test_punch_replace_removes_armed_cues_in_range() -> None:
    cues = [
        TimelineCue(t=1.0, layers={"layer_1": False}),
        TimelineCue(t=5.0, layers={"layer_2": False}),
        TimelineCue(t=8.0, layers={"layer_1": True, "layer_3": False}),
        TimelineCue(t=12.0, layers={"layer_4": False}),
    ]
    result = punch_replace(
        cues,
        armed_stems={"layer_1"},
        start_sec=4.0,
        stop_sec=10.0,
        new_cues=[TimelineCue(t=6.0, layers={"layer_1": False})],
    )
    assert result == [
        TimelineCue(t=1.0, layers={"layer_1": False}),
        TimelineCue(t=5.0, layers={"layer_2": False}),
        TimelineCue(t=6.0, layers={"layer_1": False}),
        TimelineCue(t=12.0, layers={"layer_4": False}),
    ]


def test_punch_replace_keeps_unarmed_cues_in_range() -> None:
    cues = [TimelineCue(t=5.0, layers={"layer_2": False})]
    result = punch_replace(
        cues,
        armed_stems={"layer_1"},
        start_sec=0.0,
        stop_sec=10.0,
        new_cues=[],
    )
    assert result == [TimelineCue(t=5.0, layers={"layer_2": False})]


def test_punch_replace_merges_cues_at_same_t() -> None:
    cues = [TimelineCue(t=20.0, layers={"layer_4": False})]
    result = punch_replace(
        cues,
        armed_stems={"layer_1", "layer_2"},
        start_sec=0.0,
        stop_sec=10.0,
        new_cues=[
            TimelineCue(t=2.0, layers={"layer_1": True}),
            TimelineCue(t=2.0, layers={"layer_2": False}),
        ],
    )
    assert result == [
        TimelineCue(t=2.0, layers={"layer_1": True, "layer_2": False}),
        TimelineCue(t=20.0, layers={"layer_4": False}),
    ]


def test_should_accept_toggle_debounces() -> None:
    assert should_accept_toggle(None, 1.0) is True
    assert should_accept_toggle(1.0, 1.0 + RECORD_DEBOUNCE_SEC - 0.01) is False
    assert should_accept_toggle(1.0, 1.0 + RECORD_DEBOUNCE_SEC) is True
