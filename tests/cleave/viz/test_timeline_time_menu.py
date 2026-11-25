"""Time items for a right-click on the timeline ruler or an empty row spot."""

from __future__ import annotations

from cleave.song_markers import SongMarker
from cleave.timeline import SlotCue, TimelineLane
from cleave.viz.context_menu import ContextMenuItem, ContextSubmenu
from cleave.viz.timeline_time_menu import TimelineTimeMenu
from tests.support.viz import make_controls


class _Transport:
    def __init__(self, *, paused: bool = True) -> None:
        self.paused = paused
        self.calls: list[tuple] = []

    def seek_to(self, t_sec: float) -> None:
        self.calls.append(("seek", t_sec))

    def toggle_transport(self) -> None:
        self.calls.append(("transport",))
        self.paused = not self.paused


def _flatten(entries):
    """Each row by id, with a submenu's child rows after it."""
    rows = {}
    for entry in entries:
        if isinstance(entry, (ContextMenuItem, ContextSubmenu)):
            rows[entry.id] = entry
        if isinstance(entry, ContextSubmenu):
            rows.update(_flatten(entry.items))
    return rows


def _items(menu: TimelineTimeMenu, t: float = 12.0, *, commands: bool = True):
    return {
        item_id: entry
        for item_id, entry in _flatten(menu.entries(t, 0.5, commands=commands)).items()
        if isinstance(entry, ContextMenuItem)
    }


def test_drop_song_marker_submenu_drops_at_the_playhead_or_here() -> None:
    controls = make_controls()
    transport = _Transport()
    playhead_drops: list[str] = []
    controls.song_markers.drop = lambda: playhead_drops.append("drop")
    entries = TimelineTimeMenu(controls, transport).entries(12.0, 0.5, commands=False)
    assert len(entries) == 2
    drop = entries[0]
    assert isinstance(drop, ContextSubmenu)
    assert (drop.id, drop.label, drop.enabled) == (
        "timeline.time.drop_marker",
        "Drop song marker",
        True,
    )
    playhead, here = drop.items
    assert (playhead.label, playhead.shortcut) == ("At playhead", "Ctrl+Enter")
    assert (here.label, here.shortcut) == ("Here", None)
    playhead.run()
    assert playhead_drops == ["drop"]
    here.run()
    assert controls.session.song_markers.times == [0.0, 12.0]
    assert transport.calls == []


def test_drop_section_here_drops_a_typed_marker() -> None:
    controls = make_controls()
    entries = TimelineTimeMenu(controls, _Transport()).entries(12.0, 0.5, commands=False)
    section = entries[1]
    assert isinstance(section, ContextSubmenu)
    assert section.label == "Drop section here"
    assert [item.label for item in section.items] == [
        "intro",
        "verse",
        "build",
        "chorus",
        "drop",
        "breakdown",
        "bridge",
        "outro",
    ]
    section.items[3].run()
    assert controls.session.song_markers.markers == [SongMarker(0.0), SongMarker(12.0, "chorus")]


def _marker_entries(controls, *, commands: bool = False):
    return TimelineTimeMenu(controls, _Transport()).entries(
        12.0, 0.5, commands=commands, marker_index=0
    )


def test_marker_items_replace_the_time_items() -> None:
    controls = make_controls()
    controls.session.song_markers.markers = [SongMarker(time=12.2, marker_type="verse")]
    transport = _Transport()
    entries = TimelineTimeMenu(controls, transport).entries(
        12.0, 0.5, commands=False, marker_index=0
    )
    ids = [getattr(entry, "id", None) for entry in entries]
    assert ids == [
        "timeline.marker.seek",
        "timeline.marker.play",
        None,
        "timeline.marker.type",
        "timeline.marker.intensity",
        "timeline.marker.delete",
    ]
    entries[0].run()
    entries[1].run()
    assert transport.calls == [("seek", 12.2), ("seek", 12.2), ("transport",)]
    assert entries[5].label == "Delete marker 00:12.20…"
    assert entries[5].shortcut == "Delete"


def test_unselected_marker_delete_item_shows_no_key() -> None:
    controls = make_controls()
    controls.session.song_markers.markers = [SongMarker(time=12.2, marker_type="verse")]
    entries = TimelineTimeMenu(controls, _Transport()).entries(
        12.0, 0.5, commands=False, marker_index=0, marker_selected=False
    )
    assert entries[5].id == "timeline.marker.delete"
    assert entries[5].shortcut is None
    assert entries[5].enabled


