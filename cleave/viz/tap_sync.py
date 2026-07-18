"""Tap-to-sync inference for machine-local wireless delay."""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from cleave.viz.transport_clock import MAX_RESIDUAL_DELAY_SEC

MIN_TAP_COUNT = 4


def _nearest_beat_delta(tap_sec: float, beat_times: Sequence[float]) -> float | None:
    if not beat_times:
        return None
    nearest = min(beat_times, key=lambda beat: abs(beat - tap_sec))
    return tap_sec - nearest


def infer_residual_delay_sec(
    tap_audible_zero_residual: Sequence[float],
    beat_times: Sequence[float],
) -> float:
    """Infer residual delay from taps captured with residual forced to zero."""
    if len(tap_audible_zero_residual) < MIN_TAP_COUNT or not beat_times:
        return 0.0

    deltas: list[float] = []
    for tap in tap_audible_zero_residual:
        delta = _nearest_beat_delta(tap, beat_times)
        if delta is not None:
            deltas.append(delta)

    if len(deltas) < MIN_TAP_COUNT:
        return 0.0

    return max(0.0, min(statistics.median(deltas), MAX_RESIDUAL_DELAY_SEC))
