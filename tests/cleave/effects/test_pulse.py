"""Tests for pulse effect sampling, opacity, and runtime wiring."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from cleave.effects.constants import PULSE_DECAY, PULSE_GAIN
from cleave.effects.pulse import (
    PulseEnvelopeState,
    effective_opacity,
    update_envelope,
)
from cleave.effects.runtime import EffectRuntime
from cleave.effects.sampling import sample_normalized
from cleave.extract import STEM_NAMES
from cleave.preset_playlist import playlist_at_dir
from cleave.signals import Signals
from cleave.viz.controls import LayerRuntime, TuningSession
from tests.support.signals import make_onset_signals, make_signals


def _layer_runtime(stem: str, *, opacity_pct: int = 50, effects: dict | None = None) -> LayerRuntime:
    return LayerRuntime(
        playlist=playlist_at_dir(Path(f"/tmp/presets/{stem}"), index=0),
        browse_floor=Path(f"/tmp/presets/{stem}"),
        opacity_pct=opacity_pct,
        effects=effects or {},
    )


def test_effective_opacity_at_zero_is_static() -> None:
    assert effective_opacity(0.5, 0, 0.8) == 0.5
    assert effective_opacity(0.5, 0, 0.0) == 0.5


def test_effective_opacity_at_full_tracks_signal() -> None:
    assert effective_opacity(0.4, 100, 0.5) == 0.2
    assert effective_opacity(0.4, 100, 1.0) == 0.4


def test_effective_opacity_lerp_half() -> None:
    assert effective_opacity(1.0, 50, 0.0) == 0.5


def test_update_envelope_uses_decay_and_gain() -> None:
    assert update_envelope(0.8, 0.2, driver_slug="onset") == max(0.8 * 0.92, 0.2)
    assert update_envelope(0.1, 0.9, driver_slug="onset") == 0.9


@pytest.mark.parametrize(
    ("driver_slug", "decay", "gain"),
    [
        ("onset", 0.92, 1.0),
        ("sub_bass", 0.96, 1.0),
        ("mid_bass", 0.94, 1.0),
        ("rms", 0.96, 1.0),
        ("centroid", 0.98, 1.0),
    ],
)
def test_pulse_decay_gain_constants(driver_slug: str, decay: float, gain: float) -> None:
    assert PULSE_DECAY[driver_slug] == decay
    assert PULSE_GAIN[driver_slug] == gain
    assert update_envelope(0.5, 0.3, driver_slug=driver_slug) == max(
        0.5 * decay, 0.3 * gain
    )


def test_sample_normalized_interpolates() -> None:
    signals = make_onset_signals([0.0, 1.0])
    assert sample_normalized(signals, "drums", "onset_strength", 0.0) == 0.0
    mid = sample_normalized(signals, "drums", "onset_strength", 0.005)
    assert 0.0 < mid < 1.0


def test_pulse_envelope_state_tracks_playback() -> None:
    signals = make_onset_signals([0.0, 1.0, 0.0])
    state = PulseEnvelopeState()
    first = state.sample_and_update(
        signals, "drums", "onset_strength", "onset", 0.01
    )
    second = state.sample_and_update(
        signals, "drums", "onset_strength", "onset", 0.02
    )
    assert first > 0.0
    assert second >= first * 0.92 or second > 0.0


def test_effect_runtime_all_stems_pulse_modulate() -> None:
    signals = Signals(
        sample_rate_hz=100.0,
        duration_sec=0.02,
        source=None,
        path=__file__,
        stems={
            "drums": {"onset_strength": np.array([0.0, 1.0, 0.0])},
            "bass": {
                "sub_bass": np.array([0.0, 0.8, 0.0]),
                "mid_bass": np.array([0.0, 0.6, 0.0]),
            },
            "vocals": {"rms": np.array([0.0, 0.7, 0.0])},
            "other": {"spectral_centroid": np.array([0.0, 0.5, 0.0])},
        },
    )
    session = TuningSession(
        layer_z_order=list(STEM_NAMES),
        layers={
            "drums": _layer_runtime(
                "drums", effects={"pulse": {"onset": 100}}
            ),
            "bass": _layer_runtime(
                "bass", effects={"pulse": {"sub_bass": 100}}
            ),
            "vocals": _layer_runtime(
                "vocals", effects={"pulse": {"rms": 100}}
            ),
            "other": _layer_runtime(
                "other", effects={"pulse": {"centroid": 100}}
            ),
        },
    )
    runtime = EffectRuntime()
    mods = runtime.tick(session, signals, 0.02)
    for stem in STEM_NAMES:
        assert mods[stem].opacity != 0.5


def test_effect_runtime_bass_multi_pulse_stacking() -> None:
    # Non-proportional shapes so per-array normalization yields distinct samples.
    signals = Signals(
        sample_rate_hz=100.0,
        duration_sec=0.03,
        source=None,
        path=__file__,
        stems={
            "bass": {
                "sub_bass": np.array([0.0, 1.0, 0.3, 0.0]),
                "mid_bass": np.array([0.0, 0.3, 1.0, 0.0]),
            },
        },
    )
    session = TuningSession(
        layer_z_order=["bass"],
        layers={
            "bass": _layer_runtime(
                "bass",
                opacity_pct=100,
                effects={"pulse": {"sub_bass": 100, "mid_bass": 100}},
            ),
        },
    )
    runtime = EffectRuntime()
    runtime.tick(session, signals, 0.01)
    sub_state = runtime._pulse_state("bass", "pulse", "sub_bass")
    mid_state = runtime._pulse_state("bass", "pulse", "mid_bass")
    assert sub_state.envelope != mid_state.envelope

    mods = runtime.tick(session, signals, 0.02)
    sub_env = sub_state.envelope
    mid_env = mid_state.envelope
    expected = effective_opacity(1.0, 100, sub_env)
    expected = effective_opacity(expected, 100, mid_env)
    assert mods["bass"].opacity == pytest.approx(expected)
    assert mods["bass"].opacity != effective_opacity(1.0, 100, sub_env)


@pytest.mark.parametrize(
    ("stem", "key", "driver_slug", "values"),
    [
        ("drums", "onset_strength", "onset", [0.0, 1.0, 0.0]),
        ("bass", "sub_bass", "sub_bass", [0.0, 0.9, 0.0]),
        ("bass", "mid_bass", "mid_bass", [0.0, 0.7, 0.0]),
        ("vocals", "rms", "rms", [0.0, 0.8, 0.0]),
        ("other", "spectral_centroid", "centroid", [0.0, 0.6, 0.0]),
    ],
)
def test_effect_runtime_pulse_driver_modulates_opacity(
    stem: str, key: str, driver_slug: str, values: list[float]
) -> None:
    signals = make_signals(stem, key, values)
    session = TuningSession(
        layer_z_order=[stem],
        layers={
            stem: _layer_runtime(
                stem,
                opacity_pct=50,
                effects={"pulse": {driver_slug: 100}},
            ),
        },
    )
    runtime = EffectRuntime()
    baseline = runtime.tick(session, signals, 0.0)
    modulated = runtime.tick(session, signals, 0.01)
    assert modulated[stem].opacity != baseline[stem].opacity
