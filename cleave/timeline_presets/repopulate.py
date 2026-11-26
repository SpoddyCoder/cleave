"""What Generate timeline does with the preset lists of the clips it builds.

Applies to layers whose presets change on each clip: every generated clip
needs a preset of its own, dealt from the layer's preset list.
"""

from __future__ import annotations

from typing import Literal

TimelinePresetRepopulate = Literal[
    "keep",
    "directory random",
    "directory sequential",
    "cue roles",
]

DEFAULT_TIMELINE_PRESET_REPOPULATE: TimelinePresetRepopulate = "keep"

TIMELINE_PRESET_REPOPULATE_OPTIONS: tuple[TimelinePresetRepopulate, ...] = (
    "keep",
    "directory random",
    "directory sequential",
    "cue roles",
)


_DISPLAY: dict[TimelinePresetRepopulate, str] = {
    "keep": "use current list",
    "directory random": "new, shuffled from folder",
    "directory sequential": "new, in order from folder",
    "cue roles": "new, by clip roles",
}


def timeline_preset_repopulate_display(
    mode: TimelinePresetRepopulate,
) -> str:
    """The dialog label for *mode*; an unknown mode shows the default's."""
    return _DISPLAY.get(mode, _DISPLAY[DEFAULT_TIMELINE_PRESET_REPOPULATE])
