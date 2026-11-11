"""Timeline row context menu items, through real ``TimelineControls``."""

from __future__ import annotations

import pygame

from cleave.timeline import TimelineLane
from cleave.viz.context_menu import ContextMenuItem
from cleave.viz.timeline_context_menu import timeline_row_menu, timeline_row_menu_entries
from tests.cleave.viz.test_timeline_controls import _make_timeline_controls
from tests.support.viz import keydown


def _items(controls, session, row: int) -> dict[str, ContextMenuItem]:
    return {
        entry.id: entry
        for entry in timeline_row_menu_entries(controls, session, row)
        if isinstance(entry, ContextMenuItem)
    }


def test_plain_row_offers_override_and_arm() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls()
    items = _items(controls, session, 1)
    visibility = items["timeline.row.visibility"]
    assert visibility.label == "Hide layer"
    assert visibility.enabled is False
    assert visibility.shortcut == "2"
    assert visibility.hint == "Turn on Override visibility to show or hide by hand"
    override = items["timeline.row.override"]
    assert (override.enabled, override.checked, override.shortcut) == (
        True,
        False,
        "Shift+Enter",
    )
    release = items["timeline.row.release_overrides"]
    assert release.enabled is False
    assert release.hint == "No row is overridden"
    arm = items["timeline.row.arm"]
    assert (arm.enabled, arm.checked, arm.shortcut) == (True, False, "A")


def test_override_item_starts_and_releases_and_show_hide_follows() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        lanes={"layer_2": TimelineLane(baseline=0.0, cues=[])},
    )
    items = _items(controls, session, 1)
    assert items["timeline.row.visibility"].label == "Show layer"
    items["timeline.row.override"].run()
    assert session.timeline.override_slots == {"layer_2"}

    items = _items(controls, session, 1)
    assert items["timeline.row.override"].checked is True
    assert items["timeline.row.release_overrides"].enabled is True
    visibility = items["timeline.row.visibility"]
    assert visibility.enabled is True and visibility.hint is None
    visibility.run()
    assert session.timeline.override_visible == {"layer_2": True}
    assert _items(controls, session, 1)["timeline.row.visibility"].label == (
        "Hide layer"
    )

    _items(controls, session, 0)["timeline.row.release_overrides"].run()
    assert session.timeline.override_slots == set()


def test_recording_blocks_overrides_and_allows_armed_show_hide() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(armed_slots={"layer_1"})
    controls.handle_keydown(keydown(pygame.K_r))
    armed = _items(controls, session, 0)
    assert armed["timeline.row.visibility"].enabled is True
    assert armed["timeline.row.override"].enabled is False
    assert armed["timeline.row.override"].hint == "Stop recording to change overrides"
    assert armed["timeline.row.arm"].checked is True
    other = _items(controls, session, 1)
    assert other["timeline.row.visibility"].hint == "Arm this row to record show / hide"


def test_locked_timeline_greys_out_arm() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls()
    session.timeline.locked = True
    arm = _items(controls, session, 0)["timeline.row.arm"]
    assert arm.enabled is False
    assert arm.hint == "Unlock the timeline to arm"


def test_arm_item_arms_the_row() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls()
    _items(controls, session, 2)["timeline.row.arm"].run()
    assert session.timeline.armed_slots == {"layer_3"}


def test_row_past_the_last_layer_has_no_menu() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls()
    assert timeline_row_menu(controls, session, 9)() == ()
