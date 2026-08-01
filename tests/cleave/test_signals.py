"""Tests for cleave.signals."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from cleave.signals import Signals, load_signals, resolve_signals_path
from tests.support.signals import make_signals


def test_resolve_signals_path_file(tmp_path: Path) -> None:
    signals_file = tmp_path / "signals.json"
    signals_file.write_text("{}", encoding="utf-8")
    assert resolve_signals_path(signals_file) == signals_file.resolve()


def test_resolve_signals_path_directory(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    signals_file = project / "signals.json"
    signals_file.write_text("{}", encoding="utf-8")
    assert resolve_signals_path(project) == signals_file.resolve()


def test_load_signals_minimal_fixture(
    minimal_signals_json_path: Path,
) -> None:
    raw = json.loads(minimal_signals_json_path.read_text(encoding="utf-8"))
    assert raw["version"] == 4
    assert "rms" in raw["other"]

    signals = load_signals(minimal_signals_json_path)

    assert signals.path == minimal_signals_json_path.resolve()
    assert signals.sample_rate_hz == 100.0
    assert signals.duration_sec == pytest.approx(0.14)
    assert signals.beat_times == (0.0, 0.5, 1.0)
    assert signals.downbeat_times == (0.0, 1.0)

    pitch = signals.array("vocals", "pitch_hz")
    assert math.isnan(pitch[2])
    assert pitch[0] == pytest.approx(220.0)

    full_mix_onset = signals.array("full_mix", "onset_strength")
    assert full_mix_onset[3] == pytest.approx(0.7)
    full_mix_rms = signals.array("full_mix", "rms")
    assert full_mix_rms[0] == pytest.approx(0.10)
    other_rms = signals.array("other", "rms")
    assert other_rms[0] == pytest.approx(0.02)


def test_load_signals_missing_beat_times_defaults_empty(tmp_path: Path) -> None:
    path = tmp_path / "signals.json"
    path.write_text(
        json.dumps(
            {
                "version": 4,
                "sample_rate_hz": 100,
                "duration_sec": 0.1,
                "drums": {"onset_strength": [0.0]},
                "bass": {"rms": [0.0], "sub_bass": [0.0], "mid_bass": [0.0]},
                "vocals": {"rms": [0.0], "pitch_hz": [220.0]},
                "other": {"spectral_centroid": [1000.0], "rms": [0.0]},
                "full_mix": {"onset_strength": [0.0], "rms": [0.0]},
            }
        ),
        encoding="utf-8",
    )
    signals = load_signals(path)
    assert signals.beat_times == ()
    assert signals.downbeat_times == ()


def test_load_signals_rejects_version_1(tmp_path: Path) -> None:
    path = tmp_path / "signals.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "sample_rate_hz": 100,
                "duration_sec": 0.1,
                "drums": {"onset_strength": [0.0]},
                "bass": {"rms": [0.0], "sub_bass": [0.0], "mid_bass": [0.0]},
                "vocals": {"rms": [0.0], "pitch_hz": [220.0]},
                "other": {"spectral_centroid": [1000.0]},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsupported signals.json version"):
        load_signals(path)


def test_load_signals_rejects_version_2(tmp_path: Path) -> None:
    path = tmp_path / "signals.json"
    path.write_text(
        json.dumps(
            {
                "version": 2,
                "sample_rate_hz": 100,
                "duration_sec": 0.1,
                "beat_times": [0.0, 0.5],
                "drums": {"onset_strength": [0.0]},
                "bass": {"rms": [0.0], "sub_bass": [0.0], "mid_bass": [0.0]},
                "vocals": {"rms": [0.0], "pitch_hz": [220.0]},
                "other": {"spectral_centroid": [1000.0]},
                "full_mix": {"onset_strength": [0.0], "rms": [0.0]},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsupported signals.json version"):
        load_signals(path)


def test_load_signals_rejects_version_3(tmp_path: Path) -> None:
    path = tmp_path / "signals.json"
    path.write_text(
        json.dumps(
            {
                "version": 3,
                "sample_rate_hz": 100,
                "duration_sec": 0.1,
                "drums": {"onset_strength": [0.0]},
                "bass": {"rms": [0.0], "sub_bass": [0.0], "mid_bass": [0.0]},
                "vocals": {"rms": [0.0], "pitch_hz": [220.0]},
                "other": {"spectral_centroid": [1000.0]},
                "full_mix": {"onset_strength": [0.0], "rms": [0.0]},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        ValueError, match=r"re-run: python -m cleave separate <project>"
    ):
        load_signals(path)


def test_load_signals_rejects_missing_full_mix(tmp_path: Path) -> None:
    path = tmp_path / "signals.json"
    path.write_text(
        json.dumps(
            {
                "version": 4,
                "sample_rate_hz": 100,
                "duration_sec": 0.1,
                "drums": {"onset_strength": [0.0]},
                "bass": {"rms": [0.0], "sub_bass": [0.0], "mid_bass": [0.0]},
                "vocals": {"rms": [0.0], "pitch_hz": [220.0]},
                "other": {"spectral_centroid": [1000.0], "rms": [0.0]},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing stem section"):
        load_signals(path)


def test_load_signals_rejects_missing_other_rms(tmp_path: Path) -> None:
    path = tmp_path / "signals.json"
    path.write_text(
        json.dumps(
            {
                "version": 4,
                "sample_rate_hz": 100,
                "duration_sec": 0.1,
                "drums": {"onset_strength": [0.0]},
                "bass": {"rms": [0.0], "sub_bass": [0.0], "mid_bass": [0.0]},
                "vocals": {"rms": [0.0], "pitch_hz": [220.0]},
                "other": {"spectral_centroid": [1000.0]},
                "full_mix": {"onset_strength": [0.0], "rms": [0.0]},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="other missing key"):
        load_signals(path)


def test_sample_clamps_below_zero(minimal_signals: Signals) -> None:
    assert minimal_signals.sample("drums", "onset_strength", -1.0) == pytest.approx(
        0.0
    )


def test_sample_clamps_past_end(minimal_signals: Signals) -> None:
    at_end = minimal_signals.sample("drums", "onset_strength", 0.02)
    past_end = minimal_signals.sample("drums", "onset_strength", 99.0)
    assert past_end == pytest.approx(at_end)


def test_sample_interpolates(minimal_signals: Signals) -> None:
    # [0.0, 0.5, 1.0] at 100 Hz: t=0.005 is halfway between index 0 and 1
    value = minimal_signals.sample("drums", "onset_strength", 0.005)
    assert value == pytest.approx(0.25)


def test_normalized_percentile_scaling() -> None:
    signals = make_signals("drums", "onset_strength", [0.0, 50.0, 100.0])
    normed = signals.normalized("drums", "onset_strength", percentile=99.0)
    scale = float(np.percentile(signals.array("drums", "onset_strength"), 99.0))
    expected = signals.array("drums", "onset_strength") / scale
    np.testing.assert_allclose(normed, expected)


def test_normalized_empty_array() -> None:
    signals = make_signals("drums", "onset_strength", [])
    normed = signals.normalized("drums", "onset_strength")
    assert normed.size == 0


def test_normalized_uses_cache() -> None:
    signals = make_signals("drums", "onset_strength", [0.0, 1.0, 2.0])
    first = signals.normalized("drums", "onset_strength", percentile=99.0)
    second = signals.normalized("drums", "onset_strength", percentile=99.0)
    assert first is second


def test_window_mean_range() -> None:
    signals = make_signals("drums", "onset_strength", [0.0, 50.0, 100.0, 50.0, 0.0])
    # indices [1, 3) at 100 Hz -> t in [0.01, 0.03)
    mean = signals.window_mean("drums", "onset_strength", 0.01, 0.03)
    normed = signals.normalized("drums", "onset_strength")
    assert mean == pytest.approx(float(np.nanmean(normed[1:3])))


def test_window_mean_clamps_and_empty_slice() -> None:
    signals = make_signals("drums", "onset_strength", [10.0, 20.0, 30.0])
    assert signals.window_mean("drums", "onset_strength", -1.0, 0.0) == pytest.approx(
        0.0
    )
    assert signals.window_mean("drums", "onset_strength", 0.05, 0.05) == pytest.approx(
        0.0
    )


def test_window_mean_nan_safe() -> None:
    signals = Signals(
        sample_rate_hz=100.0,
        duration_sec=0.02,
        path=Path("."),
        stems={
            "drums": {
                "onset_strength": np.array([np.nan, np.nan, np.nan], dtype=np.float64)
            }
        },
    )
    assert signals.window_mean("drums", "onset_strength", 0.0, 0.03) == pytest.approx(
        0.0
    )
