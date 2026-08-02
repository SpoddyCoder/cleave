"""Staged reshuffle toggle for timeline preset Apply."""

from __future__ import annotations

DEFAULT_TIMELINE_PRESET_RESHUFFLE = False


def timeline_preset_reshuffle_display(reshuffle: bool) -> str:
    return "on" if reshuffle else "off"


def cycle_timeline_preset_reshuffle(value: bool, *, forward: bool) -> bool:
    options = (False, True)
    try:
        index = options.index(bool(value))
    except ValueError:
        index = options.index(DEFAULT_TIMELINE_PRESET_RESHUFFLE)
    delta = 1 if forward else -1
    return options[(index + delta) % len(options)]
