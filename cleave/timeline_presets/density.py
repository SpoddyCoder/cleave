"""Stack-density staging for timeline presets (persisted under timeline.preset)."""

from __future__ import annotations

from typing import Literal

TimelinePresetDensity = Literal[
    "very sparse",
    "sparse",
    "normal",
    "dense",
    "very dense",
]

DEFAULT_TIMELINE_PRESET_DENSITY: TimelinePresetDensity = "normal"

TIMELINE_PRESET_DENSITY_OPTIONS: tuple[TimelinePresetDensity, ...] = (
    "very sparse",
    "sparse",
    "normal",
    "dense",
    "very dense",
)

_DENSITY_BIAS: dict[TimelinePresetDensity, int] = {
    "very sparse": -2,
    "sparse": -1,
    "normal": 0,
    "dense": 1,
    "very dense": 2,
}


def timeline_preset_density_display(density: TimelinePresetDensity) -> str:
    if density in _DENSITY_BIAS:
        return density
    return DEFAULT_TIMELINE_PRESET_DENSITY


def cycle_timeline_preset_density(
    value: TimelinePresetDensity, *, forward: bool
) -> TimelinePresetDensity:
    options = TIMELINE_PRESET_DENSITY_OPTIONS
    try:
        index = options.index(value)
    except ValueError:
        index = options.index(DEFAULT_TIMELINE_PRESET_DENSITY)
    delta = 1 if forward else -1
    return options[(index + delta) % len(options)]


def density_bias_for(density: TimelinePresetDensity) -> int:
    return _DENSITY_BIAS.get(density, _DENSITY_BIAS[DEFAULT_TIMELINE_PRESET_DENSITY])
