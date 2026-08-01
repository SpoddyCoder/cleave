"""Tests for per-lane timeline evaluation and editing."""

from __future__ import annotations

import pytest

from cleave.config_schema import DEFAULT_LAYER_SLOTS
from cleave.easing import smoothstep
from cleave.timeline import (
    LEVEL_EPS,
    RECORD_DEBOUNCE_SEC,
    SlotCue,
    TimelineFadeGroup,
    TimelineLane,
    canonicalize,
    empty_lane,
    lane_blend_at,
    lane_role_at,
    lane_level_at,
    lane_level_breakpoints,
    lane_level_envelope,
    lane_on_transition_count,
    lane_on_transition_cues,
    lane_on_transition_trigger_times,
    punch_lane,
    set_lane_cue,
    shift_lane_cues_by_beats,
    should_accept_toggle,
    snap_lane_to_beats,
    stem_abbreviation,
    strip_lane_range,
)

_OFF = TimelineFadeGroup(enabled=False)
_STD = TimelineFadeGroup(enabled=True, fade_in=2.0, fade_out=2.0)


def _std(*, fade_in: float = 2.0, fade_out: float = 2.0) -> TimelineFadeGroup:
    return TimelineFadeGroup(enabled=True, fade_in=fade_in, fade_out=fade_out)


def _markers(*, fade_in: float = 2.0, fade_out: float = 2.0) -> TimelineFadeGroup:
    return TimelineFadeGroup(enabled=True, fade_in=fade_in, fade_out=fade_out)


