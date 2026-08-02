"""Song-marker snap staging for timeline presets (persisted under timeline.preset)."""

from __future__ import annotations

TimelinePresetSongMarkerSnap = float | None

DEFAULT_TIMELINE_PRESET_SONG_MARKER_SNAP: TimelinePresetSongMarkerSnap = None

SONG_MARKER_SNAP_PROXIMITY_OPTIONS: tuple[float, ...] = (
    0.5,
    1.0,
    2.0,
    5.0,
    10.0,
    15.0,
    30.0,
)

TIMELINE_PRESET_SONG_MARKER_SNAP_OPTIONS: tuple[TimelinePresetSongMarkerSnap, ...] = (
    None,
) + SONG_MARKER_SNAP_PROXIMITY_OPTIONS


def song_marker_snap_proximity_label(proximity: float) -> str:
    return f"{proximity:.1f}s"


def timeline_preset_song_marker_snap_display(
    proximity: TimelinePresetSongMarkerSnap,
) -> str:
    if proximity is None:
        return "none"
    return song_marker_snap_proximity_label(float(proximity))


def cycle_timeline_preset_song_marker_snap(
    value: TimelinePresetSongMarkerSnap, *, forward: bool
) -> TimelinePresetSongMarkerSnap:
    options = TIMELINE_PRESET_SONG_MARKER_SNAP_OPTIONS
    try:
        if value is None:
            index = 0
        else:
            index = options.index(float(value))
    except ValueError:
        index = 0
    delta = 1 if forward else -1
    return options[(index + delta) % len(options)]
