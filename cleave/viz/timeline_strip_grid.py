"""Which bar and beat lines the timeline strip draws at the current zoom.

Zoomed out, only every second, fourth, eighth... bar is drawn, always counted
from bar 1 so the lines hold still while the strip scrolls. Zoomed in, the
beats between bars join them.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

from cleave.viz.theme import scale_px, ui_scale

_BAR_STEPS: tuple[int, ...] = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)
_MIN_BAR_PX: int = 10
_MIN_BEAT_PX: int = 8


@dataclass(frozen=True)
class GridLines:
    """Times of the lines in view. ``labels`` are ``(time, 1-based bar)``."""

    bars: tuple[float, ...] = ()
    beats: tuple[float, ...] = ()
    labels: tuple[tuple[float, int], ...] = ()


def _typical_gap(times: Sequence[float]) -> float:
    """Median spacing, so a beatless stretch does not widen it. 0 under two times."""
    gaps = [b - a for a, b in zip(times, times[1:]) if b > a]
    return median(gaps) if gaps else 0.0


def _near(times: Sequence[float], t: float, tolerance: float) -> bool:
    """True when *t* is as good as on one of *times*."""
    index = bisect_left(times, t - tolerance)
    return index < len(times) and times[index] <= t + tolerance


def _bar_step(bar_px: float, min_px: float) -> int:
    for step in _BAR_STEPS:
        if step * bar_px >= min_px:
            return step
    return _BAR_STEPS[-1]


def grid_lines(
    bar_times: Sequence[float],
    beat_times: Sequence[float],
    *,
    view_start_sec: float,
    view_end_sec: float,
    bar_width: int,
    min_label_px: int,
) -> GridLines:
    """Lines in the visible window, with labels at least *min_label_px* apart."""
    span = view_end_sec - view_start_sec
    if span <= 0 or bar_width <= 0 or not bar_times:
        return GridLines()
    px_per_sec = bar_width / span
    scale = ui_scale()
    # A lone bar has no spacing to crowd: every line fits.
    bar_px = _typical_gap(bar_times) * px_per_sec or float(bar_width)
    step = _bar_step(bar_px, scale_px(_MIN_BAR_PX, scale=scale))
    label_step = max(step, _bar_step(bar_px, min_label_px))
    first = bisect_left(bar_times, view_start_sec)
    last = bisect_right(bar_times, view_end_sec)
    in_view = range(first, last)
    beats: tuple[float, ...] = ()
    beat_gap = _typical_gap(beat_times)
    if step == 1 and beat_gap * px_per_sec >= scale_px(_MIN_BEAT_PX, scale=scale):
        beats = tuple(
            t
            for t in beat_times[
                bisect_left(beat_times, view_start_sec) : bisect_right(
                    beat_times, view_end_sec
                )
            ]
            if not _near(bar_times, t, beat_gap / 4)
        )
    return GridLines(
        bars=tuple(bar_times[i] for i in in_view if i % step == 0),
        beats=beats,
        labels=tuple((bar_times[i], i + 1) for i in in_view if i % label_step == 0),
    )
