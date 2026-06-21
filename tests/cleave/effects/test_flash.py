"""Tests for flash burst triggers, decay, and EffectRuntime integration."""

from __future__ import annotations

import numpy as np
import pytest

from cleave.effects.flash import (
    FLASH_DECAY,
    FLASH_THRESHOLD_CONTINUOUS,
    FLASH_THRESHOLD_ONSET,
    FlashBurstState,
    flash_alpha,
    flash_threshold,
    update_burst,
)
from cleave.effects.registry import EffectDef
from cleave.effects.runtime import EffectRuntime
from cleave.extract import STEM_NAMES
from cleave.preset_playlist import playlist_at_dir
from cleave.signals import Signals
from cleave.viz.session import LayerRuntime, TuningSession
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


def test_flash_threshold_onset_vs_continuous() -> None:
    assert flash_threshold("onset") == FLASH_THRESHOLD_ONSET
    assert flash_threshold("sub_bass") == FLASH_THRESHOLD_CONTINUOUS
    assert flash_threshold("rms") == FLASH_THRESHOLD_CONTINUOUS
    assert flash_threshold("centroid") == FLASH_THRESHOLD_CONTINUOUS


def test_update_burst_onset_requires_higher_signal() -> None:
    below = update_burst(0.0, 0.60, driver_slug="onset")
    above = update_burst(0.0, 0.70, driver_slug="onset")
    assert below == 0.0
    assert above == pytest.approx((0.70 - FLASH_THRESHOLD_ONSET) * 1.8)


def test_update_burst_continuous_driver_threshold() -> None:
    below = update_burst(0.0, 0.45, driver_slug="rms")
    above = update_burst(0.0, 0.55, driver_slug="rms")
    assert below == 0.0
    assert above == pytest.approx((0.55 - FLASH_THRESHOLD_CONTINUOUS) * 1.8)


def test_update_burst_decays_without_trigger() -> None:
    decayed = update_burst(0.5, 0.0, driver_slug="onset")
    assert decayed == pytest.approx(0.5 * FLASH_DECAY)


def test_update_burst_trigger_beats_decay_same_frame() -> None:
    burst = update_burst(0.5, 0.80, driver_slug="onset")
    expected_hit = (0.80 - FLASH_THRESHOLD_ONSET) * 1.8
    assert burst == pytest.approx(max(0.5 * FLASH_DECAY, expected_hit))


def test_flash_alpha_scales_with_depth_and_burst() -> None:
    assert flash_alpha(0, 1.0) == 0.0
    assert flash_alpha(100, 0.5) == pytest.approx(0.5)
    assert flash_alpha(50, 0.4) == pytest.approx(0.2)


def test_flash_burst_can_remain_after_pulse_opacity_fades() -> None:
    from cleave.effects.pulse import effective_opacity

    assert effective_opacity(1.0, 100, 0.0) == 0.0
    assert flash_alpha(100, 0.12) > 0.0


def test_flash_burst_state_decays_toward_zero() -> None:
    signals = _signals_with_stem_key("drums", "onset_strength", [0.0, 0.0, 0.0])
    state = FlashBurstState(burst=1.0)
    row = EffectDef("flash", "onset", "drums", "onset_strength")
    for t_sec in (0.0, 0.01):
        state.sample_and_update(signals, row, t_sec)
    assert 0.0 < state.burst < 1.0
    assert state.burst == pytest.approx(FLASH_DECAY**2)


def test_effect_runtime_flash_per_layer_isolation() -> None:
    signals = Signals(
        sample_rate_hz=100.0,
        duration_sec=0.02,
        path=__file__,
        stems={
            "drums": {"onset_strength": np.array([0.0, 1.0, 0.0])},
            "bass": {"sub_bass": np.array([0.0, 0.0, 0.0])},
        },
    )
    session = TuningSession(
        layer_z_order=["layer_1", "layer_2"],
        layers={
            "layer_1": _layer_runtime("drums", effects={"flash": {"onset": 100}}),
            "layer_2": _layer_runtime("bass", effects={"flash": {"sub_bass": 100}}),
        },
    )
    runtime = EffectRuntime()
    mods = runtime.tick(session, signals, 0.01)
    assert mods["layer_1"].flash_alpha > 0.0
    assert mods["layer_2"].flash_alpha == 0.0


@pytest.mark.parametrize(
    ("stem", "key", "driver_slug", "values"),
    [
        ("drums", "onset_strength", "onset", [0.0, 1.0, 0.0]),
        ("bass", "sub_bass", "sub_bass", [0.0, 0.9, 0.0]),
        ("vocals", "rms", "rms", [0.0, 0.8, 0.0]),
        ("other", "spectral_centroid", "centroid", [0.0, 0.7, 0.0]),
    ],
)
def test_effect_runtime_flash_driver_triggers(
    stem: str, key: str, driver_slug: str, values: list[float]
) -> None:
    signals = _signals_with_stem_key(stem, key, values)
    slot = SLOT_FOR_STEM[stem]
    session = TuningSession(
        layer_z_order=[slot],
        layers={
            slot: _layer_runtime(stem, effects={"flash": {driver_slug: 100}}),
        },
    )
    runtime = EffectRuntime()
    baseline = runtime.tick(session, signals, 0.0)
    triggered = runtime.tick(session, signals, 0.01)
    assert baseline[slot].flash_alpha == 0.0
    assert triggered[slot].flash_alpha > 0.0


def test_effect_runtime_flash_zero_depth_is_noop() -> None:
    signals = _signals_with_stem_key("drums", "onset_strength", [0.0, 1.0, 0.0])
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={"layer_1": _layer_runtime("drums", effects={"flash": {"onset": 0}})},
    )
    runtime = EffectRuntime()
    mods = runtime.tick(session, signals, 0.01)
    assert mods["layer_1"].flash_alpha == 0.0


def test_effect_runtime_all_stems_expose_flash_modifier() -> None:
    signals = Signals(
        sample_rate_hz=100.0,
        duration_sec=0.02,
        path=__file__,
        stems={
            "drums": {"onset_strength": np.array([0.0, 1.0, 0.0])},
            "bass": {"sub_bass": np.array([0.0, 0.9, 0.0])},
            "vocals": {"rms": np.array([0.0, 0.8, 0.0])},
            "other": {"spectral_centroid": np.array([0.0, 0.7, 0.0])},
        },
    )
    flash_effects = {
        "drums": {"flash": {"onset": 100}},
        "bass": {"flash": {"sub_bass": 100}},
        "vocals": {"flash": {"rms": 100}},
        "other": {"flash": {"centroid": 100}},
    }
    session = TuningSession(
        layer_z_order=list(DEFAULT_LAYER_SLOTS),
        layers={
            slot: _layer_runtime(TEST_LAYER_STEMS[slot], effects=flash_effects[TEST_LAYER_STEMS[slot]])
            for slot in DEFAULT_LAYER_SLOTS
        },
    )
    runtime = EffectRuntime()
    mods = runtime.tick(session, signals, 0.01)
    for slot in DEFAULT_LAYER_SLOTS:
        assert mods[slot].flash_alpha > 0.0