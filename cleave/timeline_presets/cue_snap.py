"""Cue-grid snap staging for timeline presets (persisted under timeline.preset)."""

from __future__ import annotations

from typing import Literal

TimelinePresetCueSnap = Literal["beats", "bars", "none"]

DEFAULT_TIMELINE_PRESET_CUE_SNAP: TimelinePresetCueSnap = "none"

TIMELINE_PRESET_CUE_SNAP_OPTIONS: tuple[TimelinePresetCueSnap, ...] = (
    "beats",
    "bars",
    "none",
)


def timeline_preset_cue_snap_display(cue_snap: TimelinePresetCueSnap) -> str:
    if cue_snap in TIMELINE_PRESET_CUE_SNAP_OPTIONS:
        return cue_snap
    return DEFAULT_TIMELINE_PRESET_CUE_SNAP
