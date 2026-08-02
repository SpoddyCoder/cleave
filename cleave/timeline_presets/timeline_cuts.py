"""Cut-type staging for timeline presets (persisted under timeline.preset)."""

from __future__ import annotations

from typing import Literal

TimelinePresetTimelineCuts = Literal["by marker", "all soft", "all hard", "none"]

DEFAULT_TIMELINE_PRESET_TIMELINE_CUTS: TimelinePresetTimelineCuts = "by marker"

TIMELINE_PRESET_TIMELINE_CUTS_OPTIONS: tuple[TimelinePresetTimelineCuts, ...] = (
    "by marker",
    "all soft",
    "all hard",
    "none",
)


def timeline_preset_timeline_cuts_display(
    cuts: TimelinePresetTimelineCuts,
) -> str:
    if cuts in TIMELINE_PRESET_TIMELINE_CUTS_OPTIONS:
        return cuts
    return DEFAULT_TIMELINE_PRESET_TIMELINE_CUTS


def cycle_timeline_preset_timeline_cuts(
    value: TimelinePresetTimelineCuts, *, forward: bool
) -> TimelinePresetTimelineCuts:
    options = TIMELINE_PRESET_TIMELINE_CUTS_OPTIONS
    try:
        index = options.index(value)
    except ValueError:
        index = options.index(DEFAULT_TIMELINE_PRESET_TIMELINE_CUTS)
    delta = 1 if forward else -1
    return options[(index + delta) % len(options)]