def _as_level(value: float | bool | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return float(value)


def _lane(
    baseline: float | bool | None,
    *transitions: tuple[float, float | bool],
) -> TimelineLane:
    base = _as_level(baseline)
    cues = [
        SlotCue(t=t, level=float(_as_level(level)))
        for t, level in transitions
    ]
    return TimelineLane(baseline=base, cues=canonicalize(base, cues))


def _env(
    lane: TimelineLane,
    t_sec: float,
    *,
    inherit: float | bool,
    song_marker_fades: TimelineFadeGroup,
    standard_fades: TimelineFadeGroup,
    duration_sec: float,
    song_marker_times: tuple[float, ...] = (),
) -> float:
    breakpoints = lane_level_breakpoints(
        lane,
        inherit=float(_as_level(inherit) or 0.0),
        song_marker_fades=song_marker_fades,
        standard_fades=standard_fades,
        duration_sec=duration_sec,
        song_marker_times=song_marker_times,
    )
    return lane_level_envelope(t_sec, breakpoints)


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


def test_lane_level_at_uses_inherit_when_baseline_none() -> None:
    lane = empty_lane()
    assert lane_level_at(lane, 10.0, inherit=0.0) == 0.0
    assert lane_level_at(lane, 10.0, inherit=1.0) == 1.0


def test_lane_level_at_uses_concrete_baseline() -> None:
    lane = _lane(0.0)
    assert lane_level_at(lane, 10.0, inherit=1.0) == 0.0


def test_lane_level_at_applies_cues_up_to_t_sec() -> None:
    lane = _lane(1.0, (5.0, 0.0), (10.0, 1.0), (15.0, 0.0))
    assert lane_level_at(lane, 4.9, inherit=1.0) == 1.0
    assert lane_level_at(lane, 5.0, inherit=1.0) == 0.0
    assert lane_level_at(lane, 12.0, inherit=1.0) == 1.0
    assert lane_level_at(lane, 14.9, inherit=1.0) == 1.0
    assert lane_level_at(lane, 20.0, inherit=1.0) == 0.0


def test_lane_level_at_across_slots() -> None:
    lanes = {
        "layer_1": _lane(0.0),
        "layer_2": _lane(1.0, (1.0, 0.0)),
    }
    inherits = {slot: 1.0 for slot in DEFAULT_LAYER_SLOTS}
    state = {
        slot: lane_level_at(
            lanes.get(slot) or empty_lane(),
            2.0,
            inherit=inherits[slot],
        )
        for slot in DEFAULT_LAYER_SLOTS
    }
    assert set(state) == set(DEFAULT_LAYER_SLOTS)
    assert state["layer_1"] == 0.0
    assert state["layer_2"] == 0.0
    assert state["layer_3"] == 1.0
    assert state["layer_4"] == 1.0


def test_canonicalize_last_write_wins_at_equal_t() -> None:
    cues = canonicalize(
        1.0,
        [SlotCue(t=1.0, level=0.0), SlotCue(t=1.0, level=1.0)],
    )
    assert cues == []


def test_canonicalize_drops_redundant_transitions() -> None:
    cues = canonicalize(
        0.0,
        [SlotCue(t=1.0, level=0.0), SlotCue(t=2.0, level=1.0)],
    )
    assert cues == [SlotCue(t=2.0, level=1.0)]


def test_canonicalize_keeps_blend_only_change() -> None:
    cues = canonicalize(
        0.0,
        [
            SlotCue(t=1.0, level=1.0),
            SlotCue(t=2.0, level=1.0, blend="add"),
        ],
    )
    assert cues == [
        SlotCue(t=1.0, level=1.0),
        SlotCue(t=2.0, level=1.0, blend="add"),
    ]


def test_canonicalize_drops_full_noop_including_blend() -> None:
    cues = canonicalize(
        0.0,
        [
            SlotCue(t=1.0, level=1.0, blend="add"),
            SlotCue(t=2.0, level=1.0, blend="add", role="pulse"),
        ],
    )
    assert cues == [SlotCue(t=1.0, level=1.0, blend="add")]


def test_canonicalize_strips_blend_and_role_on_off_cues() -> None:
    cues = canonicalize(
        0.0,
        [
            SlotCue(t=1.0, level=1.0, blend="add", role="lead"),
            SlotCue(t=2.0, level=0.0, blend="screen", role="accent"),
            SlotCue(t=3.0, level=0.5, blend="add", role="pulse"),
        ],
    )
    assert cues == [
        SlotCue(t=1.0, level=1.0, blend="add", role="lead"),
        SlotCue(t=2.0, level=0.0),
        SlotCue(t=3.0, level=0.5, blend="add", role="pulse"),
    ]


def test_canonicalize_off_with_dead_metadata_still_level_only() -> None:
    """Stripping off metadata must not invent blend-only keep/drop bugs."""
    cues = canonicalize(
        1.0,
        [SlotCue(t=1.0, level=0.0, blend="add", role="pulse")],
    )
    assert cues == [SlotCue(t=1.0, level=0.0)]


def test_cue_editable_and_navigable_times() -> None:
    from cleave.timeline import (
        cue_editable_for_blend_role,
        navigable_cue_times,
        opening_baseline_editable,
        opening_cue,
    )

    on = SlotCue(t=1.0, level=0.5)
    mid = SlotCue(t=2.0, level=1.0)
    off = SlotCue(t=3.0, level=0.0, blend="add", role="lead")
    assert cue_editable_for_blend_role(on)
    assert cue_editable_for_blend_role(mid)
    assert not cue_editable_for_blend_role(off)
    lane = TimelineLane(baseline=0.0, cues=[on, mid, off])
    assert navigable_cue_times(lane) == [1.0, 2.0]
    assert not opening_baseline_editable(lane)
    assert opening_cue(lane) is None

    opening_on = TimelineLane(baseline=0.5, cues=[SlotCue(t=10.0, level=0.0)])
    assert opening_baseline_editable(opening_on)
    assert opening_cue(opening_on) == SlotCue(t=0.0, level=0.5)
    assert navigable_cue_times(opening_on) == [0.0]

    already_at_zero = TimelineLane(
        baseline=0.0,
        cues=[SlotCue(t=0.0, level=0.5), SlotCue(t=10.0, level=0.0)],
    )
    assert not opening_baseline_editable(already_at_zero)
    assert navigable_cue_times(already_at_zero) == [0.0]


def test_update_lane_cue_materializes_opening_baseline() -> None:
    from cleave.timeline import update_lane_cue

    lane = TimelineLane(
        baseline=0.5,
        cues=[SlotCue(t=10.0, level=0.0), SlotCue(t=20.0, level=1.0)],
    )
    updated = update_lane_cue(lane, 0.0, blend="add", role="lead")
    assert updated.baseline == 0.0
    assert updated.cues[0] == SlotCue(t=0.0, level=0.5, blend="add", role="lead")
    assert updated.cues[1:] == [
        SlotCue(t=10.0, level=0.0),
        SlotCue(t=20.0, level=1.0),
    ]


def test_update_lane_cue_level_only_keeps_opening_baseline() -> None:
    from cleave.timeline import update_lane_cue

    lane = TimelineLane(
        baseline=0.5,
        cues=[SlotCue(t=10.0, level=0.0), SlotCue(t=20.0, level=1.0)],
    )
    updated = update_lane_cue(lane, 0.0, blend=None, role=None, level=0.75)
    assert updated.baseline == 0.75
    assert updated.cues == [
        SlotCue(t=10.0, level=0.0),
        SlotCue(t=20.0, level=1.0),
    ]


def test_update_lane_cue_changes_stored_cue_level() -> None:
    from cleave.timeline import update_lane_cue

    lane = TimelineLane(
        baseline=0.0,
        cues=[SlotCue(t=5.0, level=1.0, blend="add", role="lead")],
    )
    updated = update_lane_cue(
        lane, 5.0, blend="add", role="lead", level=0.25
    )
    assert updated.cues == [
        SlotCue(t=5.0, level=0.25, blend="add", role="lead"),
    ]


def test_lane_blend_at_holds_and_reverts() -> None:
    lane = TimelineLane(
        baseline=0.0,
        cues=[
            SlotCue(t=1.0, level=1.0, blend="add"),
            SlotCue(t=2.0, level=1.0, blend=None),
            SlotCue(t=3.0, level=0.0),
            SlotCue(t=4.0, level=1.0, blend="screen"),
        ],
    )
    assert lane_blend_at(lane, 0.5) is None
    assert lane_blend_at(lane, 1.0) == "add"
    assert lane_blend_at(lane, 1.5) == "add"
    assert lane_blend_at(lane, 2.0) is None
    assert lane_blend_at(lane, 3.0) is None
    assert lane_blend_at(lane, 4.0) == "screen"


def test_lane_role_at_holds_and_clears() -> None:
    lane = TimelineLane(
        baseline=0.0,
        cues=[
            SlotCue(t=1.0, level=1.0, role="lead"),
            SlotCue(t=2.0, level=1.0, role="bed"),
            SlotCue(t=3.0, level=0.0, role=None),
            SlotCue(t=4.0, level=1.0, role="accent"),
        ],
    )
    assert lane_role_at(lane, 0.5) is None
    assert lane_role_at(lane, 1.0) == "lead"
    assert lane_role_at(lane, 1.5) == "lead"
    assert lane_role_at(lane, 2.0) == "bed"
    assert lane_role_at(lane, 3.0) is None
    assert lane_role_at(lane, 4.0) == "accent"


def test_snap_and_shift_preserve_blend_and_role_on_ons_strip_offs() -> None:
    lane = TimelineLane(
        baseline=0.0,
        cues=[
            SlotCue(t=0.4, level=1.0, blend="add", role="lead"),
            SlotCue(t=1.6, level=0.0, blend="screen", role="accent"),
        ],
    )
    snapped = snap_lane_to_beats(lane, (0.0, 1.0, 2.0))
    assert snapped.cues == [
        SlotCue(t=0.0, level=1.0, blend="add", role="lead"),
        SlotCue(t=2.0, level=0.0),
    ]
    shifted = shift_lane_cues_by_beats(lane, (0.0, 1.0, 2.0, 3.0), 1)
    assert shifted.cues == [
        SlotCue(t=1.0, level=1.0, blend="add", role="lead"),
        SlotCue(t=3.0, level=0.0),
    ]


def test_lane_on_transition_cues_returns_cue_per_trigger() -> None:
    lane = TimelineLane(
        baseline=0.0,
        cues=[
            SlotCue(t=10.0, level=1.0, role="bed"),
            SlotCue(t=20.0, level=0.0),
            SlotCue(t=30.0, level=1.0, blend="add", role="pulse"),
        ],
    )
    pairs = lane_on_transition_cues(
        lane,
        song_marker_fades=_OFF,
        standard_fades=_std(fade_in=2.0, fade_out=2.0),
    )
    assert [(t, cue.t, cue.role, cue.blend) for t, cue in pairs] == [
        (8.0, 10.0, "bed", None),
        (28.0, 30.0, "pulse", "add"),
    ]
    assert lane_on_transition_trigger_times(
        lane,
        song_marker_fades=_OFF,
        standard_fades=_std(fade_in=2.0, fade_out=2.0),
    ) == [8.0, 28.0]


def test_punch_lane_replaces_cues_in_range() -> None:
    lane = _lane(1.0, (1.0, 0.0), (5.0, 1.0), (8.0, 0.0), (12.0, 1.0))
    result = punch_lane(
        lane,
        4.0,
        10.0,
        [SlotCue(t=6.0, level=0.0)],
    )
    assert result.baseline == 1.0
    assert result.cues == [
        SlotCue(t=1.0, level=0.0),
        SlotCue(t=12.0, level=1.0),
    ]


def test_punch_lane_isolation_leaves_other_lanes_untouched() -> None:
    lanes = {
        "layer_1": _lane(1.0, (10.0, 0.0)),
        "layer_2": _lane(0.0, (10.0, 1.0)),
        "layer_3": _lane(1.0, (20.0, 0.0)),
        "layer_4": _lane(0.0),
    }
    before_unarmed = {
        slot: TimelineLane(baseline=lane.baseline, cues=list(lane.cues))
        for slot, lane in lanes.items()
        if slot != "layer_1"
    }
    lanes["layer_1"] = punch_lane(
        lanes["layer_1"],
        0.0,
        15.0,
        [SlotCue(t=0.0, level=0.0), SlotCue(t=5.0, level=1.0)],
    )
    for slot, expected in before_unarmed.items():
        assert lanes[slot].baseline == expected.baseline
        assert lanes[slot].cues == expected.cues
    assert lanes["layer_1"].cues == [
        SlotCue(t=0.0, level=0.0),
        SlotCue(t=5.0, level=1.0),
    ]


def test_punch_lane_does_not_touch_sibling_lane_at_same_t() -> None:
    layer_2 = _lane(0.0, (12.0, 1.0))
    layer_1 = punch_lane(
        _lane(0.0),
        5.0,
        12.0,
        [SlotCue(t=12.0, level=1.0)],
    )
    assert layer_2.cues == [SlotCue(t=12.0, level=1.0)]
    assert lane_level_at(layer_2, 6.0, inherit=1.0) == 0.0
    assert layer_1.cues == [SlotCue(t=12.0, level=1.0)]


def test_strip_lane_range_removes_cues_in_range() -> None:
    lane = _lane(1.0, (1.0, 0.0), (5.0, 1.0), (8.0, 0.0))
    result = strip_lane_range(lane, 4.0, 6.0)
    assert result.cues == [SlotCue(t=1.0, level=0.0)]


def test_set_lane_cue_replaces_at_t() -> None:
    lane = _lane(1.0, (5.0, 0.0))
    result = set_lane_cue(lane, 5.0, 1.0)
    assert result.cues == []


def test_should_accept_toggle_debounces() -> None:
    assert should_accept_toggle(None, 1.0) is True
    assert should_accept_toggle(1.0, 1.0 + RECORD_DEBOUNCE_SEC - 0.01) is False
    assert should_accept_toggle(1.0, 1.0 + RECORD_DEBOUNCE_SEC) is True


def test_lane_level_envelope_full_inside_segment() -> None:
    lane = _lane(0.0, (5.0, 1.0), (15.0, 0.0))
    assert _env(
        lane,
        10.0,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=60.0,
    ) == pytest.approx(1.0)


def test_lane_level_envelope_rise_completes_at_cue_time() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0))
    mid = _env(
        lane,
        9.0,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=60.0,
    )
    assert mid == pytest.approx(smoothstep(0.5))
    assert _env(
        lane,
        8.0,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=60.0,
    ) == pytest.approx(0.0)
    assert _env(
        lane,
        10.0,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=60.0,
    ) == pytest.approx(1.0)


