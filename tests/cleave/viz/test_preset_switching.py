"""Tests for cleave.viz.preset_switching runtime helper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

from cleave.config_schema import (
    DEFAULT_EASTER_EGG,
    DEFAULT_HARD_CUT_DURATION,
    DEFAULT_HARD_CUT_ENABLED,
    DEFAULT_HARD_CUT_SENSITIVITY,
    DEFAULT_PRESET_DURATION,
    DEFAULT_PRESET_START_CLEAN,
    DEFAULT_SOFT_CUT_DURATION,
)
from cleave.preset_playlist import PresetPlaylist
from cleave.projectm import ProjectM
from cleave.viz.layer import StemLayer
from cleave.timeline import SlotCue, TimelineLane
from cleave.viz.preset_switching import (
    EMPTY_ROTATION_NOTIFICATION,
    EMPTY_USER_PRESETS_NOTIFICATION,
    active_auto_preset_path,
    advance_timeline_preset_switching,
    apply_preset_switching,
    load_manual_preset_clean,
    reapply_projectm_preset_switching,
    reset_projectm_preset_timer,
    restart_projectm_preset_timer,
)
from cleave.viz.session import LayerRuntime, TuningSession

_MILK = (
    Path("/tmp/presets/drums/a.milk"),
    Path("/tmp/presets/drums/b.milk"),
    Path("/tmp/presets/drums/c.milk"),
)


def _stem_layer(*, paths: tuple[Path, ...], index: int = 0) -> StemLayer:
    current_dir = Path("/tmp/presets/drums")
    playlist = PresetPlaylist(current_dir=current_dir, paths=paths, index=index)
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


def test_load_manual_preset_clean_forces_black_boot_then_restores() -> None:
    layer = _stem_layer(paths=_MILK)
    layer.playlist.load_into = MagicMock()

    load_manual_preset_clean(layer, preset_start_clean=False)

    assert layer.pm.set_preset_start_clean.call_args_list == [
        call(True),
        call(False),
    ]
    layer.playlist.load_into.assert_called_once_with(layer.pm, smooth=False)


def test_load_manual_preset_clean_restores_configured_start_clean() -> None:
    layer = _stem_layer(paths=_MILK)
    layer.playlist.load_into = MagicMock()

    load_manual_preset_clean(layer, preset_start_clean=True)

    assert layer.pm.set_preset_start_clean.call_args_list == [
        call(True),
        call(True),
    ]


def test_load_manual_preset_clean_noop_without_preset() -> None:
    layer = _stem_layer(paths=())
    layer.playlist.load_into = MagicMock()

    load_manual_preset_clean(layer)

    layer.pm.set_preset_start_clean.assert_not_called()
    layer.playlist.load_into.assert_not_called()


def test_apply_none_locks_and_disables_hard_cuts() -> None:
    layer = _stem_layer(paths=_MILK)
    mock_pl = MagicMock()
    layer.projectm_playlist = mock_pl
    layer.auto_preset_path = _MILK[2]

    apply_preset_switching(layer, mode="none", rotation_set="directory")

    mock_pl.destroy.assert_called_once()
    assert layer.projectm_playlist is None
    assert layer.auto_preset_path is None
    layer.pm.lock_preset.assert_called_with(True)
    layer.pm.set_hard_cut_enabled.assert_called_with(False)


@patch("cleave.viz.preset_switching.milk_files_in_dir", return_value=_MILK)
@patch("cleave.viz.preset_switching.ProjectMPlaylist")
def test_apply_projectm_connects_playlist(
    mock_playlist_cls: MagicMock,
    _mock_milk: MagicMock,
) -> None:
    layer = _stem_layer(paths=_MILK)
    playlist = MagicMock()
    playlist.size.return_value = 3
    playlist.item.side_effect = lambda i: _MILK[i]
    mock_playlist_cls.create.return_value = playlist
    on_empty = MagicMock()

    apply_preset_switching(
        layer, mode="projectm", rotation_set="directory", on_empty=on_empty
    )

    layer.pm.lock_preset.assert_called_with(False)
    layer.pm.set_hard_cut_enabled.assert_called_with(DEFAULT_HARD_CUT_ENABLED)
    layer.pm.set_preset_duration.assert_called_once_with(DEFAULT_PRESET_DURATION)
    layer.pm.set_soft_cut_duration.assert_called_once_with(DEFAULT_SOFT_CUT_DURATION)
    layer.pm.set_hard_cut_duration.assert_called_once_with(DEFAULT_HARD_CUT_DURATION)
    layer.pm.set_hard_cut_sensitivity.assert_called_once_with(
        DEFAULT_HARD_CUT_SENSITIVITY
    )
    layer.pm.set_easter_egg.assert_called_once_with(DEFAULT_EASTER_EGG)
    layer.pm.set_preset_start_clean.assert_called_once_with(False)
    playlist.connect.assert_called_once()
    assert playlist.connect.call_args.kwargs["on_preset_loaded"] is not None
    playlist.add_path.assert_called_once_with(
        layer.playlist.current_dir, recurse=False, allow_duplicates=False
    )
    playlist.sort.assert_called_once_with()
    playlist.set_shuffle.assert_called_once_with(False)
    assert layer.projectm_playlist is playlist
    layer.pm.load_preset.assert_called_once_with(_MILK[0], smooth=False)
    assert layer.auto_preset_path == _MILK[0].resolve()
    playlist.set_position.assert_called_once_with(0, hard_cut=True)
    on_empty.assert_not_called()


@patch("cleave.viz.preset_switching.milk_files_in_dir", return_value=_MILK)
@patch("cleave.viz.preset_switching.ProjectMPlaylist")
def test_apply_projectm_shuffle_enabled(
    mock_playlist_cls: MagicMock,
    _mock_milk: MagicMock,
) -> None:
    layer = _stem_layer(paths=_MILK)
    playlist = MagicMock()
    playlist.size.return_value = 3
    playlist.item.side_effect = lambda i: _MILK[i]
    mock_playlist_cls.create.return_value = playlist

    apply_preset_switching(
        layer,
        mode="projectm",
        rotation_set="directory",
        shuffle=True,
    )

    playlist.set_shuffle.assert_called_once_with(True)


@patch("cleave.viz.preset_switching.milk_files_in_dir", return_value=_MILK)
@patch("cleave.viz.preset_switching.ProjectMPlaylist")
def test_apply_projectm_respects_hard_cut_disabled(
    mock_playlist_cls: MagicMock,
    _mock_milk: MagicMock,
) -> None:
    layer = _stem_layer(paths=_MILK)
    playlist = MagicMock()
    playlist.size.return_value = 3
    playlist.item.side_effect = lambda i: _MILK[i]
    mock_playlist_cls.create.return_value = playlist

    apply_preset_switching(
        layer,
        mode="projectm",
        rotation_set="directory",
        hard_cut_enabled=False,
    )

    layer.pm.set_hard_cut_enabled.assert_called_with(False)


def test_restart_projectm_preset_timer_skips_when_no_current() -> None:
    layer = _stem_layer(paths=())
    restart_projectm_preset_timer(layer)
    layer.pm.load_preset.assert_not_called()


def test_restart_projectm_preset_timer_uses_tracked_auto_preset() -> None:
    layer = _stem_layer(paths=_MILK, index=0)
    layer.auto_preset_path = _MILK[2].resolve()
    restart_projectm_preset_timer(layer)
    layer.pm.load_preset.assert_called_once_with(_MILK[2].resolve(), smooth=False)


def test_restart_projectm_preset_timer_falls_back_to_browse_current() -> None:
    layer = _stem_layer(paths=_MILK, index=1)
    restart_projectm_preset_timer(layer)
    layer.pm.load_preset.assert_called_once_with(_MILK[1], smooth=False)
    assert layer.auto_preset_path == _MILK[1].resolve()


def test_reset_projectm_preset_timer_locks_and_unlocks() -> None:
    layer = _stem_layer(paths=_MILK)
    reset_projectm_preset_timer(layer)
    layer.pm.lock_preset.assert_has_calls([call(True), call(False)])
    layer.pm.load_preset.assert_not_called()


def test_active_auto_preset_path_prefers_tracked() -> None:
    layer = _stem_layer(paths=_MILK, index=0)
    layer.auto_preset_path = _MILK[2].resolve()
    assert active_auto_preset_path(layer) == _MILK[2].resolve()


@patch("cleave.viz.preset_switching.ProjectMPlaylist")
def test_apply_projectm_empty_dir_falls_back(mock_playlist_cls: MagicMock) -> None:
    layer = _stem_layer(paths=())
    on_empty = MagicMock()

    apply_preset_switching(
        layer, mode="projectm", rotation_set="directory", on_empty=on_empty
    )

    mock_playlist_cls.create.assert_not_called()
    layer.pm.lock_preset.assert_called_with(True)
    on_empty.assert_called_once()


def test_empty_rotation_notification_text() -> None:
    assert "No presets" in EMPTY_ROTATION_NOTIFICATION


def test_empty_user_presets_notification_text() -> None:
    assert "user-defined" in EMPTY_USER_PRESETS_NOTIFICATION


@patch("cleave.viz.preset_switching.ProjectMPlaylist")
def test_apply_user_defined_rotation_set_adds_presets(
    mock_playlist_cls: MagicMock,
) -> None:
    layer = _stem_layer(paths=_MILK)
    playlist = MagicMock()
    playlist.size.return_value = 2
    playlist.item.side_effect = lambda i: _MILK[i]
    mock_playlist_cls.create.return_value = playlist
    on_empty = MagicMock()

    apply_preset_switching(
        layer,
        mode="projectm",
        rotation_set="user_defined",
        user_presets=[str(_MILK[0]), str(_MILK[1])],
        on_empty=on_empty,
    )

    layer.pm.lock_preset.assert_called_with(False)
    playlist.add_presets.assert_called_once_with(
        [Path(str(_MILK[0])), Path(str(_MILK[1]))],
        allow_duplicates=True,
    )
    playlist.sort.assert_not_called()
    playlist.add_path.assert_not_called()
    on_empty.assert_not_called()


@patch("cleave.viz.preset_switching.ProjectMPlaylist")
def test_apply_user_defined_rotation_set_empty_falls_back(
    mock_playlist_cls: MagicMock,
) -> None:
    layer = _stem_layer(paths=_MILK)
    on_empty = MagicMock()

    apply_preset_switching(
        layer,
        mode="projectm",
        rotation_set="user_defined",
        user_presets=[],
        on_empty=on_empty,
    )

    mock_playlist_cls.create.assert_not_called()
    layer.pm.lock_preset.assert_called_with(True)
    on_empty.assert_called_once()


def test_reapply_projectm_preset_switching_only_projectm_layers() -> None:
    layer_projectm = _stem_layer(paths=_MILK)
    layer_projectm.projectm_playlist = MagicMock()
    layer_none = _stem_layer(paths=_MILK)
    session = TuningSession(
        layer_z_order=["layer_1", "layer_2"],
        layers={
            "layer_1": LayerRuntime(
                playlist=layer_projectm.playlist,
                browse_floor=layer_projectm.playlist.current_dir,
                stem="drums",
                preset_switching="projectm",
            ),
            "layer_2": LayerRuntime(
                playlist=layer_none.playlist,
                browse_floor=layer_none.playlist.current_dir,
                stem="bass",
                preset_switching="none",
            ),
        },
    )

    with (
        patch("cleave.viz.preset_switching.milk_files_in_dir", return_value=_MILK),
        patch("cleave.viz.preset_switching.apply_preset_switching") as mock_apply,
        patch("cleave.viz.preset_switching._reapply_on_seek") as mock_reapply,
    ):
        reapply_projectm_preset_switching(
            session,
            {"layer_1": layer_projectm, "layer_2": layer_none},
        )

    mock_apply.assert_not_called()
    mock_reapply.assert_called_once_with(
        layer_projectm,
        0.0,
        preset_duration=DEFAULT_PRESET_DURATION,
        soft_cut_duration=DEFAULT_SOFT_CUT_DURATION,
        easter_egg=DEFAULT_EASTER_EGG,
        preset_start_clean=DEFAULT_PRESET_START_CLEAN,
        hard_cut_duration=DEFAULT_HARD_CUT_DURATION,
        hard_cut_sensitivity=DEFAULT_HARD_CUT_SENSITIVITY,
        hard_cut_enabled=DEFAULT_HARD_CUT_ENABLED,
    )


def test_reapply_without_playlist_falls_back_to_apply() -> None:
    layer = _stem_layer(paths=_MILK)
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=layer.playlist,
                browse_floor=layer.playlist.current_dir,
                stem="drums",
                preset_switching="projectm",
            ),
        },
    )

    with patch("cleave.viz.preset_switching.apply_preset_switching") as mock_apply:
        reapply_projectm_preset_switching(session, {"layer_1": layer})

    mock_apply.assert_called_once()
    assert mock_apply.call_args.kwargs.get("on_empty") is None


@patch("cleave.viz.preset_switching.ProjectMPlaylist")
def test_reapply_without_playlist_does_not_notify_empty(
    mock_playlist_cls: MagicMock,
) -> None:
    layer = _stem_layer(paths=())
    on_empty = MagicMock()
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=layer.playlist,
                browse_floor=layer.playlist.current_dir,
                stem="drums",
                preset_switching="projectm",
            ),
        },
    )

    apply_preset_switching(
        layer, mode="projectm", rotation_set="directory", on_empty=on_empty
    )
    on_empty.assert_called_once()
    on_empty.reset_mock()

    reapply_projectm_preset_switching(session, {"layer_1": layer})

    on_empty.assert_not_called()
    mock_playlist_cls.create.assert_not_called()


def test_reapply_on_forward_seek_reconnects_without_reload() -> None:
    layer = _stem_layer(paths=_MILK, index=0)
    layer.auto_preset_path = _MILK[2].resolve()
    playlist = MagicMock()
    layer.projectm_playlist = playlist
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=layer.playlist,
                browse_floor=layer.playlist.current_dir,
                stem="drums",
                preset_switching="projectm",
            ),
        },
    )

    reapply_projectm_preset_switching(session, {"layer_1": layer}, delta_sec=5.0)

    playlist.connect.assert_called_once()
    layer.pm.lock_preset.assert_has_calls([call(False), call(True), call(False)])
    layer.pm.load_preset.assert_not_called()
    playlist.set_position.assert_not_called()


def test_reapply_on_backward_seek_restarts_tracked_preset() -> None:
    layer = _stem_layer(paths=_MILK, index=0)
    layer.auto_preset_path = _MILK[2].resolve()
    playlist = MagicMock()
    layer.projectm_playlist = playlist
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=layer.playlist,
                browse_floor=layer.playlist.current_dir,
                stem="drums",
                preset_switching="projectm",
            ),
        },
    )

    reapply_projectm_preset_switching(session, {"layer_1": layer}, delta_sec=-5.0)

    playlist.connect.assert_called_once()
    layer.pm.load_preset.assert_called_once_with(_MILK[2].resolve(), smooth=False)
    layer.pm.lock_preset.assert_called_with(False)


def _timeline_session(layer: StemLayer, *, enabled: bool = True) -> TuningSession:
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=layer.playlist,
                browse_floor=layer.playlist.current_dir,
                stem="drums",
                preset_switching="timeline",
            ),
        },
    )
    session.timeline.enabled = enabled
    session.timeline.lanes["layer_1"] = TimelineLane(
        baseline=False,
        cues=[
            SlotCue(t=5.0, visible=True),
            SlotCue(t=10.0, visible=False),
            SlotCue(t=15.0, visible=True),
        ],
    )
    return session


@patch("cleave.viz.preset_switching.milk_files_in_dir", return_value=_MILK)
def test_apply_timeline_locks_and_loads_anchor(_mock_milk: MagicMock) -> None:
    layer = _stem_layer(paths=_MILK, index=1)
    apply_preset_switching(layer, mode="timeline", rotation_set="directory")
    layer.pm.lock_preset.assert_called_with(True)
    layer.pm.set_hard_cut_enabled.assert_called_with(False)
    assert layer.preset_rotation is not None
    assert layer.rotation_anchor == 1
    assert layer.timeline_switch_count == 0
    layer.pm.load_preset.assert_called_once_with(_MILK[1], smooth=False)


@patch("cleave.viz.preset_switching.milk_files_in_dir", return_value=_MILK)
def test_advance_timeline_loads_next_on_rising_edge(_mock_milk: MagicMock) -> None:
    layer = _stem_layer(paths=_MILK, index=0)
    session = _timeline_session(layer)
    apply_preset_switching(layer, mode="timeline", rotation_set="directory")
    layer.pm.load_preset.reset_mock()

    advance_timeline_preset_switching(session, {"layer_1": layer}, 4.9)
    layer.pm.load_preset.assert_not_called()
    assert layer.timeline_switch_count == 0

    advance_timeline_preset_switching(session, {"layer_1": layer}, 5.0)
    layer.pm.load_preset.assert_called_once_with(_MILK[1], smooth=False)
    assert layer.timeline_switch_count == 1

    layer.pm.load_preset.reset_mock()
    advance_timeline_preset_switching(session, {"layer_1": layer}, 15.0)
    layer.pm.load_preset.assert_called_once_with(_MILK[2], smooth=False)
    assert layer.timeline_switch_count == 2


@patch("cleave.viz.preset_switching.milk_files_in_dir", return_value=_MILK)
def test_advance_timeline_noop_when_timeline_disabled(_mock_milk: MagicMock) -> None:
    layer = _stem_layer(paths=_MILK, index=0)
    session = _timeline_session(layer, enabled=False)
    apply_preset_switching(layer, mode="timeline", rotation_set="directory")
    layer.pm.load_preset.reset_mock()

    advance_timeline_preset_switching(session, {"layer_1": layer}, 15.0)
    layer.pm.load_preset.assert_not_called()
    assert layer.timeline_switch_count == 0


def test_tick_frame_core_advances_timeline_when_playing() -> None:
    from cleave.viz.app import tick_frame_core

    runtime = MagicMock()
    runtime.seed.session = MagicMock()
    runtime.layers_by_slot = {}
    runtime.layers = []
    with (
        patch("cleave.viz.app.apply_layer_visibility"),
        patch("cleave.viz.app.advance_timeline_preset_switching") as mock_advance,
        patch("cleave.viz.app.LayerFramePipeline.render_frame"),
        patch("cleave.viz.app.LayerFramePipeline.composite"),
    ):
        tick_frame_core(
            runtime,
            1.0,
            paused=False,
            was_paused=False,
            n_pcm=0,
            pm_time_sec=1.0,
            blank_visualizers=False,
        )
    mock_advance.assert_called_once_with(runtime.seed.session, {}, 1.0)


def test_tick_frame_core_skips_advance_when_paused() -> None:
    from cleave.viz.app import tick_frame_core

    runtime = MagicMock()
    runtime.seed.session = MagicMock()
    runtime.layers_by_slot = {}
    runtime.layers = []
    with (
        patch("cleave.viz.app.apply_layer_visibility"),
        patch("cleave.viz.app.advance_timeline_preset_switching") as mock_advance,
        patch("cleave.viz.app.LayerFramePipeline.render_frame"),
        patch("cleave.viz.app.LayerFramePipeline.composite"),
    ):
        tick_frame_core(
            runtime,
            1.0,
            paused=True,
            was_paused=True,
            n_pcm=0,
            pm_time_sec=1.0,
            blank_visualizers=False,
        )
    mock_advance.assert_not_called()
