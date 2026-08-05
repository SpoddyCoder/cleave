"""Pure domain helpers for project-scoped song markers."""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Literal, Sequence

SongMarkerType = Literal["standard", "crescendo", "diminuendo"]

DEFAULT_SONG_MARKER_TYPE: SongMarkerType = "standard"

SONG_MARKER_TYPES: tuple[SongMarkerType, ...] = (
    "standard",
    "crescendo",
    "diminuendo",
)


@dataclass(frozen=True)
class SongMarker:
    """One project-scoped song marker (time plus structural type)."""

    time: float
    marker_type: SongMarkerType = DEFAULT_SONG_MARKER_TYPE


def cycle_song_marker_type(
    value: SongMarkerType, *, forward: bool
) -> SongMarkerType:
    try:
        index = SONG_MARKER_TYPES.index(value)
    except ValueError:
        index = 0
    delta = 1 if forward else -1
    return SONG_MARKER_TYPES[(index + delta) % len(SONG_MARKER_TYPES)]


def parse_song_marker_type(raw: object) -> SongMarkerType:
    if raw in SONG_MARKER_TYPES:
        return raw  # type: ignore[return-value]
    raise ValueError(f"invalid song marker type: {raw!r}")


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
    markers: Sequence[SongMarker],
    t: float,
    window: float = 2.0,
) -> tuple[tuple[SongMarker, ...], int | None, float | None]:
    """Insert ``t`` into sorted song markers, or replace within ``window`` seconds.

    If any existing marker lies within ``window`` of ``t``, the nearest one is
    replaced (earlier marker on a tie). The replaced marker keeps its type.
    Otherwise ``t`` is inserted as a standard marker in sorted order.

    Returns ``(new_markers, replaced_index, replaced_time)``. On replace,
    ``replaced_index`` is the index of the new marker in ``new_markers`` and
    ``replaced_time`` is the previous time. On insert, both are ``None``.
    """
    t = float(t)
    if not markers:
        return (SongMarker(t),), None, None

    times = [m.time for m in markers]
    idx = nearest_index(times, t)
    if abs(times[idx] - t) <= window:
        old = float(markers[idx].time)
        updated = list(markers)
        updated[idx] = SongMarker(t, markers[idx].marker_type)
        updated.sort(key=lambda m: m.time)
        new_idx = next(i for i, m in enumerate(updated) if m.time == t)
        return tuple(updated), new_idx, old

    updated = list(markers)
    bisect.insort(updated, SongMarker(t), key=lambda m: m.time)
    return tuple(updated), None, None


def format_marker_time(t: float) -> str:
    """Format a song marker time as ``mm:ss.cc`` (minutes, seconds, hundredths)."""
    total_hundredths = max(0, int(round(float(t) * 100.0)))
    minutes = total_hundredths // 6000
    seconds = (total_hundredths % 6000) // 100
    hundredths = total_hundredths % 100
    return f"{minutes:02d}:{seconds:02d}.{hundredths:02d}"
