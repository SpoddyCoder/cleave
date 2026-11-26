"""Unit tests for timeline preset repopulate staging helpers."""

from cleave.timeline_presets.repopulate import (
    DEFAULT_TIMELINE_PRESET_REPOPULATE,
    timeline_preset_repopulate_display,
)


def test_default_keeps_the_current_list() -> None:
    assert DEFAULT_TIMELINE_PRESET_REPOPULATE == "keep"
    assert timeline_preset_repopulate_display("keep") == "use current list"
