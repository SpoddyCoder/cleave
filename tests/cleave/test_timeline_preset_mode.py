"""Unit tests for timeline preset mode staging helpers."""

from cleave.timeline_presets.mode import (
    DEFAULT_TIMELINE_PRESET_MODE,
    cycle_timeline_preset_mode,
    timeline_preset_mode_display,
)


def test_mode_defaults_and_cycle() -> None:
    assert DEFAULT_TIMELINE_PRESET_MODE == "layers"
    assert timeline_preset_mode_display("layers") == "layers"
    assert timeline_preset_mode_display("pattern_mask") == "pattern mask"
    assert cycle_timeline_preset_mode("layers", forward=True) == "pattern_mask"
    assert cycle_timeline_preset_mode("pattern_mask", forward=True) == "layers"
    assert cycle_timeline_preset_mode("layers", forward=False) == "pattern_mask"
    assert cycle_timeline_preset_mode("pattern_mask", forward=False) == "layers"
