"""Tests for song-marker controller."""

from __future__ import annotations

from cleave.song_markers import SongMarker
from cleave.viz.modal import ModalHost
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.song_marker_controls import SongMarkerController
from cleave.preset_playlist import PresetPlaylist
from tests.support.viz import keydown, stub_playback_state

import pygame
from pathlib import Path


def _make_controller(
    *,
    beat_times: tuple[float, ...] = (),
    bar_times: tuple[float, ...] = (),
    duration_sec: float = 120.0,
    on_notification=None,
    on_focus_marker=None,
) -> tuple[SongMarkerController, TuningSession, ModalHost]:
    playlist = PresetPlaylist(
        current_dir=Path("/tmp/presets/pack"),
        paths=(Path("/tmp/presets/pack/demo.milk"),),
        index=0,
    )
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=playlist,
                browse_floor=Path("/tmp/presets"),
                stem="drums",
                opacity_pct=50,
            ),
        },
    )
    modal = ModalHost()
    playback = stub_playback_state()
    controller = SongMarkerController(
        session,
        modal,
        beat_times,
        bar_times,
        playback,
        duration_sec,
        on_notification=on_notification,
        on_focus_marker=on_focus_marker,
    )
    return controller, session, modal


def test_drop_inserts_without_selecting() -> None:
    controller, session, _modal = _make_controller()
    notes: list[str] = []
    controller._on_notification = notes.append
    controller._playback.player.seek(15.0)
    controller.drop()
    markers = session.song_markers
    assert markers.times == [0.0, 15.0]
    assert markers.selected_index is None
    assert notes == ["Song markers 00:00.00 and 00:15.00"]


def test_drop_refused_while_recording() -> None:
    controller, session, _modal = _make_controller()
    session.timeline.recording = True
    controller._playback.player.seek(15.0)
    controller.drop()
    assert session.song_markers.times == []


def test_sync_focus_selects_marker_item() -> None:
    controller, session, _modal = _make_controller()
    session.song_markers.times = [5.0, 15.0]
    controller.sync_focus(
        RowDescriptor(RowKind.SONG_MARKER_ITEM, marker_index=1)
    )
    assert session.song_markers.selected_index == 1
    controller.sync_focus(RowDescriptor(RowKind.SONG_MARKERS_HEADER))
    assert session.song_markers.selected_index == 1


def test_prompt_delete_opens_yes_no() -> None:
    controller, session, modal = _make_controller()
    session.song_markers.times = [5.0, 15.0]
    controller.prompt_delete(1)
    view = modal.view_state()
    assert view is not None
    assert view.message == "Delete song marker 00:15.00?"
    assert view.options == ("Delete marker", "Cancel")
    assert session.song_markers.times == [5.0, 15.0]


def test_confirm_delete_adjusts_selection_and_focus() -> None:
    focused: list[int | None] = []
    notes: list[str] = []
    controller, session, modal = _make_controller(
        on_notification=notes.append,
        on_focus_marker=focused.append,
    )
    session.song_markers.times = [5.0, 15.0, 25.0]
    session.song_markers.selected_index = 1
    controller.prompt_delete(1)
    modal.handle_keydown(keydown(pygame.K_LEFT))
    modal.handle_keydown(keydown(pygame.K_RETURN))
    assert session.song_markers.times == [5.0, 25.0]
    assert session.song_markers.selected_index == 1
    assert focused == [1]
    assert notes == ["Song marker removed 00:15.00"]


def test_drop_snaps_to_beat() -> None:
    controller, session, _modal = _make_controller(beat_times=(10.0, 20.0))
    session.timeline.placement_snap = "beat"
    controller._playback.player.seek(11.0)
    controller.drop()
    assert session.song_markers.times == [0.0, 10.0]


def test_drop_at_places_at_the_given_time_not_the_playhead() -> None:
    controller, session, _modal = _make_controller(beat_times=(10.0, 20.0, 30.0))
    session.song_markers.markers = [SongMarker(time=50.0)]
    session.song_markers.selected_index = 0
    session.timeline.placement_snap = "beat"
    controller._playback.player.seek(5.0)
    controller.drop_at(19.0)
    assert session.song_markers.times == [20.0, 50.0]
    assert session.song_markers.selected_index == 1


def test_drop_at_refused_while_recording() -> None:
    controller, session, _modal = _make_controller()
    session.timeline.recording = True
    controller.drop_at(15.0)
    assert session.song_markers.times == []


def test_marker_near_finds_the_closest_within_tolerance() -> None:
    controller, session, _modal = _make_controller()
    assert controller.marker_near(10.0, 1.0) is None
    session.song_markers.markers = [SongMarker(time=10.0), SongMarker(time=12.0)]
    assert controller.marker_near(11.8, 0.5) == 1
    assert controller.marker_near(10.3, 0.5) == 0
    assert controller.marker_near(11.0, 0.5) is None


