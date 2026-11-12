"""Time items for a right-click on the timeline ruler or an empty row spot."""

from __future__ import annotations

from cleave.song_markers import SongMarker
from cleave.timeline import SlotCue, TimelineLane
from cleave.viz.context_menu import ContextMenuItem, ContextSubmenu
from cleave.viz.timeline_time_menu import TimelineTimeMenu
from tests.cleave.viz.test_controls import _make_controls


class _Transport:
    def __init__(self, *, paused: bool = True) -> None:
        self.paused = paused
        self.calls: list[tuple] = []

    def seek_to(self, t_sec: float) -> None:
        self.calls.append(("seek", t_sec))

    def toggle_transport(self) -> None:
        self.calls.append(("transport",))
        self.paused = not self.paused


def _items(menu: TimelineTimeMenu, t: float = 12.0, *, commands: bool = True):
    return {
        entry.id: entry
        for entry in menu.entries(t, 0.5, commands=commands)
        if isinstance(entry, ContextMenuItem)
    }


def test_row_time_items_seek_play_and_drop() -> None:
    controls = _make_controls()
    transport = _Transport()
    items = _items(TimelineTimeMenu(controls, transport), commands=False)
    assert list(items) == [
        "timeline.time.seek",
        "timeline.time.play",
        "timeline.time.drop_marker",
    ]
    items["timeline.time.seek"].run()
    items["timeline.time.play"].run()
    assert transport.calls == [("seek", 12.0), ("seek", 12.0), ("transport",)]
    items["timeline.time.drop_marker"].run()
    assert controls.session.song_markers.times == [12.0]


def test_play_from_here_does_not_pause_a_playing_song() -> None:
    transport = _Transport(paused=False)
    _items(TimelineTimeMenu(_make_controls(), transport))["timeline.time.play"].run()
    assert transport.calls == [("seek", 12.0)]


def _marker_entries(controls, *, commands: bool = False):
    return TimelineTimeMenu(controls, _Transport()).entries(
        12.0, 0.5, commands=commands, marker_index=0
    )


def test_marker_items_replace_the_time_items() -> None:
    controls = _make_controls()
    controls.session.song_markers.markers = [SongMarker(time=12.2, marker_type="begin")]
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
        "timeline.marker.delete",
    ]
    entries[0].run()
    entries[1].run()
    assert transport.calls == [("seek", 12.2), ("seek", 12.2), ("transport",)]
    assert entries[4].label == "Delete marker 00:12.20..."
    assert entries[4].shortcut == "Delete"


def test_marker_type_submenu_checks_and_sets_the_type() -> None:
    controls = _make_controls()
    controls.session.song_markers.markers = [
        SongMarker(time=12.2),
        SongMarker(time=30.0, marker_type="crescendo"),
    ]
    submenu = _marker_entries(controls)[3]
    assert isinstance(submenu, ContextSubmenu)
    checked = [item.id for item in submenu.items if getattr(item, "checked", False)]
    assert checked == ["timeline.marker.type.standard"]
    begin = next(i for i in submenu.items if i.id == "timeline.marker.type.begin")
    begin.run()
    assert controls.session.song_markers.markers[0].marker_type == "begin"


def test_recording_disables_marker_edits_but_not_seeking() -> None:
    controls = _make_controls()
    controls.session.song_markers.markers = [SongMarker(time=12.2)]
    controls.session.timeline.recording = True
    entries = _marker_entries(controls)
    assert entries[0].enabled is True
    assert entries[3].enabled is False
    assert entries[4].enabled is False
    assert entries[4].hint == "Stop recording to edit markers"


def test_a_gone_marker_falls_back_to_the_time_items() -> None:
    controls = _make_controls()
    ids = [getattr(e, "id", None) for e in _marker_entries(controls)]
    assert ids[0] == "timeline.time.seek"


def test_recording_blocks_marker_drop() -> None:
    controls = _make_controls()
    controls.session.timeline.recording = True
    drop = _items(TimelineTimeMenu(controls, _Transport()))["timeline.time.drop_marker"]
    assert drop.enabled is False
    assert drop.hint == "Stop recording to drop markers"


def test_ruler_lists_history_and_timeline_commands() -> None:
    items = _items(TimelineTimeMenu(_make_controls(), _Transport()))
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
    assert items["timeline.generate"].enabled is True
    assert items["edit.undo"].label == "Undo"
    assert items["edit.undo"].enabled is False
    assert items["edit.undo"].hint == "Nothing to undo"
    assert items["edit.undo"].shortcut == "Ctrl+Z"


def test_undo_label_names_the_last_command() -> None:
    controls = _make_controls()
    with controls.timeline_history.recording("Snap cues"):
        controls.session.timeline.lanes["layer_1"] = TimelineLane(
            baseline=None, cues=[SlotCue(t=3.0, level=1.0)]
        )
    undo = _items(TimelineTimeMenu(controls, _Transport()))["edit.undo"]
    assert undo.label == "Undo Snap cues"
    assert undo.enabled is True


def test_locked_timeline_disables_commands_with_a_hint() -> None:
    controls = _make_controls()
    controls.session.timeline.locked = True
    items = _items(TimelineTimeMenu(controls, _Transport()))
    assert items["timeline.generate"].enabled is False
    assert items["timeline.generate"].hint == "Unlock the timeline to edit"
    assert items["edit.undo"].hint == "Unlock the timeline to edit"
