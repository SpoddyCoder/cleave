"""Unit tests for timeline preset reshuffle staging helpers."""

from __future__ import annotations

from cleave.timeline_presets.reshuffle import (
    DEFAULT_TIMELINE_PRESET_RESHUFFLE,
    cycle_timeline_preset_reshuffle,
    timeline_preset_reshuffle_display,
)


def test_reshuffle_defaults_and_cycle() -> None:
    assert DEFAULT_TIMELINE_PRESET_RESHUFFLE is False
    assert timeline_preset_reshuffle_display(False) == "off"
    assert timeline_preset_reshuffle_display(True) == "on"
    assert cycle_timeline_preset_reshuffle(False, forward=True) is True
    assert cycle_timeline_preset_reshuffle(True, forward=True) is False
    assert cycle_timeline_preset_reshuffle(False, forward=False) is True
    assert cycle_timeline_preset_reshuffle(True, forward=False) is False
