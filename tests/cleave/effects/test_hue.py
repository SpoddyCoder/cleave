"""Tests for pitch-driven hue tint, unvoiced hold/decay, and EffectRuntime integration."""

from __future__ import annotations

import math

import numpy as np
import pytest

from cleave.effects.hue import (
    HUE_DECAY_UNVOICED,
    HUE_LERP,
    NEUTRAL_HUE_DEG,
    PITCH_MAX_HZ,
    PITCH_MIN_HZ,
    HueState,
    hue_mix_pct,
    hue_rgb,
    is_voiced_pitch,
    lerp_hue,
    pitch_to_hue,
    sample_pitch_hz,
    update_hue,
)
from cleave.effects.registry import EffectDef
from cleave.effects.runtime import EffectRuntime
from cleave.preset_playlist import playlist_at_dir
from cleave.signals import Signals
from cleave.viz.session import LayerRuntime, TuningSession
from pathlib import Path


def _signals_with_pitch(values: list[float]) -> Signals:
    arr = np.array(values, dtype=np.float64)
    return Signals(
        sample_rate_hz=100.0,
        duration_sec=(len(values) - 1) / 100.0,
        path=__file__,
        stems={"vocals": {"pitch_hz": arr}},
    )


def _layer_runtime(stem: str, *, effects: dict | None = None) -> LayerRuntime:
    return LayerRuntime(
        playlist=playlist_at_dir(Path(f"/tmp/presets/{stem}"), index=0),
        browse_floor=Path(f"/tmp/presets/{stem}"),
        opacity_pct=50,
        effects=effects or {},
    )


def test_pitch_to_hue_min_max_mid() -> None:
    assert pitch_to_hue(PITCH_MIN_HZ) == pytest.approx(0.0)
    assert pitch_to_hue(PITCH_MAX_HZ) == pytest.approx(300.0)
    mid_hz = (PITCH_MIN_HZ + PITCH_MAX_HZ) / 2.0
    assert pitch_to_hue(mid_hz) == pytest.approx(150.0)


def test_pitch_to_hue_clamps_out_of_range() -> None:
    assert pitch_to_hue(40.0) == pytest.approx(0.0)
    assert pitch_to_hue(1200.0) == pytest.approx(300.0)


def test_is_voiced_pitch_rejects_nan_and_nonpositive() -> None:
    assert not is_voiced_pitch(float("nan"))
    assert not is_voiced_pitch(0.0)
    assert not is_voiced_pitch(-10.0)
    assert is_voiced_pitch(200.0)


def test_sample_pitch_hz_interpolates_and_propagates_nan() -> None:
    signals = _signals_with_pitch([200.0, 400.0, 600.0])
    assert sample_pitch_hz(signals, "vocals", "pitch_hz", 0.0) == pytest.approx(200.0)
    assert sample_pitch_hz(signals, "vocals", "pitch_hz", 0.005) == pytest.approx(300.0)

    nan_signals = _signals_with_pitch([200.0, float("nan")])
    assert sample_pitch_hz(nan_signals, "vocals", "pitch_hz", 0.0) == pytest.approx(200.0)
    assert math.isnan(sample_pitch_hz(nan_signals, "vocals", "pitch_hz", 0.005))


def test_voiced_pitch_shifts_hue_toward_target() -> None:
    state = HueState(hue_deg=NEUTRAL_HUE_DEG, last_hue=NEUTRAL_HUE_DEG)
    target = pitch_to_hue(440.0)
    update_hue(state, 440.0)
    assert state.last_hue == pytest.approx(target)
    expected = lerp_hue(NEUTRAL_HUE_DEG, target, HUE_LERP)
    assert state.hue_deg == pytest.approx(expected)


def test_unvoiced_holds_last_hue_and_decays_toward_neutral() -> None:
    state = HueState(hue_deg=NEUTRAL_HUE_DEG, last_hue=NEUTRAL_HUE_DEG)
    voiced_target = pitch_to_hue(440.0)
    update_hue(state, 440.0)
    stored_last = state.last_hue
    assert stored_last == pytest.approx(voiced_target)

    pre_unvoiced = state.hue_deg
    update_hue(state, float("nan"))
    assert state.last_hue == pytest.approx(stored_last)
    assert state.hue_deg == pytest.approx(
        lerp_hue(pre_unvoiced, NEUTRAL_HUE_DEG, HUE_DECAY_UNVOICED)
    )


def test_hue_state_unvoiced_frames_continue_decay() -> None:
    signals = _signals_with_pitch([440.0, float("nan"), float("nan")])
    state = HueState()
    row = EffectDef("hue", "pitch", "vocals", "pitch_hz")
    state.sample_and_update(signals, row, 0.0)
    voiced_hue = state.hue_deg
    state.sample_and_update(signals, row, 0.01)
    after_one = state.hue_deg
    state.sample_and_update(signals, row, 0.02)
    after_two = state.hue_deg
    assert state.last_hue == pytest.approx(pitch_to_hue(440.0))
    assert after_one != pytest.approx(voiced_hue)
    assert abs(after_two - NEUTRAL_HUE_DEG) < abs(after_one - NEUTRAL_HUE_DEG)


def test_hue_rgb_returns_unit_float_factors() -> None:
    rgb = hue_rgb(120.0)
    assert all(0.0 <= c <= 1.0 for c in rgb)
    assert rgb != (1.0, 1.0, 1.0)


def test_hue_mix_pct_scales_depth() -> None:
    assert hue_mix_pct(0) == 0.0
    assert hue_mix_pct(100) == pytest.approx(1.0)
    assert hue_mix_pct(25) == pytest.approx(0.25)


def test_effect_runtime_hue_vocals_only() -> None:
    signals = _signals_with_pitch([200.0, 600.0])
    session = TuningSession(
        layer_z_order=["vocals", "drums"],
        layers={
            "vocals": _layer_runtime("vocals", effects={"hue": {"pitch": 100}}),
            "drums": _layer_runtime("drums", effects={"hue": {"pitch": 100}}),
        },
    )
    runtime = EffectRuntime()
    mods_low = runtime.tick(session, signals, 0.0)
    mods_high = runtime.tick(session, signals, 0.01)
    assert mods_low["vocals"].hue_mix == pytest.approx(1.0)
    assert mods_high["vocals"].hue_mix == pytest.approx(1.0)
    assert mods_low["vocals"].hue_rgb != mods_high["vocals"].hue_rgb
    assert mods_low["drums"].hue_mix == 0.0
    assert mods_low["drums"].hue_rgb == (1.0, 1.0, 1.0)


def test_effect_runtime_hue_zero_depth_is_noop() -> None:
    signals = _signals_with_pitch([440.0, 440.0])
    session = TuningSession(
        layer_z_order=["vocals"],
        layers={"vocals": _layer_runtime("vocals", effects={"hue": {"pitch": 0}})},
    )
    runtime = EffectRuntime()
    mods = runtime.tick(session, signals, 0.0)
    assert mods["vocals"].hue_mix == 0.0
    assert mods["vocals"].hue_rgb == (1.0, 1.0, 1.0)