def test_lane_level_envelope_fall_starts_at_cue_time() -> None:
    lane = _lane(0.0, (5.0, 1.0), (15.0, 0.0))
    mid = _env(
        lane,
        16.0,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=60.0,
    )
    assert mid == pytest.approx(1.0 - smoothstep(0.5))
    assert _env(
        lane,
        17.0,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=60.0,
    ) == pytest.approx(0.0)
    assert _env(
        lane,
        14.9,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=60.0,
    ) == pytest.approx(1.0)


def test_lane_level_envelope_constant_slope_partial_fall() -> None:
    """A 1.0 to 0.5 fall with 2s fade-out reaches 0.5 at t + 1.0."""
    lane = _lane(1.0, (10.0, 0.5))
    assert _env(
        lane,
        11.0,
        inherit=1.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=60.0,
    ) == pytest.approx(0.5)
    mid = _env(
        lane,
        10.5,
        inherit=1.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=60.0,
    )
    assert mid == pytest.approx(1.0 + (0.5 - 1.0) * smoothstep(0.5))


def test_lane_level_envelope_no_fade_at_song_edges_without_cue() -> None:
    lane = _lane(1.0)
    assert _env(
        lane,
        0.5,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=30.0,
    ) == pytest.approx(1.0)
    assert _env(
        lane,
        29.5,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=30.0,
    ) == pytest.approx(1.0)


