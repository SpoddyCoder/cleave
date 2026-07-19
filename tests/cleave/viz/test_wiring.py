"""Tests for cleave.viz.wiring live layer callbacks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from cleave.preset_playlist import PresetPlaylist
from cleave.projectm import ProjectM
from cleave.viz.layer import StemLayer
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.wiring import make_tuning_controls
from tests.support.viz import make_test_cfg, stub_playback_state


def _session_with_mode(
    mode: str, *, rotation_set: str = "directory"
) -> TuningSession:
    preset_root = Path("/tmp/presets")
    playlist = PresetPlaylist(
        current_dir=preset_root / "layer_1",
        paths=(preset_root / "layer_1" / "a.milk",),
        index=0,
    )
    return TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=playlist,
                browse_floor=preset_root / "layer_1",
                stem="drums",
                preset_switching=mode,  # type: ignore[arg-type]
                preset_switching_rotation_set=rotation_set,  # type: ignore[arg-type]
            )
        },
    )


def test_on_preset_change_rebuilds_rotation_in_projectm_mode() -> None:
    session = _session_with_mode("projectm")
    cfg = make_test_cfg(("layer_1",))
    pm = ProjectM.__new__(ProjectM)
    pm.lock_preset = MagicMock()
    pm.load_preset = MagicMock()
    layer = StemLayer(
        slot="layer_1",
        pm=pm,
        fbo=MagicMock(),
        playlist=session.layers["layer_1"].playlist,
    )
    layers_by_slot = {"layer_1": layer}
    playlist = session.layers["layer_1"].playlist

    with patch("cleave.viz.wiring.apply_preset_switching") as mock_apply:
        controls = make_tuning_controls(
            session=session,
            cfg=cfg,
            preset_root=cfg.paths.preset_root,
            project_dir=Path("/tmp/project"),
            layers_by_slot=layers_by_slot,
            layers=[layer],
            playback=stub_playback_state(),
            duration_sec=120.0,
            signals=None,
            effect_runtime=MagicMock(),
        )

        bindings = controls._layer_bindings
        assert bindings is not None
        playlist.load_into = MagicMock()
        bindings.on_preset_change("layer_1", playlist)

    playlist.load_into.assert_not_called()
    mock_apply.assert_called_once()
    assert mock_apply.call_args.args[0] is layer
    assert mock_apply.call_args.kwargs["mode"] == "projectm"
    assert layer.auto_preset_path == playlist.current.resolve()


def test_on_preset_change_loads_preset_in_user_defined_rotation_set() -> None:
    session = _session_with_mode("projectm", rotation_set="user_defined")
    cfg = make_test_cfg(("layer_1",))
    pm = ProjectM.__new__(ProjectM)
    pm.lock_preset = MagicMock()
    pm.load_preset = MagicMock()
    pm.set_preset_start_clean = MagicMock()
    layer = StemLayer(
        slot="layer_1",
        pm=pm,
        fbo=MagicMock(),
        playlist=session.layers["layer_1"].playlist,
    )
    layers_by_slot = {"layer_1": layer}
    playlist = session.layers["layer_1"].playlist

    with patch("cleave.viz.wiring.apply_preset_switching"):
        controls = make_tuning_controls(
            session=session,
            cfg=cfg,
            preset_root=cfg.paths.preset_root,
            project_dir=Path("/tmp/project"),
            layers_by_slot=layers_by_slot,
            layers=[layer],
            playback=stub_playback_state(),
            duration_sec=120.0,
            signals=None,
            effect_runtime=MagicMock(),
        )

    bindings = controls._layer_bindings
    assert bindings is not None
    playlist.load_into = MagicMock()
    bindings.on_preset_change("layer_1", playlist)

    playlist.load_into.assert_called_once_with(pm, smooth=False)
    pm.lock_preset.assert_called_once_with(False)


def test_on_preset_change_forces_clean_boot_then_restores() -> None:
    session = _session_with_mode("none")
    session.layers["layer_1"].preset_start_clean = False
    cfg = make_test_cfg(("layer_1",))
    pm = ProjectM.__new__(ProjectM)
    pm.lock_preset = MagicMock()
    pm.load_preset = MagicMock()
    pm.set_preset_start_clean = MagicMock()
    layer = StemLayer(
        slot="layer_1",
        pm=pm,
        fbo=MagicMock(),
        playlist=session.layers["layer_1"].playlist,
    )
    layers_by_slot = {"layer_1": layer}
    playlist = session.layers["layer_1"].playlist

    with patch("cleave.viz.wiring.apply_preset_switching"):
        controls = make_tuning_controls(
            session=session,
            cfg=cfg,
            preset_root=cfg.paths.preset_root,
            project_dir=Path("/tmp/project"),
            layers_by_slot=layers_by_slot,
            layers=[layer],
            playback=stub_playback_state(),
            duration_sec=120.0,
            signals=None,
            effect_runtime=MagicMock(),
        )

    bindings = controls._layer_bindings
    assert bindings is not None
    bindings.on_preset_change("layer_1", playlist)

    assert pm.set_preset_start_clean.call_args_list == [
        (((True,)), {}),
        (((False,)), {}),
    ]


def test_on_seek_reapplies_projectm_preset_switching() -> None:
    session = _session_with_mode("projectm")
    cfg = make_test_cfg(("layer_1",))
    pm = ProjectM.__new__(ProjectM)
    layer = StemLayer(
        slot="layer_1",
        pm=pm,
        fbo=MagicMock(),
        playlist=session.layers["layer_1"].playlist,
    )

    with (
        patch("cleave.viz.wiring.reapply_projectm_preset_switching") as mock_reapply,
        patch("cleave.viz.wiring.LayerFramePipeline.flush_pcm"),
        patch("cleave.viz.wiring.seek"),
    ):
        controls = make_tuning_controls(
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
        bindings = controls._layer_bindings
        assert bindings is not None
        bindings.on_seek(5.0)

    mock_reapply.assert_called_once()
    assert mock_reapply.call_args.kwargs["delta_sec"] == 5.0
