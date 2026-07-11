"""Tests for timeline beat snapping."""

from __future__ import annotations

from cleave.timeline import TimelineCue, snap_cues_to_beats


def test_snap_empty_cues_noop() -> None:
    beats = (0.0, 1.0, 2.0)
    assert snap_cues_to_beats([], beats) == []


def test_snap_empty_beats_noop() -> None:
    cues = [TimelineCue(t=0.4, layers={"layer_1": True})]
    assert snap_cues_to_beats(cues, []) == cues


def test_snap_nearest_beat() -> None:
    cues = [
        TimelineCue(t=0.1, layers={"layer_1": True}),
        TimelineCue(t=0.9, layers={"layer_2": False}),
    ]
    result = snap_cues_to_beats(cues, (0.0, 1.0, 2.0))
    assert result == [
        TimelineCue(t=0.0, layers={"layer_1": True}),
        TimelineCue(t=1.0, layers={"layer_2": False}),
    ]


def test_snap_midpoint_tie_prefers_earlier() -> None:
    cues = [TimelineCue(t=0.5, layers={"layer_1": True})]
    result = snap_cues_to_beats(cues, (0.0, 1.0))
    assert result == [TimelineCue(t=0.0, layers={"layer_1": True})]


def test_snap_extrapolates_outside_range_via_median_interval() -> None:
    # beats at 1.0, 2.0, 3.0 -> median interval 1.0; grid continues before/after
    cues = [
        TimelineCue(t=-0.4, layers={"layer_1": True}),
        TimelineCue(t=4.4, layers={"layer_2": False}),
    ]
    result = snap_cues_to_beats(cues, (1.0, 2.0, 3.0))
    assert result == [
        TimelineCue(t=0.0, layers={"layer_1": True}),
        TimelineCue(t=4.0, layers={"layer_2": False}),
    ]


def test_snap_extrapolation_midpoint_prefers_earlier() -> None:
    cues = [TimelineCue(t=3.5, layers={"layer_1": True})]
    result = snap_cues_to_beats(cues, (1.0, 2.0, 3.0))
    assert result == [TimelineCue(t=3.0, layers={"layer_1": True})]


def test_snap_merges_collisions() -> None:
    cues = [
        TimelineCue(t=0.1, layers={"layer_1": True}),
        TimelineCue(t=0.2, layers={"layer_2": False}),
        TimelineCue(t=0.9, layers={"layer_1": False}),
    ]
    result = snap_cues_to_beats(cues, (0.0, 1.0))
    assert result == [
        TimelineCue(t=0.0, layers={"layer_1": True, "layer_2": False}),
        TimelineCue(t=1.0, layers={"layer_1": False}),
    ]


def test_snap_single_beat_snaps_everything() -> None:
    cues = [
        TimelineCue(t=0.0, layers={"layer_1": True}),
        TimelineCue(t=10.0, layers={"layer_2": False}),
    ]
    result = snap_cues_to_beats(cues, (2.5,))
    assert result == [
        TimelineCue(t=2.5, layers={"layer_1": True, "layer_2": False}),
    ]


def test_snap_preserves_no_tick_slots() -> None:
    cues = [
        TimelineCue(t=0.1, layers={"layer_1": True}, no_tick_slots=frozenset({"layer_1"}))
    ]
    result = snap_cues_to_beats(cues, (0.0, 1.0))
    assert result == [
        TimelineCue(
            t=0.0, layers={"layer_1": True}, no_tick_slots=frozenset({"layer_1"})
        ),
    ]
