"""Tests for cleave.viz.wiring control callbacks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from cleave.effects.runtime import EffectRuntime
from cleave.preset_playlist import PresetPlaylist
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.layer import StemLayer
from tests.support.viz import stub_playback_state
from cleave.viz.wiring import make_tuning_controls


def _make_wired_controls() -> tuple:
    pm = MagicMock()
    layer = StemLayer(
        slot="layer_1",
        stem="drums",
        pm=pm,
        fbo=MagicMock(),
        playlist=PresetPlaylist(
            current_dir=Path("/tmp/presets/layer_1"),
            paths=(),
            index=0,
        ),
    )
    layers_by_slot = {"layer_1": layer}
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=layer.playlist,
                browse_floor=Path("/tmp/presets/layer_1"),
                stem="drums",
                opacity_pct=100,
                beat_sensitivity=1.0,
            )
        },
    )
    controls = make_tuning_controls(
        session=session,
        cfg=None,
        preset_root=Path("/tmp/presets"),
        project_dir=Path("/tmp/projects/test"),
        layers_by_slot=layers_by_slot,
        layers=[layer],
        playback=stub_playback_state(),
        duration_sec=120.0,
        signals=None,
        effect_runtime=EffectRuntime(),
    )
    return controls, pm


def test_on_beat_change_updates_projectm() -> None:
    controls, pm = _make_wired_controls()
    controls.session.layers["layer_1"].beat_sensitivity = 1.0

    controls._set_beat("layer_1", 1.5)

    assert controls.session.layers["layer_1"].beat_sensitivity == 1.5
    pm.set_beat_sensitivity.assert_called_once_with(1.5)
