"""Staged preset-list repopulate mode for timeline preset Apply."""

from __future__ import annotations

from typing import Literal

TimelinePresetRepopulate = Literal[
    "no",
    "cue roles",
    "directory random",
    "directory sequential",
]

DEFAULT_TIMELINE_PRESET_REPOPULATE: TimelinePresetRepopulate = "no"

TIMELINE_PRESET_REPOPULATE_OPTIONS: tuple[TimelinePresetRepopulate, ...] = (
    "no",
    "cue roles",
    "directory random",
    "directory sequential",
)


def timeline_preset_repopulate_display(
    mode: TimelinePresetRepopulate,
) -> str:
    if mode in TIMELINE_PRESET_REPOPULATE_OPTIONS:
        return mode
    return DEFAULT_TIMELINE_PRESET_REPOPULATE
