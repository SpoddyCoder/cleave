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
    assert markers.times == [15.0]
    assert markers.selected_index is None
    assert markers.expanded is True
    assert session.timeline.panel_open is True
    assert notes == ["Song marker 00:15.00"]


def test_drop_refused_while_recording() -> None:
    controller, session, _modal = _make_controller()
    session.timeline.recording = True
    controller._playback.player.seek(15.0)
    controller.drop()
    assert session.song_markers.times == []


def test_set_expanded() -> None:
    controller, session, _modal = _make_controller()
    assert session.song_markers.expanded is False
    controller.set_expanded(True)
    assert session.song_markers.expanded is True
    controller.set_expanded(True)
    assert session.song_markers.expanded is True


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
    assert view.message == "Remove song marker 00:15.00?"
    assert view.options == ("Yes", "No")
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
    assert session.song_markers.times == [10.0]
