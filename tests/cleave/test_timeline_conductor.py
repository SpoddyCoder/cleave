"""Tests for cleave.timeline_presets.conductor."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pytest

from cleave.cue_roles import CUE_ROLE_BLEND
from cleave.extract import StemSource
from cleave.signals import Signals
from cleave.timeline import (
    LEVEL_QUANTUM,
    SlotCue,
    TimelineLane,
    empty_lane,
    lane_level_at,
)
from cleave.timeline_presets import ALL_BUILDERS, build_breathing_cues, build_pulse_cues
from cleave.timeline_presets.conductor import (
    CONDUCTOR_ACTIVITY_MIDPOINT,
    CONDUCTOR_CEILING_MIN,
    CONDUCTOR_GAIN_MAX,
    CONDUCTOR_GAIN_MIN,
    CONDUCTOR_LEVEL_FLOOR,
    DEFAULT_TIMELINE_PRESET_CONDUCTOR,
    PhraseWeights,
    StemConductor,
    cycle_timeline_preset_conductor,
    support_floor_for,
    timeline_preset_conductor_display,
)
from cleave.timeline_presets.crescendo import (
    apply_crescendo,
    resolve_crescendo_window,
)
from cleave.timeline_presets.emit import cues_from_states

_SR = 100.0
_DUR = 20.0
_N = int(_DUR * _SR)


def _envelope(quiet: float, loud: float) -> np.ndarray:
    """Quiet first half, loud second half."""
    arr = np.empty(_N, dtype=np.float64)
    mid = _N // 2
    arr[:mid] = quiet
    arr[mid:] = loud
    return arr


def _make_signals(
    *,
    drums: np.ndarray | None = None,
    bass: np.ndarray | None = None,
    vocals: np.ndarray | None = None,
    other: np.ndarray | None = None,
    mix_rms: np.ndarray | None = None,
    mix_onset: np.ndarray | None = None,
) -> Signals:
    drums_arr = drums if drums is not None else _envelope(0.1, 0.9)
    bass_arr = bass if bass is not None else _envelope(0.2, 0.8)
    vocals_arr = vocals if vocals is not None else _envelope(0.05, 0.7)
    other_arr = other if other is not None else _envelope(0.15, 0.6)
    mix_rms_arr = mix_rms if mix_rms is not None else _envelope(0.1, 1.0)
    mix_onset_arr = mix_onset if mix_onset is not None else _envelope(0.05, 0.8)
    return Signals(
        sample_rate_hz=_SR,
        duration_sec=_DUR,
        path=Path("."),
        stems={
            "drums": {"onset_strength": drums_arr},
            "bass": {"rms": bass_arr, "sub_bass": bass_arr, "mid_bass": bass_arr},
            "vocals": {"rms": vocals_arr, "pitch_hz": vocals_arr},
            "other": {
                "spectral_centroid": other_arr * 1000.0,
                "rms": other_arr,
            },
            "full_mix": {
                "onset_strength": mix_onset_arr,
                "rms": mix_rms_arr,
            },
        },
    )


def _slot_stems() -> dict[str, StemSource]:
    return {
        "layer_1": "drums",
        "layer_2": "bass",
        "layer_3": "vocals",
        "layer_4": "other",
    }


def _phrases() -> list[tuple[float, float]]:
    return [(0.0, 10.0), (10.0, 20.0)]


def test_build_returns_none_without_signals() -> None:
    assert StemConductor.build(None, _slot_stems(), _phrases()) is None


def test_build_returns_none_without_slot_stems() -> None:
    assert StemConductor.build(_make_signals(), None, _phrases()) is None
    assert StemConductor.build(_make_signals(), {}, _phrases()) is None


def test_build_returns_none_when_energy_empty() -> None:
    zeros = np.zeros(_N, dtype=np.float64)
    signals = _make_signals(mix_rms=zeros, mix_onset=zeros)
    assert StemConductor.build(signals, _slot_stems(), _phrases()) is None


def test_build_returns_none_when_energy_flat() -> None:
    flat = np.full(_N, 0.5, dtype=np.float64)
    signals = _make_signals(mix_rms=flat, mix_onset=flat)
    assert StemConductor.build(signals, _slot_stems(), _phrases()) is None


def test_loud_phrase_has_higher_gain_and_ceiling() -> None:
    conductor = StemConductor.build(_make_signals(), _slot_stems(), _phrases())
    assert conductor is not None
    quiet = conductor.phrase_at(5.0)
    loud = conductor.phrase_at(15.0)
    assert quiet.budget_gain < loud.budget_gain
    assert quiet.lead_ceiling < loud.lead_ceiling
    assert quiet.budget_gain == pytest.approx(CONDUCTOR_GAIN_MIN)
    assert loud.budget_gain == pytest.approx(CONDUCTOR_GAIN_MAX)
    assert CONDUCTOR_CEILING_MIN <= quiet.lead_ceiling < 1.0
    assert loud.lead_ceiling == pytest.approx(1.0)


def test_budget_gain_curve_is_centred_on_one() -> None:
    """Gain redistributes budget between phrases instead of lowering it overall."""
    assert CONDUCTOR_GAIN_MIN + CONDUCTOR_GAIN_MAX == pytest.approx(2.0)
    n = int(_DUR * 5)
    step = _DUR / n
    ramp = np.linspace(0.05, 1.0, _N, dtype=np.float64)
    signals = _make_signals(mix_rms=ramp, mix_onset=ramp)
    phrases = [(i * step, (i + 1) * step) for i in range(n)]
    conductor = StemConductor.build(signals, _slot_stems(), phrases)
    assert conductor is not None
    gains = [
        conductor.phrase_at((t0 + t1) * 0.5).budget_gain for t0, t1 in phrases
    ]
    assert sum(gains) / len(gains) == pytest.approx(1.0)


def test_lead_ceiling_only_dims_quiet_phrases() -> None:
    """A loud song keeps the lead near full instead of dimming half its phrases."""
    n = 10
    step = _DUR / n
    # Consistently loud apart from one quiet phrase.
    arr = np.full(_N, 0.9, dtype=np.float64)
    arr[: _N // n] = 0.15
    signals = _make_signals(mix_rms=arr, mix_onset=arr)
    phrases = [(i * step, (i + 1) * step) for i in range(n)]
    conductor = StemConductor.build(signals, _slot_stems(), phrases)
    assert conductor is not None
    ceilings = [
        conductor.phrase_at((t0 + t1) * 0.5).lead_ceiling for t0, t1 in phrases
    ]
    assert ceilings[0] < 0.8
    assert all(ceiling > 0.95 for ceiling in ceilings[1:])


def test_near_silent_level_states_floor_lead_only() -> None:
    # Absolute energy below silence floor in the quiet half after normalize.
    mix_rms = _envelope(0.001, 1.0)
    mix_onset = _envelope(0.001, 1.0)
    signals = _make_signals(mix_rms=mix_rms, mix_onset=mix_onset)
    conductor = StemConductor.build(signals, _slot_stems(), _phrases())
    assert conductor is not None
    quiet = conductor.phrase_at(5.0)
    assert quiet.near_silent

    states = [
        (0.0, frozenset({"layer_1", "layer_2", "layer_3"})),
        (10.0, frozenset({"layer_1", "layer_2"})),
    ]
    levels = conductor.level_states(states, _DUR)
    quiet_levels = levels[0][1]
    on = [slot for slot, level in quiet_levels.items() if level > 0.0]
    assert len(on) == 1
    assert quiet_levels[on[0]] == pytest.approx(CONDUCTOR_LEVEL_FLOOR)
    for slot, level in quiet_levels.items():
        if slot != on[0]:
            assert level == pytest.approx(0.0)


def test_rotation_for_prefers_active_stem() -> None:
    # Vocals silent throughout; drums loud.
    drums = np.full(_N, 1.0, dtype=np.float64)
    vocals = np.zeros(_N, dtype=np.float64)
    signals = _make_signals(drums=drums, vocals=vocals)
    conductor = StemConductor.build(signals, _slot_stems(), _phrases())
    assert conductor is not None
    weights = conductor.phrase_at(15.0)
    assert weights.slot_activity["layer_3"] == pytest.approx(0.0)
    singles = ["layer_3", "layer_1"]  # vocals (silent), drums (loud)
    airtime = {slot: 0.0 for slot in singles}
    index = conductor.rotation_for(singles, weights, airtime)
    assert singles[index] == "layer_1"


def test_slot_activity_is_comparable_across_stems() -> None:
    """Standardised activity compares each stem to itself, not to other scales."""
    n = 8
    step = _DUR / n
    phrases = [(i * step, (i + 1) * step) for i in range(n)]
    # Drum onsets are spiky and low-mean; bass rms is dense and high-mean. Both
    # peak in the same phrase, so both should rank top there.
    shape = np.zeros(_N, dtype=np.float64)
    for i in range(n):
        lo = int(i * _N / n)
        hi = int((i + 1) * _N / n)
        shape[lo:hi] = 0.1 + 0.1 * i
    signals = _make_signals(drums=shape * 0.2, bass=shape * 5.0)
    conductor = StemConductor.build(signals, _slot_stems(), phrases)
    assert conductor is not None
    top = conductor.phrase_at(phrases[-1][0] + 0.1)
    assert top.slot_activity["layer_1"] == pytest.approx(1.0)
    assert top.slot_activity["layer_2"] == pytest.approx(1.0)


def test_rotation_for_penalises_airtime_share() -> None:
    conductor = StemConductor.build(_make_signals(), _slot_stems(), _phrases())
    assert conductor is not None
    weights = conductor.phrase_at(15.0)
    singles = ["layer_1", "layer_2", "layer_3", "layer_4"]
    balanced = {slot: 0.0 for slot in singles}
    lead = singles[conductor.rotation_for(singles, weights, balanced)]
    # Airtime is a share of total screen time, so a hogging slot loses the lead.
    hogging = {slot: (600.0 if slot == lead else 1.0) for slot in singles}
    assert singles[conductor.rotation_for(singles, weights, hogging)] != lead


def test_levels_are_quantum_multiples_and_active_floor() -> None:
    conductor = StemConductor.build(_make_signals(), _slot_stems(), _phrases())
    assert conductor is not None
    states = [
        (10.0, frozenset({"layer_1", "layer_2", "layer_3", "layer_4"})),
    ]
    levels = conductor.level_states(states, _DUR)[0][1]
    for slot, level in levels.items():
        steps = level / LEVEL_QUANTUM
        assert steps == pytest.approx(round(steps))
        assert level == 0.0 or level >= CONDUCTOR_LEVEL_FLOOR
        assert not (0.0 < level < CONDUCTOR_LEVEL_FLOOR)


def test_deterministic_for_same_inputs() -> None:
    signals = _make_signals()
    slots = _slot_stems()
    phrases = _phrases()
    a = StemConductor.build(signals, slots, phrases)
    b = StemConductor.build(signals, slots, phrases)
    assert a is not None and b is not None
    states = [(0.0, frozenset({"layer_1", "layer_2"})), (10.0, frozenset({"layer_3"}))]
    assert a.level_states(states, _DUR) == b.level_states(states, _DUR)
    assert a.phrase_at(12.0) == b.phrase_at(12.0)
    weights = a.phrase_at(12.0)
    airtime = {"layer_1": 0.2, "layer_2": 0.1}
    assert a.rotation_for(["layer_1", "layer_2"], weights, airtime) == b.rotation_for(
        ["layer_1", "layer_2"], weights, airtime
    )


def test_cast_for_state_near_silent_all_bed() -> None:
    mix_rms = _envelope(0.001, 1.0)
    mix_onset = _envelope(0.001, 1.0)
    signals = _make_signals(mix_rms=mix_rms, mix_onset=mix_onset)
    conductor = StemConductor.build(signals, _slot_stems(), _phrases())
    assert conductor is not None
    weights = conductor.phrase_at(5.0)
    assert weights.near_silent
    active = frozenset({"layer_1", "layer_2", "layer_3"})
    cast = conductor.cast_for_state(active, weights)
    assert set(cast) == active
    for role, blend in cast.values():
        assert role == "bed"
        assert blend == CUE_ROLE_BLEND["bed"]


def test_cast_for_state_drums_pulse_and_one_lead() -> None:
    conductor = StemConductor.build(_make_signals(), _slot_stems(), _phrases())
    assert conductor is not None
    weights = conductor.phrase_at(15.0)
    assert not weights.near_silent
    assert weights.slot_activity["layer_1"] > 0.0
    active = frozenset({"layer_1", "layer_2", "layer_3", "layer_4"})
    cast = conductor.cast_for_state(active, weights)
    assert cast["layer_1"] == ("pulse", CUE_ROLE_BLEND["pulse"])
    roles = {role for role, _blend in cast.values()}
    assert roles == {"pulse", "lead", "bed"}
    leads = [slot for slot, (role, _) in cast.items() if role == "lead"]
    assert len(leads) == 1
    lead = leads[0]
    assert lead != "layer_1"
    non_pulse = [s for s in active if s != "layer_1"]
    expected_lead = max(
        sorted(non_pulse), key=lambda s: weights.slot_activity.get(s, 0.0)
    )
    assert lead == expected_lead
    for slot in non_pulse:
        if slot != lead:
            assert cast[slot] == ("bed", CUE_ROLE_BLEND["bed"])
    assert "accent" not in roles


def test_cast_for_state_solo_is_lead() -> None:
    conductor = StemConductor.build(_make_signals(), _slot_stems(), _phrases())
    assert conductor is not None
    weights = conductor.phrase_at(15.0)
    # Solo drums still casts as lead (solo overrides pulse).
    cast = conductor.cast_for_state(frozenset({"layer_1"}), weights)
    assert cast == {"layer_1": ("lead", CUE_ROLE_BLEND["lead"])}
    cast_bass = conductor.cast_for_state(frozenset({"layer_2"}), weights)
    assert cast_bass == {"layer_2": ("lead", CUE_ROLE_BLEND["lead"])}


def test_cast_for_state_silent_drums_not_pulse() -> None:
    drums = np.zeros(_N, dtype=np.float64)
    signals = _make_signals(drums=drums)
    conductor = StemConductor.build(signals, _slot_stems(), _phrases())
    assert conductor is not None
    weights = conductor.phrase_at(15.0)
    assert weights.slot_activity["layer_1"] == pytest.approx(0.0)
    cast = conductor.cast_for_state(
        frozenset({"layer_1", "layer_2", "layer_3"}), weights
    )
    assert cast["layer_1"][0] != "pulse"
    leads = [slot for slot, (role, _) in cast.items() if role == "lead"]
    assert len(leads) == 1


def test_cues_from_states_writes_cast_on_on_transitions() -> None:
    slots = ["layer_1", "layer_2"]
    states = [
        (0.0, {"layer_1": 1.0, "layer_2": 0.0}),
        (4.0, {"layer_1": 0.0, "layer_2": 0.5}),
        (8.0, {"layer_1": 0.0, "layer_2": 1.0}),
    ]
    casts = [
        {"layer_1": ("lead", "black-key")},
        {"layer_2": ("pulse", "add")},
        {"layer_2": ("pulse", "add")},
    ]
    lanes = cues_from_states(slots, states, casts)
    assert lanes["layer_1"].cues == [
        SlotCue(t=0.0, level=1.0, blend="black-key", role="lead", cut="soft"),
        SlotCue(t=4.0, level=0.0, cut="soft"),
    ]
    assert lanes["layer_2"].cues == [
        SlotCue(t=4.0, level=0.5, blend="add", role="pulse", cut="soft"),
        SlotCue(t=8.0, level=1.0, blend="add", role="pulse", cut="soft"),
    ]


def test_cues_from_states_without_casts_omits_role_blend() -> None:
    slots = ["layer_1"]
    lanes = cues_from_states(slots, [(0.0, {"layer_1": 1.0})])
    assert lanes["layer_1"].cues == [SlotCue(t=0.0, level=1.0, cut="soft")]


def test_cues_from_states_marks_song_marker_on_cues_hard() -> None:
    slots = ["layer_1"]
    lanes = cues_from_states(
        slots,
        [
            (0.0, {"layer_1": 1.0}),
            (10.0, {"layer_1": 0.0}),
            (20.0, {"layer_1": 1.0}),
        ],
        song_marker_times=(10.0, 20.0),
    )
    assert lanes["layer_1"].cues == [
        SlotCue(t=0.0, level=1.0, cut="soft"),
        # Off at a marker still inherits cut from the preceding on-cue.
        SlotCue(t=10.0, level=0.0, cut="soft"),
        SlotCue(t=20.0, level=1.0, cut="hard"),
    ]


def test_cues_from_states_off_inherits_preceding_on_cut() -> None:
    slots = ["layer_1"]
    lanes = cues_from_states(
        slots,
        [
            (0.0, {"layer_1": 1.0}),
            (10.0, {"layer_1": 0.0}),
            (20.0, {"layer_1": 1.0}),
            (30.0, {"layer_1": 0.0}),
        ],
        song_marker_times=(0.0,),
    )
    assert lanes["layer_1"].cues == [
        SlotCue(t=0.0, level=1.0, cut="hard"),
        SlotCue(t=10.0, level=0.0, cut="hard"),
        SlotCue(t=20.0, level=1.0, cut="soft"),
        SlotCue(t=30.0, level=0.0, cut="soft"),
    ]


def test_arranger_with_conductor_emits_roles_and_blends() -> None:
    slots = ["layer_1", "layer_2", "layer_3", "layer_4"]
    duration_sec = 20.0
    bars = _bar_times(duration_sec)
    lanes = build_breathing_cues(
        slots,
        duration_sec,
        random.Random(7),
        bar_times=bars,
        signals=_make_signals(),
        slot_stems=_slot_stems(),
    )
    on_cues = [
        cue
        for lane in lanes.values()
        for cue in lane.cues
        if cue.level > 0.0
    ]
    assert on_cues
    assert any(cue.role is not None and cue.blend is not None for cue in on_cues)
    for cue in on_cues:
        if cue.role is None:
            continue
        assert cue.role in ("bed", "pulse", "lead")
        assert cue.blend == CUE_ROLE_BLEND[cue.role]
        assert cue.role != "accent"


def test_chord_score_is_centred_mean_activity() -> None:
    conductor = StemConductor.build(_make_signals(), _slot_stems(), _phrases())
    assert conductor is not None
    weights = conductor.phrase_at(15.0)
    score = conductor.chord_score(frozenset({"layer_1", "layer_2"}), weights)
    expected = (
        weights.slot_activity["layer_1"]
        + weights.slot_activity["layer_2"]
        - 2.0 * CONDUCTOR_ACTIVITY_MIDPOINT
    ) / 2.0
    assert score == pytest.approx(expected)
    assert conductor.chord_score(frozenset(), weights) == pytest.approx(0.0)


def test_chord_score_does_not_penalise_larger_chords() -> None:
    """A chord of neutral slots scores the same at any cardinality."""
    conductor = StemConductor.build(_make_signals(), _slot_stems(), _phrases())
    assert conductor is not None
    weights = PhraseWeights(
        budget_gain=1.0,
        slot_activity={
            slot: CONDUCTOR_ACTIVITY_MIDPOINT for slot in _slot_stems()
        },
        lead_ceiling=1.0,
        near_silent=False,
    )
    solo = conductor.chord_score(frozenset({"layer_1"}), weights)
    quartet = conductor.chord_score(frozenset(_slot_stems()), weights)
    assert solo == pytest.approx(0.0)
    assert quartet == pytest.approx(solo)


def test_staging_display_and_cycle() -> None:
    assert DEFAULT_TIMELINE_PRESET_CONDUCTOR is False
    assert timeline_preset_conductor_display(False) == "off"
    assert timeline_preset_conductor_display(True) == "on"
    assert cycle_timeline_preset_conductor(False, forward=True) is True
    assert cycle_timeline_preset_conductor(True, forward=True) is False
    assert cycle_timeline_preset_conductor(False, forward=False) is True
    assert cycle_timeline_preset_conductor(True, forward=False) is False


def _bar_times(duration_sec: float, bar_sec: float = 2.0) -> list[float]:
    bars: list[float] = []
    t = 0.0
    while t < duration_sec - 1e-9:
        bars.append(t)
        t += bar_sec
    return bars


def _lane_signature(lanes: dict[str, TimelineLane]) -> dict[str, object]:
    return {
        slot: (lane.baseline, tuple((c.t, c.level) for c in lane.cues))
        for slot, lane in sorted(lanes.items())
    }


@pytest.mark.parametrize("builder", ALL_BUILDERS)
def test_arranger_without_signals_matches_baseline(builder) -> None:
    slots = ["layer_1", "layer_2", "layer_3", "layer_4"]
    duration_sec = 60.0
    bars = _bar_times(duration_sec)
    seed = 42
    baseline = builder(
        slots, duration_sec, random.Random(seed), bar_times=bars
    )
    without = builder(
        slots,
        duration_sec,
        random.Random(seed),
        bar_times=bars,
        signals=None,
        slot_stems=None,
    )
    assert _lane_signature(without) == _lane_signature(baseline)


def test_arranger_with_conductor_emits_quantized_levels() -> None:
    slots = ["layer_1", "layer_2", "layer_3", "layer_4"]
    duration_sec = 20.0
    bars = _bar_times(duration_sec)
    signals = _make_signals()
    slot_stems = _slot_stems()
    lanes = build_breathing_cues(
        slots,
        duration_sec,
        random.Random(7),
        bar_times=bars,
        signals=signals,
        slot_stems=slot_stems,
    )
    assert set(lanes) == set(slots)
    saw_partial = False
    levels: list[float] = []
    for lane in lanes.values():
        if lane.baseline is not None:
            levels.append(float(lane.baseline))
        levels.extend(float(cue.level) for cue in lane.cues)
    assert levels
    for level in levels:
        steps = level / LEVEL_QUANTUM
        assert steps == pytest.approx(round(steps))
        assert level == 0.0 or level >= CONDUCTOR_LEVEL_FLOOR
        assert not (0.0 < level < CONDUCTOR_LEVEL_FLOOR)
        if 0.0 < level < 1.0 - 1e-9:
            saw_partial = True
    assert saw_partial


def _compressed_master_signals(duration_sec: float) -> Signals:
    """Compressed mix with stems always near their own scale (typical master)."""
    n = int(duration_sec * _SR)
    t = np.linspace(0.0, 1.0, n, dtype=np.float64)
    # Mild full-mix sway only: min ~0.6 of peak.
    mix = 0.6 + 0.4 * (0.5 + 0.5 * np.sin(np.pi * t))

    def flat(scale: float, wobble: float = 0.02) -> np.ndarray:
        return scale * (1.0 + wobble * np.sin(8.0 * np.pi * t))

    return Signals(
        sample_rate_hz=_SR,
        duration_sec=duration_sec,
        path=Path("."),
        stems={
            "drums": {"onset_strength": flat(0.2)},
            "bass": {
                "rms": flat(0.7),
                "sub_bass": flat(0.7),
                "mid_bass": flat(0.7),
            },
            "vocals": {"rms": flat(0.5), "pitch_hz": flat(0.5)},
            "other": {
                "spectral_centroid": flat(700.0),
                "rms": flat(0.65),
            },
            "full_mix": {"onset_strength": mix * 0.8, "rms": mix},
        },
    )


def test_conductor_emits_partial_cue_levels_on_compressed_master() -> None:
    """Regression: high support floors + soft ceiling pinned every active cue at 1.0."""
    slots = ["layer_1", "layer_2", "layer_3", "layer_4"]
    duration_sec = 180.0
    bars = _bar_times(duration_sec)
    signals = _compressed_master_signals(duration_sec)
    slot_stems = _slot_stems()
    off = build_pulse_cues(
        slots,
        duration_sec,
        random.Random(42),
        bar_times=bars,
        density_bias=1,
    )
    on = build_pulse_cues(
        slots,
        duration_sec,
        random.Random(42),
        bar_times=bars,
        density_bias=1,
        signals=signals,
        slot_stems=slot_stems,
    )
    off_active = [
        float(cue.level)
        for lane in off.values()
        for cue in lane.cues
        if cue.level > 1e-9
    ]
    on_active = [
        float(cue.level)
        for lane in on.values()
        for cue in lane.cues
        if cue.level > 1e-9
    ]
    assert off_active
    assert on_active
    assert all(level == pytest.approx(1.0) for level in off_active)
    partial = [level for level in on_active if 0.0 < level < 1.0 - 1e-9]
    assert partial, f"expected partial levels, got {sorted(set(on_active))}"
    assert any(level in (0.25, 0.5, 0.75) for level in partial)
    assert sum(on_active) / len(on_active) < 1.0 - 1e-9


def test_arranger_conductor_is_deterministic() -> None:
    slots = ["layer_1", "layer_2", "layer_3", "layer_4"]
    duration_sec = 20.0
    bars = _bar_times(duration_sec)
    signals = _make_signals()
    slot_stems = _slot_stems()
    a = build_breathing_cues(
        slots,
        duration_sec,
        random.Random(11),
        bar_times=bars,
        signals=signals,
        slot_stems=slot_stems,
    )
    b = build_breathing_cues(
        slots,
        duration_sec,
        random.Random(11),
        bar_times=bars,
        signals=signals,
        slot_stems=slot_stems,
    )
    assert _lane_signature(a) == _lane_signature(b)


def test_loud_phrases_have_more_level_weight() -> None:
    conductor = StemConductor.build(_make_signals(), _slot_stems(), _phrases())
    assert conductor is not None
    active = frozenset({"layer_1", "layer_2", "layer_3", "layer_4"})
    levels = conductor.level_states(
        [(0.0, active), (10.0, active)],
        _DUR,
    )
    quiet_weight = sum(levels[0][1].values())
    loud_weight = sum(levels[1][1].values())
    assert loud_weight > quiet_weight


def test_arranger_silent_stem_soloed_less_often() -> None:
    slots = ["layer_1", "layer_2", "layer_3", "layer_4"]
    duration_sec = 60.0
    bars = _bar_times(duration_sec)
    n = int(duration_sec * _SR)
    drums = np.full(n, 1.0, dtype=np.float64)
    vocals = np.zeros(n, dtype=np.float64)
    bass = np.full(n, 0.5, dtype=np.float64)
    other = np.full(n, 0.4, dtype=np.float64)
    mix_rms = np.linspace(0.2, 1.0, n, dtype=np.float64)
    mix_onset = np.linspace(0.1, 0.9, n, dtype=np.float64)
    signals = Signals(
        sample_rate_hz=_SR,
        duration_sec=duration_sec,
        path=Path("."),
        stems={
            "drums": {"onset_strength": drums},
            "bass": {"rms": bass, "sub_bass": bass, "mid_bass": bass},
            "vocals": {"rms": vocals, "pitch_hz": vocals},
            "other": {"spectral_centroid": other * 1000.0, "rms": other},
            "full_mix": {"onset_strength": mix_onset, "rms": mix_rms},
        },
    )
    solo_counts = {"layer_1": 0, "layer_3": 0}
    samples = 0
    for seed in range(20):
        lanes = build_breathing_cues(
            slots,
            duration_sec,
            random.Random(seed),
            bar_times=bars,
            signals=signals,
            slot_stems=_slot_stems(),
        )
        t = 0.0
        while t < duration_sec - 1e-9:
            levels = {
                slot: lane_level_at(lanes[slot], t, inherit=0.0) for slot in slots
            }
            active = [slot for slot, level in levels.items() if level > 0.0]
            if len(active) == 1 and active[0] in solo_counts:
                solo_counts[active[0]] += 1
            samples += 1
            t += 1.0
    assert samples > 0
    assert solo_counts["layer_1"] > solo_counts["layer_3"]


def _ducked_conductor(density_bias: int) -> StemConductor:
    """Layer 2 is loud early and faint late, so it supports rather than leads."""
    faint = np.empty(_N, dtype=np.float64)
    mid = _N // 2
    faint[:mid] = 0.9
    faint[mid:] = 0.05
    signals = _make_signals(
        drums=np.full(_N, 0.9, dtype=np.float64),
        bass=faint,
        vocals=np.full(_N, 0.85, dtype=np.float64),
        other=np.full(_N, 0.8, dtype=np.float64),
        mix_rms=_envelope(0.8, 1.0),
        mix_onset=_envelope(0.7, 1.0),
    )
    conductor = StemConductor.build(
        signals, _slot_stems(), _phrases(), density_bias=density_bias
    )
    assert conductor is not None
    return conductor


def test_support_floor_rises_with_density_bias() -> None:
    floors = [support_floor_for(bias) for bias in (-2, -1, 0, 1, 2)]
    assert floors == sorted(floors)
    assert floors[0] < floors[2] < floors[-1]


def test_supporting_slot_stays_visible() -> None:
    """A ducked slot lands well above the floor, not at an invisible 0.25."""
    active = frozenset({"layer_1", "layer_2", "layer_3", "layer_4"})
    levels = _ducked_conductor(0).level_states([(10.0, active)], _DUR)[0][1]
    lead = max(levels.values())
    support = levels["layer_2"]
    assert lead == pytest.approx(1.0)
    assert support < lead
    assert support >= 2.0 * LEVEL_QUANTUM


def test_duck_depth_shrinks_as_density_rises() -> None:
    active = frozenset({"layer_1", "layer_2", "layer_3", "layer_4"})
    sparse = _ducked_conductor(-2).level_states([(10.0, active)], _DUR)[0][1]
    dense = _ducked_conductor(2).level_states([(10.0, active)], _DUR)[0][1]
    assert sparse["layer_2"] < dense["layer_2"]
    # Very dense lifts the support toward the lead without erasing ducking.
    assert dense["layer_2"] < max(dense.values())


def _varied_signals(duration_sec: float) -> Signals:
    """Each stem takes its turn as the busiest; stem scales differ widely."""
    n = int(duration_sec * _SR)
    t = np.linspace(0.0, 1.0, n, dtype=np.float64)

    def turn(phase: float, scale: float) -> np.ndarray:
        cycle = np.sin(2.0 * np.pi * (3.0 * t + phase))
        return scale * (0.35 + 0.3 * (1.0 + cycle))

    arc = 0.3 + 0.6 * np.abs(np.sin(np.pi * t))
    return Signals(
        sample_rate_hz=_SR,
        duration_sec=duration_sec,
        path=Path("."),
        stems={
            "drums": {"onset_strength": turn(0.0, 0.2)},
            "bass": {
                "rms": turn(0.25, 0.9),
                "sub_bass": turn(0.25, 0.9),
                "mid_bass": turn(0.25, 0.9),
            },
            "vocals": {"rms": turn(0.5, 0.6), "pitch_hz": turn(0.5, 0.6)},
            "other": {
                "spectral_centroid": turn(0.75, 700.0),
                "rms": turn(0.75, 0.75),
            },
            "full_mix": {"onset_strength": arc * 0.8, "rms": arc},
        },
    )


def _sampled_weight_and_shares(
    lanes: dict[str, TimelineLane],
    slots: list[str],
    duration_sec: float,
    step: float = 0.5,
) -> tuple[float, dict[str, float]]:
    total = 0.0
    samples = 0
    on = {slot: 0 for slot in slots}
    t = 0.0
    while t < duration_sec - 1e-9:
        levels = {
            slot: lane_level_at(lanes[slot], t, inherit=0.0) for slot in slots
        }
        total += sum(levels.values())
        for slot, level in levels.items():
            if level > 0.0:
                on[slot] += 1
        samples += 1
        t += step
    return total / samples, {slot: count / samples for slot, count in on.items()}


def test_density_bias_raises_concurrent_weight_with_conductor() -> None:
    slots = ["layer_1", "layer_2", "layer_3", "layer_4"]
    duration_sec = 180.0
    bars = _bar_times(duration_sec)
    signals = _varied_signals(duration_sec)
    means: list[float] = []
    for bias in (-2, 0, 2):
        totals = []
        for seed in range(6):
            lanes = build_breathing_cues(
                slots,
                duration_sec,
                random.Random(seed),
                bar_times=bars,
                density_bias=bias,
                signals=signals,
                slot_stems=_slot_stems(),
            )
            mean, _shares = _sampled_weight_and_shares(lanes, slots, duration_sec)
            totals.append(mean)
        means.append(sum(totals) / len(totals))
    assert means == sorted(means), means
    assert means[-1] > means[0], means


def test_conductor_does_not_let_one_slot_dominate() -> None:
    """With every stem taking its turn, no slot hogs the composite."""
    slots = ["layer_1", "layer_2", "layer_3", "layer_4"]
    duration_sec = 180.0
    bars = _bar_times(duration_sec)
    signals = _varied_signals(duration_sec)
    totals = {slot: 0.0 for slot in slots}
    seeds = 6
    for seed in range(seeds):
        lanes = build_breathing_cues(
            slots,
            duration_sec,
            random.Random(seed),
            bar_times=bars,
            signals=signals,
            slot_stems=_slot_stems(),
        )
        _mean, shares = _sampled_weight_and_shares(lanes, slots, duration_sec)
        # Each seed must move the composite around rather than hold one layer.
        assert max(shares.values()) < 0.85, (seed, shares)
        assert len(lanes[max(shares, key=shares.get)].cues) > 0
        for slot, share in shares.items():
            totals[slot] += share / seeds
    assert max(totals.values()) < 0.6, totals
    assert min(totals.values()) > 0.05, totals


def test_arranger_conductor_crescendo_preserves_prefix_levels() -> None:
    slots = ["layer_1", "layer_2", "layer_3", "layer_4"]
    duration_sec = 120.0
    bars = _bar_times(duration_sec)
    n = int(duration_sec * _SR)
    mix_rms = np.linspace(0.15, 1.0, n, dtype=np.float64)
    mix_onset = np.linspace(0.1, 0.9, n, dtype=np.float64)
    stem = np.linspace(0.2, 0.9, n, dtype=np.float64)
    signals = Signals(
        sample_rate_hz=_SR,
        duration_sec=duration_sec,
        path=Path("."),
        stems={
            "drums": {"onset_strength": stem},
            "bass": {"rms": stem, "sub_bass": stem, "mid_bass": stem},
            "vocals": {"rms": stem, "pitch_hz": stem},
            "other": {"spectral_centroid": stem * 1000.0, "rms": stem},
            "full_mix": {"onset_strength": mix_onset, "rms": mix_rms},
        },
    )
    markers = [20.0, 50.0, 80.0, 100.0]
    window = resolve_crescendo_window(markers, duration_sec, "last")
    assert window is not None
    base = build_breathing_cues(
        slots,
        duration_sec,
        random.Random(5),
        bar_times=bars,
        signals=signals,
        slot_stems=_slot_stems(),
    )
    after = apply_crescendo(
        base,
        slots,
        duration_sec=duration_sec,
        bar_times=bars,
        song_marker_times=markers,
        target="last",
        rng=random.Random(6),
    )
    t = 0.0
    while t < window.t_start - 1e-9:
        for slot in slots:
            assert lane_level_at(after[slot], t, inherit=0.0) == pytest.approx(
                lane_level_at(base[slot], t, inherit=0.0)
            )
        t += 1.0


def test_arranger_conductor_crescendo_preserves_prefix_roles() -> None:
    """Regression: apply_crescendo must not strip conductor casts on rebuild."""
    slots = ["layer_1", "layer_2", "layer_3", "layer_4"]
    duration_sec = 120.0
    bars = _bar_times(duration_sec)
    n = int(duration_sec * _SR)
    mix_rms = np.linspace(0.15, 1.0, n, dtype=np.float64)
    mix_onset = np.linspace(0.1, 0.9, n, dtype=np.float64)
    stem = np.linspace(0.2, 0.9, n, dtype=np.float64)
    signals = Signals(
        sample_rate_hz=_SR,
        duration_sec=duration_sec,
        path=Path("."),
        stems={
            "drums": {"onset_strength": stem},
            "bass": {"rms": stem, "sub_bass": stem, "mid_bass": stem},
            "vocals": {"rms": stem, "pitch_hz": stem},
            "other": {"spectral_centroid": stem * 1000.0, "rms": stem},
            "full_mix": {"onset_strength": mix_onset, "rms": mix_rms},
        },
    )
    markers = [20.0, 50.0, 80.0, 100.0]
    window = resolve_crescendo_window(markers, duration_sec, "last")
    assert window is not None
    base = build_breathing_cues(
        slots,
        duration_sec,
        random.Random(5),
        bar_times=bars,
        signals=signals,
        slot_stems=_slot_stems(),
    )
    base_prefix_on = [
        cue
        for lane in base.values()
        for cue in lane.cues
        if cue.t < window.t_start - 1e-9 and cue.level > 0.0
    ]
    assert base_prefix_on
    assert any(cue.role is not None for cue in base_prefix_on)

    after = apply_crescendo(
        base,
        slots,
        duration_sec=duration_sec,
        bar_times=bars,
        song_marker_times=markers,
        target="last",
        rng=random.Random(6),
    )
    after_prefix_on = [
        cue
        for lane in after.values()
        for cue in lane.cues
        if cue.t < window.t_start - 1e-9 and cue.level > 0.0
    ]
    assert after_prefix_on
    assert all(cue.role is not None for cue in after_prefix_on)
    for cue in after_prefix_on:
        assert cue.blend == CUE_ROLE_BLEND[cue.role]

    # Crescendo ramp itself also gets lead/bed casts (not left null).
    ramp_on = [
        cue
        for lane in after.values()
        for cue in lane.cues
        if cue.t >= window.t_start - 1e-9 and cue.level > 0.0
    ]
    assert ramp_on
    assert all(cue.role in ("lead", "bed") for cue in ramp_on)
    assert all(cue.blend == CUE_ROLE_BLEND[cue.role] for cue in ramp_on)


def test_apply_crescendo_without_roles_stays_role_free() -> None:
    slots = ["layer_1", "layer_2", "layer_3", "layer_4"]
    duration_sec = 120.0
    bars = _bar_times(duration_sec)
    markers = [20.0, 50.0, 80.0, 100.0]
    base = build_breathing_cues(
        slots, duration_sec, random.Random(1), bar_times=bars
    )
    assert all(cue.role is None for lane in base.values() for cue in lane.cues)
    after = apply_crescendo(
        base,
        slots,
        duration_sec=duration_sec,
        bar_times=bars,
        song_marker_times=markers,
        target="last",
        rng=random.Random(2),
    )
    assert all(cue.role is None for lane in after.values() for cue in lane.cues)
