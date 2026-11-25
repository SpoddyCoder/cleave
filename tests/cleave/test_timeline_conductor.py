"""Tests for cleave.timeline_presets.conductor."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from cleave.cue_roles import CUE_ROLE_BLEND
from cleave.stems import StemSource
from cleave.signals import Signals
from cleave.timeline import (
    LEVEL_QUANTUM,
    SlotCue,
    TimelineLane,
    empty_lane,
    lane_level_at,
)
from cleave.timeline_presets.conductor import (
    CONDUCTOR_ACTIVITY_MIDPOINT,
    CONDUCTOR_GAIN_MAX,
    CONDUCTOR_GAIN_MIN,
    DEFAULT_TIMELINE_PRESET_CONDUCTOR,
    PhraseWeights,
    StemConductor,
    timeline_preset_conductor_display,
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
        SlotCue(t=0.0, level=1.0, blend="black-key", role="lead", cut="none"),
        SlotCue(t=4.0, level=0.0, cut="none"),
    ]
    assert lanes["layer_2"].cues == [
        SlotCue(t=4.0, level=0.5, blend="add", role="pulse", cut="none"),
        SlotCue(t=8.0, level=1.0, blend="add", role="pulse", cut="none"),
    ]


def test_cues_from_states_without_casts_omits_role_blend() -> None:
    slots = ["layer_1"]
    lanes = cues_from_states(slots, [(0.0, {"layer_1": 1.0})])
    assert lanes["layer_1"].cues == [SlotCue(t=0.0, level=1.0, cut="none")]


def test_cues_from_states_always_assigns_cut_none() -> None:
    slots = ["layer_1"]
    lanes = cues_from_states(
        slots,
        [
            (0.0, {"layer_1": 1.0}),
            (10.0, {"layer_1": 0.0}),
            (20.0, {"layer_1": 1.0}),
        ],
    )
    assert lanes["layer_1"].cues == [
        SlotCue(t=0.0, level=1.0, cut="none"),
        SlotCue(t=10.0, level=0.0, cut="none"),
        SlotCue(t=20.0, level=1.0, cut="none"),
    ]


def test_loud_phrase_has_higher_gain() -> None:
    conductor = StemConductor.build(_make_signals(), _slot_stems(), _phrases())
    assert conductor is not None
    assert conductor.phrase_at(5.0).budget_gain == pytest.approx(CONDUCTOR_GAIN_MIN)
    assert conductor.phrase_at(15.0).budget_gain == pytest.approx(CONDUCTOR_GAIN_MAX)
