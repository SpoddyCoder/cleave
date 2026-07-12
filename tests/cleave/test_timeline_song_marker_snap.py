"""Tests for exclusive snap of timeline cues to song markers."""

from __future__ import annotations

from cleave.timeline import (
    SlotCue,
    TimelineLane,
    snap_lanes_to_song_markers,
)


def _lane(
    baseline: bool | None,
    *transitions: tuple[float, bool],
) -> TimelineLane:
    return TimelineLane(
        baseline=baseline,
        cues=[SlotCue(t=t, visible=v) for t, v in transitions],
    )


def test_proximity_no_op_when_outside_window() -> None:
    lanes = {"layer_1": _lane(None, (10.0, True))}
    result, moved = snap_lanes_to_song_markers(
        lanes,
        (0.0,),
        proximity=5.0,
        layer_z_order=("layer_1",),
        slots=("layer_1",),
    )
    assert moved == 0
    assert result["layer_1"].cues == [SlotCue(t=10.0, visible=True)]


def test_proximity_zero_no_op() -> None:
    lanes = {"layer_1": _lane(None, (1.0, True))}
    result, moved = snap_lanes_to_song_markers(
        lanes,
        (1.0,),
        proximity=0.0,
        layer_z_order=("layer_1",),
        slots=("layer_1",),
    )
    assert moved == 0
    assert result["layer_1"].cues == [SlotCue(t=1.0, visible=True)]


def test_empty_markers_no_op() -> None:
    lanes = {"layer_1": _lane(None, (1.0, True))}
    result, moved = snap_lanes_to_song_markers(
        lanes,
        (),
        proximity=5.0,
        layer_z_order=("layer_1",),
        slots=("layer_1",),
    )
    assert moved == 0
    assert result["layer_1"].cues == [SlotCue(t=1.0, visible=True)]


def test_closest_pick_within_proximity() -> None:
    lanes = {"layer_1": _lane(None, (3.0, True), (8.0, False))}
    result, moved = snap_lanes_to_song_markers(
        lanes,
        (5.0,),
        proximity=5.0,
        layer_z_order=("layer_1",),
        slots=("layer_1",),
    )
    assert moved == 1
    assert result["layer_1"].cues == [
        SlotCue(t=5.0, visible=True),
        SlotCue(t=8.0, visible=False),
    ]


def test_distance_tie_prefers_earlier_cue_time() -> None:
    lanes = {"layer_1": _lane(None, (4.0, True), (6.0, False))}
    result, moved = snap_lanes_to_song_markers(
        lanes,
        (5.0,),
        proximity=5.0,
        layer_z_order=("layer_1",),
        slots=("layer_1",),
    )
    assert moved == 1
    assert result["layer_1"].cues == [
        SlotCue(t=5.0, visible=True),
        SlotCue(t=6.0, visible=False),
    ]


def test_exclusive_claim_later_marker_skips_claimed_cue() -> None:
    lanes = {"layer_1": _lane(None, (5.0, True), (12.0, False))}
    result, moved = snap_lanes_to_song_markers(
        lanes,
        (5.5, 6.0),
        proximity=5.0,
        layer_z_order=("layer_1",),
        slots=("layer_1",),
    )
    # First marker at 5.5 claims cue at 5.0; second marker at 6.0 has no
    # remaining cue within 5s of an unclaimed cue (12.0 is 6s away).
    assert moved == 1
    assert result["layer_1"].cues == [
        SlotCue(t=5.5, visible=True),
        SlotCue(t=12.0, visible=False),
    ]


def test_exclusive_claim_second_marker_takes_next_cue() -> None:
    lanes = {"layer_1": _lane(None, (5.0, True), (11.0, False))}
    result, moved = snap_lanes_to_song_markers(
        lanes,
        (5.5, 10.0),
        proximity=5.0,
        layer_z_order=("layer_1",),
        slots=("layer_1",),
    )
    assert moved == 2
    assert result["layer_1"].cues == [
        SlotCue(t=5.5, visible=True),
        SlotCue(t=10.0, visible=False),
    ]


