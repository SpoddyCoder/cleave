"""Tests for per-lane timeline beat snapping and bar-grid nudge."""

from __future__ import annotations

from cleave.timeline import (
    SlotCue,
    TimelineLane,
    shift_bars_by_beats,
    shift_lane_cues_by_beats,
    snap_lane_to_beats,
    snap_placement_time,
    snap_time_to_grid,
)


def _lane(
    baseline: bool | None,
    *transitions: tuple[float, bool],
) -> TimelineLane:
    return TimelineLane(
        baseline=baseline,
        cues=[SlotCue(t=t, visible=v) for t, v in transitions],
    )


def test_snap_time_to_grid_nearest_beat() -> None:
    assert snap_time_to_grid(0.4, (0.0, 1.0, 2.0)) == 0.0
    assert snap_time_to_grid(0.6, (0.0, 1.0, 2.0)) == 1.0


def test_snap_time_to_grid_nearest_bar() -> None:
    bars = (0.0, 4.0, 8.0)
    assert snap_time_to_grid(3.1, bars) == 4.0
    assert snap_time_to_grid(1.0, bars) == 0.0


def test_snap_time_to_grid_earlier_on_tie() -> None:
    assert snap_time_to_grid(0.5, (0.0, 1.0)) == 0.0


def test_snap_time_to_grid_empty_returns_t() -> None:
    assert snap_time_to_grid(1.25, ()) == 1.25


def test_snap_placement_time_modes() -> None:
    beats = (0.0, 1.0, 2.0)
    bars = (0.0, 4.0)
    assert snap_placement_time(0.6, "off", beat_times=beats, bar_times=bars) == 0.6
    assert snap_placement_time(0.6, "beat", beat_times=beats, bar_times=bars) == 1.0
    assert snap_placement_time(1.5, "bar", beat_times=beats, bar_times=bars) == 0.0
    assert snap_placement_time(0.6, "beat", beat_times=(), bar_times=bars) == 0.6


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


def test_shift_bars_by_beats_offsets() -> None:
    beat_times = tuple(float(i) for i in range(8))
    downbeats = (0.0, 4.0)
    assert shift_bars_by_beats(downbeats, beat_times, 0) == (0.0, 4.0)
    assert shift_bars_by_beats(downbeats, beat_times, 1) == (1.0, 5.0)
    assert shift_bars_by_beats(downbeats, beat_times, 2) == (2.0, 6.0)
    assert shift_bars_by_beats(downbeats, beat_times, 3) == (3.0, 7.0)


def test_shift_bars_by_beats_clamps() -> None:
    beat_times = (0.0, 1.0, 2.0, 3.0)
    assert shift_bars_by_beats((0.0, 3.0), beat_times, 2) == (2.0, 3.0)
    assert shift_bars_by_beats((0.0,), beat_times, -1) == (0.0,)


def test_shift_bars_by_beats_nearest_and_empty() -> None:
    beat_times = (0.0, 1.0, 2.0, 3.0, 4.0)
    assert shift_bars_by_beats((0.4, 3.6), beat_times, 1) == (1.0, 4.0)
    assert shift_bars_by_beats((), beat_times, 1) == ()
    assert shift_bars_by_beats((0.0,), (), 1) == ()


def test_shift_lane_cues_by_beats_offsets() -> None:
    lane = _lane(False, (0.1, True), (2.1, False))
    result = shift_lane_cues_by_beats(lane, (0.0, 1.0, 2.0, 3.0), 1)
    assert result.cues == [
        SlotCue(t=1.0, visible=True),
        SlotCue(t=3.0, visible=False),
    ]


def test_shift_lane_cues_by_beats_clamps_and_canonicalizes() -> None:
    lane = _lane(False, (0.0, True), (0.1, False))
    result = shift_lane_cues_by_beats(lane, (0.0, 1.0), -1)
    assert result.cues == []
    # Both cues collapse onto beat 1 as False; matches baseline -> dropped.
    result_fwd = shift_lane_cues_by_beats(lane, (0.0, 1.0), 1)
    assert result_fwd.cues == []
    lane_on = _lane(False, (0.0, True), (0.9, True))
    result_on = shift_lane_cues_by_beats(lane_on, (0.0, 1.0), 1)
    assert result_on.cues == [SlotCue(t=1.0, visible=True)]


def test_shift_lane_cues_by_beats_empty_noop() -> None:
    lane = _lane(None, (0.4, True))
    assert shift_lane_cues_by_beats(lane, (), 1).cues == [SlotCue(t=0.4, visible=True)]
    assert shift_lane_cues_by_beats(_lane(True), (0.0, 1.0), 1).cues == []
