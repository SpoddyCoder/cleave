"""Tests for per-lane timeline evaluation and editing."""

from __future__ import annotations

import pytest

from cleave.config_schema import DEFAULT_LAYER_SLOTS
from cleave.timeline import (
    RECORD_DEBOUNCE_SEC,
    SlotCue,
    Timeline,
    TimelineLane,
    canonicalize,
    empty_lane,
    lane_fade_alpha,
    lane_fade_spans,
    lane_visible_at,
    punch_lane,
    set_lane_cue,
    should_accept_toggle,
    stem_abbreviation,
    strip_lane_range,
)


def _lane(
    baseline: bool | None,
    *transitions: tuple[float, bool],
) -> TimelineLane:
    cues = [SlotCue(t=t, visible=v) for t, v in transitions]
    return TimelineLane(baseline=baseline, cues=canonicalize(baseline, cues))


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


def test_lane_visible_at_uses_inherit_when_baseline_none() -> None:
    lane = empty_lane()
    assert lane_visible_at(lane, 10.0, inherit=False) is False
    assert lane_visible_at(lane, 10.0, inherit=True) is True


def test_lane_visible_at_uses_concrete_baseline() -> None:
    lane = _lane(False)
    assert lane_visible_at(lane, 10.0, inherit=True) is False


def test_lane_visible_at_applies_cues_up_to_t_sec() -> None:
    lane = _lane(True, (5.0, False), (10.0, True), (15.0, False))
    assert lane_visible_at(lane, 4.9, inherit=True) is True
    assert lane_visible_at(lane, 5.0, inherit=True) is False
    assert lane_visible_at(lane, 12.0, inherit=True) is True
    assert lane_visible_at(lane, 14.9, inherit=True) is True
    assert lane_visible_at(lane, 20.0, inherit=True) is False


def test_canonicalize_last_write_wins_at_equal_t() -> None:
    cues = canonicalize(
        True,
        [SlotCue(t=1.0, visible=False), SlotCue(t=1.0, visible=True)],
    )
    assert cues == []


def test_canonicalize_drops_redundant_transitions() -> None:
    cues = canonicalize(
        False,
        [SlotCue(t=1.0, visible=False), SlotCue(t=2.0, visible=True)],
    )
    assert cues == [SlotCue(t=2.0, visible=True)]


def test_timeline_visible_state_at_returns_all_slots() -> None:
    timeline = Timeline(
        lanes={
            "layer_1": _lane(False),
            "layer_2": _lane(True, (1.0, False)),
        }
    )
    inherits = {slot: True for slot in DEFAULT_LAYER_SLOTS}
    state = timeline.visible_state_at(list(DEFAULT_LAYER_SLOTS), 2.0, inherits)
    assert set(state) == set(DEFAULT_LAYER_SLOTS)
    assert state["layer_1"] is False
    assert state["layer_2"] is False
    assert state["layer_3"] is True
    assert state["layer_4"] is True


def test_timeline_visible_state_at_with_six_slots() -> None:
    slots = [f"layer_{i}" for i in range(1, 7)]
    inherits = {slot: True for slot in slots}
    inherits["layer_3"] = False
    timeline = Timeline(
        lanes={
            "layer_3": empty_lane(),
            "layer_4": _lane(True, (1.0, False)),
        }
    )
    state = timeline.visible_state_at(slots, 2.0, inherits)
    assert set(state) == set(slots)
    assert state["layer_3"] is False
    assert state["layer_4"] is False
    assert state["layer_1"] is True
    assert state["layer_6"] is True


def test_punch_lane_replaces_cues_in_range() -> None:
    lane = _lane(True, (1.0, False), (5.0, True), (8.0, False), (12.0, True))
    result = punch_lane(
        lane,
        4.0,
        10.0,
        [SlotCue(t=6.0, visible=False)],
    )
    assert result.baseline is True
    assert result.cues == [
        SlotCue(t=1.0, visible=False),
        SlotCue(t=12.0, visible=True),
    ]