def test_marker_type_submenu_checks_and_sets_the_type() -> None:
    controls = make_controls()
    controls.session.song_markers.markers = [
        SongMarker(time=12.2),
        SongMarker(time=30.0, marker_type="drop"),
    ]
    submenu = _marker_entries(controls)[3]
    assert isinstance(submenu, ContextSubmenu)
    checked = [item.id for item in submenu.items if getattr(item, "checked", False)]
    assert checked == ["timeline.marker.type.standard"]
    verse = next(i for i in submenu.items if i.id == "timeline.marker.type.verse")
    verse.run()
    assert controls.session.song_markers.markers[0].marker_type == "verse"


def test_recording_disables_marker_edits_but_not_seeking() -> None:
    controls = make_controls()
    controls.session.song_markers.markers = [SongMarker(time=12.2)]
    controls.session.timeline.recording = True
    entries = _marker_entries(controls)
    assert entries[0].enabled is True
    assert entries[3].enabled is False
    assert entries[4].enabled is False
    assert entries[5].enabled is False
    assert entries[4].hint == "Stop recording to edit markers"


def test_a_gone_marker_falls_back_to_the_time_items() -> None:
    controls = make_controls()
    ids = [getattr(e, "id", None) for e in _marker_entries(controls)]
    assert ids[0] == "timeline.time.drop_marker"


def test_recording_blocks_marker_drop() -> None:
    controls = make_controls()
    controls.session.timeline.recording = True
    entries = TimelineTimeMenu(controls, _Transport()).entries(12.0, 0.5, commands=True)
    drop = entries[0]
    assert drop.id == "timeline.time.drop_marker"
    assert drop.enabled is False
    assert drop.hint == "Stop recording to drop markers"
    items = _items(TimelineTimeMenu(controls, _Transport()))
    for item_id in ("timeline.time.drop_marker.playhead", "timeline.time.drop_marker.here"):
        assert items[item_id].enabled is False
        assert items[item_id].hint == "Stop recording to drop markers"


def test_ruler_lists_history_and_timeline_commands() -> None:
    items = _items(TimelineTimeMenu(make_controls(), _Transport()))
    for command_id in (
        "edit.undo",
        "edit.redo",
        "timeline.generate",
        "timeline.snap_cues",
        "timeline.snap_to_markers",
        "timeline.set_cut_type",
        "timeline.reset",
    ):
        assert command_id in items
    entries = TimelineTimeMenu(make_controls(), _Transport()).entries(
        12.0, 0.5, commands=True
    )
    commands = entries[-1]
    assert isinstance(commands, ContextSubmenu)
    assert (commands.id, commands.label, commands.enabled) == (
        "timeline.commands",
        "Timeline",
        True,
    )
    assert [item.id for item in commands.items] == [
        "timeline.generate",
        "timeline.snap_cues",
        "timeline.snap_to_markers",
        "timeline.set_cut_type",
        "timeline.reset",
    ]
    assert items["timeline.generate"].enabled is True
    assert items["edit.undo"].label == "Undo"
    assert items["edit.undo"].enabled is False
    assert items["edit.undo"].hint == "Nothing to undo"
    assert items["edit.undo"].shortcut == "Ctrl+Z"


def test_undo_label_names_the_last_command() -> None:
    controls = make_controls()
    with controls.edit_history.recording("Snap clips"):
        controls.session.timeline.lanes["layer_1"] = TimelineLane(
            baseline=None, cues=[SlotCue(t=3.0, level=1.0)]
        )
    undo = _items(TimelineTimeMenu(controls, _Transport()))["edit.undo"]
    assert undo.label == "Undo Snap clips"
    assert undo.enabled is True


def test_locked_timeline_disables_commands_with_a_hint() -> None:
    controls = make_controls()
    controls.session.timeline.locked = True
    entries = TimelineTimeMenu(controls, _Transport()).entries(12.0, 0.5, commands=True)
    assert entries[-1].enabled is False
    assert entries[-1].hint == "Unlock the timeline to edit"
    items = _items(TimelineTimeMenu(controls, _Transport()))
    assert items["timeline.generate"].enabled is False
    assert items["timeline.generate"].hint == "Unlock the timeline to edit"
    assert items["edit.undo"].hint == "Unlock the timeline to edit"


def test_marker_intensity_submenu_checks_and_sets_it() -> None:
    controls = make_controls()
    controls.session.song_markers.markers = [SongMarker(12.2, "drop")]
    submenu = _marker_entries(controls)[4]
    assert submenu.label == "Intensity"
    assert [(i.label, i.checked) for i in submenu.items] == [
        ("very calm", False),
        ("calm", False),
        ("normal", True),
        ("intense", False),
        ("very intense", False),
    ]
    submenu.items[1].run()
    assert controls.session.song_markers.markers == [SongMarker(12.2, "drop", "calm")]
