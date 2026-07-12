"""Pure domain helpers for project-scoped song markers."""

from __future__ import annotations

import bisect
from typing import Sequence


def nearest_index(times: Sequence[float], t: float) -> int:
    """Return the index of the song marker nearest to ``t``.

    On an exact distance tie, prefers the earlier marker (lower index).
    """
    if not times:
        raise ValueError("nearest_index requires at least one song marker")
    best_i = 0
    best_d = abs(times[0] - t)
    for i in range(1, len(times)):
        d = abs(times[i] - t)
        if d < best_d:
            best_i = i
            best_d = d
    return best_i


def place_marker(
    times: Sequence[float],
    t: float,
    window: float = 2.0,
) -> tuple[tuple[float, ...], int | None, float | None]:
    """Insert ``t`` into sorted song markers, or replace within ``window`` seconds.

    If any existing marker lies within ``window`` of ``t``, the nearest one is
    replaced (earlier marker on a tie). Otherwise ``t`` is inserted in sorted
    order.

    Returns ``(new_times, replaced_index, replaced_time)``. On replace,
    ``replaced_index`` is the index of the new marker in ``new_times`` and
    ``replaced_time`` is the previous time. On insert, both are ``None``.
    """
    if not times:
        return (float(t),), None, None

    idx = nearest_index(times, t)
    if abs(times[idx] - t) <= window:
        old = float(times[idx])
        updated = [float(x) for x in times]
        updated[idx] = float(t)
        updated.sort()
        new_idx = updated.index(float(t))
        return tuple(updated), new_idx, old

    updated = [float(x) for x in times]
    bisect.insort(updated, float(t))
    return tuple(updated), None, None


def format_marker_time(t: float) -> str:
    """Format a song marker time as ``mm:ss.cc`` (minutes, seconds, hundredths)."""
    total_hundredths = max(0, int(round(float(t) * 100.0)))
    minutes = total_hundredths // 6000
    seconds = (total_hundredths % 6000) // 100
    hundredths = total_hundredths % 100
    return f"{minutes:02d}:{seconds:02d}.{hundredths:02d}"