def test_punch_lane_isolation_leaves_other_lanes_untouched() -> None:
    """Lane isolation: punching one track cannot rewrite another (by construction)."""
    lanes = {
        "layer_1": _lane(
            True,
            (0.0, True),  # redundant with baseline; dropped
            (10.0, False),
        ),
        "layer_2": _lane(False, (10.0, True)),
        "layer_3": _lane(True, (20.0, False)),
        "layer_4": _lane(False),
    }
    # Fold baselines the way presets would: concrete baselines, transition cues.
    lanes["layer_1"] = _lane(True, (10.0, False))
    before_unarmed = {
        slot: TimelineLane(baseline=lane.baseline, cues=list(lane.cues))
        for slot, lane in lanes.items()
        if slot != "layer_1"
    }
    lanes["layer_1"] = punch_lane(
        lanes["layer_1"],
        0.0,
        15.0,
        [SlotCue(t=0.0, visible=False), SlotCue(t=5.0, visible=True)],
    )
    for slot, expected in before_unarmed.items():
        assert lanes[slot].baseline == expected.baseline
        assert lanes[slot].cues == expected.cues
    assert lanes["layer_1"].cues == [
        SlotCue(t=0.0, visible=False),
        SlotCue(t=5.0, visible=True),
    ]


def test_punch_lane_does_not_touch_sibling_lane_at_same_t() -> None:
    """Collision at the same t stays per-lane; no shared cue / no_tick merge."""
    layer_2 = _lane(False, (12.0, True))
    layer_1 = punch_lane(
        _lane(False),
        5.0,
        12.0,
        [SlotCue(t=12.0, visible=True)],
    )
    assert layer_2.cues == [SlotCue(t=12.0, visible=True)]
    assert lane_visible_at(layer_2, 6.0, inherit=True) is False
    assert layer_1.cues == [SlotCue(t=12.0, visible=True)]


def test_strip_lane_range_removes_cues_in_range() -> None:
    lane = _lane(True, (1.0, False), (5.0, True), (8.0, False))
    result = strip_lane_range(lane, 4.0, 6.0)
    assert result.cues == [SlotCue(t=1.0, visible=False)]


def test_set_lane_cue_replaces_at_t() -> None:
    lane = _lane(True, (5.0, False))
    result = set_lane_cue(lane, 5.0, True)
    assert result.cues == []  # True matches baseline after canonicalize


def test_should_accept_toggle_debounces() -> None:
    assert should_accept_toggle(None, 1.0) is True
    assert should_accept_toggle(1.0, 1.0 + RECORD_DEBOUNCE_SEC - 0.01) is False
    assert should_accept_toggle(1.0, 1.0 + RECORD_DEBOUNCE_SEC) is True


def test_lane_fade_alpha_full_inside_visible_segment() -> None:
    lane = _lane(False, (5.0, True), (15.0, False))
    assert lane_fade_alpha(
        lane, 10.0, inherit=False, fade_in=2.0, fade_out=2.0, duration_sec=60.0
    ) == pytest.approx(1.0)


def test_lane_fade_alpha_fade_in_before_on_cue() -> None:
    from cleave.easing import smoothstep

    lane = _lane(False, (10.0, True), (20.0, False))
    mid = lane_fade_alpha(
        lane, 9.0, inherit=False, fade_in=2.0, fade_out=2.0, duration_sec=60.0
    )
    assert mid == pytest.approx(smoothstep(0.5))
    assert lane_fade_alpha(
        lane, 8.0, inherit=False, fade_in=2.0, fade_out=2.0, duration_sec=60.0
    ) == pytest.approx(0.0)
    assert lane_fade_alpha(
        lane, 10.0, inherit=False, fade_in=2.0, fade_out=2.0, duration_sec=60.0
    ) == pytest.approx(1.0)


def test_lane_fade_alpha_fade_out_after_off_cue() -> None:
    from cleave.easing import smoothstep

    lane = _lane(False, (5.0, True), (15.0, False))
    mid = lane_fade_alpha(
        lane, 16.0, inherit=False, fade_in=2.0, fade_out=2.0, duration_sec=60.0
    )
    assert mid == pytest.approx(smoothstep(0.5))
    assert lane_fade_alpha(
        lane, 17.0, inherit=False, fade_in=2.0, fade_out=2.0, duration_sec=60.0
    ) == pytest.approx(0.0)
    assert lane_fade_alpha(
        lane, 14.9, inherit=False, fade_in=2.0, fade_out=2.0, duration_sec=60.0
    ) == pytest.approx(1.0)


def test_lane_fade_alpha_no_fade_at_song_edges_without_cue() -> None:
    lane = _lane(True)
    assert lane_fade_alpha(
        lane, 0.5, inherit=False, fade_in=2.0, fade_out=2.0, duration_sec=30.0
    ) == pytest.approx(1.0)
    assert lane_fade_alpha(
        lane, 29.5, inherit=False, fade_in=2.0, fade_out=2.0, duration_sec=30.0
    ) == pytest.approx(1.0)
    assert lane_fade_alpha(
        lane, 0.0, inherit=False, fade_in=2.0, fade_out=2.0, duration_sec=30.0
    ) == pytest.approx(1.0)


