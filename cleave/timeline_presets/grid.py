"""Bar-grid helpers for timeline preset arrange (generation only)."""

from __future__ import annotations

import statistics
from collections.abc import Sequence

# Keep bars at least this fraction of the song median gap apart when thinning.
_THIN_GAP_FACTOR = 0.75


def thin_bar_times_for_arrange(
    bar_times: Sequence[float],
    duration_sec: float,
) -> list[float]:
    """Thin over-dense downbeats toward the song median bar interval.

    Used only for preset generation. Overlay / snap keep the full detection list.
    """
    bars = [t for t in bar_times if 0.0 <= t < duration_sec]
    if len(bars) < 3:
        return list(bars)

    gaps = [bars[i + 1] - bars[i] for i in range(len(bars) - 1)]
    if len(gaps) < 2:
        return list(bars)

    median_gap = statistics.median(gaps)
    if median_gap <= 1e-12:
        return list(bars)

    threshold = _THIN_GAP_FACTOR * median_gap
    kept: list[float] = [bars[0]]
    for t in bars[1:-1]:
        if t - kept[-1] >= threshold - 1e-12:
            kept.append(t)
    last = bars[-1]
    if abs(last - kept[-1]) > 1e-12:
        kept.append(last)
    return kept
