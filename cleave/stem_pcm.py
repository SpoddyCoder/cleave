"""Preloaded per-stem PCM at 44.1 kHz for libprojectM audio feed."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from cleave.extract import STEM_NAMES, StemSource, stem_paths
from cleave.pcm_io import SAMPLE_RATE_HZ, load_wav_pcm_44k
from cleave.project import mix_path


@dataclass
class StemPcmBank:
    project_dir: Path
    duration_sec: float
    _pcm: dict[str, np.ndarray] = field(repr=False)
    _channels: dict[str, int] = field(repr=False)
    sample_rate_hz: int = SAMPLE_RATE_HZ

    def pcm(self, stem: StemSource) -> np.ndarray:
        """Preloaded float32 PCM for *stem* (mono 1D or interleaved stereo)."""
        return self._pcm[stem]

    def channels(self, stem: StemSource) -> int:
        """Channel count for *stem* (1 mono, 2 interleaved stereo)."""
        return self._channels[stem]

    def slice_pcm(self, stem: StemSource, t_sec: float, n_samples: int) -> np.ndarray:
        """Return per-channel *n_samples* of float32 PCM from *t_sec*, zero-padded past end."""
        pcm = self._pcm[stem]
        ch = self._channels[stem]
        if n_samples <= 0:
            return np.array([], dtype=np.float32)

        t_sec = max(t_sec, 0.0)
        start_frame = int(t_sec * self.sample_rate_hz)
        n_out = n_samples * ch
        out = np.zeros(n_out, dtype=np.float32)
        start = start_frame * ch
        if start >= len(pcm):
            return out

        take = min(n_out, len(pcm) - start)
        out[:take] = pcm[start : start + take]
        return out


def samples_per_frame(fps: int = 60) -> int:
    """PCM samples to feed libprojectM per visual frame at *fps*."""
    return SAMPLE_RATE_HZ // fps


def load_stem_pcm(project_dir: Path) -> StemPcmBank:
    """Load five audio sources from *project_dir* into memory."""
    project_dir = project_dir.resolve()
    paths = stem_paths(project_dir)
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"missing stem wav(s) in {project_dir}: {', '.join(missing)}"
        )

    mix = mix_path(project_dir)
    if not mix.is_file():
        raise FileNotFoundError(f"missing mix wav in {project_dir}: {mix.name}")

    pcm: dict[str, np.ndarray] = {}
    channels: dict[str, int] = {}
    for name in STEM_NAMES:
        pcm[name], channels[name] = load_wav_pcm_44k(paths[name])
    pcm["full_mix"], channels["full_mix"] = load_wav_pcm_44k(mix)

    duration_sec = max(len(pcm[s]) // channels[s] for s in pcm) / SAMPLE_RATE_HZ
    return StemPcmBank(
        project_dir=project_dir,
        duration_sec=duration_sec,
        _pcm=pcm,
        _channels=channels,
    )
