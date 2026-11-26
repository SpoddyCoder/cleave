"""What Generate timeline may change on the layers themselves (session only)."""

from __future__ import annotations

# Layer opacity multiplies clip opacity, so the planned brightness shows only at 100%.
DEFAULT_TIMELINE_PRESET_FULL_OPACITY = False
# The planned preset changes show only on layers whose presets change on each clip.
DEFAULT_TIMELINE_PRESET_EACH_CLIP = False

FULL_OPACITY_PCT = 100


def opacity_display(full: bool) -> str:
    return "set to 100%" if full else "keep"


def change_presets_display(each_clip: bool) -> str:
    return "each clip" if each_clip else "keep"
