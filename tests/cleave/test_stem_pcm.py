"""Tests for cleave.stem_pcm."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from cleave.extract import STEM_NAMES, stems_dir
from cleave.pcm_io import SAMPLE_RATE_HZ, _to_mono_float32
from cleave.project import write_manifest
from cleave.stem_pcm import StemPcmBank, load_stem_pcm, samples_per_frame


def _make_bank(*, duration_samples: int = 4410) -> StemPcmBank:
    pcm = {
        stem: np.arange(duration_samples, dtype=np.float32) + float(i)
        for i, stem in enumerate(STEM_NAMES)
    }
    return StemPcmBank(
        project_dir=Path("/tmp/test-project"),
        duration_sec=duration_samples / SAMPLE_RATE_HZ,
        _pcm=pcm,
    )


def test_slice_pcm_mid_buffer() -> None:
    bank = _make_bank(duration_samples=10000)
    t_sec = 0.1
    out = bank.slice_pcm("drums", t_sec=t_sec, n_samples=10)
    start = int(t_sec * SAMPLE_RATE_HZ)
    expected = bank._pcm["drums"][start : start + 10]
    np.testing.assert_array_equal(out, expected)


def test_slice_pcm_past_end_zero_pads() -> None:
    bank = _make_bank(duration_samples=1000)
    start = int(0.02 * SAMPLE_RATE_HZ)
    n_samples = 500
    out = bank.slice_pcm("bass", t_sec=0.02, n_samples=n_samples)
    take = min(n_samples, 1000 - start)
    assert out.shape == (n_samples,)
    assert out.dtype == np.float32
    np.testing.assert_array_equal(out[:take], bank._pcm["bass"][start : start + take])
    assert np.all(out[take:] == 0.0)


def test_slice_pcm_past_end_when_start_beyond_buffer() -> None:
    bank = _make_bank(duration_samples=50)
    out = bank.slice_pcm("vocals", t_sec=1.0, n_samples=16)
    assert out.shape == (16,)
    assert np.all(out == 0.0)


@pytest.mark.parametrize("n_samples", [0, -1, -10])
def test_slice_pcm_non_positive_n_samples(n_samples: int) -> None:
    bank = _make_bank()
    out = bank.slice_pcm("other", t_sec=0.0, n_samples=n_samples)
    assert out.size == 0
    assert out.dtype == np.float32


def test_to_mono_float32_mono_passthrough() -> None:
    mono = np.array([0.5, -0.25, 1.0], dtype=np.float64)
    out = _to_mono_float32(mono)
    np.testing.assert_array_equal(out, mono.astype(np.float32))
    assert out.dtype == np.float32
    assert out.flags["C_CONTIGUOUS"]


def test_to_mono_float32_stereo_mean() -> None:
    stereo = np.array([[1.0, 3.0], [0.0, 2.0]], dtype=np.float32)
    out = _to_mono_float32(stereo)
    np.testing.assert_array_equal(out, np.array([2.0, 1.0], dtype=np.float32))


def test_to_mono_float32_output_is_float32_contiguous() -> None:
    stereo = np.arange(6, dtype=np.float64).reshape(3, 2)
    out = _to_mono_float32(stereo)
    assert out.dtype == np.float32
    assert out.flags["C_CONTIGUOUS"]


def test_samples_per_frame_matches_sample_rate_over_fps() -> None:
    assert samples_per_frame(fps=30) == SAMPLE_RATE_HZ // 30
    assert samples_per_frame(fps=60) == SAMPLE_RATE_HZ // 60


def test_samples_per_frame_ignores_libprojectm_max_chunk() -> None:
    mock_lib = MagicMock()
    mock_lib.projectm_pcm_get_max_samples.return_value = 480
    with patch("cleave.projectm._get_lib", return_value=mock_lib):
        assert samples_per_frame(fps=30) == SAMPLE_RATE_HZ // 30


def _write_wav(path: Path, data: np.ndarray) -> None:
    sf.write(path, data, SAMPLE_RATE_HZ, subtype="FLOAT")


def _write_pcm_project(project: Path) -> None:
    stem_root = stems_dir(project)
    stem_root.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(STEM_NAMES):
        _write_wav(
            stem_root / f"{name}.wav",
            np.full(100, float(i + 1), dtype=np.float32),
        )
    mix_path = project / "mix.wav"
    _write_wav(mix_path, np.full(100, 9.0, dtype=np.float32))
    write_manifest(
        project,
        slug="test-project",
        mix_filename="mix.wav",
        original_path=mix_path,
        demucs_model="htdemucs",
    )


def test_load_stem_pcm_includes_full_mix(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_pcm_project(project)

    bank = load_stem_pcm(project)

    assert "full_mix" in bank._pcm
    out = bank.slice_pcm("full_mix", t_sec=0.0, n_samples=5)
    np.testing.assert_array_equal(out, np.full(5, 9.0, dtype=np.float32))


def test_load_stem_pcm_missing_mix_raises(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    stem_root = stems_dir(project)
    stem_root.mkdir(parents=True, exist_ok=True)
    for name in STEM_NAMES:
        _write_wav(stem_root / f"{name}.wav", np.zeros(10, dtype=np.float32))
    write_manifest(
        project,
        slug="test-project",
        mix_filename="missing.wav",
        original_path=project / "missing.wav",
        demucs_model="htdemucs",
    )

    with pytest.raises(FileNotFoundError, match="missing mix wav"):
        load_stem_pcm(project)
