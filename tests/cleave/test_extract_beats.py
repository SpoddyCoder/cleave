"""Tempo-aware drum beat tracking."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from cleave.extract import extract_drums_beats


def _tempo_step_clicks(
    *,
    sr: int,
    bpm_slow: float,
    bpm_fast: float,
    sec_slow: float,
    sec_fast: float,
) -> np.ndarray:
    """Impulse clicks that step from bpm_slow to bpm_fast at sec_slow."""
    n = int(sr * (sec_slow + sec_fast))
    y = np.zeros(n, dtype=np.float32)
    click_n = max(1, int(0.01 * sr))
    click = np.sin(2 * np.pi * 1000.0 * np.arange(click_n) / sr).astype(np.float32)
    click *= np.linspace(1.0, 0.0, click_n, dtype=np.float32)

    def _place(start_sec: float, end_sec: float, bpm: float) -> None:
        t = start_sec
        period = 60.0 / bpm
        while t < end_sec:
            i = int(t * sr)
            end = min(n, i + click_n)
            y[i:end] += click[: end - i]
            t += period

    _place(0.0, sec_slow, bpm_slow)
    _place(sec_slow, sec_slow + sec_fast, bpm_fast)
    peak = float(np.max(np.abs(y)))
    if peak > 0.0:
        y /= peak
    return y


def test_extract_drums_beats_tracks_tempo_step(tmp_path: Path) -> None:
    """Detected inter-beat intervals should shrink after a tempo increase."""
    sr = 22050
    bpm_slow, bpm_fast = 90.0, 140.0
    sec_slow, sec_fast = 4.0, 4.0
    path = tmp_path / "tempo_step.wav"
    sf.write(
        path,
        _tempo_step_clicks(
            sr=sr,
            bpm_slow=bpm_slow,
            bpm_fast=bpm_fast,
            sec_slow=sec_slow,
            sec_fast=sec_fast,
        ),
        sr,
    )

    beats = extract_drums_beats(path)
    assert len(beats) >= 8

    # Ignore a small window around the tempo change.
    margin = 0.25
    early = beats[beats < sec_slow - margin]
    late = beats[beats > sec_slow + margin]
    assert len(early) >= 3
    assert len(late) >= 3

    early_ibi = float(np.median(np.diff(early)))
    late_ibi = float(np.median(np.diff(late)))
    assert late_ibi < early_ibi * 0.85
    assert abs(early_ibi - 60.0 / bpm_slow) < 0.08
    assert abs(late_ibi - 60.0 / bpm_fast) < 0.08
