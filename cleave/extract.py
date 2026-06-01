"""Per-stem librosa feature extraction at native analysis rates."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import librosa
import numpy as np

HOP_LENGTH = 512
BASS_RMS_HOP_MS = 0.02
BASS_SPLIT_HZ = 120.0
N_FFT = 2048

STEM_NAMES = ("drums", "bass", "vocals", "other")


class BassSignals(TypedDict):
    rms: tuple[np.ndarray, np.ndarray]
    sub_bass: tuple[np.ndarray, np.ndarray]
    mid_bass: tuple[np.ndarray, np.ndarray]


class VocalSignals(TypedDict):
    rms: tuple[np.ndarray, np.ndarray]
    pitch_hz: tuple[np.ndarray, np.ndarray]


def stem_paths(stems_dir: Path) -> dict[str, Path]:
    """Map stem names to expected wav paths under *stems_dir*."""
    return {name: stems_dir / f"{name}.wav" for name in STEM_NAMES}


def _load(path: Path | str) -> tuple[np.ndarray, float]:
    y, sr = librosa.load(path, sr=None, mono=True)
    return y, float(sr)


def _frame_times(n_frames: int, sr: float, hop_length: int) -> np.ndarray:
    return librosa.frames_to_time(np.arange(n_frames), sr=sr, hop_length=hop_length)


def _rms_envelope(y: np.ndarray, sr: float, hop_length: int) -> tuple[np.ndarray, np.ndarray]:
    values = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    times = _frame_times(len(values), sr, hop_length)
    return values, times


def _stft_band_filter(
    y: np.ndarray,
    sr: float,
    *,
    low_hz: float | None = None,
    high_hz: float | None = None,
) -> np.ndarray:
    stft = librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    mask = np.ones(len(freqs), dtype=np.float64)
    if low_hz is not None:
        mask[freqs < low_hz] = 0.0
    if high_hz is not None:
        mask[freqs > high_hz] = 0.0
    filtered = librosa.istft(stft * mask[:, np.newaxis], hop_length=HOP_LENGTH, length=len(y))
    return filtered


def extract_drums_onset(path: Path | str) -> tuple[np.ndarray, np.ndarray]:
    """Onset strength envelope from the drum stem."""
    y, sr = _load(path)
    values = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP_LENGTH)
    times = _frame_times(len(values), sr, HOP_LENGTH)
    return values, times


def extract_mix_onset(path: Path | str) -> tuple[np.ndarray, np.ndarray]:
    """Onset strength envelope from the mixed source track."""
    return extract_drums_onset(path)


def extract_bass(path: Path | str) -> BassSignals:
    """RMS envelopes for full bass, sub-bass (<=120 Hz), and mid-bass (>120 Hz)."""
    y, sr = _load(path)
    hop = max(1, int(sr * BASS_RMS_HOP_MS))

    rms = _rms_envelope(y, sr, hop)
    sub_y = _stft_band_filter(y, sr, high_hz=BASS_SPLIT_HZ)
    mid_y = _stft_band_filter(y, sr, low_hz=BASS_SPLIT_HZ)
    sub_bass = _rms_envelope(sub_y, sr, hop)
    mid_bass = _rms_envelope(mid_y, sr, hop)

    return {
        "rms": rms,
        "sub_bass": sub_bass,
        "mid_bass": mid_bass,
    }


def extract_vocals(path: Path | str, *, slow: bool = False) -> VocalSignals:
    """RMS envelope and pitch (Hz); unvoiced frames are NaN."""
    y, sr = _load(path)
    rms = _rms_envelope(y, sr, HOP_LENGTH)

    fmin = librosa.note_to_hz("C2")
    fmax = librosa.note_to_hz("C7")

    if slow:
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=fmin,
            fmax=fmax,
            sr=sr,
            hop_length=HOP_LENGTH,
        )
        pitch = np.where(voiced_flag, f0, np.nan)
    else:
        f0 = librosa.yin(y, fmin=fmin, fmax=fmax, sr=sr, hop_length=HOP_LENGTH)
        pitch = f0.astype(np.float64)
        pitch[(pitch <= 0) | (pitch < fmin) | (pitch > fmax)] = np.nan

    times = _frame_times(len(pitch), sr, HOP_LENGTH)
    return {
        "rms": rms,
        "pitch_hz": (pitch, times),
    }


def extract_other(path: Path | str) -> tuple[np.ndarray, np.ndarray]:
    """Spectral centroid over time."""
    y, sr = _load(path)
    values = librosa.feature.spectral_centroid(
        y=y, sr=sr, hop_length=HOP_LENGTH, n_fft=N_FFT
    )[0]
    times = _frame_times(len(values), sr, HOP_LENGTH)
    return values, times
