"""Timeline row context menu items, through real ``TimelineControls``."""

from __future__ import annotations

import pygame

from cleave.timeline import SlotCue, TimelineLane
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
    assert "timeline.row.visibility" not in items
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


def test_override_item_starts_and_releases() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(
        lanes={"layer_2": TimelineLane(baseline=0.0, cues=[])},
    )
    _items(controls, session, 1)["timeline.row.override"].run()
    assert session.timeline.override_slots == {"layer_2"}

    items = _items(controls, session, 1)
    assert items["timeline.row.override"].checked is True
    assert items["timeline.row.release_overrides"].enabled is True

    _items(controls, session, 0)["timeline.row.release_overrides"].run()
    assert session.timeline.override_slots == set()


def test_recording_blocks_overrides() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls(armed_slots={"layer_1"})
    controls.handle_keydown(keydown(pygame.K_r))
    armed = _items(controls, session, 0)
    assert armed["timeline.row.override"].enabled is False
    assert armed["timeline.row.override"].hint == "Stop recording to change overrides"
    assert armed["timeline.row.arm"].checked is True


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


def test_solo_item_solos_the_row_and_shows_the_check() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls()
    solo = _items(controls, session, 2)["timeline.row.solo"]
    assert solo.checked is False
    solo.run()
    assert session.solo_slot == "layer_3"
    assert _items(controls, session, 2)["timeline.row.solo"].checked is True
    assert _items(controls, session, 0)["timeline.row.solo"].checked is False
    _items(controls, session, 2)["timeline.row.solo"].run()
    assert session.solo_slot is None


def test_row_past_the_last_layer_has_no_menu() -> None:
    controls, session, _, _, _, _ = _make_timeline_controls()
    assert timeline_row_menu(controls, session, 9)() == ()


def _clip_controls(*, position_sec: float = 1.0, **kwargs):
    from tests.cleave.viz.test_timeline_controls import _lane

    lanes = {"layer_1": _lane(False, (4.0, True), (10.0, False))}
    return _make_timeline_controls(lanes=lanes, position_sec=position_sec, **kwargs)


def _entries_by_id(controls, session, row: int, **kwargs):
    return {
        entry.id: entry
        for entry in timeline_row_menu_entries(controls, session, row, **kwargs)
        if isinstance(entry, (ContextMenuItem, ContextSubmenu))
    }


def test_no_selected_clip_means_no_clip_items() -> None:
    controls, session, _, _, _, _ = _clip_controls()
    entries = timeline_row_menu_entries(controls, session, 0)
    assert entries[0].id == "timeline.row.override"


def test_selected_clip_leads_with_go_to_splits_cuts_role_delete() -> None:
    controls, session, _, _, seeks, _ = _clip_controls()
    session.timeline.selected_clip_t["layer_1"] = 4.0
    entries = timeline_row_menu_entries(controls, session, 0)
    assert [getattr(entry, "id", None) for entry in entries[:8]] == [
        "timeline.clip.go_to",
        "timeline.clip.split",
        "timeline.clip.split_here",
        "timeline.clip.cut_in",
        "timeline.clip.cut_out",
        "timeline.clip.role",
        "timeline.clip.delete",
        None,
    ]
    assert "timeline.clip.blend" not in _entries_by_id(controls, session, 0)
    by_id = _entries_by_id(controls, session, 0)
    cut_in = by_id["timeline.clip.cut_in"]
    assert cut_in.enabled and cut_in.shortcut == "C"
    assert [(item.label, item.checked) for item in cut_in.items] == [
        ("None", True),
        ("Hard", False),
        ("Soft", False),
    ]
    cut_out = by_id["timeline.clip.cut_out"]
    assert cut_out.enabled and cut_out.shortcut == "Shift+C"
    role = by_id["timeline.clip.role"]
    assert [item.label for item in role.items] == [
        "None", "Bed", "Pulse", "Lead", "Accent"
    ]

    cut_in.items[1].run()
    cut_out.items[2].run()
    role.items[3].run()
    start, end = session.timeline.lanes["layer_1"].cues
    assert (start.cut, start.role) == ("hard", "lead")
    assert end.cut == "soft"
    assert _entries_by_id(controls, session, 0)["timeline.clip.cut_in"].items[1].checked

    by_id["timeline.clip.go_to"].run()
    assert seeks and abs(sum(seeks) - 3.0) < 1e-6


def test_cut_out_is_greyed_out_on_a_butted_clip_and_at_the_song_end() -> None:
    from tests.cleave.viz.test_timeline_controls import _lane

    lanes = {
        "layer_1": _lane(False, (4.0, 1.0), (10.0, 0.5)),
    }
    controls, session, _, _, _, _ = _make_timeline_controls(lanes=lanes)
    session.timeline.selected_clip_t["layer_1"] = 4.0
    butted = _entries_by_id(controls, session, 0)["timeline.clip.cut_out"]
    assert butted.enabled is False
    assert butted.hint == "Butts the next clip; set its Cut in"
    session.timeline.selected_clip_t["layer_1"] = 10.0
    last = _entries_by_id(controls, session, 0)["timeline.clip.cut_out"]
    assert last.enabled is False
    assert last.hint == "Runs to the song end"


