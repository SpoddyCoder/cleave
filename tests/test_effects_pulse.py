"""Tests for pulse effect sampling, opacity, and config wiring."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import yaml

from cleave.config import CleaveConfig, LayerConfig, PathsConfig, VisualizerConfig, clamp_effect_pct, _parse_layers
from cleave.config_snapshot import write_session_snapshot
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
from cleave.viz_tuning_controls import LayerRuntime, TuningSession


def _signals_with_onset(values: list[float]) -> Signals:
    arr = np.array(values, dtype=np.float64)
    return Signals(
        sample_rate_hz=100.0,
        duration_sec=(len(values) - 1) / 100.0,
        source=None,
        path=__file__,
        stems={"drums": {"onset_strength": arr}},
    )


def _signals_with_stem_key(stem: str, key: str, values: list[float]) -> Signals:
    arr = np.array(values, dtype=np.float64)
    return Signals(
        sample_rate_hz=100.0,
        duration_sec=(len(values) - 1) / 100.0,
        source=None,
        path=__file__,
        stems={stem: {key: arr}},
    )


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
    signals = _signals_with_onset([0.0, 1.0])
    assert sample_normalized(signals, "drums", "onset_strength", 0.0) == 0.0
    mid = sample_normalized(signals, "drums", "onset_strength", 0.005)
    assert 0.0 < mid < 1.0


def test_pulse_envelope_state_tracks_playback() -> None:
    signals = _signals_with_onset([0.0, 1.0, 0.0])
    state = PulseEnvelopeState()
    first = state.sample_and_update(
        signals, "drums", "onset_strength", "onset", 0.01
    )
    second = state.sample_and_update(
        signals, "drums", "onset_strength", "onset", 0.02
    )
    assert first > 0.0
    assert second >= first * 0.92 or second > 0.0


def test_clamp_effect_pct() -> None:
    assert clamp_effect_pct(-5) == 0
    assert clamp_effect_pct(150) == 100
    assert clamp_effect_pct(42.4) == 42


def test_parse_layers_reads_effects() -> None:
    preset_root = Path("/tmp/presets")
    layers_raw = {
        name: {"preset": f"{name}/anchor.milk"} for name in STEM_NAMES
    }
    layers_raw["drums"]["effects"] = {"pulse": {"onset": 75}}
    layers = _parse_layers({"layers": layers_raw}, preset_root)
    assert layers["drums"].effects == {"pulse": {"onset": 75}}
    assert layers["bass"].effects == {}


def test_parse_layers_rejects_invalid_effect() -> None:
    preset_root = Path("/tmp/presets")
    layers_raw = {
        name: {"preset": f"{name}/anchor.milk"} for name in STEM_NAMES
    }
    layers_raw["drums"]["effects"] = {"ripple": {"onset": 10}}
    with pytest.raises(ValueError, match="unknown effect"):
        _parse_layers({"layers": layers_raw}, preset_root)


def test_write_session_snapshot_sparse_effects() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        for name in STEM_NAMES:
            stem_dir = preset_root / name
            stem_dir.mkdir(parents=True)
            (stem_dir / "anchor.milk").write_text("milk")

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                name: LayerConfig(preset=preset_root / name / "anchor.milk")
                for name in STEM_NAMES
            },
            visualizer=VisualizerConfig(),
            config_path=config_path,
        )

        session = TuningSession(
            layer_z_order=list(STEM_NAMES),
            layers={
                name: LayerRuntime(
                    playlist=playlist_at_dir(preset_root / name, index=0),
                    browse_floor=preset_root / name,
                    effects={"pulse": {"onset": 60}} if name == "drums" else {},
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layers"]["drums"]["effects"] == {"pulse": {"onset": 60}}
        assert "effects" not in data["layers"]["bass"]


def test_write_session_snapshot_sparse_all_effect_types() -> None:
    """Non-zero effect keys persist; zero drivers and empty effect groups are omitted."""
    session_effects: dict[str, dict[str, dict[str, int]]] = {
        "drums": {
            "pulse": {"onset": 35},
            "flare": {"onset": 20},
            "flash": {"onset": 15},
            "grit": {"onset": 10},
        },
        "bass": {
            "pulse": {"sub_bass": 40, "mid_bass": 0},
            "flash": {"sub_bass": 10},
            "grit": {"sub_bass": 5},
        },
        "vocals": {
            "pulse": {"rms": 45},
            "hue": {"pitch": 25},
            "flash": {"rms": 10},
            "grit": {"rms": 0},
        },
        "other": {
            "pulse": {"centroid": 30},
            "flash": {"centroid": 0},
            "grit": {"centroid": 5},
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        for name in STEM_NAMES:
            stem_dir = preset_root / name
            stem_dir.mkdir(parents=True)
            (stem_dir / "anchor.milk").write_text("milk")

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                name: LayerConfig(preset=preset_root / name / "anchor.milk")
                for name in STEM_NAMES
            },
            visualizer=VisualizerConfig(),
            config_path=config_path,
        )

        session = TuningSession(
            layer_z_order=list(STEM_NAMES),
            layers={
                name: LayerRuntime(
                    playlist=playlist_at_dir(preset_root / name, index=0),
                    browse_floor=preset_root / name,
                    effects=session_effects[name],
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layers"]["drums"]["effects"] == session_effects["drums"]
        assert data["layers"]["bass"]["effects"] == {
            "pulse": {"sub_bass": 40},
            "flash": {"sub_bass": 10},
            "grit": {"sub_bass": 5},
        }
        assert data["layers"]["vocals"]["effects"] == {
            "pulse": {"rms": 45},
            "hue": {"pitch": 25},
            "flash": {"rms": 10},
        }
        assert data["layers"]["other"]["effects"] == {
            "pulse": {"centroid": 30},
            "grit": {"centroid": 5},
        }

        round_trip = _parse_layers({"layers": data["layers"]}, preset_root)
        assert round_trip["drums"].effects == session_effects["drums"]
        assert round_trip["bass"].effects["pulse"] == {"sub_bass": 40}
        assert round_trip["vocals"].effects["hue"] == {"pitch": 25}


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
    signals = _signals_with_stem_key(stem, key, values)
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