def test_lane_level_envelope_zero_durations_match_stepped() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0))
    zero = _std(fade_in=0.0, fade_out=0.0)
    assert _env(
        lane,
        9.9,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=zero,
        duration_sec=60.0,
    ) == pytest.approx(0.0)
    assert _env(
        lane,
        10.0,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=zero,
        duration_sec=60.0,
    ) == pytest.approx(1.0)
    assert _env(
        lane,
        20.0,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=zero,
        duration_sec=60.0,
    ) == pytest.approx(0.0)


def test_lane_level_envelope_fades_disabled_piecewise_constant() -> None:
    lane = _lane(0.0, (10.0, 0.5), (20.0, 1.0))
    assert _env(
        lane,
        9.0,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_OFF,
        duration_sec=60.0,
    ) == pytest.approx(0.0)
    assert _env(
        lane,
        10.0,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_OFF,
        duration_sec=60.0,
    ) == pytest.approx(0.5)
    assert _env(
        lane,
        20.0,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_OFF,
        duration_sec=60.0,
    ) == pytest.approx(1.0)


def test_lane_level_envelope_song_marker_group_disabled_makes_edge_abrupt() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0))
    before = _env(
        lane,
        9.0,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=60.0,
        song_marker_times=(10.0,),
    )
    assert before == pytest.approx(0.0)


