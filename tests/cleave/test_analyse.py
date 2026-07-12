"""Tests for cleave.analyse."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from cleave.analyse import run_analyse
from cleave.extract import STEM_NAMES, stems_dir
from cleave.project import write_manifest


def _stub_signal(length: int = 4) -> tuple[np.ndarray, np.ndarray]:
    values = np.linspace(0.0, 1.0, length, dtype=np.float64)
    times = np.arange(length, dtype=np.float64) * 0.01
    return values, times


def _stub_bass() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    signal = _stub_signal()
    return {"rms": signal, "sub_bass": signal, "mid_bass": signal}


def _stub_vocals() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    values, times = _stub_signal()
    return {"rms": (values, times), "pitch_hz": (values, times)}


def _write_project(project: Path) -> None:
    project.mkdir()
    stem_root = stems_dir(project)
    stem_root.mkdir(parents=True, exist_ok=True)
    for name in STEM_NAMES:
        (stem_root / f"{name}.wav").write_bytes(b"wav")
    mix = project / "mix.wav"
    mix.write_bytes(b"wav")
    write_manifest(
        project,
        slug="test-project",
        mix_filename="mix.wav",
        original_path=mix,
        demucs_model="htdemucs",
    )


@patch("cleave.analyse.extract_mix_rms", return_value=_stub_signal())
@patch("cleave.analyse.extract_mix_onset", return_value=_stub_signal())
@patch("cleave.analyse.extract_other", return_value=_stub_signal())
@patch("cleave.analyse.extract_vocals", return_value=_stub_vocals())
@patch("cleave.analyse.extract_bass", return_value=_stub_bass())
@patch(
    "cleave.analyse.extract_beats_downbeats",
    return_value=(np.array([0.5, 1.0, 1.5]), np.array([0.5, 1.5])),
)
@patch("cleave.analyse.extract_drums_onset", return_value=_stub_signal())
@patch("cleave.analyse._stem_duration_sec", return_value=1.0)
def test_run_analyse_writes_version_3_full_mix(
    _duration: object,
    _drums: object,
    beats_downbeats: object,
    _bass: object,
    _vocals: object,
    _other: object,
    _mix_onset: object,
    _mix_rms: object,
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    _write_project(project)

    signals_path = run_analyse(project, high_quality=False)
    data = json.loads(signals_path.read_text(encoding="utf-8"))

    assert data["version"] == 3
    assert data["beat_detection_stem"] == "full_mix"
    assert "mix_onset_strength" not in data["drums"]
    assert set(data["full_mix"]) == {"onset_strength", "rms"}
    assert len(data["full_mix"]["onset_strength"]) > 0
    assert len(data["full_mix"]["rms"]) > 0
    assert data["beat_times"] == [0.5, 1.0, 1.5]
    assert data["downbeat_times"] == [0.5, 1.5]
    beats_downbeats.assert_called_once_with(project / "mix.wav")


@patch("cleave.analyse.extract_mix_rms", return_value=_stub_signal())
@patch("cleave.analyse.extract_mix_onset", return_value=_stub_signal())
@patch("cleave.analyse.extract_other", return_value=_stub_signal())
@patch("cleave.analyse.extract_vocals", return_value=_stub_vocals())
@patch("cleave.analyse.extract_bass", return_value=_stub_bass())
@patch(
    "cleave.analyse.extract_beats_downbeats",
    return_value=(np.array([0.5, 1.0]), np.array([0.5])),
)
@patch("cleave.analyse.extract_drums_onset", return_value=_stub_signal())
@patch("cleave.analyse._stem_duration_sec", return_value=1.0)
def test_run_analyse_uses_beat_detection_stem_path(
    _duration: object,
    _drums: object,
    beats_downbeats: object,
    _bass: object,
    _vocals: object,
    _other: object,
    _mix_onset: object,
    _mix_rms: object,
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    _write_project(project)

    signals_path = run_analyse(
        project, high_quality=False, beat_detection_stem="drums"
    )
    data = json.loads(signals_path.read_text(encoding="utf-8"))

    assert data["beat_detection_stem"] == "drums"
    beats_downbeats.assert_called_once_with(stems_dir(project) / "drums.wav")


@patch("cleave.analyse.extract_mix_rms", return_value=_stub_signal())
@patch("cleave.analyse.extract_mix_onset", return_value=_stub_signal())
@patch("cleave.analyse.extract_other", return_value=_stub_signal())
@patch("cleave.analyse.extract_vocals", return_value=_stub_vocals())
@patch("cleave.analyse.extract_bass", return_value=_stub_bass())
@patch(
    "cleave.analyse.extract_beats_downbeats",
    return_value=(np.array([]), np.array([])),
)
@patch("cleave.analyse.extract_drums_onset", return_value=_stub_signal())
@patch("cleave.analyse._stem_duration_sec", return_value=1.0)
def test_run_analyse_empty_beats_warns_and_persists_empty(
    _duration: object,
    _drums: object,
    _beats_downbeats: object,
    _bass: object,
    _vocals: object,
    _other: object,
    _mix_onset: object,
    _mix_rms: object,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "project"
    _write_project(project)

    signals_path = run_analyse(project, high_quality=False)
    data = json.loads(signals_path.read_text(encoding="utf-8"))

    assert data["beat_times"] == []
    assert data["downbeat_times"] == []
    assert data["beat_detection_stem"] == "full_mix"
    out = capsys.readouterr().out
    assert "full-mix beat detection produced no useful data" in out
    assert "full-mix downbeat detection produced no useful data" in out


@patch(
    "cleave.extract._rms_envelope",
    return_value=(np.array([0.1, 0.2, 0.3]), np.array([0.0, 0.02, 0.04])),
)
@patch("cleave.extract._load", return_value=(np.zeros(22050), 44100.0))
def test_extract_mix_rms_returns_matching_lengths(
    _load: object,
    _rms: object,
    tmp_path: Path,
) -> None:
    from cleave.extract import extract_mix_rms

    path = tmp_path / "mix.wav"
    path.write_bytes(b"wav")
    values, times = extract_mix_rms(path)
    assert len(values) == len(times)
    assert len(values) > 0
    _load.assert_called_once_with(path)
    _rms.assert_called_once()
