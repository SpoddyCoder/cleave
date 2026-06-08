"""Preloaded per-stem PCM at 44.1 kHz for libprojectM audio feed."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from cleave.extract import STEM_NAMES, stem_paths

SAMPLE_RATE_HZ = 44100


def _to_mono_float32(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        mono = data
    else:
        mono = data.mean(axis=1)
    return np.ascontiguousarray(mono, dtype=np.float32)


def _load_stem_wav(path: Path) -> np.ndarray:
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = _to_mono_float32(data)
    if sr != SAMPLE_RATE_HZ:
        mono = librosa.resample(mono, orig_sr=sr, target_sr=SAMPLE_RATE_HZ)
        mono = np.ascontiguousarray(mono, dtype=np.float32)
    return mono


@dataclass
class StemPcmBank:
    project_dir: Path
    duration_sec: float
    _pcm: dict[str, np.ndarray] = field(repr=False)
    sample_rate_hz: int = SAMPLE_RATE_HZ

    def slice_pcm(self, stem: str, t_sec: float, n_samples: int) -> np.ndarray:
        """Return *n_samples* of mono float32 PCM from *t_sec*, zero-padded past end."""
        pcm = self._pcm[stem]
        if n_samples <= 0:
            return np.array([], dtype=np.float32)

        t_sec = max(t_sec, 0.0)
        start = int(t_sec * self.sample_rate_hz)
        out = np.zeros(n_samples, dtype=np.float32)
        if start >= len(pcm):
            return out

        take = min(n_samples, len(pcm) - start)
        out[:take] = pcm[start : start + take]
        return out


def samples_per_frame(fps: int = 60) -> int:
    """PCM samples to feed libprojectM per visual frame at *fps*."""
    n = SAMPLE_RATE_HZ // fps
    try:
        from cleave.projectm import _get_lib

        max_n = int(_get_lib().projectm_pcm_get_max_samples())
        if max_n > 0:
            n = min(n, max_n)
    except OSError:
        pass
    return n


def load_stem_pcm(project_dir: Path) -> StemPcmBank:
    """Load all four stem wavs from *project_dir* into memory."""
    project_dir = project_dir.resolve()
    paths = stem_paths(project_dir)
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"missing stem wav(s) in {project_dir}: {', '.join(missing)}"
        )

    pcm: dict[str, np.ndarray] = {}
    for name in STEM_NAMES:
        pcm[name] = _load_stem_wav(paths[name])

    duration_sec = max(len(arr) for arr in pcm.values()) / SAMPLE_RATE_HZ
    return StemPcmBank(
        project_dir=project_dir,
        duration_sec=duration_sec,
        _pcm=pcm,
    )