def test_lane_level_envelope_marker_edge_uses_song_marker_durations() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0))
    mid = _env(
        lane,
        9.0,
        inherit=0.0,
        song_marker_fades=_markers(fade_in=2.0, fade_out=2.0),
        standard_fades=_std(fade_in=4.0, fade_out=4.0),
        duration_sec=60.0,
        song_marker_times=(10.0,),
    )
    assert mid == pytest.approx(smoothstep(0.5))


def test_lane_level_envelope_non_marker_edge_uses_standard_durations() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0))
    mid = _env(
        lane,
        8.0,
        inherit=0.0,
        song_marker_fades=_markers(fade_in=2.0, fade_out=2.0),
        standard_fades=_std(fade_in=4.0, fade_out=4.0),
        duration_sec=60.0,
        song_marker_times=(20.0,),
    )
    assert mid == pytest.approx(smoothstep(0.5))


def test_lane_level_breakpoints_rise_and_fall() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0))
    bps = lane_level_breakpoints(
        lane,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=60.0,
    )
    assert (8.0, 0.0) in bps
    assert (10.0, 1.0) in bps
    assert (20.0, 1.0) in bps
    assert (22.0, 0.0) in bps


def test_lane_level_breakpoints_no_cues_holds_baseline() -> None:
    lane = _lane(1.0)
    bps = lane_level_breakpoints(
        lane,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=30.0,
    )
    assert bps == [(0.0, 1.0)]


def test_lane_level_breakpoints_zero_durations_hard_step() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0))
    bps = lane_level_breakpoints(
        lane,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_std(fade_in=0.0, fade_out=0.0),
        duration_sec=60.0,
    )
    assert bps == [(10.0, 0.0), (10.0, 1.0), (20.0, 1.0), (20.0, 0.0)]


