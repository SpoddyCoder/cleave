"""Tests for grit envelope, scaling, and EffectRuntime integration."""

from __future__ import annotations

from pathlib import Path

from cleave.config_schema import DEFAULT_STEM_FOR_SLOT, LAYER_SLOTS

SLOT_FOR_STEM = {v: k for k, v in DEFAULT_STEM_FOR_SLOT.items()}

import numpy as np
import pytest

from cleave.effects.constants import PULSE_DECAY, PULSE_GAIN
from cleave.effects.grit import (
    ABERRATION_MAX_PX,
    GRIT_SCALE,
    GritState,
    aberration_px,
    grit_strength,
)
from cleave.effects.registry import EffectDef
from cleave.effects.pulse import update_envelope
from cleave.effects.runtime import EffectRuntime
from cleave.extract import STEM_NAMES
from cleave.preset_playlist import playlist_at_dir
from cleave.signals import Signals
from cleave.viz.session import LayerRuntime, TuningSession


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
    audio = DEFAULT_STEM_FOR_SLOT.get(slot, stem)
    return LayerRuntime(
        playlist=playlist_at_dir(Path(f"/tmp/presets/{slot}"), index=0),
        browse_floor=Path(f"/tmp/presets/{slot}"),
        stem=audio,
        opacity_pct=opacity_pct,
        effects=effects or {},
    )


def test_grit_strength_scales_with_envelope_and_depth() -> None:
    assert grit_strength(0, 1.0) == 0.0
    assert grit_strength(100, 0.0) == 0.0
    assert grit_strength(100, 1.0) == pytest.approx(GRIT_SCALE)
    assert grit_strength(50, 0.8) == pytest.approx(0.5 * 0.8 * GRIT_SCALE)


def test_aberration_px_scales_with_envelope_and_depth() -> None:
    assert aberration_px(0, 1.0) == 0.0
    assert aberration_px(100, 0.0) == 0.0
    assert aberration_px(100, 1.0) == pytest.approx(ABERRATION_MAX_PX)
    assert aberration_px(50, 0.6) == pytest.approx(ABERRATION_MAX_PX * 0.6 * 0.5)


@pytest.mark.parametrize(
    ("driver_slug", "decay", "gain"),
    [
        ("onset", 0.92, 1.0),
        ("sub_bass", 0.96, 1.0),
        ("rms", 0.96, 1.0),
        ("centroid", 0.98, 1.0),
    ],
)
def test_grit_envelope_uses_pulse_decay_gain(
    driver_slug: str, decay: float, gain: float
) -> None:
    assert PULSE_DECAY[driver_slug] == decay
    assert PULSE_GAIN[driver_slug] == gain
    assert update_envelope(0.5, 0.3, driver_slug=driver_slug) == max(
        0.5 * decay, 0.3 * gain
    )


def test_grit_state_tracks_envelope() -> None:
    signals = _signals_with_stem_key("drums", "onset_strength", [0.0, 1.0, 0.0])
    state = GritState()
    row = EffectDef("grit", "onset", "drums", "onset_strength")
    first = state.sample_and_update(signals, row, 0.01)
    second = state.sample_and_update(signals, row, 0.02)
    assert first > 0.0
    assert second >= first * PULSE_DECAY["onset"] or second > 0.0


def test_effect_runtime_grit_triggers_on_signal_peak() -> None:
    signals = _signals_with_stem_key("drums", "onset_strength", [0.0, 1.0, 0.0])
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": _layer_runtime("drums", effects={"grit": {"onset": 100}}),
        },
    )
    runtime = EffectRuntime()
    baseline = runtime.tick(session, signals, 0.0)
    triggered = runtime.tick(session, signals, 0.01)
    assert baseline["layer_1"].grit_strength == 0.0
    assert baseline["layer_1"].aberration_px == 0.0
    assert triggered["layer_1"].grit_strength > 0.0
    assert triggered["layer_1"].aberration_px > 0.0


def test_effect_runtime_grit_zero_depth_is_noop() -> None:
    signals = _signals_with_stem_key("drums", "onset_strength", [0.0, 1.0, 0.0])
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={"layer_1": _layer_runtime("drums", effects={"grit": {"onset": 0}})},
    )
    runtime = EffectRuntime()
    mods = runtime.tick(session, signals, 0.01)
    assert mods["layer_1"].grit_strength == 0.0
    assert mods["layer_1"].aberration_px == 0.0


@pytest.mark.parametrize(
    ("stem", "key", "driver_slug", "values"),
    [
        ("drums", "onset_strength", "onset", [0.0, 1.0, 0.0]),
        ("bass", "sub_bass", "sub_bass", [0.0, 0.9, 0.0]),
        ("vocals", "rms", "rms", [0.0, 0.8, 0.0]),
        ("other", "spectral_centroid", "centroid", [0.0, 0.6, 0.0]),
    ],
)
def test_effect_runtime_grit_per_stem(
    stem: str, key: str, driver_slug: str, values: list[float]
) -> None:
    signals = _signals_with_stem_key(stem, key, values)
    slot = SLOT_FOR_STEM[stem]
    session = TuningSession(
        layer_z_order=[slot],
        layers={
            slot: _layer_runtime(stem, effects={"grit": {driver_slug: 100}}),
        },
    )
    runtime = EffectRuntime()
    baseline = runtime.tick(session, signals, 0.0)
    modulated = runtime.tick(session, signals, 0.01)
    assert baseline[slot].grit_strength == 0.0
    assert modulated[slot].grit_strength > 0.0
    assert modulated[slot].aberration_px > 0.0


def test_effect_runtime_grit_all_stems() -> None:
    signals = Signals(
        sample_rate_hz=100.0,
        duration_sec=0.02,
        path=__file__,
        stems={
            "drums": {"onset_strength": np.array([0.0, 1.0, 0.0])},
            "bass": {"sub_bass": np.array([0.0, 0.9, 0.0])},
            "vocals": {"rms": np.array([0.0, 0.8, 0.0])},
            "other": {"spectral_centroid": np.array([0.0, 0.6, 0.0])},
        },
    )
    session = TuningSession(
        layer_z_order=list(LAYER_SLOTS),
        layers={
            "layer_1": _layer_runtime("drums", effects={"grit": {"onset": 100}}),
            "layer_2": _layer_runtime("bass", effects={"grit": {"sub_bass": 100}}),
            "layer_3": _layer_runtime("vocals", effects={"grit": {"rms": 100}}),
            "layer_4": _layer_runtime("other", effects={"grit": {"centroid": 100}}),
        },
    )
    runtime = EffectRuntime()
    mods = runtime.tick(session, signals, 0.01)
    for slot in LAYER_SLOTS:
        assert mods[slot].grit_strength > 0.0
        assert mods[slot].aberration_px > 0.0
