"""Tests for timeline cue evaluation and editing."""

from __future__ import annotations

import pytest

from cleave.extract import STEM_NAMES
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
    base = {name: True for name in STEM_NAMES}
    base.update(overrides)
    return base


def test_stem_abbreviation_maps_known_stems() -> None:
    assert stem_abbreviation("drums") == "D"
    assert stem_abbreviation("bass") == "B"
    assert stem_abbreviation("vocals") == "V"
    assert stem_abbreviation("other") == "O"


def test_stem_abbreviation_rejects_unknown_stem() -> None:
    with pytest.raises(ValueError, match="unknown stem"):
        stem_abbreviation("synth")


def test_layer_visible_at_uses_defaults_when_no_cues() -> None:
    defaults = _defaults(drums=False, bass=True)
    assert layer_visible_at([], defaults, "drums", 10.0) is False
    assert layer_visible_at([], defaults, "bass", 10.0) is True


def test_layer_visible_at_applies_cues_up_to_t_sec() -> None:
    defaults = _defaults()
    cues = [
        TimelineCue(t=5.0, layers={"drums": False}),
        TimelineCue(t=10.0, layers={"drums": True}),
        TimelineCue(t=15.0, layers={"drums": False}),
    ]
    assert layer_visible_at(cues, defaults, "drums", 4.9) is True
    assert layer_visible_at(cues, defaults, "drums", 5.0) is False
    assert layer_visible_at(cues, defaults, "drums", 12.0) is True
    assert layer_visible_at(cues, defaults, "drums", 14.9) is True
    assert layer_visible_at(cues, defaults, "drums", 20.0) is False


def test_layer_visible_at_last_write_wins_per_stem() -> None:
    defaults = _defaults()
    cues = [
        TimelineCue(t=1.0, layers={"drums": False, "bass": False}),
        TimelineCue(t=1.0, layers={"drums": True}),
    ]
    assert layer_visible_at(cues, defaults, "drums", 2.0) is True
    assert layer_visible_at(cues, defaults, "bass", 2.0) is False


def test_visible_state_at_returns_all_stems() -> None:
    defaults = _defaults(drums=False)
    cues = [TimelineCue(t=1.0, layers={"bass": False})]
    state = visible_state_at(cues, defaults, 2.0)
    assert set(state) == set(STEM_NAMES)
    assert state["drums"] is False
    assert state["bass"] is False
    assert state["vocals"] is True
    assert state["other"] is True


def test_punch_replace_removes_armed_cues_in_range() -> None:
    cues = [
        TimelineCue(t=1.0, layers={"drums": False}),
        TimelineCue(t=5.0, layers={"bass": False}),
        TimelineCue(t=8.0, layers={"drums": True, "vocals": False}),
        TimelineCue(t=12.0, layers={"other": False}),
    ]
    result = punch_replace(
        cues,
        armed_stems={"drums"},
        start_sec=4.0,
        stop_sec=10.0,
        new_cues=[TimelineCue(t=6.0, layers={"drums": False})],
    )
    assert result == [
        TimelineCue(t=1.0, layers={"drums": False}),
        TimelineCue(t=5.0, layers={"bass": False}),
        TimelineCue(t=6.0, layers={"drums": False}),
        TimelineCue(t=12.0, layers={"other": False}),
    ]


def test_punch_replace_keeps_unarmed_cues_in_range() -> None:
    cues = [TimelineCue(t=5.0, layers={"bass": False})]
    result = punch_replace(
        cues,
        armed_stems={"drums"},
        start_sec=0.0,
        stop_sec=10.0,
        new_cues=[],
    )
    assert result == [TimelineCue(t=5.0, layers={"bass": False})]


def test_punch_replace_merges_cues_at_same_t() -> None:
    cues = [TimelineCue(t=20.0, layers={"other": False})]
    result = punch_replace(
        cues,
        armed_stems={"drums", "bass"},
        start_sec=0.0,
        stop_sec=10.0,
        new_cues=[
            TimelineCue(t=2.0, layers={"drums": True}),
            TimelineCue(t=2.0, layers={"bass": False}),
        ],
    )
    assert result == [
        TimelineCue(t=2.0, layers={"drums": True, "bass": False}),
        TimelineCue(t=20.0, layers={"other": False}),
    ]


def test_should_accept_toggle_debounces() -> None:
    assert should_accept_toggle(None, 1.0) is True
    assert should_accept_toggle(1.0, 1.0 + RECORD_DEBOUNCE_SEC - 0.01) is False
    assert should_accept_toggle(1.0, 1.0 + RECORD_DEBOUNCE_SEC) is True
