"""Shared signal sampling helpers for compositor effects."""

from __future__ import annotations

from cleave.signals import Signals


def sample_normalized(signals: Signals, stem: str, key: str, t_sec: float) -> float:
    values = signals.normalized(stem, key)
    if len(values) == 0:
        return 0.0

    sr = signals.sample_rate_hz
    t_max = (len(values) - 1) / sr
    t = min(max(t_sec, 0.0), t_max)
    pos = t * sr
    i = int(pos)
    if i >= len(values) - 1:
        return float(values[-1])
    frac = pos - i
    return float(values[i] * (1.0 - frac) + values[i + 1] * frac)
