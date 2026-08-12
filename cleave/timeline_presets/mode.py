"""Arrangement-mode staging for timeline presets (persisted under timeline.preset)."""

from __future__ import annotations

from typing import Literal

TimelinePresetMode = Literal["layers", "pattern_mask"]

DEFAULT_TIMELINE_PRESET_MODE: TimelinePresetMode = "layers"

TIMELINE_PRESET_MODE_OPTIONS: tuple[TimelinePresetMode, ...] = (
    "layers",
    "pattern_mask",
)

_MODE_DISPLAY: dict[TimelinePresetMode, str] = {
    "layers": "layers",
    "pattern_mask": "pattern mask",
}


def timeline_preset_mode_display(mode: TimelinePresetMode) -> str:
    return _MODE_DISPLAY.get(mode, _MODE_DISPLAY[DEFAULT_TIMELINE_PRESET_MODE])


def cycle_timeline_preset_mode(
    value: TimelinePresetMode, *, forward: bool
) -> TimelinePresetMode:
    options = TIMELINE_PRESET_MODE_OPTIONS
    try:
        index = options.index(value)
    except ValueError:
        index = options.index(DEFAULT_TIMELINE_PRESET_MODE)
    delta = 1 if forward else -1
    return options[(index + delta) % len(options)]
