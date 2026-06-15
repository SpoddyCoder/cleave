"""Tests for VisualizerApp frame tick ordering."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame

from cleave.viz.app import VisualizerApp, VisualizerRuntime
from cleave.viz.controls import RenderPostFxRuntime, TuningSession
from tests.support.compositor_mock import recording_compositor


def _minimal_runtime(compositor: MagicMock, *, upscale: float = 2.0) -> VisualizerRuntime:
    display_w = int(1280 * upscale)
    display_h = int(720 * upscale)
    session = TuningSession(layer_z_order=[], layers={})
    session.render_post_fx = RenderPostFxRuntime(
        enabled=False, expanded=False, fade_in=0.0, fade_out=0.0
    )
    runtime = VisualizerRuntime(
        project_dir=MagicMock(),
        audio_path=MagicMock(),
        width=1280,
        height=720,
        upscale=upscale,
        display_width=display_w,
        display_height=display_h,
        fps=30,
        window_title="test",
        session=session,
        cfg=MagicMock(),
        pcm_bank=MagicMock(),
        duration_sec=120.0,
        n_pcm=1024,
        signals=None,
        effect_runtime=MagicMock(),
        preset_root=MagicMock(),
        layers=[],
        layers_by_name={},
        compositor=compositor,
        post_process=MagicMock(),
        controls=MagicMock(),
        overlay=MagicMock(),
        timeline_overlay=MagicMock(),
        overlay_surface=pygame.Surface((display_w, display_h), pygame.SRCALPHA),
    )
    runtime.controls.build_view_state.return_value = MagicMock()
    runtime.overlay.update = MagicMock()
    runtime.session.timeline.enabled = False
    runtime.session.timeline.panel_open = False
    return runtime


@patch("cleave.viz.app._draw_tuning_overlay")
@patch("cleave.viz.app._composite_live_render_overlay")
@patch("cleave.viz.app.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app._composite_ordered")
@patch("cleave.viz.app.apply_effect_modifiers")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_overlay_order_fade_content_present_then_ui(
    _mock_visibility: MagicMock,
    _mock_effects: MagicMock,
    _mock_composite: MagicMock,
    mock_fade_alpha: MagicMock,
    mock_live_overlay: MagicMock,
    mock_draw_tuning: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    call_order: list[str] = []

    compositor.apply_frame_fade.side_effect = lambda *_a, **_k: call_order.append(
        "apply_frame_fade"
    )
    compositor.present_content.side_effect = lambda: call_order.append("present_content")
    mock_live_overlay.side_effect = lambda *_a, **_k: call_order.append("content_overlay")
    mock_draw_tuning.side_effect = lambda *_a, **_k: call_order.append("draw_overlay")

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True)

    mock_fade_alpha.assert_called_once()
    assert call_order == [
        "apply_frame_fade",
        "content_overlay",
        "present_content",
        "draw_overlay",
    ]


@patch("cleave.viz.app._draw_tuning_overlay")
@patch("cleave.viz.app._composite_live_render_overlay")
@patch("cleave.viz.app.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app._composite_ordered")
@patch("cleave.viz.app.apply_effect_modifiers")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_overlay_order_at_upscale_one(
    _mock_visibility: MagicMock,
    _mock_effects: MagicMock,
    _mock_composite: MagicMock,
    mock_fade_alpha: MagicMock,
    mock_live_overlay: MagicMock,
    mock_draw_tuning: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor, upscale=1.0)
    call_order: list[str] = []

    compositor.apply_frame_fade.side_effect = lambda *_a, **_k: call_order.append(
        "apply_frame_fade"
    )
    compositor.present_content.side_effect = lambda: call_order.append("present_content")
    mock_live_overlay.side_effect = lambda *_a, **_k: call_order.append("content_overlay")
    mock_draw_tuning.side_effect = lambda *_a, **_k: call_order.append("draw_overlay")

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True)

    mock_fade_alpha.assert_called_once()
    assert call_order == [
        "apply_frame_fade",
        "content_overlay",
        "present_content",
        "draw_overlay",
    ]
