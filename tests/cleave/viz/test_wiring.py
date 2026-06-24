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


def _session_with_mode(mode: str) -> TuningSession:
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
                preset_switching=mode,
            )
        },
    )


def test_on_preset_change_skips_relock_in_projectm_mode() -> None:
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

    playlist.load_into.assert_not_called()
    pm.lock_preset.assert_not_called()
