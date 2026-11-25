"""Bar-grid thinning for timeline generation."""

from __future__ import annotations

import statistics

import pytest

from cleave.timeline_presets.grid import thin_bar_times_for_arrange


def _dense_middle_bars(duration_sec: float = 60.0) -> list[float]:
    """Sparse ~2s bars with a short dense ~0.25s burst (median stays ~2s)."""
    bars: list[float] = []
    t = 0.0
    while t < 24.0 - 1e-9:
        bars.append(round(t, 6))
        t += 2.0
    t = 24.0
    while t < 28.0 - 1e-9:
        bars.append(round(t, 6))
        t += 0.25
    t = 28.0
    while t < duration_sec - 1e-9:
        bars.append(round(t, 6))
        t += 2.0
    return bars


def test_thin_bar_times_dense_middle() -> None:
    duration_sec = 60.0
    raw = _dense_middle_bars(duration_sec)
    thinned = thin_bar_times_for_arrange(raw, duration_sec)
    assert thinned[0] == raw[0]
    assert abs(thinned[-1] - raw[-1]) < 1e-9

    gaps = [thinned[i + 1] - thinned[i] for i in range(len(thinned) - 1)]
    median_raw = statistics.median(
        [raw[i + 1] - raw[i] for i in range(len(raw) - 1)]
    )
    assert median_raw == pytest.approx(2.0, abs=0.05)
    assert min(gaps) >= 0.75 * median_raw - 1e-6
    # Dense 0.25s chatter in the middle must not survive thinning.
    middle = [g for t0, _t1, g in zip(thinned, thinned[1:], gaps) if 24.0 <= t0 < 28.0]
    assert middle
    assert min(middle) >= 1.4