def test_select_starts_the_flash_only_on_a_change(monkeypatch) -> None:
    controller, session, _modal = _make_controller()
    session.song_markers.markers = [SongMarker(10.0), SongMarker(20.0)]
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: 5000)
    controller.select(1)
    assert session.song_markers.selected_index == 1
    assert session.song_markers.selected_flash_start_ms == 5000
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: 9000)
    controller.select(1)
    assert session.song_markers.selected_flash_start_ms == 5000
    controller.select(7)
    assert session.song_markers.selected_index == 1


def test_set_type_changes_the_type() -> None:
    notes: list[str] = []
    controller, session, _modal = _make_controller(on_notification=notes.append)
    session.song_markers.markers = [SongMarker(10.0)]
    controller.set_type(0, "verse")
    assert session.song_markers.markers[0] == SongMarker(10.0, "verse")
    assert notes == []


def test_drop_while_playing_subtracts_tap_latency() -> None:
    controller, session, _modal = _make_controller()
    player = controller._playback.player
    player.seek(15.25)
    player.set_tap_latency_sec(0.25)
    controller.drop()
    assert session.song_markers.times == [0.0, 15.0]


def test_drop_while_paused_ignores_tap_latency() -> None:
    controller, session, _modal = _make_controller()
    player = controller._playback.player
    player.seek(15.0)
    player.set_tap_latency_sec(0.25)
    player.pause(True)
    controller.drop()
    assert session.song_markers.times == [0.0, 15.0]


def test_drop_with_negative_tap_latency_lands_later() -> None:
    controller, session, _modal = _make_controller()
    player = controller._playback.player
    player.seek(15.0)
    player.set_tap_latency_sec(-0.05)
    controller.drop()
    assert session.song_markers.times == [0.0, 15.05]


def _open_snap(modal: ModalHost, target: str) -> None:
    row = modal.view_state().form_rows[0]
    modal.set_form_value(0, row.options.index(target))


def _snap_controller():
    notes: list[str] = []
    controller, session, modal = _make_controller(
        beat_times=tuple(float(t) for t in range(0, 17)),
        bar_times=(0.0, 4.0, 8.0, 12.0, 16.0),
        on_notification=notes.append,
    )
    return controller, session, modal, notes


def test_snap_moves_markers_to_bars_and_keeps_types_and_selection() -> None:
    controller, session, modal, notes = _snap_controller()
    session.song_markers.markers = [
        SongMarker(4.3, "verse"),
        SongMarker(8.0),
        SongMarker(60.0),
    ]
    session.song_markers.selected_index = 1
    controller.prompt_snap()
    view = modal.view_state()
    assert view.form_rows[0].options == ("beats", "bars")
    assert view.form_info == "Moves 1 of 3 song markers"
    modal.activate_option(0)
    assert session.song_markers.markers == [
        SongMarker(4.0, "verse"),
        SongMarker(8.0),
        SongMarker(60.0),
    ]
    assert session.song_markers.selected_index == 1
    assert notes == ["Snapped 1 song marker to bars"]


def test_snap_to_beats_and_remembers_target() -> None:
    controller, session, modal, notes = _snap_controller()
    session.song_markers.times = [4.3, 6.6]
    controller.prompt_snap()
    _open_snap(modal, "beats")
    modal.activate_option(0)
    assert session.song_markers.times == [4.0, 7.0]
    controller.prompt_snap()
    row = modal.view_state().form_rows[0]
    assert row.options[row.value] == "beats"


def test_snap_to_bars_follows_bar_phase() -> None:
    controller, session, modal, _notes = _snap_controller()
    session.timeline.bar_phase_offset = 1
    session.song_markers.times = [4.3]
    controller.prompt_snap()
    modal.activate_option(0)
    assert session.song_markers.times == [5.0]


def test_snap_merge_follows_selection() -> None:
    controller, session, modal, _notes = _snap_controller()
    session.song_markers.times = [3.9, 4.2, 8.1]
    session.song_markers.selected_index = 2
    controller.prompt_snap()
    assert modal.view_state().form_info == "Moves 3 of 3 song markers, merges 1"
    modal.activate_option(0)
    assert session.song_markers.times == [4.0, 8.0]
    assert session.song_markers.selected_index == 1


def test_snap_refused_without_markers_grid_or_while_locked_or_recording() -> None:
    controller, session, modal, notes = _snap_controller()
    controller.prompt_snap()
    assert notes == ["No song markers to snap"]
    session.song_markers.times = [4.3]
    session.timeline.recording = True
    controller.prompt_snap()
    session.timeline.recording = False
    session.timeline.locked = True
    controller.prompt_snap()
    assert not modal.active

    gridless, session, modal = _make_controller(on_notification=notes.append)
    session.song_markers.times = [4.3]
    gridless.prompt_snap()
    assert not modal.active
    assert notes[-1] == "No beats available; re-run separate"


def test_type_and_intensity_keep_each_other() -> None:
    controller, session, _modal = _make_controller()
    session.song_markers.markers = [SongMarker(10.0)]
    controller.set_intensity(0, "intense")
    controller.set_type(0, "drop")
    assert session.song_markers.markers == [SongMarker(10.0, "drop", "intense")]
    controller.set_intensity(5, "calm")
    assert session.song_markers.markers == [SongMarker(10.0, "drop", "intense")]
