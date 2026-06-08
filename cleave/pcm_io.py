"""Shared PCM loading for stems and mix playback."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

SAMPLE_RATE_HZ = 44100


def _to_mono_float32(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        mono = data
    else:
        mono = data.mean(axis=1)
    return np.ascontiguousarray(mono, dtype=np.float32)


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


def _resample_stereo_interleaved(
    pcm: np.ndarray, *, orig_sr: int, target_sr: int
) -> np.ndarray:
    frames = pcm.reshape(-1, 2)
    left = librosa.resample(frames[:, 0], orig_sr=orig_sr, target_sr=target_sr)
    right = librosa.resample(frames[:, 1], orig_sr=orig_sr, target_sr=target_sr)
    stereo = np.column_stack([left, right])
    return np.ascontiguousarray(stereo.reshape(-1), dtype=np.float32)


def load_wav_mono_44k(path: Path) -> np.ndarray:
    """Load a wav as mono float32 PCM at 44.1 kHz."""
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = _to_mono_float32(data)
    if sr != SAMPLE_RATE_HZ:
        mono = librosa.resample(mono, orig_sr=sr, target_sr=SAMPLE_RATE_HZ)
        mono = np.ascontiguousarray(mono, dtype=np.float32)
    return mono


def load_mix_pcm(path: Path) -> tuple[np.ndarray, int]:
    """Load mix audio as interleaved stereo float32 at 44.1 kHz."""
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    pcm = _to_stereo_interleaved(data)
    if sr != SAMPLE_RATE_HZ:
        pcm = _resample_stereo_interleaved(pcm, orig_sr=sr, target_sr=SAMPLE_RATE_HZ)
    return pcm, SAMPLE_RATE_HZ
