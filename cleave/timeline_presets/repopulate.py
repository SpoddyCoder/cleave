"""How Generate timeline picks presets for the clips it builds.

Applies to layers whose presets change on each clip: every generated clip
needs a preset of its own.
"""

from __future__ import annotations

from typing import Literal

TimelinePresetRepopulate = Literal[
    "cue roles",
    "directory random",
    "directory sequential",
]

DEFAULT_TIMELINE_PRESET_REPOPULATE: TimelinePresetRepopulate = "directory random"

TIMELINE_PRESET_REPOPULATE_OPTIONS: tuple[TimelinePresetRepopulate, ...] = (
    "cue roles",
    "directory random",
    "directory sequential",
)


_DISPLAY: dict[TimelinePresetRepopulate, str] = {
    "cue roles": "clip roles",
    "directory random": "shuffled (each layer's directory)",
    "directory sequential": "in order (each layer's directory)",
}


def timeline_preset_repopulate_display(
    mode: TimelinePresetRepopulate,
) -> str:
    """The dialog label for *mode*; an unknown mode shows the default's."""
    return _DISPLAY.get(mode, _DISPLAY[DEFAULT_TIMELINE_PRESET_REPOPULATE])
