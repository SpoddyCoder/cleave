"""Tests for cleave.stem_pcm."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from cleave.extract import STEM_NAMES
from cleave.stem_pcm import SAMPLE_RATE_HZ, StemPcmBank, _to_mono_float32, samples_per_frame


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


def test_samples_per_frame_default_without_libprojectm() -> None:
    with patch("cleave.projectm._get_lib", side_effect=OSError("no lib")):
        assert samples_per_frame(fps=30) == SAMPLE_RATE_HZ // 30
        assert samples_per_frame(fps=60) == SAMPLE_RATE_HZ // 60
