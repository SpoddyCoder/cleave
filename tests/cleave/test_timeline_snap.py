"""Tests for per-lane timeline beat snapping and bar-phase derivation."""

from __future__ import annotations

import pytest

from cleave.timeline import (
    SlotCue,
    TimelineLane,
    bar_phase_from_beats,
    bar_phase_matching,
    bar_times_at_phase,
    bar_times_from_beats,
    snap_lane_to_beats,
)


def _lane(
    baseline: bool | None,
    *transitions: tuple[float, bool],
) -> TimelineLane:
    return TimelineLane(
        baseline=baseline,
        cues=[SlotCue(t=t, visible=v) for t, v in transitions],
    )


def test_snap_empty_cues_noop() -> None:
    lane = _lane(True)
    assert snap_lane_to_beats(lane, (0.0, 1.0, 2.0)).cues == []


def test_snap_empty_beats_noop() -> None:
    lane = _lane(None, (0.4, True))
    result = snap_lane_to_beats(lane, [])
    assert result.cues == [SlotCue(t=0.4, visible=True)]


def test_snap_nearest_beat() -> None:
    lane = _lane(False, (0.1, True), (0.9, False))
    result = snap_lane_to_beats(lane, (0.0, 1.0, 2.0))
    assert result.cues == [
        SlotCue(t=0.0, visible=True),
        SlotCue(t=1.0, visible=False),
    ]


def test_snap_midpoint_tie_prefers_earlier() -> None:
    lane = _lane(False, (0.5, True))
    result = snap_lane_to_beats(lane, (0.0, 1.0))
    assert result.cues == [SlotCue(t=0.0, visible=True)]


def test_snap_extrapolates_outside_range_via_median_interval() -> None:
    lane = _lane(False, (-0.4, True), (4.4, False))
    result = snap_lane_to_beats(lane, (1.0, 2.0, 3.0))
    assert result.cues == [
        SlotCue(t=0.0, visible=True),
        SlotCue(t=4.0, visible=False),
    ]


def test_snap_extrapolation_midpoint_prefers_earlier() -> None:
    lane = _lane(False, (3.5, True))
    result = snap_lane_to_beats(lane, (1.0, 2.0, 3.0))
    assert result.cues == [SlotCue(t=3.0, visible=True)]


def test_snap_merges_collisions_within_lane() -> None:
    lane = _lane(False, (0.1, True), (0.2, False), (0.9, True))
    result = snap_lane_to_beats(lane, (0.0, 1.0))
    # 0.1 and 0.2 both snap to 0.0; last-wins -> False; 0.9 -> 1.0 True
    assert result.cues == [SlotCue(t=1.0, visible=True)]


def test_snap_single_beat_snaps_everything() -> None:
    lane = _lane(True, (0.0, True), (10.0, False))
    result = snap_lane_to_beats(lane, (2.5,))
    assert result.cues == [SlotCue(t=2.5, visible=False)]


def test_snap_preserves_baseline() -> None:
    lane = _lane(True, (0.1, False))
    result = snap_lane_to_beats(lane, (0.0, 1.0))
    assert result.baseline is True
    assert result.cues == [SlotCue(t=0.0, visible=False)]


def test_bar_times_picks_strongest_phase() -> None:
    # Two bars; phase 2 has the strongest onsets.
    beat_times = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0)
    onset_at_beats = (1.0, 1.0, 5.0, 1.0, 1.0, 1.0, 5.0, 1.0)
    assert bar_phase_from_beats(beat_times, onset_at_beats) == 2
    assert bar_times_from_beats(beat_times, onset_at_beats) == (2.0, 6.0)


def test_bar_times_short_input_returns_empty() -> None:
    assert bar_phase_from_beats((0.0, 1.0, 2.0), (1.0, 1.0, 1.0)) is None
    assert bar_times_from_beats((0.0, 1.0, 2.0), (1.0, 1.0, 1.0)) == ()


def test_bar_times_n4_slicing() -> None:
    beat_times = tuple(float(i) for i in range(12))
    # Phase 0 strongest.
    onset = [3.0, 0.0, 0.0, 0.0] * 3
    assert bar_times_from_beats(beat_times, onset) == (0.0, 4.0, 8.0)


def test_bar_times_at_phase_slices() -> None:
    beat_times = tuple(float(i) for i in range(8))
    assert bar_times_at_phase(beat_times, 0) == (0.0, 4.0)
    assert bar_times_at_phase(beat_times, 1) == (1.0, 5.0)
    assert bar_times_at_phase(beat_times, 2) == (2.0, 6.0)
    assert bar_times_at_phase(beat_times, 3) == (3.0, 7.0)


def test_bar_times_at_phase_wraps_and_offsets_heuristic() -> None:
    beat_times = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0)
    onset_at_beats = (1.0, 1.0, 5.0, 1.0, 1.0, 1.0, 5.0, 1.0)
    base = bar_phase_from_beats(beat_times, onset_at_beats)
    assert base == 2
    assert bar_times_at_phase(beat_times, (base + 0) % 4) == (2.0, 6.0)
    assert bar_times_at_phase(beat_times, (base + 1) % 4) == (3.0, 7.0)
    assert bar_times_at_phase(beat_times, (base + 2) % 4) == (0.0, 4.0)
    assert bar_times_at_phase(beat_times, (base + 3) % 4) == (1.0, 5.0)


def test_bar_times_at_phase_empty_beats() -> None:
    assert bar_times_at_phase((), 0) == ()


def test_bar_times_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="same length"):
        bar_times_from_beats((0.0, 1.0, 2.0, 3.0), (1.0, 1.0, 1.0))


def test_bar_phase_matching_finds_phase() -> None:
    beat_times = tuple(float(i) for i in range(8))
    assert bar_phase_matching(beat_times, (0.0, 4.0)) == 0
    assert bar_phase_matching(beat_times, (2.0, 6.0)) == 2
    assert bar_phase_matching(beat_times, (1.0, 9.0)) is None
    assert bar_phase_matching((), (0.0,)) is None
    assert bar_phase_matching(beat_times, ()) is None