def test_split_item_needs_the_playhead_inside_the_clip() -> None:
    controls, session, _, _, _, _ = _clip_controls()
    session.timeline.selected_clip_t["layer_1"] = 4.0
    split = _entries_by_id(controls, session, 0)["timeline.clip.split"]
    assert split.enabled is False
    assert split.hint == "Move the playhead inside this clip"
    assert split.shortcut == "Ctrl+K"

    controls, session, _, _, _, _ = _clip_controls(position_sec=6.0)
    session.timeline.selected_clip_t["layer_1"] = 4.0
    split = _entries_by_id(controls, session, 0)["timeline.clip.split"]
    assert split.enabled is True
    split.run()
    cues = session.timeline.lanes["layer_1"].cues
    assert [cue.t for cue in cues] == [4.0, 6.0, 10.0]
    assert cues[1].anchor
    assert session.timeline.selected_clip_t["layer_1"] == 6.0


def test_split_here_splits_at_the_right_clicked_time() -> None:
    controls, session, _, _, _, _ = _clip_controls()
    session.timeline.selected_clip_t["layer_1"] = 4.0
    keyboard = _entries_by_id(controls, session, 0)["timeline.clip.split_here"]
    assert keyboard.enabled is False
    assert keyboard.hint == "Right-click inside the clip to split there"

    edge = _entries_by_id(controls, session, 0, split_t=4.0)["timeline.clip.split_here"]
    assert edge.enabled is False
    assert edge.hint == "Too close to the clip's edge"

    item = _entries_by_id(controls, session, 0, split_t=7.0)["timeline.clip.split_here"]
    assert item.enabled is True
    item.run()
    assert [cue.t for cue in session.timeline.lanes["layer_1"].cues] == [4.0, 7.0, 10.0]
    assert session.timeline.selected_clip_t["layer_1"] == 7.0


def test_locked_timeline_greys_out_clip_edits_but_keeps_go_to() -> None:
    controls, session, _, _, _, _ = _clip_controls()
    session.timeline.selected_clip_t["layer_1"] = 4.0
    session.timeline.locked = True
    by_id = _entries_by_id(controls, session, 0)
    assert by_id["timeline.clip.go_to"].enabled is True
    for key in (
        "timeline.clip.cut_in",
        "timeline.clip.cut_out",
        "timeline.clip.role",
        "timeline.clip.split",
        "timeline.clip.split_here",
        "timeline.clip.delete",
    ):
        assert by_id[key].enabled is False
        assert by_id[key].hint == "Unlock the timeline to edit clips"


def test_clip_false_leaves_out_the_clip_items() -> None:
    controls, session, _, _, _, _ = _clip_controls()
    session.timeline.selected_clip_t["layer_1"] = 4.0
    assert "timeline.clip.go_to" not in _entries_by_id(
        controls, session, 0, clip=False
    )


def test_delete_clip_item_turns_the_selected_clip_off() -> None:
    controls, session, _, _, _, _ = _clip_controls()
    session.timeline.selected_clip_t["layer_1"] = 4.0
    item = _entries_by_id(controls, session, 0)["timeline.clip.delete"]
    assert (item.label, item.shortcut) == ("Delete clip", "Delete")
    item.run()
    assert session.timeline.lanes["layer_1"].cues == []
    assert "layer_1" not in session.timeline.selected_clip_t


def test_add_clip_here_item_adds_a_clip_at_the_clicked_time() -> None:
    controls, session, _, _, _, _ = _clip_controls()
    entries = timeline_row_menu_entries(controls, session, 0, add_clip_t=20.0)
    item = entries[0]
    assert (item.id, item.label, item.shortcut) == (
        "timeline.clip.add",
        "Add clip here",
        "Double-click",
    )
    item.run()
    # With no bar grid a new clip is two seconds long.
    assert session.timeline.lanes["layer_1"].cues[2:] == [
        SlotCue(t=20.0, level=1.0),
        SlotCue(t=22.0, level=0.0),
    ]
    assert session.timeline.selected_clip_t["layer_1"] == 20.0


def test_add_clip_here_is_greyed_out_while_recording() -> None:
    controls, session, _, _, _, _ = _clip_controls()
    session.timeline.recording = True
    item = _entries_by_id(controls, session, 0, add_clip_t=20.0)["timeline.clip.add"]
    assert item.enabled is False
    assert item.hint == "Stop recording to edit clips"
