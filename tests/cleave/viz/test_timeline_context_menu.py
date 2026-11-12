"""Timeline row context menu items, through real ``TimelineControls``."""

from __future__ import annotations

import pygame

from cleave.timeline import TimelineLane
from cleave.viz.context_menu import ContextMenuItem, ContextSubmenu
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


def _cue_controls(**kwargs):
    from tests.cleave.viz.test_timeline_controls import _lane

    lanes = {"layer_1": _lane(False, (4.0, True), (10.0, False))}
    return _make_timeline_controls(lanes=lanes, position_sec=1.0, **kwargs)


def _entries_by_id(controls, session, row: int, **kwargs):
    return {
        entry.id: entry
        for entry in timeline_row_menu_entries(controls, session, row, **kwargs)
        if isinstance(entry, (ContextMenuItem, ContextSubmenu))
    }


def test_no_selected_cue_means_no_cue_items() -> None:
    controls, session, _, _, _, _ = _cue_controls()
    entries = timeline_row_menu_entries(controls, session, 0)
    assert entries[0].id == "timeline.row.visibility"


def test_selected_on_cue_leads_with_go_to_and_cut_blend_role() -> None:
    controls, session, _, _, seeks, _ = _cue_controls()
    session.timeline.selected_cue_t["layer_1"] = 4.0
    entries = timeline_row_menu_entries(controls, session, 0)
    assert [getattr(entry, "id", None) for entry in entries[:5]] == [
        "timeline.cue.go_to",
        "timeline.cue.cut",
        "timeline.cue.blend",
        "timeline.cue.role",
        None,
    ]
    by_id = _entries_by_id(controls, session, 0)
    cut = by_id["timeline.cue.cut"]
    assert cut.enabled and cut.shortcut == "C"
    assert [(item.label, item.checked) for item in cut.items] == [
        ("None", True),
        ("Hard", False),
        ("Soft", False),
    ]
    blend = by_id["timeline.cue.blend"]
    assert blend.items[0].label == "Layer blend" and blend.items[0].checked
    role = by_id["timeline.cue.role"]
    assert [item.label for item in role.items] == [
        "None", "Bed", "Pulse", "Lead", "Accent"
    ]

    cut.items[1].run()
    blend.items[2].run()
    role.items[3].run()
    cue = session.timeline.lanes["layer_1"].cues[0]
    assert (cue.cut, cue.blend, cue.role) == ("hard", "add", "lead")
    assert _entries_by_id(controls, session, 0)["timeline.cue.cut"].items[1].checked

    by_id["timeline.cue.go_to"].run()
    assert seeks and abs(sum(seeks) - 3.0) < 1e-6


def test_end_cue_takes_only_a_cut() -> None:
    controls, session, _, _, _, _ = _cue_controls()
    session.timeline.selected_cue_t["layer_1"] = 10.0
    by_id = _entries_by_id(controls, session, 0)
    assert by_id["timeline.cue.cut"].enabled is True
    for key in ("timeline.cue.blend", "timeline.cue.role"):
        assert by_id[key].enabled is False
        assert by_id[key].hint == "An end cue takes only a cut"


def test_locked_timeline_greys_out_cue_edits_but_keeps_go_to() -> None:
    controls, session, _, _, _, _ = _cue_controls()
    session.timeline.selected_cue_t["layer_1"] = 4.0
    session.timeline.locked = True
    by_id = _entries_by_id(controls, session, 0)
    assert by_id["timeline.cue.go_to"].enabled is True
    for key in ("timeline.cue.cut", "timeline.cue.blend", "timeline.cue.role"):
        assert by_id[key].enabled is False
        assert by_id[key].hint == "Unlock the timeline to edit cues"


def test_cue_false_leaves_out_the_cue_items() -> None:
    controls, session, _, _, _, _ = _cue_controls()
    session.timeline.selected_cue_t["layer_1"] = 4.0
    assert "timeline.cue.go_to" not in _entries_by_id(controls, session, 0, cue=False)