def test_lane_level_breakpoints_overlapping_rise_clamped_monotone() -> None:
    """Overlapping ramps stay monotone in t (clamped rise start)."""
    lane = _lane(0.0, (5.0, 1.0), (10.0, 0.0), (11.0, 1.0))
    bps = lane_level_breakpoints(
        lane,
        inherit=0.0,
        song_marker_fades=_OFF,
        standard_fades=_STD,
        duration_sec=60.0,
    )
    times = [t for t, _ in bps]
    assert times == sorted(times)
    for prev, cur in zip(times, times[1:]):
        assert cur >= prev


def test_on_transition_triggers_at_cue_when_fades_off() -> None:
    lane = _lane(0.0, (5.0, 1.0), (10.0, 0.0), (15.0, 1.0))
    triggers = lane_on_transition_trigger_times(
        lane,
        song_marker_fades=_OFF,
        standard_fades=_OFF,
    )
    assert triggers == [5.0, 15.0]


def test_on_transition_triggers_lead_by_standard_fade_in() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), (30.0, 1.0))
    triggers = lane_on_transition_trigger_times(
        lane,
        song_marker_fades=_OFF,
        standard_fades=_std(fade_in=2.0, fade_out=3.0),
    )
    assert triggers == [8.0, 28.0]


def test_on_transition_triggers_ignores_non_zero_rise() -> None:
    """Ignores 0.25 to 0.75; fires on 0 to 0.5 at t - fade_in * 0.5."""
    lane = _lane(0.25, (10.0, 0.75), (20.0, 0.0), (30.0, 0.5))
    triggers = lane_on_transition_trigger_times(
        lane,
        song_marker_fades=_OFF,
        standard_fades=_std(fade_in=2.0, fade_out=2.0),
    )
    assert triggers == [30.0 - 2.0 * 0.5]


def test_on_transition_triggers_song_marker_vs_standard() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), (30.0, 1.0))
    triggers = lane_on_transition_trigger_times(
        lane,
        song_marker_times=(10.0,),
        song_marker_fades=_markers(fade_in=1.0, fade_out=1.0),
        standard_fades=_std(fade_in=4.0, fade_out=4.0),
    )
    assert triggers == [9.0, 26.0]


def test_on_transition_count_seek_stable() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), (30.0, 1.0))
    kwargs = dict(
        song_marker_fades=_OFF,
        standard_fades=_std(fade_in=2.0, fade_out=2.0),
    )
    assert lane_on_transition_count(lane, 7.9, **kwargs) == 0
    assert lane_on_transition_count(lane, 8.0, **kwargs) == 1
    assert lane_on_transition_count(lane, 27.9, **kwargs) == 1
    assert lane_on_transition_count(lane, 28.0, **kwargs) == 2
    assert lane_on_transition_count(lane, 28.0, **kwargs) == 2
    assert lane_on_transition_count(lane, 100.0, **kwargs) == 2


def test_on_transition_count_hard_cut_uses_cue_time() -> None:
    lane = _lane(0.0, (10.0, 1.0))
    zero = _std(fade_in=0.0, fade_out=2.0)
    assert lane_on_transition_count(
        lane,
        9.9,
        song_marker_fades=_OFF,
        standard_fades=zero,
    ) == 0
    assert lane_on_transition_count(
        lane,
        10.0,
        song_marker_fades=_OFF,
        standard_fades=zero,
    ) == 1


def test_boolean_parity_zero_one_lane_levels() -> None:
    """0/1 lanes produce the same stepped levels as the former boolean path."""
    lane = _lane(1.0, (5.0, 0.0), (10.0, 1.0))
    assert lane_level_at(lane, 0.0, inherit=1.0) == 1.0
    assert lane_level_at(lane, 5.0, inherit=1.0) == 0.0
    assert lane_level_at(lane, 10.0, inherit=1.0) == 1.0
    assert lane_level_at(lane, 5.0, inherit=1.0) <= LEVEL_EPS
    assert lane_level_at(lane, 10.0, inherit=1.0) > LEVEL_EPS