def test_lane_fade_alpha_zero_durations_match_boolean() -> None:
    lane = _lane(False, (10.0, True), (20.0, False))
    assert lane_fade_alpha(
        lane, 9.9, inherit=False, fade_in=0.0, fade_out=0.0, duration_sec=60.0
    ) == pytest.approx(0.0)
    assert lane_fade_alpha(
        lane, 10.0, inherit=False, fade_in=0.0, fade_out=0.0, duration_sec=60.0
    ) == pytest.approx(1.0)
    assert lane_fade_alpha(
        lane, 20.0, inherit=False, fade_in=0.0, fade_out=0.0, duration_sec=60.0
    ) == pytest.approx(0.0)


def test_lane_fade_alpha_exclude_song_markers_makes_edge_abrupt() -> None:
    lane = _lane(False, (10.0, True), (20.0, False))
    before = lane_fade_alpha(
        lane,
        9.0,
        inherit=False,
        fade_in=2.0,
        fade_out=2.0,
        duration_sec=60.0,
        song_marker_times=(10.0,),
        exclude_song_markers=True,
    )
    assert before == pytest.approx(0.0)
    after = lane_fade_alpha(
        lane,
        21.0,
        inherit=False,
        fade_in=2.0,
        fade_out=2.0,
        duration_sec=60.0,
        song_marker_times=(20.0,),
        exclude_song_markers=True,
    )
    assert after == pytest.approx(0.0)


def test_lane_fade_alpha_overlapping_segments_take_max() -> None:
    from cleave.easing import smoothstep

    # Visible [5, 10) fading out and [11, 20) fading in overlap in gap with long fades.
    lane = _lane(False, (5.0, True), (10.0, False), (11.0, True), (20.0, False))
    t = 10.5
    out_env = smoothstep((10.0 + 2.0 - t) / 2.0)
    in_env = smoothstep((t - (11.0 - 2.0)) / 2.0)
    alpha = lane_fade_alpha(
        lane, t, inherit=False, fade_in=2.0, fade_out=2.0, duration_sec=60.0
    )
    assert alpha == pytest.approx(max(out_env, in_env))


def test_lane_fade_spans_fade_in_before_on_cue() -> None:
    lane = _lane(False, (10.0, True), (20.0, False))
    spans = lane_fade_spans(
        lane, inherit=False, fade_in=2.0, fade_out=2.0, duration_sec=60.0
    )
    assert (8.0, 10.0, "in") in spans
    assert (20.0, 22.0, "out") in spans


def test_lane_fade_spans_no_fade_at_song_edges_without_cue() -> None:
    lane = _lane(True)
    spans = lane_fade_spans(
        lane, inherit=False, fade_in=2.0, fade_out=2.0, duration_sec=30.0
    )
    assert spans == []


def test_lane_fade_spans_zero_durations_empty() -> None:
    lane = _lane(False, (10.0, True), (20.0, False))
    assert (
        lane_fade_spans(
            lane, inherit=False, fade_in=0.0, fade_out=0.0, duration_sec=60.0
        )
        == []
    )


def test_lane_fade_spans_exclude_song_markers() -> None:
    lane = _lane(False, (10.0, True), (20.0, False))
    spans = lane_fade_spans(
        lane,
        inherit=False,
        fade_in=2.0,
        fade_out=2.0,
        duration_sec=60.0,
        song_marker_times=(10.0, 20.0),
        exclude_song_markers=True,
    )
    assert (8.0, 10.0, "in") not in spans
    assert (20.0, 22.0, "out") not in spans


def test_lane_fade_spans_clips_to_duration() -> None:
    lane = _lane(False, (50.0, True), (59.0, False))
    spans = lane_fade_spans(
        lane, inherit=False, fade_in=2.0, fade_out=5.0, duration_sec=60.0
    )
    fade_out = next(span for span in spans if span[2] == "out")
    assert fade_out == (59.0, 60.0, "out")


def test_lane_fade_spans_clips_fade_in_at_song_start() -> None:
    lane = _lane(False, (1.0, True))
    spans = lane_fade_spans(
        lane, inherit=False, fade_in=5.0, fade_out=2.0, duration_sec=60.0
    )
    fade_in = next(span for span in spans if span[2] == "in")
    assert fade_in == (0.0, 1.0, "in")
