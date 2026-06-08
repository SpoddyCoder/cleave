"""Tests for cleave.pcm_io."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from cleave.pcm_io import SAMPLE_RATE_HZ, load_mix_pcm, load_wav_mono_44k


def _write_wav(path: Path, data: np.ndarray, sr: int) -> None:
    sf.write(path, data, sr, subtype="FLOAT")


def test_load_wav_mono_44k_from_mono(tmp_path: Path) -> None:
    path = tmp_path / "mono.wav"
    mono = np.array([0.25, -0.5, 1.0], dtype=np.float32)
    _write_wav(path, mono, SAMPLE_RATE_HZ)
    out = load_wav_mono_44k(path)
    np.testing.assert_array_equal(out, mono)


def test_load_wav_mono_44k_stereo_becomes_mean(tmp_path: Path) -> None:
    path = tmp_path / "stereo.wav"
    stereo = np.array([[1.0, 3.0], [0.0, 2.0]], dtype=np.float32)
    _write_wav(path, stereo, SAMPLE_RATE_HZ)
    out = load_wav_mono_44k(path)
    np.testing.assert_array_equal(out, np.array([2.0, 1.0], dtype=np.float32))


def test_load_mix_pcm_mono_duplicates_to_stereo(tmp_path: Path) -> None:
    path = tmp_path / "mono.wav"
    mono = np.array([0.5, -0.25], dtype=np.float32)
    _write_wav(path, mono, SAMPLE_RATE_HZ)
    pcm, sr = load_mix_pcm(path)
    assert sr == SAMPLE_RATE_HZ
    np.testing.assert_array_equal(pcm, np.array([0.5, 0.5, -0.25, -0.25], dtype=np.float32))


def test_load_mix_pcm_stereo_interleaved(tmp_path: Path) -> None:
    path = tmp_path / "stereo.wav"
    stereo = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    _write_wav(path, stereo, SAMPLE_RATE_HZ)
    pcm, sr = load_mix_pcm(path)
    assert sr == SAMPLE_RATE_HZ
    np.testing.assert_array_equal(pcm, np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32))