def test_each_layer_vs_closest_wins() -> None:
    lanes = {
        "layer_1": _lane(None, (4.5, True)),
        "layer_2": _lane(None, (4.8, False)),
    }
    z_order = ("layer_1", "layer_2")
    markers = (5.0,)

    each, each_moved = snap_lanes_to_song_markers(
        lanes,
        markers,
        proximity=5.0,
        layer_z_order=z_order,
        slots=z_order,
        mode="each_layer",
    )
    assert each_moved == 2
    assert each["layer_1"].cues == [SlotCue(t=5.0, visible=True)]
    assert each["layer_2"].cues == [SlotCue(t=5.0, visible=False)]

    closest, closest_moved = snap_lanes_to_song_markers(
        lanes,
        markers,
        proximity=5.0,
        layer_z_order=z_order,
        slots=z_order,
        mode="closest_wins",
    )
    assert closest_moved == 1
    assert closest["layer_1"].cues == [SlotCue(t=4.5, visible=True)]
    assert closest["layer_2"].cues == [SlotCue(t=5.0, visible=False)]


def test_closest_wins_tie_prefers_earlier_layer_in_z_order() -> None:
    lanes = {
        "layer_1": _lane(None, (4.0, True)),
        "layer_2": _lane(None, (6.0, False)),
    }
    # Equal distance 1.0 from marker 5.0; earlier time wins before z-order.
    result, moved = snap_lanes_to_song_markers(
        lanes,
        (5.0,),
        proximity=5.0,
        layer_z_order=("layer_1", "layer_2"),
        slots=("layer_1", "layer_2"),
        mode="closest_wins",
    )
    assert moved == 1
    assert result["layer_1"].cues == [SlotCue(t=5.0, visible=True)]
    assert result["layer_2"].cues == [SlotCue(t=6.0, visible=False)]

    # Equal distance and equal times: earlier z-order wins.
    lanes_eq = {
        "layer_2": _lane(None, (4.5, False)),
        "layer_1": _lane(None, (4.5, True)),
    }
    result_eq, moved_eq = snap_lanes_to_song_markers(
        lanes_eq,
        (5.0,),
        proximity=5.0,
        layer_z_order=("layer_1", "layer_2"),
        slots=("layer_1", "layer_2"),
        mode="closest_wins",
    )
    assert moved_eq == 1
    assert result_eq["layer_1"].cues == [SlotCue(t=5.0, visible=True)]
    assert result_eq["layer_2"].cues == [SlotCue(t=4.5, visible=False)]


def test_canonicalize_after_collision() -> None:
    # Two markers at the same time claim two cues; last-wins at equal t, then
    # redundant False vs baseline False is dropped.
    lanes = {"layer_1": _lane(False, (4.0, True), (6.0, False))}
    result, moved = snap_lanes_to_song_markers(
        lanes,
        (5.0, 5.0),
        proximity=5.0,
        layer_z_order=("layer_1",),
        slots=("layer_1",),
    )
    assert moved == 2
    assert result["layer_1"].cues == []


def test_preserves_visibility_and_baseline() -> None:
    lanes = {"layer_1": _lane(True, (3.0, False))}
    result, moved = snap_lanes_to_song_markers(
        lanes,
        (5.0,),
        proximity=5.0,
        layer_z_order=("layer_1",),
        slots=("layer_1",),
    )
    assert moved == 1
    assert result["layer_1"].baseline is True
    assert result["layer_1"].cues == [SlotCue(t=5.0, visible=False)]


def test_single_slot_leaves_other_lanes_unchanged() -> None:
    lanes = {
        "layer_1": _lane(None, (4.0, True)),
        "layer_2": _lane(None, (4.0, False)),
    }
    result, moved = snap_lanes_to_song_markers(
        lanes,
        (5.0,),
        proximity=5.0,
        layer_z_order=("layer_1", "layer_2"),
        slots=("layer_1",),
    )
    assert moved == 1
    assert result["layer_1"].cues == [SlotCue(t=5.0, visible=True)]
    assert result["layer_2"].cues == [SlotCue(t=4.0, visible=False)]
