"""Shared PCM loading for stems and mix playback."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soxr
import soundfile as sf

SAMPLE_RATE_HZ = 44100


def _to_stereo_interleaved(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        mono = data
        stereo = np.column_stack([mono, mono])
    elif data.shape[1] == 1:
        mono = data[:, 0]
        stereo = np.column_stack([mono, mono])
    else:
        stereo = data[:, :2]
    return np.ascontiguousarray(stereo.reshape(-1), dtype=np.float32)


def load_wav_pcm_44k(path: Path) -> tuple[np.ndarray, int]:
    """Load a wav as float32 PCM at 44.1 kHz in native channel layout."""
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    if data.shape[1] == 1:
        frames = data
        channels = 1
    else:
        frames = data[:, :2]
        channels = 2
    if sr != SAMPLE_RATE_HZ:
        frames = soxr.resample(frames, sr, SAMPLE_RATE_HZ)
    pcm = np.ascontiguousarray(np.asarray(frames).reshape(-1), dtype=np.float32)
    return pcm, channels


def load_mix_pcm(path: Path) -> tuple[np.ndarray, int]:
    """Load mix audio as interleaved stereo float32 at 44.1 kHz."""
    pcm, channels = load_wav_pcm_44k(path)
    if channels == 1:
        pcm = _to_stereo_interleaved(pcm)
    return pcm, SAMPLE_RATE_HZ
