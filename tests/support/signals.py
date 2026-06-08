"""Shared signal factories for unit tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from cleave.signals import Signals

_SAMPLE_RATE_HZ = 100.0


def make_signals(
    stem: str,
    key: str,
    values: list[float],
    *,
    path: Path | None = None,
) -> Signals:
    arr = np.array(values, dtype=np.float64)
    return Signals(
        sample_rate_hz=_SAMPLE_RATE_HZ,
        duration_sec=(len(values) - 1) / _SAMPLE_RATE_HZ,
        path=path or Path(__file__),
        stems={stem: {key: arr}},
    )


def make_onset_signals(
    values: list[float],
    *,
    path: Path | None = None,
) -> Signals:
    return make_signals("drums", "onset_strength", values, path=path)
