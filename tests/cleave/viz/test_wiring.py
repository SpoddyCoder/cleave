"""Tests for cleave.viz.wiring control callbacks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from cleave.effects.runtime import EffectRuntime
from cleave.preset_playlist import PresetPlaylist
from cleave.stem_pcm import StemPcmBank
from cleave.viz.mix_player import MixPlayer
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.layer import StemLayer
from cleave.viz.wiring import make_tuning_controls
from tests.support.viz import make_test_cfg, stub_playback_state


def _make_wired_controls() -> tuple:
    pm = MagicMock()
    layer = StemLayer(
        slot="layer_1",
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
        cfg=make_test_cfg(("layer_1",)),
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


def test_on_stem_change_updates_mix_player_solo_source() -> None:
    pm = MagicMock()
    layer = StemLayer(
        slot="layer_1",
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
        solo_slot="layer_1",
    )
    mix = np.zeros(8, dtype=np.float32)
    mix_player = MixPlayer(mix)
    pcm_bank = StemPcmBank(
        project_dir=Path("/tmp/projects/test"),
        duration_sec=1.0,
        _pcm={
            "drums": np.array([1.0], dtype=np.float32),
            "bass": np.array([2.0], dtype=np.float32),
            "vocals": np.array([3.0], dtype=np.float32),
            "other": np.array([4.0], dtype=np.float32),
            "full_mix": np.array([5.0], dtype=np.float32),
        },
        _channels={
            "drums": 1,
            "bass": 1,
            "vocals": 1,
            "other": 1,
            "full_mix": 1,
        },
    )
    controls = make_tuning_controls(
        session=session,
        cfg=make_test_cfg(("layer_1",)),
        preset_root=Path("/tmp/presets"),
        project_dir=Path("/tmp/projects/test"),
        layers_by_slot=layers_by_slot,
        layers=[layer],
        playback=stub_playback_state(),
        duration_sec=120.0,
        signals=None,
        effect_runtime=EffectRuntime(),
        pcm_bank=pcm_bank,
        mix_player=mix_player,
    )

    controls._cycle_stem("layer_1", forward=True)

    assert session.layers["layer_1"].stem == "bass"
    with mix_player._lock:
        assert mix_player._solo_source == "bass"
