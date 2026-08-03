"""Tests for unified list-based preset switching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

from cleave.preset_playlist import PresetPlaylist
from cleave.projectm import ProjectM
from cleave.timeline import SlotCue, TimelineLane
from cleave.viz.layer import StemLayer
from cleave.viz.preset_switching import (
    EMPTY_PRESET_LIST_NOTIFICATION,
    active_auto_preset_path,
    advance_preset_switching,
    apply_preset_switching,
    load_manual_preset_clean,
    reanchor_list_preset_after_browse,
    reapply_projectm_preset_switching,
)
from cleave.viz.session import LayerRuntime, TuningSession

_MILK = (
    Path("/tmp/presets/drums/a.milk"),
    Path("/tmp/presets/drums/b.milk"),
    Path("/tmp/presets/drums/c.milk"),
)
_LIST = [str(path) for path in _MILK]


def _stem_layer(*, paths: tuple[Path, ...] = _MILK, index: int = 0) -> StemLayer:
    playlist = PresetPlaylist(
        current_dir=Path("/tmp/presets/drums"), paths=paths, index=index
    )
    pm = ProjectM.__new__(ProjectM)
    pm.lock_preset = MagicMock()
    pm.set_hard_cut_enabled = MagicMock()
    pm.set_soft_cut_duration = MagicMock()
    pm.set_preset_duration = MagicMock()
    pm.set_hard_cut_duration = MagicMock()
    pm.set_hard_cut_sensitivity = MagicMock()
    pm.set_easter_egg = MagicMock()
    pm.set_preset_start_clean = MagicMock()
    pm.load_preset = MagicMock()
    return StemLayer(slot="layer_1", pm=pm, fbo=MagicMock(), playlist=playlist)


def _session(
    *,
    switching: str = "on",
    trigger: str = "timer",
    preset_list: list[str] | None = None,
    timeline_enabled: bool = False,
    duration: float = 30.0,
) -> TuningSession:
    runtime = LayerRuntime(
        playlist=PresetPlaylist(
            current_dir=Path("/tmp/presets/drums"),
            paths=_MILK,
            index=0,
        ),
        browse_floor=Path("/tmp/presets/drums"),
        stem="drums",
        preset_switching=switching,  # type: ignore[arg-type]
        preset_switching_trigger=trigger,  # type: ignore[arg-type]
        preset_list=list(preset_list if preset_list is not None else _LIST),
        preset_duration=duration,
    )
    session = TuningSession(layer_z_order=["layer_1"], layers={"layer_1": runtime})
    session.timeline.enabled = timeline_enabled
    return session


def test_load_manual_preset_clean_forces_black_boot_then_restores() -> None:
    layer = _stem_layer()
    layer.playlist.load_into = MagicMock()
    load_manual_preset_clean(layer, preset_start_clean=False)
    assert layer.pm.set_preset_start_clean.call_args_list == [
        call(True),
        call(False),
    ]
    layer.playlist.load_into.assert_called_once_with(layer.pm, smooth=False)
    assert layer.auto_preset_path == _MILK[0].resolve()


def test_apply_off_locks_and_clears_playlist() -> None:
    layer = _stem_layer()
    mock_pl = MagicMock()
    layer.projectm_playlist = mock_pl
    layer.auto_preset_path = _MILK[2]
    apply_preset_switching(layer, mode="off", preset_list=_LIST)
    mock_pl.destroy.assert_called_once()
    assert layer.projectm_playlist is None
    assert layer.auto_preset_path is None
    assert layer.preset_rotation is None
    layer.pm.lock_preset.assert_called_with(True)


def test_apply_on_empty_list_notifies_and_holds() -> None:
    layer = _stem_layer()
    on_empty = MagicMock()
    apply_preset_switching(
        layer, mode="on", trigger="timer", preset_list=[], on_empty=on_empty
    )
    on_empty.assert_called_once()
    assert layer.preset_rotation is None
    layer.pm.lock_preset.assert_called_with(True)


@patch("cleave.viz.preset_switching.ProjectMPlaylist")
def test_apply_projectm_trigger_feeds_list(mock_playlist_cls: MagicMock) -> None:
    layer = _stem_layer()
    playlist = MagicMock()
    playlist.size.return_value = 3
    playlist.item.side_effect = list(_MILK)
    mock_playlist_cls.create.return_value = playlist
    apply_preset_switching(
        layer, mode="on", trigger="projectm", preset_list=_LIST
    )
    playlist.add_presets.assert_called_once_with(list(_MILK), allow_duplicates=True)
    playlist.set_shuffle.assert_called_once_with(False)
    assert layer.projectm_playlist is playlist
    layer.pm.lock_preset.assert_called_with(False)


def test_apply_timer_trigger_builds_rotation() -> None:
    layer = _stem_layer()
    apply_preset_switching(
        layer, mode="on", trigger="timer", preset_list=_LIST
    )
    assert layer.projectm_playlist is None
    assert layer.preset_rotation is not None
    assert layer.preset_rotation.paths == _MILK
    layer.pm.lock_preset.assert_called_with(True)
    layer.pm.load_preset.assert_called()


def test_apply_timeline_trigger_indexes_list() -> None:
    layer = _stem_layer()
    session = _session(trigger="timeline", timeline_enabled=True)
    apply_preset_switching(
        layer,
        mode="on",
        trigger="timeline",
        preset_list=_LIST,
        session=session,
    )
    assert layer.projectm_playlist is None
    assert layer.preset_rotation is not None
    layer.pm.lock_preset.assert_called_with(True)


@patch("cleave.viz.preset_switching.ProjectMPlaylist")
def test_apply_projectm_trigger_works_with_timeline_enabled(
    mock_playlist_cls: MagicMock,
) -> None:
    layer = _stem_layer()
    playlist = MagicMock()
    playlist.size.return_value = 3
    playlist.item.side_effect = list(_MILK)
    mock_playlist_cls.create.return_value = playlist
    session = _session(trigger="projectm", timeline_enabled=True)
    apply_preset_switching(
        layer,
        mode="on",
        trigger="projectm",
        preset_list=_LIST,
        session=session,
    )
    assert layer.projectm_playlist is playlist
    layer.pm.lock_preset.assert_called_with(False)


def test_apply_timer_trigger_works_with_timeline_enabled() -> None:
    layer = _stem_layer()
    session = _session(trigger="timer", timeline_enabled=True)
    apply_preset_switching(
        layer,
        mode="on",
        trigger="timer",
        preset_list=_LIST,
        session=session,
    )
    assert layer.projectm_playlist is None
    assert layer.preset_rotation is not None


def test_advance_timer_uses_floor_playhead() -> None:
    layer = _stem_layer()
    session = _session(trigger="timer", duration=10.0)
    apply_preset_switching(
        layer,
        mode="on",
        trigger="timer",
        preset_list=_LIST,
        preset_duration=10.0,
        session=session,
    )
    layer.pm.load_preset.reset_mock()
    advance_preset_switching(session, {"layer_1": layer}, 0.0)
    layer.pm.load_preset.assert_not_called()
    advance_preset_switching(session, {"layer_1": layer}, 10.0)
    layer.pm.load_preset.assert_called_once()
    assert layer.list_switch_index == 1


def test_advance_timeline_uses_on_transition_count() -> None:
    layer = _stem_layer()
    session = _session(trigger="timeline", timeline_enabled=True)
    session.timeline.lanes["layer_1"] = TimelineLane(
        baseline=0.0,
        cues=(
            SlotCue(t=1.0, level=1.0),
            SlotCue(t=2.0, level=0.0),
            SlotCue(t=3.0, level=1.0),
        ),
    )
    apply_preset_switching(
        layer,
        mode="on",
        trigger="timeline",
        preset_list=_LIST,
        session=session,
    )
    layer.pm.load_preset.reset_mock()
    advance_preset_switching(session, {"layer_1": layer}, 0.5)
    layer.pm.load_preset.assert_not_called()
    advance_preset_switching(session, {"layer_1": layer}, 1.5)
    layer.pm.load_preset.assert_called_once()
    assert layer.list_switch_index == 1


def test_advance_timeline_skips_when_timeline_disabled() -> None:
    layer = _stem_layer()
    session = _session(trigger="timeline", timeline_enabled=False)
    session.timeline.lanes["layer_1"] = TimelineLane(
        baseline=0.0,
        cues=(
            SlotCue(t=1.0, level=1.0),
            SlotCue(t=2.0, level=0.0),
            SlotCue(t=3.0, level=1.0),
        ),
    )
    apply_preset_switching(
        layer,
        mode="on",
        trigger="timeline",
        preset_list=_LIST,
        session=session,
    )
    layer.pm.load_preset.reset_mock()
    advance_preset_switching(session, {"layer_1": layer}, 1.5)
    layer.pm.load_preset.assert_not_called()
    assert layer.list_switch_index == 0


def test_advance_timer_works_with_timeline_enabled() -> None:
    layer = _stem_layer()
    session = _session(trigger="timer", timeline_enabled=True, duration=10.0)
    apply_preset_switching(
        layer,
        mode="on",
        trigger="timer",
        preset_list=_LIST,
        preset_duration=10.0,
        session=session,
    )
    layer.pm.load_preset.reset_mock()
    advance_preset_switching(session, {"layer_1": layer}, 10.0)
    layer.pm.load_preset.assert_called_once()
    assert layer.list_switch_index == 1


def test_advance_skips_when_switching_off() -> None:
    layer = _stem_layer()
    session = _session(switching="off")
    advance_preset_switching(session, {"layer_1": layer}, 100.0)
    layer.pm.load_preset.assert_not_called()


def test_reanchor_after_browse_preserves_current() -> None:
    layer = _stem_layer(index=1)
    session = _session(trigger="timer", duration=10.0)
    apply_preset_switching(
        layer,
        mode="on",
        trigger="timer",
        preset_list=_LIST,
        preset_duration=10.0,
        session=session,
    )
    reanchor_list_preset_after_browse(
        layer, session, 10.0, preset_list=_LIST
    )
    assert layer.list_switch_index == 1
    assert layer.preset_rotation is not None
    # browsed b.milk at index 1 while count==1 => anchor 0 keeps b at count 1
    assert layer.preset_rotation.path_for(1) == _MILK[1]


@patch("cleave.viz.preset_switching.ProjectMPlaylist")
def test_reapply_projectm_only_when_trigger_projectm(
    mock_playlist_cls: MagicMock,
) -> None:
    layer = _stem_layer()
    playlist = MagicMock()
    playlist.size.return_value = 3
    playlist.item.side_effect = list(_MILK)
    mock_playlist_cls.create.return_value = playlist
    session = _session(trigger="projectm")
    apply_preset_switching(
        layer,
        mode="on",
        trigger="projectm",
        preset_list=_LIST,
        session=session,
    )
    layer.projectm_playlist = playlist
    reapply_projectm_preset_switching(
        session, {"layer_1": layer}, preset_root=Path("/tmp/presets"), delta_sec=1.0
    )
    layer.pm.lock_preset.assert_any_call(False)


def test_active_auto_preset_path_prefers_auto() -> None:
    layer = _stem_layer()
    layer.auto_preset_path = _MILK[2].resolve()
    assert active_auto_preset_path(layer) == _MILK[2].resolve()


def test_empty_notification_constant() -> None:
    assert "list" in EMPTY_PRESET_LIST_NOTIFICATION.lower()
