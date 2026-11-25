"""Pure domain helpers for project-scoped song markers."""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Callable, Literal, Sequence

from cleave.choice import step_choice

SongMarkerType = Literal[
    "standard",
    "intro",
    "verse",
    "build",
    "chorus",
    "drop",
    "breakdown",
    "bridge",
    "outro",
]

DEFAULT_SONG_MARKER_TYPE: SongMarkerType = "standard"

SONG_MARKER_TYPES: tuple[SongMarkerType, ...] = (
    "standard",
    "intro",
    "verse",
    "build",
    "chorus",
    "drop",
    "breakdown",
    "bridge",
    "outro",
)

SONG_MARKER_TYPE_HELP: dict[SongMarkerType, str] = {
    "standard": (
        "a plain section change. It ends the section before it, and the character sets how busy this one is. With conductor on, one layer gets an accent in layers mode."
    ),
    "intro": "a calm opening on one layer.",
    "verse": "one or two layers, changing slowly.",
    "build": (
        "rises from one layer to the full stack by the next marker. Follow it with a drop or a chorus."
    ),
    "chorus": (
        "high energy, three or four layers. With conductor on, one layer gets an accent in layers mode."
    ),
    "drop": (
        "the biggest moment: four layers at once, changing fast. With conductor on, one layer gets an accent in layers mode."
    ),
    "breakdown": "the music strips back, down to one layer.",
    "bridge": "one or two layers, led by a different layer than before.",
    "outro": "winds down from two layers to one.",
}


def song_marker_type_display(marker_type: str) -> str:
    """Name shown for *marker_type*: ``-`` for a plain marker."""
    return "-" if marker_type == DEFAULT_SONG_MARKER_TYPE else marker_type


@dataclass(frozen=True)
class SongMarker:
    """One project-scoped song marker (time plus structural type)."""

    time: float
    marker_type: SongMarkerType = DEFAULT_SONG_MARKER_TYPE


def step_song_marker_type(
    value: SongMarkerType, *, forward: bool
) -> SongMarkerType:
    return step_choice(SONG_MARKER_TYPES, value, 1 if forward else -1)


def parse_song_marker_type(raw: object) -> SongMarkerType:
    if raw in SONG_MARKER_TYPES:
        return raw  # type: ignore[return-value]
    raise ValueError(
        f"invalid song marker type {raw!r}; "
        f"expected one of: {', '.join(SONG_MARKER_TYPES)}"
    )


@dataclass(frozen=True)
class SongSection:
    """A stretch of the song, from one marker to the next."""

    start: float
    end: float
    section_type: SongMarkerType = DEFAULT_SONG_MARKER_TYPE

    @property
    def typed(self) -> bool:
        return self.section_type != DEFAULT_SONG_MARKER_TYPE

    def contains(self, t: float) -> bool:
        return self.start - 1e-9 <= t < self.end - 1e-9


def resolve_sections(
    markers: Sequence[SongMarker], duration_sec: float
) -> tuple[SongSection, ...]:
    """Sections covering the whole song, in order.

    A stretch before the first marker is plain. Markers outside the song are
    ignored, and the first of several at one time wins.
    """
    if duration_sec <= 0.0:
        return ()
    by_time: dict[float, SongMarkerType] = {}
    for marker in markers:
        t = float(marker.time)
        if 0.0 <= t < duration_sec:
            by_time.setdefault(t, marker.marker_type)
    by_time.setdefault(0.0, DEFAULT_SONG_MARKER_TYPE)
    times = sorted(by_time)
    return tuple(
        SongSection(start, end, by_time[start])
        for start, end in zip(times, [*times[1:], float(duration_sec)])
    )


def section_at(
    sections: Sequence[SongSection], t: float
) -> SongSection | None:
    """The section holding *t*, or None outside the song."""
    return next((section for section in sections if section.contains(t)), None)


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


def marker_index_near(
    times: Sequence[float], t: float, tolerance: float
) -> int | None:
    """Index of the marker nearest ``t`` within ``tolerance``, or None."""
    if not times:
        return None
    index = nearest_index(times, t)
    if abs(times[index] - t) > tolerance:
        return None
    return index


def place_marker(
    markers: Sequence[SongMarker],
    t: float,
    window: float = 2.0,
    marker_type: SongMarkerType | None = None,
) -> tuple[tuple[SongMarker, ...], int | None, float | None]:
    """Insert ``t`` into sorted song markers, or replace within ``window`` seconds.

    If any existing marker lies within ``window`` of ``t``, the nearest one is
    replaced (earlier marker on a tie). Otherwise ``t`` is inserted in sorted
    order. ``marker_type`` sets the type; without it a replaced marker keeps its
    own and an inserted one is standard.

    Returns ``(new_markers, replaced_index, replaced_time)``. On replace,
    ``replaced_index`` is the index of the new marker in ``new_markers`` and
    ``replaced_time`` is the previous time. On insert, both are ``None``.
    """
    t = float(t)
    if not markers:
        return (SongMarker(t, marker_type or DEFAULT_SONG_MARKER_TYPE),), None, None

    times = [m.time for m in markers]
    idx = nearest_index(times, t)
    if abs(times[idx] - t) <= window:
        old = float(markers[idx].time)
        updated = list(markers)
        updated[idx] = SongMarker(t, marker_type or markers[idx].marker_type)
        updated.sort(key=lambda m: m.time)
        new_idx = next(i for i, m in enumerate(updated) if m.time == t)
        return tuple(updated), new_idx, old

    updated = list(markers)
    bisect.insort(
        updated,
        SongMarker(t, marker_type or DEFAULT_SONG_MARKER_TYPE),
        key=lambda m: m.time,
    )
    return tuple(updated), None, None


def snap_markers(
    markers: Sequence[SongMarker],
    snap: Callable[[float], float],
) -> tuple[tuple[SongMarker, ...], tuple[int, ...]]:
    """Move every marker to ``snap(time)``, merging markers that land together.

    A merged marker keeps the first type that is not standard. Returns
    ``(new_markers, new_indices)``, where ``new_indices[i]`` is where
    ``markers[i]`` ended up in ``new_markers``.
    """
    snapped = [float(snap(m.time)) for m in markers]
    merged: dict[float, SongMarker] = {}
    for marker, t in zip(markers, snapped):
        held = merged.get(t)
        if held is None or held.marker_type == DEFAULT_SONG_MARKER_TYPE:
            merged[t] = SongMarker(t, marker.marker_type)
    times = sorted(merged)
    return (
        tuple(merged[t] for t in times),
        tuple(times.index(t) for t in snapped),
    )


def format_marker_time(t: float) -> str:
    """Format a song marker time as ``mm:ss.cc`` (minutes, seconds, hundredths)."""
    total_hundredths = max(0, int(round(float(t) * 100.0)))
    minutes = total_hundredths // 6000
    seconds = (total_hundredths % 6000) // 100
    hundredths = total_hundredths % 100
    return f"{minutes:02d}:{seconds:02d}.{hundredths:02d}"
