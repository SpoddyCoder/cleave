"""Tests for cleave.viz.wiring live layer callbacks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from cleave.preset_playlist import PresetPlaylist
from cleave.projectm import ProjectM
from cleave.viz.layer import StemLayer
from cleave.viz.session import LayerRuntime, TimelineRuntime, TuningSession
from cleave.viz.wiring import make_tuning_controls
from tests.support.viz import make_test_cfg, stub_playback_state

_MILK = (
    Path("/tmp/presets/layer_1/a.milk"),
    Path("/tmp/presets/layer_1/b.milk"),
)


def _session(
    *,
    mode: str = "on",
    trigger: str = "timer",
    preset_list: list[str] | None = None,
    timeline_enabled: bool = False,
) -> TuningSession:
    playlist = PresetPlaylist(
        current_dir=Path("/tmp/presets/layer_1"),
        paths=_MILK,
        index=0,
    )
    return TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=playlist,
                browse_floor=Path("/tmp/presets/layer_1"),
                stem="drums",
                preset_switching=mode,  # type: ignore[arg-type]
                preset_switching_trigger=trigger,  # type: ignore[arg-type]
                preset_list=list(preset_list or [str(p) for p in _MILK]),
            )
        },
        timeline=TimelineRuntime(enabled=timeline_enabled),
    )


def _layer(session: TuningSession) -> StemLayer:
    pm = ProjectM.__new__(ProjectM)
    pm.lock_preset = MagicMock()
    pm.load_preset = MagicMock()
    pm.set_preset_start_clean = MagicMock()
    pm.set_hard_cut_enabled = MagicMock()
    pm.flush_pcm = MagicMock()
    pm._pcm_channels = 2
    return StemLayer(
        slot="layer_1",
        pm=pm,
        fbo=MagicMock(),
        playlist=session.layers["layer_1"].playlist,
    )


def _make_controls(session: TuningSession, layer: StemLayer):
    cfg = make_test_cfg(("layer_1",))
    return make_tuning_controls(
        session=session,
        cfg=cfg,
        preset_root=cfg.paths.preset_root,
        project_dir=Path("/tmp/project"),
        layers_by_slot={"layer_1": layer},
        layers=[layer],
        playback=stub_playback_state(),
        duration_sec=120.0,
        signals=None,
        effect_runtime=MagicMock(),
    )


def test_on_preset_change_forces_off_in_curation_mode() -> None:
    session = _session(mode="on", trigger="projectm")
    session.settings.editor_mode = "preset_curation"
    layer = _layer(session)
    playlist = session.layers["layer_1"].playlist
    with patch("cleave.viz.wiring.apply_preset_switching") as mock_apply:
        controls = _make_controls(session, layer)
        bindings = controls._layer_bindings
        assert bindings is not None
        playlist.load_into = MagicMock()
        bindings.on_preset_change("layer_1", playlist)
    mock_apply.assert_not_called()
    playlist.load_into.assert_called_once_with(layer.pm, smooth=False)
    layer.pm.lock_preset.assert_called_with(True)


def test_on_preset_switching_change_forces_off_in_curation_mode() -> None:
    session = _session(mode="on", trigger="projectm")
    session.settings.editor_mode = "preset_curation"
    layer = _layer(session)
    with patch("cleave.viz.wiring.apply_preset_switching") as mock_apply:
        controls = _make_controls(session, layer)
        bindings = controls._layer_bindings
        assert bindings is not None
        bindings.on_preset_switching_change("layer_1")
    assert mock_apply.call_args.kwargs["mode"] == "off"


def test_reapply_projectm_preset_switching_noop_in_curation_mode() -> None:
    session = _session(mode="on", trigger="projectm")
    session.settings.editor_mode = "preset_curation"
    layer = _layer(session)
    with patch("cleave.viz.wiring.apply_preset_switching") as mock_apply:
        controls = _make_controls(session, layer)
        bindings = controls._layer_bindings
        assert bindings is not None
        bindings.on_seek(1.0)
    mock_apply.assert_not_called()


def test_on_preset_change_rebuilds_projectm_playlist() -> None:
    session = _session(mode="on", trigger="projectm", timeline_enabled=False)
    layer = _layer(session)
    playlist = session.layers["layer_1"].playlist
    with patch("cleave.viz.wiring.apply_preset_switching") as mock_apply:
        controls = _make_controls(session, layer)
        bindings = controls._layer_bindings
        assert bindings is not None
        bindings.on_preset_change("layer_1", playlist)
    mock_apply.assert_called_once()
    assert mock_apply.call_args.kwargs["mode"] == "on"
    assert mock_apply.call_args.kwargs["trigger"] == "projectm"


def test_on_preset_change_forces_clean_boot_for_timer() -> None:
    session = _session(mode="on", trigger="timer", timeline_enabled=False)
    layer = _layer(session)
    playlist = session.layers["layer_1"].playlist
    with patch("cleave.viz.wiring.apply_preset_switching") as mock_apply:
        with patch("cleave.viz.wiring.reanchor_list_preset_after_browse") as mock_reanchor:
            controls = _make_controls(session, layer)
            bindings = controls._layer_bindings
            assert bindings is not None
            playlist.load_into = MagicMock()
            bindings.on_preset_change("layer_1", playlist)
    mock_apply.assert_not_called()
    playlist.load_into.assert_called_once_with(layer.pm, smooth=False)
    mock_reanchor.assert_called_once()


def test_on_seek_reapplies_projectm_preset_switching() -> None:
    session = _session(mode="on", trigger="projectm", timeline_enabled=False)
    layer = _layer(session)
    layer.projectm_playlist = MagicMock()
    with patch("cleave.viz.wiring.reapply_projectm_preset_switching") as mock_reapply:
        with patch("cleave.viz.wiring.resync_timeline_preset_switching"):
            controls = _make_controls(session, layer)
            bindings = controls._layer_bindings
            assert bindings is not None
            bindings.on_seek(1.0)
    mock_reapply.assert_called_once()


def test_on_preset_change_timeline_trigger_reanchors_and_stays_locked() -> None:
    session = _session(mode="on", trigger="timeline", timeline_enabled=True)
    layer = _layer(session)
    playlist = session.layers["layer_1"].playlist
    with patch(
        "cleave.viz.wiring.reanchor_list_preset_after_browse",
        side_effect=lambda *args, **kwargs: layer.pm.lock_preset(True),
    ) as mock_reanchor:
        controls = _make_controls(session, layer)
        bindings = controls._layer_bindings
        assert bindings is not None
        playlist.load_into = MagicMock()
        bindings.on_preset_change("layer_1", playlist)
    mock_reanchor.assert_called_once()
    layer.pm.lock_preset.assert_called_with(True)


def test_on_preset_change_timer_reanchors_with_timeline_enabled() -> None:
    session = _session(mode="on", trigger="timer", timeline_enabled=True)
    layer = _layer(session)
    playlist = session.layers["layer_1"].playlist
    with patch("cleave.viz.wiring.apply_preset_switching") as mock_apply:
        with patch("cleave.viz.wiring.reanchor_list_preset_after_browse") as mock_reanchor:
            controls = _make_controls(session, layer)
            bindings = controls._layer_bindings
            assert bindings is not None
            playlist.load_into = MagicMock()
            bindings.on_preset_change("layer_1", playlist)
    mock_apply.assert_not_called()
    mock_reanchor.assert_called_once()


def test_unlock_preset_after_modal_keeps_indexed_locked() -> None:
    session = _session(mode="on", trigger="timeline", timeline_enabled=True)
    layer = _layer(session)
    controls = _make_controls(session, layer)
    bindings = controls._layer_bindings
    assert bindings is not None
    layer.pm.lock_preset.reset_mock()
    bindings.unlock_preset_after_modal("layer_1")
    layer.pm.lock_preset.assert_called_with(True)
