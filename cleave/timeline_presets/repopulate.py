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


_DISPLAY: dict[TimelinePresetRepopulate, str] = {
    "no": "no, keep the lists",
    "cue roles": "clip roles",
    "directory random": "shuffled (each layer's directory)",
    "directory sequential": "in order (each layer's directory)",
}


def timeline_preset_repopulate_display(
    mode: TimelinePresetRepopulate,
) -> str:
    """The dialog label for *mode*; an unknown mode shows the default's."""
    return _DISPLAY.get(mode, _DISPLAY[DEFAULT_TIMELINE_PRESET_REPOPULATE])
