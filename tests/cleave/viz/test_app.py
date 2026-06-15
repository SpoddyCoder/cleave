"""Tests for VisualizerApp frame tick ordering."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

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


def _heavy_init_side_effect(rt: VisualizerRuntime, on_progress=None) -> None:
    if on_progress is not None:
        on_progress("Building layers...")
    rt.controls = MagicMock()
    rt.controls.build_view_state.return_value = MagicMock()
    rt.controls.tick = MagicMock()
    rt.controls.consume_hide_overlay.return_value = False
    rt.timeline_controls = MagicMock()
    rt.playback = MagicMock()
    rt.playback.paused = False
    rt.mix_player = MagicMock()
    rt.overlay = MagicMock()
    rt.timeline_overlay = MagicMock()
    rt.layers = []


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app._warmup_layers")
@patch("cleave.viz.app.draw_loading_screen")
@patch("cleave.viz.app._init_gl_resources_heavy")
@patch("cleave.viz.app._init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_boot_order_audio_starts_after_first_frame(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_draw_loading: MagicMock,
    mock_warmup: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    runtime.cfg = MagicMock()
    runtime.cfg.visualizer.warmup_sec = 1.0
    runtime.mix_player = None
    runtime.playback = None
    runtime.controls = None
    runtime.timeline_controls = None

    call_order: list[str] = []

    def cheap_side_effect(rt: VisualizerRuntime) -> None:
        call_order.append("init_cheap")

    def heavy_with_start(rt: VisualizerRuntime, on_progress=None) -> None:
        _heavy_init_side_effect(rt, on_progress)
        rt.mix_player.start.side_effect = lambda: call_order.append("mix_start")

    mock_init_cheap.side_effect = cheap_side_effect
    mock_init_heavy.side_effect = heavy_with_start
    mock_draw_loading.side_effect = lambda *_a, **_k: call_order.append("loading_screen")
    mock_warmup.side_effect = lambda *_a, **_k: call_order.append("warmup")
    mock_tick_frame.side_effect = lambda *_a, **_k: call_order.append("tick_frame")

    quit_event = MagicMock()
    quit_event.type = pygame.QUIT
    mock_pygame.event.get.side_effect = [[], [quit_event]]
    mock_pygame.QUIT = pygame.QUIT
    mock_pygame.K_t = pygame.K_t
    mock_pygame.time.Clock.return_value.tick.return_value = 33

    VisualizerApp(runtime).run()

    mock_init_cheap.assert_called_once_with(runtime)
    mock_init_heavy.assert_called_once()
    mock_warmup.assert_called_once_with(
        runtime.layers,
        runtime.pcm_bank,
        0.0,
        30,
        runtime.fps,
        runtime.n_pcm,
        session=runtime.session,
    )
    mock_tick_frame.assert_called()
    assert mock_tick_frame.call_args_list[0] == call(0.0, paused=False)
    runtime.mix_player.start.assert_called_once()
    assert call_order.index("tick_frame") < call_order.index("mix_start")
    assert mock_draw_loading.call_count >= 1


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
