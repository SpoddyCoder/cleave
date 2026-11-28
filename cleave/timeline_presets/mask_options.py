"""Generate's pattern mask options: the pattern, and how often layers change."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from cleave.config_schema.render.pattern_mask import PATTERN_MASK_TYPES

KEEP = "keep"

TimelinePresetMaskPattern = Literal["keep", "strips", "bars", "radial", "checker", "plasma"]

DEFAULT_TIMELINE_PRESET_MASK_PATTERN: TimelinePresetMaskPattern = KEEP

TIMELINE_PRESET_MASK_PATTERN_OPTIONS: tuple[TimelinePresetMaskPattern, ...] = (
    KEEP,
    *PATTERN_MASK_TYPES,
)

TimelinePresetMaskChanges = Literal["fewer", "normal", "more"]

DEFAULT_TIMELINE_PRESET_MASK_CHANGES: TimelinePresetMaskChanges = "normal"

TIMELINE_PRESET_MASK_CHANGES_OPTIONS: tuple[TimelinePresetMaskChanges, ...] = (
    "fewer",
    "normal",
    "more",
)

@dataclass(frozen=True)
class MaskChangesPace:
    """How a layer changes option spaces the changes between markers.

    ``scale`` multiplies the section's bars between changes; ``grid_bars`` is
    the step changes land on (half a bar, or a beat), and the shortest gap.
    """

    scale: float
    grid_bars: float


_CHANGES_PACE: dict[TimelinePresetMaskChanges, MaskChangesPace] = {
    "fewer": MaskChangesPace(scale=2.0, grid_bars=0.5),
    "normal": MaskChangesPace(scale=0.4, grid_bars=0.5),
    "more": MaskChangesPace(scale=0.2, grid_bars=0.25),
}


def timeline_preset_mask_pattern_display(pattern: TimelinePresetMaskPattern) -> str:
    return pattern if pattern in TIMELINE_PRESET_MASK_PATTERN_OPTIONS else KEEP


def timeline_preset_mask_changes_display(changes: TimelinePresetMaskChanges) -> str:
    if changes in _CHANGES_PACE:
        return changes
    return DEFAULT_TIMELINE_PRESET_MASK_CHANGES


def mask_changes_pace(changes: TimelinePresetMaskChanges) -> MaskChangesPace:
    """How far apart *changes* spaces the layer changes between markers."""
    return _CHANGES_PACE.get(changes, _CHANGES_PACE[DEFAULT_TIMELINE_PRESET_MASK_CHANGES])
