"""Tests for per-lane timeline evaluation and editing."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cleave.config_schema.layers import DEFAULT_LAYER_SLOTS
from cleave.easing import smoothstep
from cleave.timeline import (
    LEVEL_EPS,
    MIN_CLIP_SEC,
    RECORD_DEBOUNCE_SEC,
    SlotCue,
    TimelineClip,
    TimelineFadeGroup,
    TimelineLane,
    add_clip,
    canonicalize,
    clip_at,
    clip_move_bounds,
    clip_starting_at,
    clip_trim_bounds,
    empty_lane,
    fold_lane_baseline,
    lane_clips,
    move_clip,
    remove_clip,
    split_clip,
    trim_clip,
    update_clip,
    lane_blend_at,
    lane_role_at,
    lane_last_on_level,
    lane_level_at,
    lane_level_breakpoints,
    lane_level_envelope,
    lane_on_transition_count,
    lane_on_transition_cues,
    lane_on_transition_trigger_times,
    punch_lane,
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


def _crossfade(
    *, fade_in: float = 2.0, fade_out: float = 2.0
) -> TimelineFadeGroup:
    return TimelineFadeGroup(
        enabled=True,
        fade_in=fade_in,
        fade_out=fade_out,
        crossfade=True,
    )


def _as_level(value: float | bool | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return float(value)


def _lane(
    baseline: float | bool | None,
    *transitions: tuple[float, float | bool],
    cut: str | None = None,
) -> TimelineLane:
    base = _as_level(baseline)
    cues = [
        SlotCue(t=t, level=float(_as_level(level)), cut=cut)  # type: ignore[arg-type]
        for t, level in transitions
    ]
    return TimelineLane(baseline=base, cues=canonicalize(base, cues))


def _env(
    lane: TimelineLane,
    t_sec: float,
    *,
    inherit: float | bool,
    hard_cut_fades: TimelineFadeGroup,
    soft_cut_fades: TimelineFadeGroup,
    duration_sec: float,
) -> float:
    breakpoints = lane_level_breakpoints(
        lane,
        inherit=float(_as_level(inherit) or 0.0),
        hard_cut_fades=hard_cut_fades,
        soft_cut_fades=soft_cut_fades,
        duration_sec=duration_sec,
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


def test_canonicalize_keeps_anchored_same_level_cue() -> None:
    cues = canonicalize(
        1.0,
        [
            SlotCue(t=5.0, level=1.0),
            SlotCue(t=10.0, level=1.0, anchor=True),
            SlotCue(t=15.0, level=0.75),
        ],
    )
    assert cues == [
        SlotCue(t=10.0, level=1.0, anchor=True),
        SlotCue(t=15.0, level=0.75),
    ]


def test_canonicalize_keeps_recast_same_level_cue() -> None:
    cues = canonicalize(
        1.0,
        [
            SlotCue(t=5.0, level=1.0),
            SlotCue(t=10.0, level=1.0, recast=True),
            SlotCue(t=15.0, level=0.75),
        ],
    )
    assert cues == [
        SlotCue(t=10.0, level=1.0, recast=True),
        SlotCue(t=15.0, level=0.75),
    ]


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
            SlotCue(t=2.0, level=0.0, blend="screen", role="accent", cut="hard"),
            SlotCue(t=3.0, level=0.5, blend="add", role="pulse"),
        ],
    )
    assert cues == [
        SlotCue(t=1.0, level=1.0, blend="add", role="lead"),
        SlotCue(t=2.0, level=0.0, cut="hard"),
        SlotCue(t=3.0, level=0.5, blend="add", role="pulse"),
    ]


def test_canonicalize_off_with_dead_metadata_still_level_only() -> None:
    """Stripping off metadata must not invent blend-only keep/drop bugs."""
    cues = canonicalize(
        1.0,
        [SlotCue(t=1.0, level=0.0, blend="add", role="pulse")],
    )
    assert cues == [SlotCue(t=1.0, level=0.0)]


def test_canonicalize_preserves_cut_on_off_cues() -> None:
    cues = canonicalize(
        1.0,
        [SlotCue(t=1.0, level=0.0, blend="add", role="pulse", cut="soft")],
    )
    assert cues == [SlotCue(t=1.0, level=0.0, cut="soft")]


def test_cue_editable_and_opening_baseline() -> None:
    from cleave.timeline import (
        cue_editable_for_blend_role,
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
    assert not opening_baseline_editable(lane)
    assert opening_cue(lane) is None

    opening_on = TimelineLane(baseline=0.5, cues=[SlotCue(t=10.0, level=0.0)])
    assert opening_baseline_editable(opening_on)
    assert opening_cue(opening_on) == SlotCue(t=0.0, level=0.5)

    already_at_zero = TimelineLane(
        baseline=0.0,
        cues=[SlotCue(t=0.0, level=0.5), SlotCue(t=10.0, level=0.0)],
    )
    assert not opening_baseline_editable(already_at_zero)


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
            SlotCue(t=10.0, level=1.0, role="bed", cut="soft"),
            SlotCue(t=20.0, level=0.0, cut="soft"),
            SlotCue(t=30.0, level=1.0, blend="add", role="pulse", cut="soft"),
        ],
    )
    pairs = lane_on_transition_cues(
        lane,
        hard_cut_fades=_OFF,
        soft_cut_fades=_std(fade_in=2.0, fade_out=2.0),
    )
    assert [(t, cue.t, cue.role, cue.blend) for t, cue in pairs] == [
        (8.0, 10.0, "bed", None),
        (28.0, 30.0, "pulse", "add"),
    ]
    assert lane_on_transition_trigger_times(
        lane,
        hard_cut_fades=_OFF,
        soft_cut_fades=_std(fade_in=2.0, fade_out=2.0),
    ) == [8.0, 28.0]


def test_lane_on_transition_cues_counts_recast_while_on_not_anchor() -> None:
    lane = TimelineLane(
        baseline=1.0,
        cues=[
            SlotCue(t=10.0, level=1.0, recast=True),
            SlotCue(t=20.0, level=1.0, anchor=True),
            SlotCue(t=30.0, level=0.0),
            SlotCue(t=40.0, level=1.0),
        ],
    )
    pairs = lane_on_transition_cues(
        lane,
        hard_cut_fades=_OFF,
        soft_cut_fades=_OFF,
    )
    assert [(t, cue.t, cue.recast, cue.anchor) for t, cue in pairs] == [
        (0.0, 0.0, False, False),
        (10.0, 10.0, True, False),
        (40.0, 40.0, False, False),
    ]


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


def test_should_accept_toggle_debounces() -> None:
    assert should_accept_toggle(None, 1.0) is True
    assert should_accept_toggle(1.0, 1.0 + RECORD_DEBOUNCE_SEC - 0.01) is False
    assert should_accept_toggle(1.0, 1.0 + RECORD_DEBOUNCE_SEC) is True


def test_lane_level_envelope_full_inside_segment() -> None:
    lane = _lane(0.0, (5.0, 1.0), (15.0, 0.0), cut="soft")
    assert _env(
        lane,
        10.0,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=60.0,
    ) == pytest.approx(1.0)


def test_lane_level_envelope_rise_completes_at_cue_time() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), cut="soft")
    mid = _env(
        lane,
        9.0,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=60.0,
    )
    assert mid == pytest.approx(smoothstep(0.5))
    assert _env(
        lane,
        8.0,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=60.0,
    ) == pytest.approx(0.0)
    assert _env(
        lane,
        10.0,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=60.0,
    ) == pytest.approx(1.0)


def test_lane_level_envelope_fall_starts_at_cue_time() -> None:
    lane = _lane(0.0, (5.0, 1.0), (15.0, 0.0), cut="soft")
    mid = _env(
        lane,
        16.0,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=60.0,
    )
    assert mid == pytest.approx(1.0 - smoothstep(0.5))
    assert _env(
        lane,
        17.0,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=60.0,
    ) == pytest.approx(0.0)
    assert _env(
        lane,
        14.9,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=60.0,
    ) == pytest.approx(1.0)


def test_lane_level_envelope_constant_slope_partial_fall() -> None:
    """A 1.0 to 0.5 fall with 2s fade-out reaches 0.5 at t + 1.0."""
    lane = _lane(0.0, (0.0, 1.0), (10.0, 0.5), cut="soft")
    assert _env(
        lane,
        11.0,
        inherit=1.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=60.0,
    ) == pytest.approx(0.5)
    mid = _env(
        lane,
        10.5,
        inherit=1.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=60.0,
    )
    assert mid == pytest.approx(1.0 + (0.5 - 1.0) * smoothstep(0.5))


def test_lane_level_envelope_no_fade_at_song_edges_without_cue() -> None:
    lane = _lane(1.0)
    assert _env(
        lane,
        0.5,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=30.0,
    ) == pytest.approx(1.0)
    assert _env(
        lane,
        29.5,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=30.0,
    ) == pytest.approx(1.0)


def test_lane_level_envelope_zero_durations_match_stepped() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), cut="soft")
    zero = _std(fade_in=0.0, fade_out=0.0)
    assert _env(
        lane,
        9.9,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=zero,
        duration_sec=60.0,
    ) == pytest.approx(0.0)
    assert _env(
        lane,
        10.0,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=zero,
        duration_sec=60.0,
    ) == pytest.approx(1.0)
    assert _env(
        lane,
        20.0,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=zero,
        duration_sec=60.0,
    ) == pytest.approx(0.0)


def test_lane_level_envelope_fades_disabled_piecewise_constant() -> None:
    lane = _lane(0.0, (10.0, 0.5), (20.0, 1.0), cut="soft")
    assert _env(
        lane,
        9.0,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_OFF,
        duration_sec=60.0,
    ) == pytest.approx(0.0)
    assert _env(
        lane,
        10.0,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_OFF,
        duration_sec=60.0,
    ) == pytest.approx(0.5)
    assert _env(
        lane,
        20.0,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_OFF,
        duration_sec=60.0,
    ) == pytest.approx(1.0)


def test_lane_level_envelope_hard_cut_group_disabled_makes_edge_abrupt() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), cut="hard")
    before = _env(
        lane,
        9.0,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=60.0,
    )
    assert before == pytest.approx(0.0)


def test_lane_level_envelope_hard_cut_uses_hard_durations() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), cut="hard")
    mid = _env(
        lane,
        9.0,
        inherit=0.0,
        hard_cut_fades=_markers(fade_in=2.0, fade_out=2.0),
        soft_cut_fades=_std(fade_in=4.0, fade_out=4.0),
        duration_sec=60.0,
    )
    assert mid == pytest.approx(smoothstep(0.5))


def test_lane_level_envelope_soft_cut_uses_soft_durations() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), cut="soft")
    mid = _env(
        lane,
        8.0,
        inherit=0.0,
        hard_cut_fades=_markers(fade_in=2.0, fade_out=2.0),
        soft_cut_fades=_std(fade_in=4.0, fade_out=4.0),
        duration_sec=60.0,
    )
    assert mid == pytest.approx(smoothstep(0.5))


def test_lane_level_envelope_unset_cut_is_hard_step() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), cut=None)
    mid = _env(
        lane,
        9.0,
        inherit=0.0,
        hard_cut_fades=_markers(fade_in=2.0, fade_out=2.0),
        soft_cut_fades=_STD,
        duration_sec=60.0,
    )
    assert mid == pytest.approx(0.0)


def test_lane_level_envelope_fall_uses_off_cue_cut() -> None:
    """Fall edge uses the off-cue cut, not the preceding on-cue cut."""
    lane = TimelineLane(
        baseline=0.0,
        cues=canonicalize(
            0.0,
            [
                SlotCue(t=10.0, level=1.0, cut="hard"),
                SlotCue(t=20.0, level=0.0, cut="soft"),
            ],
        ),
    )
    # Soft fade_out=4s from t=20; hard would be 2s. Mid of soft ramp at t=22.
    mid = _env(
        lane,
        22.0,
        inherit=0.0,
        hard_cut_fades=_markers(fade_in=2.0, fade_out=2.0),
        soft_cut_fades=_std(fade_in=4.0, fade_out=4.0),
        duration_sec=60.0,
    )
    assert mid == pytest.approx(1.0 - smoothstep(0.5))


def test_lane_level_envelope_fall_hard_off_cue_cut() -> None:
    """Off-cue hard cut selects the hard fade-out ramp."""
    lane = TimelineLane(
        baseline=0.0,
        cues=canonicalize(
            0.0,
            [
                SlotCue(t=10.0, level=1.0, cut="soft"),
                SlotCue(t=20.0, level=0.0, cut="hard"),
            ],
        ),
    )
    mid = _env(
        lane,
        21.0,
        inherit=0.0,
        hard_cut_fades=_markers(fade_in=2.0, fade_out=2.0),
        soft_cut_fades=_std(fade_in=4.0, fade_out=4.0),
        duration_sec=60.0,
    )
    assert mid == pytest.approx(1.0 - smoothstep(0.5))


def test_lane_level_breakpoints_rise_and_fall() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), cut="soft")
    bps = lane_level_breakpoints(
        lane,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=60.0,
    )
    assert (8.0, 0.0) in bps
    assert (10.0, 1.0) in bps
    assert (20.0, 1.0) in bps
    assert (22.0, 0.0) in bps


def test_lane_level_breakpoints_crossfade_rise_centering() -> None:
    lane = _lane(0.0, (10.0, 1.0), cut="soft")
    bps = lane_level_breakpoints(
        lane,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_crossfade(fade_in=2.0, fade_out=2.0),
        duration_sec=60.0,
    )
    assert (9.0, 0.0) in bps
    assert (11.0, 1.0) in bps
    assert (10.0, 1.0) not in bps


def test_lane_level_breakpoints_crossfade_fall_centering() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), cut="soft")
    bps = lane_level_breakpoints(
        lane,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_crossfade(fade_in=2.0, fade_out=2.0),
        duration_sec=60.0,
    )
    assert (19.0, 1.0) in bps
    assert (21.0, 0.0) in bps
    assert (20.0, 1.0) not in bps
    assert (20.0, 0.0) not in bps


def test_lane_level_breakpoints_crossfade_overlapping_rise_clamped_monotone() -> None:
    lane = _lane(0.0, (5.0, 1.0), (10.0, 0.0), (11.0, 1.0), cut="soft")
    bps = lane_level_breakpoints(
        lane,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_crossfade(fade_in=2.0, fade_out=2.0),
        duration_sec=60.0,
    )
    times = [t for t, _ in bps]
    assert times == sorted(times)
    for prev, cur in zip(times, times[1:]):
        assert cur >= prev


def test_lane_level_breakpoints_no_cues_holds_baseline() -> None:
    lane = _lane(1.0)
    bps = lane_level_breakpoints(
        lane,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
        duration_sec=30.0,
    )
    assert bps == [(0.0, 1.0)]


def test_lane_level_breakpoints_zero_durations_hard_step() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), cut="soft")
    bps = lane_level_breakpoints(
        lane,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_std(fade_in=0.0, fade_out=0.0),
        duration_sec=60.0,
    )
    assert bps == [(10.0, 0.0), (10.0, 1.0), (20.0, 1.0), (20.0, 0.0)]


def test_lane_level_breakpoints_overlapping_rise_clamped_monotone() -> None:
    """Overlapping ramps stay monotone in t (clamped rise start)."""
    lane = _lane(0.0, (5.0, 1.0), (10.0, 0.0), (11.0, 1.0), cut="soft")
    bps = lane_level_breakpoints(
        lane,
        inherit=0.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=_STD,
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
        hard_cut_fades=_OFF,
        soft_cut_fades=_OFF,
    )
    assert triggers == [5.0, 15.0]


def test_on_transition_triggers_lead_by_standard_fade_in() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), (30.0, 1.0), cut="soft")
    triggers = lane_on_transition_trigger_times(
        lane,
        hard_cut_fades=_OFF,
        soft_cut_fades=_std(fade_in=2.0, fade_out=3.0),
    )
    assert triggers == [8.0, 28.0]


def test_on_transition_triggers_crossfade_lead_by_half_ramp() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), (30.0, 1.0), cut="soft")
    triggers = lane_on_transition_trigger_times(
        lane,
        hard_cut_fades=_OFF,
        soft_cut_fades=_crossfade(fade_in=2.0, fade_out=3.0),
    )
    assert triggers == [9.0, 29.0]


def test_on_transition_triggers_ignores_non_zero_rise() -> None:
    """Fires on the opening clip, ignores 0.25 to 0.75, and fires on 0 to 0.5 at t - fade_in * 0.5."""
    lane = _lane(0.25, (10.0, 0.75), (20.0, 0.0), (30.0, 0.5), cut="soft")
    triggers = lane_on_transition_trigger_times(
        lane,
        hard_cut_fades=_OFF,
        soft_cut_fades=_std(fade_in=2.0, fade_out=2.0),
    )
    assert triggers == [0.0, 30.0 - 2.0 * 0.5]


def test_a_lane_that_opens_on_switches_at_the_song_start() -> None:
    kwargs = {"hard_cut_fades": _OFF, "soft_cut_fades": _OFF}
    whole_song = TimelineLane(baseline=1.0, cues=[])
    assert lane_on_transition_trigger_times(whole_song, **kwargs) == [0.0]
    assert lane_on_transition_count(whole_song, 0.0, **kwargs) == 1
    reenters = TimelineLane(
        baseline=1.0, cues=[SlotCue(t=5.0, level=0.0), SlotCue(t=9.0, level=1.0)]
    )
    assert lane_on_transition_trigger_times(reenters, **kwargs) == [0.0, 9.0]
    cue_at_zero = TimelineLane(baseline=1.0, cues=[SlotCue(t=0.0, level=0.0)])
    assert lane_on_transition_trigger_times(cue_at_zero, **kwargs) == []
    assert lane_on_transition_trigger_times(empty_lane(), **kwargs) == []


def test_on_transition_triggers_hard_cut_vs_soft_cut() -> None:
    lane = TimelineLane(
        baseline=0.0,
        cues=canonicalize(
            0.0,
            [
                SlotCue(t=10.0, level=1.0, cut="hard"),
                SlotCue(t=20.0, level=0.0, cut="soft"),
                SlotCue(t=30.0, level=1.0, cut="soft"),
            ],
        ),
    )
    triggers = lane_on_transition_trigger_times(
        lane,
        hard_cut_fades=_markers(fade_in=1.0, fade_out=1.0),
        soft_cut_fades=_std(fade_in=4.0, fade_out=4.0),
    )
    assert triggers == [9.0, 26.0]


def test_on_transition_count_seek_stable() -> None:
    lane = _lane(0.0, (10.0, 1.0), (20.0, 0.0), (30.0, 1.0), cut="soft")
    kwargs = dict(
        hard_cut_fades=_OFF,
        soft_cut_fades=_std(fade_in=2.0, fade_out=2.0),
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
        hard_cut_fades=_OFF,
        soft_cut_fades=zero,
    ) == 0
    assert lane_on_transition_count(
        lane,
        10.0,
        hard_cut_fades=_OFF,
        soft_cut_fades=zero,
    ) == 1


def test_boolean_parity_zero_one_lane_levels() -> None:
    """0/1 lanes produce the same stepped levels as the former boolean path."""
    lane = _lane(1.0, (5.0, 0.0), (10.0, 1.0))
    assert lane_level_at(lane, 0.0, inherit=1.0) == 1.0
    assert lane_level_at(lane, 5.0, inherit=1.0) == 0.0
    assert lane_level_at(lane, 10.0, inherit=1.0) == 1.0
    assert lane_level_at(lane, 5.0, inherit=1.0) <= LEVEL_EPS
    assert lane_level_at(lane, 10.0, inherit=1.0) > LEVEL_EPS


def test_lane_last_on_level_reads_the_latest_on_cue_before() -> None:
    lane = TimelineLane(
        baseline=0.0,
        cues=[
            SlotCue(t=2.0, level=0.6),
            SlotCue(t=4.0, level=0.0),
            SlotCue(t=8.0, level=0.3),
        ],
    )
    assert lane_last_on_level(lane, 5.0) == 0.6
    assert lane_last_on_level(lane, 9.0) == 0.3


def test_lane_last_on_level_falls_back_to_baseline_then_later_then_full() -> None:
    assert lane_last_on_level(
        TimelineLane(baseline=0.4, cues=[SlotCue(t=2.0, level=0.0)]), 3.0
    ) == 0.4
    assert lane_last_on_level(
        TimelineLane(baseline=0.0, cues=[SlotCue(t=6.0, level=0.7)]), 3.0
    ) == 0.7
    assert lane_last_on_level(empty_lane(), 3.0) == 1.0


# Clips: an on cue up to the next cue or the song end.

_DUR = 100.0


def _clips(lane: TimelineLane, *, inherit: float = 0.0) -> list[TimelineClip]:
    return lane_clips(lane, inherit=inherit, duration_sec=_DUR)


def _spans(lane: TimelineLane, *, inherit: float = 0.0) -> list[tuple[float, float]]:
    return [(clip.start, clip.end) for clip in _clips(lane, inherit=inherit)]


def _clip_lane(*cues: SlotCue, baseline: float | None = 0.0) -> TimelineLane:
    return TimelineLane(baseline=baseline, cues=list(cues))


def test_lane_clips_pairs_on_and_off_cues() -> None:
    lane = _clip_lane(
        SlotCue(t=10.0, level=0.6, blend="add", role="lead", cut="hard"),
        SlotCue(t=20.0, level=0.0, cut="soft"),
    )
    assert _clips(lane) == [
        TimelineClip(
            start=10.0,
            end=20.0,
            level=0.6,
            blend="add",
            role="lead",
            cut_in="hard",
            cut_out="soft",
            has_end_cue=True,
        )
    ]


def test_lane_clips_opening_baseline_is_a_clip_from_zero() -> None:
    lane = _clip_lane(SlotCue(t=8.0, level=0.0), baseline=0.5)
    clips = _clips(lane)
    assert [(c.start, c.end, c.level) for c in clips] == [(0.0, 8.0, 0.5)]


def test_lane_clips_inherit_stands_in_for_a_missing_baseline() -> None:
    lane = _clip_lane(SlotCue(t=8.0, level=0.0), baseline=None)
    assert _spans(lane, inherit=1.0) == [(0.0, 8.0)]
    assert _spans(_clip_lane(baseline=None), inherit=1.0) == [(0.0, _DUR)]
    assert _spans(_clip_lane(baseline=None), inherit=0.0) == []


def test_lane_clips_last_clip_runs_to_the_song_end() -> None:
    clip = _clips(_clip_lane(SlotCue(t=90.0, level=1.0)))[0]
    assert (clip.end, clip.butts_next, clip.has_end_cue) == (_DUR, False, False)


def test_lane_clips_butted_clips_and_recast() -> None:
    lane = _clip_lane(
        SlotCue(t=10.0, level=1.0),
        SlotCue(t=20.0, level=0.5),
        SlotCue(t=30.0, level=0.5, recast=True),
        SlotCue(t=40.0, level=0.5, anchor=True),
        SlotCue(t=50.0, level=0.0),
    )
    clips = _clips(lane)
    assert [(c.start, c.end) for c in clips] == [
        (10.0, 20.0),
        (20.0, 30.0),
        (30.0, 40.0),
        (40.0, 50.0),
    ]
    assert [c.butts_next for c in clips] == [True, True, True, False]
    assert [c.recast for c in clips] == [False, False, True, False]
    assert [c.anchor for c in clips] == [False, False, False, True]
    assert clips[0].cut_out is None and not clips[0].has_end_cue


def test_lane_clips_ignores_cues_past_the_song_end() -> None:
    lane = _clip_lane(SlotCue(t=90.0, level=1.0), SlotCue(t=120.0, level=0.0))
    assert _spans(lane) == [(90.0, _DUR)]


def test_clip_at_is_start_inclusive_end_exclusive() -> None:
    clips = _clips(_clip_lane(SlotCue(t=10.0, level=1.0), SlotCue(t=20.0, level=0.0)))
    assert clip_at(clips, 10.0) is clips[0]
    assert clip_at(clips, 19.9) is clips[0]
    assert clip_at(clips, 20.0) is None
    assert clip_starting_at(clips, 10.0) is clips[0]
    assert clip_starting_at(clips, 11.0) is None


def test_add_clip_writes_on_and_off_cues() -> None:
    added = add_clip(_clip_lane(), 10.0, 20.0, 0.6, inherit=0.0, duration_sec=_DUR)
    assert added.cues == [SlotCue(t=10.0, level=0.6), SlotCue(t=20.0, level=0.0)]


def test_add_clip_running_into_the_next_clip_butts_it() -> None:
    lane = _clip_lane(SlotCue(t=20.0, level=0.5), SlotCue(t=30.0, level=0.0))
    added = add_clip(lane, 10.0, 20.0, 1.0, inherit=0.0, duration_sec=_DUR)
    assert _spans(added) == [(10.0, 20.0), (20.0, 30.0)]
    assert _clips(added)[0].butts_next


def test_add_clip_keeps_a_matching_neighbour_apart() -> None:
    lane = _clip_lane(SlotCue(t=20.0, level=1.0), SlotCue(t=30.0, level=0.0))
    added = add_clip(lane, 10.0, 20.0, 1.0, inherit=0.0, duration_sec=_DUR)
    assert _spans(added) == [(10.0, 20.0), (20.0, 30.0)]
    assert _clips(added)[1].anchor


def test_add_clip_to_the_song_end_writes_no_off_cue() -> None:
    added = add_clip(_clip_lane(), 90.0, _DUR, 1.0, inherit=0.0, duration_sec=_DUR)
    assert added.cues == [SlotCue(t=90.0, level=1.0)]


def test_add_clip_folds_an_inherited_opening() -> None:
    lane = _clip_lane(SlotCue(t=5.0, level=0.0), baseline=None)
    added = add_clip(lane, 10.0, 20.0, 1.0, inherit=1.0, duration_sec=_DUR)
    assert _spans(added, inherit=0.0) == [(0.0, 5.0), (10.0, 20.0)]


def test_remove_clip_drops_both_cues_in_a_gap() -> None:
    lane = _clip_lane(SlotCue(t=10.0, level=1.0), SlotCue(t=20.0, level=0.0))
    removed = remove_clip(lane, _clips(lane)[0], inherit=0.0, duration_sec=_DUR)
    assert removed.cues == []


def test_remove_clip_after_a_butted_clip_leaves_an_off_cue() -> None:
    lane = _clip_lane(
        SlotCue(t=10.0, level=1.0),
        SlotCue(t=20.0, level=0.5),
        SlotCue(t=30.0, level=0.0),
    )
    removed = remove_clip(lane, _clips(lane)[1], inherit=0.0, duration_sec=_DUR)
    assert removed.cues == [SlotCue(t=10.0, level=1.0), SlotCue(t=20.0, level=0.0)]


def test_remove_clip_keeps_a_butted_next_clip() -> None:
    lane = _clip_lane(
        SlotCue(t=10.0, level=1.0),
        SlotCue(t=20.0, level=0.5, role="lead"),
        SlotCue(t=30.0, level=0.0),
    )
    removed = remove_clip(lane, _clips(lane)[0], inherit=0.0, duration_sec=_DUR)
    assert removed.cues == [
        SlotCue(t=20.0, level=0.5, role="lead"),
        SlotCue(t=30.0, level=0.0),
    ]


def test_remove_clip_turns_an_opening_baseline_off() -> None:
    lane = _clip_lane(SlotCue(t=8.0, level=0.0), baseline=1.0)
    removed = remove_clip(lane, _clips(lane)[0], inherit=0.0, duration_sec=_DUR)
    assert _spans(removed) == []
    assert removed.baseline == 0.0


def test_move_clip_keeps_length_and_properties() -> None:
    lane = _clip_lane(
        SlotCue(t=10.0, level=0.6, blend="add", role="lead", cut="hard"),
        SlotCue(t=20.0, level=0.0, cut="soft"),
    )
    moved = move_clip(lane, _clips(lane)[0], 40.0, inherit=0.0, duration_sec=_DUR)
    assert moved.cues == [
        SlotCue(t=40.0, level=0.6, blend="add", role="lead", cut="hard"),
        SlotCue(t=50.0, level=0.0, cut="soft"),
    ]


def test_move_clip_stops_at_its_neighbours() -> None:
    lane = _clip_lane(
        SlotCue(t=10.0, level=1.0),
        SlotCue(t=20.0, level=0.0),
        SlotCue(t=30.0, level=0.5),
        SlotCue(t=40.0, level=0.0),
        SlotCue(t=60.0, level=1.0),
        SlotCue(t=70.0, level=0.0),
    )
    middle = _clips(lane)[1]
    assert clip_move_bounds(_clips(lane), middle, _DUR) == (20.0, 50.0)
    left = move_clip(lane, middle, 0.0, inherit=0.0, duration_sec=_DUR)
    assert _spans(left) == [(10.0, 20.0), (20.0, 30.0), (60.0, 70.0)]
    right = move_clip(lane, middle, 99.0, inherit=0.0, duration_sec=_DUR)
    assert _spans(right) == [(10.0, 20.0), (50.0, 60.0), (60.0, 70.0)]
    assert [c.level for c in _clips(right)] == [1.0, 0.5, 1.0]


def test_move_clip_away_from_a_butted_neighbour_opens_a_gap() -> None:
    lane = _clip_lane(
        SlotCue(t=10.0, level=1.0),
        SlotCue(t=20.0, level=0.5),
        SlotCue(t=30.0, level=0.0),
    )
    moved = move_clip(lane, _clips(lane)[1], 50.0, inherit=0.0, duration_sec=_DUR)
    assert _spans(moved) == [(10.0, 20.0), (50.0, 60.0)]


def test_move_clip_to_and_from_the_song_end() -> None:
    lane = _clip_lane(SlotCue(t=90.0, level=1.0))
    moved = move_clip(lane, _clips(lane)[0], 50.0, inherit=0.0, duration_sec=_DUR)
    assert moved.cues == [SlotCue(t=50.0, level=1.0), SlotCue(t=60.0, level=0.0)]
    back = move_clip(moved, _clips(moved)[0], 95.0, inherit=0.0, duration_sec=_DUR)
    assert back.cues == [SlotCue(t=90.0, level=1.0)]


def test_trim_clip_moves_a_free_edge() -> None:
    lane = _clip_lane(SlotCue(t=10.0, level=1.0, cut="hard"), SlotCue(t=20.0, level=0.0, cut="soft"))
    clip = _clips(lane)[0]
    start = trim_clip(lane, clip, "start", 12.0, inherit=0.0, duration_sec=_DUR)
    assert start.cues == [
        SlotCue(t=12.0, level=1.0, cut="hard"),
        SlotCue(t=20.0, level=0.0, cut="soft"),
    ]
    end = trim_clip(lane, clip, "end", 25.0, inherit=0.0, duration_sec=_DUR)
    assert end.cues == [
        SlotCue(t=10.0, level=1.0, cut="hard"),
        SlotCue(t=25.0, level=0.0, cut="soft"),
    ]


def test_trim_clip_keeps_a_minimum_length() -> None:
    lane = _clip_lane(SlotCue(t=10.0, level=1.0), SlotCue(t=20.0, level=0.0))
    clip = _clips(lane)[0]
    trimmed = trim_clip(lane, clip, "end", 0.0, inherit=0.0, duration_sec=_DUR)
    assert _spans(trimmed) == [(10.0, 10.0 + MIN_CLIP_SEC)]
    trimmed = trim_clip(lane, clip, "start", 99.0, inherit=0.0, duration_sec=_DUR)
    assert _spans(trimmed) == [(20.0 - MIN_CLIP_SEC, 20.0)]


def test_trim_clip_rolls_a_butted_edge() -> None:
    lane = _clip_lane(
        SlotCue(t=10.0, level=1.0),
        SlotCue(t=20.0, level=0.5, role="lead"),
        SlotCue(t=30.0, level=0.0),
    )
    first, second = _clips(lane)
    rolled = trim_clip(lane, first, "end", 24.0, inherit=0.0, duration_sec=_DUR)
    assert _spans(rolled) == [(10.0, 24.0), (24.0, 30.0)]
    assert _clips(rolled)[1].role == "lead"
    rolled = trim_clip(lane, second, "start", 15.0, inherit=0.0, duration_sec=_DUR)
    assert _spans(rolled) == [(10.0, 15.0), (15.0, 30.0)]
    assert clip_trim_bounds(_clips(lane), first, "end", 1.0, _DUR) == (11.0, 29.0)
    assert clip_trim_bounds(_clips(lane), second, "start", 1.0, _DUR) == (11.0, 29.0)


def test_trim_clip_without_roll_opens_a_gap_at_a_butted_edge() -> None:
    lane = _clip_lane(
        SlotCue(t=10.0, level=1.0),
        SlotCue(t=20.0, level=0.5, role="lead", cut="soft"),
        SlotCue(t=30.0, level=0.0),
    )
    first, second = _clips(lane)
    end = trim_clip(
        lane, first, "end", 16.0, inherit=0.0, duration_sec=_DUR, roll=False
    )
    assert _spans(end) == [(10.0, 16.0), (20.0, 30.0)]
    assert _clips(end)[1].role == "lead"
    assert _clips(end)[1].cut_in == "soft"
    start = trim_clip(
        lane, second, "start", 24.0, inherit=0.0, duration_sec=_DUR, roll=False
    )
    assert _spans(start) == [(10.0, 20.0), (24.0, 30.0)]
    assert _clips(start)[1].role == "lead"
    # Without a roll the edge only moves into its own clip.
    assert clip_trim_bounds(_clips(lane), first, "end", 1.0, _DUR, roll=False) == (
        11.0,
        20.0,
    )
    assert clip_trim_bounds(
        _clips(lane), second, "start", 1.0, _DUR, roll=False
    ) == (20.0, 29.0)
    outward = trim_clip(
        lane, first, "end", 25.0, inherit=0.0, duration_sec=_DUR, roll=False
    )
    assert outward == lane
    outward = trim_clip(
        lane, second, "start", 15.0, inherit=0.0, duration_sec=_DUR, roll=False
    )
    assert outward == lane


def test_trim_clip_end_onto_the_next_clip_butts_it() -> None:
    lane = _clip_lane(
        SlotCue(t=10.0, level=1.0),
        SlotCue(t=20.0, level=0.0),
        SlotCue(t=30.0, level=1.0),
        SlotCue(t=40.0, level=0.0),
    )
    trimmed = trim_clip(
        lane, _clips(lane)[0], "end", 35.0, inherit=0.0, duration_sec=_DUR
    )
    assert _spans(trimmed) == [(10.0, 30.0), (30.0, 40.0)]
    assert _clips(trimmed)[0].butts_next


def test_trim_clip_start_onto_the_previous_clip_butts_it() -> None:
    lane = _clip_lane(
        SlotCue(t=10.0, level=1.0),
        SlotCue(t=20.0, level=0.0),
        SlotCue(t=30.0, level=0.5),
        SlotCue(t=40.0, level=0.0),
    )
    trimmed = trim_clip(
        lane, _clips(lane)[1], "start", 5.0, inherit=0.0, duration_sec=_DUR
    )
    assert _spans(trimmed) == [(10.0, 20.0), (20.0, 40.0)]


def test_trim_clip_end_at_the_song_end() -> None:
    lane = _clip_lane(SlotCue(t=80.0, level=1.0))
    inward = trim_clip(lane, _clips(lane)[0], "end", 90.0, inherit=0.0, duration_sec=_DUR)
    assert inward.cues == [SlotCue(t=80.0, level=1.0), SlotCue(t=90.0, level=0.0)]
    outward = trim_clip(
        inward, _clips(inward)[0], "end", 500.0, inherit=0.0, duration_sec=_DUR
    )
    assert outward.cues == [SlotCue(t=80.0, level=1.0)]


def test_trim_clip_start_of_an_opening_baseline() -> None:
    lane = _clip_lane(SlotCue(t=8.0, level=0.0), baseline=1.0)
    trimmed = trim_clip(lane, _clips(lane)[0], "start", 3.0, inherit=0.0, duration_sec=_DUR)
    assert _spans(trimmed) == [(3.0, 8.0)]


def test_split_clip_adds_an_anchor_with_the_same_look() -> None:
    lane = _clip_lane(
        SlotCue(t=10.0, level=0.6, blend="add", role="lead", cut="hard"),
        SlotCue(t=20.0, level=0.0, cut="soft"),
    )
    split = split_clip(lane, _clips(lane)[0], 14.0, inherit=0.0, duration_sec=_DUR)
    first, second = _clips(split)
    assert (first.start, first.end, second.start, second.end) == (10.0, 14.0, 14.0, 20.0)
    assert (second.level, second.blend, second.role) == (0.6, "add", "lead")
    assert second.anchor and not second.recast and second.cut_in is None
    assert second.cut_out == "soft" and first.cut_in == "hard"
    assert lane_on_transition_trigger_times(
        split, hard_cut_fades=_OFF, soft_cut_fades=_OFF
    ) == [10.0]


def test_split_clip_needs_room_on_both_sides() -> None:
    lane = _clip_lane(SlotCue(t=10.0, level=1.0), SlotCue(t=20.0, level=0.0))
    clip = _clips(lane)[0]
    for t in (10.0, 10.05, 19.99, 20.0, 50.0):
        assert split_clip(lane, clip, t, inherit=0.0, duration_sec=_DUR) == lane


def test_update_clip_writes_start_cue_and_cut_out() -> None:
    lane = _clip_lane(SlotCue(t=10.0, level=1.0), SlotCue(t=20.0, level=0.0))
    clip = replace(
        _clips(lane)[0],
        level=0.4,
        blend="add",
        role="bed",
        cut_in="soft",
        cut_out="hard",
    )
    updated = update_clip(lane, clip, inherit=0.0)
    assert updated.cues == [
        SlotCue(t=10.0, level=0.4, blend="add", role="bed", cut="soft"),
        SlotCue(t=20.0, level=0.0, cut="hard"),
    ]


def test_update_clip_ignores_cut_out_without_an_end_cue() -> None:
    lane = _clip_lane(SlotCue(t=10.0, level=1.0), SlotCue(t=20.0, level=0.5, cut="soft"))
    clip = replace(_clips(lane)[0], cut_out="hard")
    assert update_clip(lane, clip, inherit=0.0) == lane


def test_update_clip_level_merges_into_a_matching_neighbour() -> None:
    lane = _clip_lane(
        SlotCue(t=10.0, level=1.0),
        SlotCue(t=20.0, level=0.5),
        SlotCue(t=30.0, level=0.0),
    )
    clip = replace(_clips(lane)[1], level=1.0)
    assert _spans(update_clip(lane, clip, inherit=0.0)) == [(10.0, 30.0)]


def test_update_clip_level_on_an_opening_baseline_stays_a_baseline() -> None:
    lane = _clip_lane(SlotCue(t=8.0, level=0.0), baseline=None)
    clip = replace(_clips(lane, inherit=1.0)[0], level=0.5)
    updated = update_clip(lane, clip, inherit=1.0)
    assert updated.baseline == 0.5
    assert updated.cues == [SlotCue(t=8.0, level=0.0)]


def test_fold_lane_baseline_freezes_inherit() -> None:
    lane = _clip_lane(SlotCue(t=5.0, level=1.0), baseline=None)
    assert fold_lane_baseline(lane, 1.0) == TimelineLane(baseline=1.0, cues=[])
    explicit = _clip_lane(SlotCue(t=5.0, level=1.0), baseline=0.0)
    assert fold_lane_baseline(explicit, 1.0) == explicit
