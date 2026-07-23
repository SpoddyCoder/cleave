"""Tests for ProjectMFrameClock and projectM time feed."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cleave.preset_playlist import PresetPlaylist
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import LayerFramePipeline
from cleave.viz.projectm_frame_clock import ProjectMFrameClock
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.config import TEST_LAYER_STEMS, default_render_post_fx_runtime


def _stem_layer(slot: str) -> StemLayer:
    current_dir = Path(f"/tmp/presets/{slot}")
    fbo = MagicMock()
    fbo.width = 1280
    fbo.height = 720
    fbo.enabled = True
    return StemLayer(
        slot=slot,
        pm=MagicMock(),
        fbo=fbo,
        playlist=PresetPlaylist(
            current_dir=current_dir,
            paths=(current_dir / "preset.milk",),
            index=0,
        ),
    )


def _session(slots: tuple[str, ...]) -> TuningSession:
    preset_root = Path("/tmp/presets")
    return TuningSession(
        layer_z_order=list(slots),
        layers={
            slot: LayerRuntime(
                playlist=PresetPlaylist(
                    current_dir=preset_root / slot,
                    paths=(preset_root / slot / "preset.milk",),
                    index=0,
                ),
                browse_floor=preset_root / slot,
                stem=TEST_LAYER_STEMS.get(slot, "drums"),
            )
            for slot in slots
        },
    )


def test_clock_starts_at_zero_on_first_unpaused_frame() -> None:
    clock = ProjectMFrameClock()
    assert clock.advance(1.0 / 60.0, paused=False) == 0.0
    assert clock.started is True


def test_clock_accumulates_positive_dt() -> None:
    clock = ProjectMFrameClock()
    clock.advance(0.0, paused=False)
    assert clock.advance(0.1, paused=False) == 0.1
    assert clock.advance(0.05, paused=False) == pytest.approx(0.15)


def test_clock_ignores_negative_dt() -> None:
    clock = ProjectMFrameClock()
    clock.advance(0.0, paused=False)
    clock.advance(1.0, paused=False)
    assert clock.advance(-0.5, paused=False) == 1.0


def test_clock_freezes_while_paused() -> None:
    clock = ProjectMFrameClock()
    clock.advance(0.0, paused=False)
    clock.advance(0.5, paused=False)
    assert clock.advance(0.25, paused=True) == 0.5
    assert clock.advance(0.25, paused=False) == 0.75


def test_clock_does_not_start_while_paused() -> None:
    clock = ProjectMFrameClock()
    assert clock.advance(0.1, paused=True) == 0.0
    assert clock.started is False
    assert clock.advance(0.1, paused=False) == 0.0
    assert clock.started is True


def test_render_frame_feeds_pm_time_not_song_time() -> None:
    layer = _stem_layer("layer_1")
    session = _session(("layer_1",))
    session.render_post_fx = default_render_post_fx_runtime(enabled=False)
    pcm_bank = MagicMock()
    pcm_bank.slice_pcm.return_value = b""
    pcm_bank.channels.return_value = 2
    effect_runtime = MagicMock()
    effect_runtime.modifiers.return_value = {
        "layer_1": MagicMock(
            opacity=1.0,
            flash_alpha=0.0,
            bloom_strength=0.0,
            hue_rgb=(1, 1, 1),
            hue_mix=0.0,
            grit_strength=0.0,
            aberration_px=0.0,
        )
    }

    with (
        patch("cleave.viz.layer_pipeline._render_layer_fbo"),
        patch(
            "cleave.viz.layer_pipeline.pcm_max_samples_per_channel",
            return_value=2048,
        ),
    ):
        LayerFramePipeline.render_frame(
            session,
            [layer],
            {"layer_1": layer},
            pcm_bank,
            512,
            MagicMock(),
            effect_runtime,
            None,
            90.0,
            paused=False,
            pm_time_sec=3.5,
        )

    layer.pm.set_frame_time.assert_called_once_with(3.5)
    pcm_bank.slice_pcm.assert_called_once()
    assert pcm_bank.slice_pcm.call_args.args[1] == 90.0
