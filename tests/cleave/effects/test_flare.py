"""Tests for flare burst triggers, decay, and EffectRuntime integration."""

from __future__ import annotations

import numpy as np
import pytest

from cleave.effects.flare import (
    FLARE_DECAY,
    FLARE_DELTA,
    FLARE_THRESHOLD,
    FlareBurstState,
    bloom_strength,
    flare_triggered,
    update_burst,
    update_smoothed,
)
from cleave.effects.registry import EffectDef
from cleave.effects.runtime import EffectRuntime
from cleave.signals import Signals
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.preset_playlist import playlist_at_dir
from pathlib import Path

from cleave.config_schema import DEFAULT_LAYER_SLOTS
from tests.support.config import TEST_LAYER_STEMS

SLOT_FOR_STEM = {v: k for k, v in TEST_LAYER_STEMS.items()}


def _signals_with_stem_key(stem: str, key: str, values: list[float]) -> Signals:
    arr = np.array(values, dtype=np.float64)
    return Signals(
        sample_rate_hz=100.0,
        duration_sec=(len(values) - 1) / 100.0,
        path=__file__,
        stems={stem: {key: arr}},
    )


def _layer_runtime(stem: str, *, opacity_pct: int = 50, effects: dict | None = None) -> LayerRuntime:
    slot = SLOT_FOR_STEM.get(stem, stem)
    audio = TEST_LAYER_STEMS.get(slot, stem)
    return LayerRuntime(
        playlist=playlist_at_dir(Path(f"/tmp/presets/{slot}"), index=0),
        browse_floor=Path(f"/tmp/presets/{slot}"),
        stem=audio,
        opacity_pct=opacity_pct,
        effects=effects or {},
    )


def test_flare_triggered_by_onset_threshold() -> None:
    assert flare_triggered(0.60, 0.20, 0.15) is True
    assert flare_triggered(0.50, 0.20, 0.15) is False


def test_flare_triggered_by_smoothed_delta() -> None:
    raw = 0.40
    prev_smoothed = 0.20
    smoothed = update_smoothed(prev_smoothed, raw)
    delta = smoothed - prev_smoothed
    assert delta > FLARE_DELTA
    assert flare_triggered(raw, smoothed, prev_smoothed) is True


def test_update_burst_instant_attack_on_trigger() -> None:
    burst = update_burst(
        0.0,
        0.70,
        smoothed=0.70,
        prev_smoothed=0.10,
    )
    assert burst == 1.0


def test_update_burst_decays_without_trigger() -> None:
    decayed = update_burst(
        0.5,
        0.0,
        smoothed=0.0,
        prev_smoothed=0.0,
    )
    assert decayed == pytest.approx(0.5 * FLARE_DECAY)


def test_update_burst_trigger_beats_decay_same_frame() -> None:
    burst = update_burst(
        0.5,
        0.70,
        smoothed=0.70,
        prev_smoothed=0.10,
    )
    assert burst == pytest.approx(max(0.5 * FLARE_DECAY, 1.0))


def test_bloom_strength_scales_with_depth_and_burst() -> None:
    assert bloom_strength(0, 1.0) == 0.0
    assert bloom_strength(100, 0.5) == pytest.approx(0.5)
    assert bloom_strength(50, 0.4) == pytest.approx(0.2)


def test_flare_burst_state_decays_toward_zero() -> None:
    signals = _signals_with_stem_key("drums", "onset_strength", [0.0, 0.0, 0.0])
    state = FlareBurstState(burst=1.0, smoothed=0.0)
    row = EffectDef("flare", "onset", "drums", "onset_strength")
    for t_sec in (0.0, 0.01):
        state.sample_and_update(signals, row, t_sec)
    assert 0.0 < state.burst < 1.0
    assert state.burst == pytest.approx(FLARE_DECAY**2)


def test_effect_runtime_flare_triggers_on_onset_peak() -> None:
    signals = _signals_with_stem_key("drums", "onset_strength", [0.0, 1.0, 0.0])
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": _layer_runtime("drums", effects={"flare": {"onset": 100}}),
        },
    )
    runtime = EffectRuntime()
    baseline = runtime.tick(session, signals, 0.0)
    triggered = runtime.tick(session, signals, 0.01)
    assert baseline["layer_1"].bloom_strength == 0.0
    assert triggered["layer_1"].bloom_strength > 0.0


def test_effect_runtime_flare_zero_depth_is_noop() -> None:
    signals = _signals_with_stem_key("drums", "onset_strength", [0.0, 1.0, 0.0])
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={"layer_1": _layer_runtime("drums", effects={"flare": {"onset": 0}})},
    )
    runtime = EffectRuntime()
    mods = runtime.tick(session, signals, 0.01)
    assert mods["layer_1"].bloom_strength == 0.0


def test_effect_runtime_flare_only_on_drums() -> None:
    signals = Signals(
        sample_rate_hz=100.0,
        duration_sec=0.02,
        path=__file__,
        stems={
            "drums": {"onset_strength": np.array([0.0, 1.0, 0.0])},
            "bass": {"sub_bass": np.array([0.0, 0.9, 0.0])},
        },
    )
    session = TuningSession(
        layer_z_order=["layer_1", "layer_2"],
        layers={
            "layer_1": _layer_runtime("drums", effects={"flare": {"onset": 100}}),
            "layer_2": _layer_runtime("bass", effects={}),
        },
    )
    runtime = EffectRuntime()
    mods = runtime.tick(session, signals, 0.01)
    assert mods["layer_1"].bloom_strength > 0.0
    assert mods["layer_2"].bloom_strength == 0.0


def test_flare_threshold_constant() -> None:
    assert FLARE_THRESHOLD == 0.55
    assert flare_triggered(FLARE_THRESHOLD + 0.01, 0.0, 0.0) is True
    assert flare_triggered(FLARE_THRESHOLD - 0.01, 0.0, 0.0) is False