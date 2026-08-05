"""Unit tests for timeline preset repopulate staging helpers."""

from cleave.timeline_presets.repopulate import (
    DEFAULT_TIMELINE_PRESET_REPOPULATE,
    cycle_timeline_preset_repopulate,
    timeline_preset_repopulate_display,
)


def test_repopulate_defaults_and_cycle() -> None:
    assert DEFAULT_TIMELINE_PRESET_REPOPULATE == "no"
    assert timeline_preset_repopulate_display("no") == "no"
    assert timeline_preset_repopulate_display("cue roles") == "cue roles"
    assert cycle_timeline_preset_repopulate("no", forward=True) == "cue roles"
    assert (
        cycle_timeline_preset_repopulate("cue roles", forward=True)
        == "directory random"
    )
    assert (
        cycle_timeline_preset_repopulate("directory random", forward=True)
        == "directory sequential"
    )
    assert (
        cycle_timeline_preset_repopulate("directory sequential", forward=True)
        == "no"
    )
    assert (
        cycle_timeline_preset_repopulate("cue roles", forward=False) == "no"
    )
