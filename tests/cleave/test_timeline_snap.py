"""Tests for per-lane timeline beat snapping."""

from __future__ import annotations

from cleave.timeline import SlotCue, TimelineLane, snap_lane_to_beats


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
