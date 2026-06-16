"""Tests for VisualizerApp frame tick ordering."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pygame

from cleave.extract import STEM_NAMES
from cleave.viz.app import VisualizerApp, VisualizerRuntime
from cleave.viz.controls import LayerRuntime, RenderPostFxRuntime, TuningSession
from cleave.viz.overlay import TuningOverlay
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


def _timeline_open_runtime(compositor: MagicMock) -> VisualizerRuntime:
    runtime = _minimal_runtime(compositor)
    runtime.overlay = TuningOverlay()
    runtime.session.layer_z_order = list(STEM_NAMES)
    runtime.session.layers = {
        stem: LayerRuntime(playlist=MagicMock(), browse_floor=MagicMock())
        for stem in STEM_NAMES
    }
    runtime.session.timeline.enabled = True
    runtime.session.timeline.panel_open = True
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


def _key_handler_for_session(runtime: VisualizerRuntime, key: int | None = None):
    """Mirror VisualizerApp.run KEYDOWN routing."""
    tl = runtime.session.timeline
    overlay_visible = runtime.overlay.is_visible()
    timeline_submenu_keys = (
        overlay_visible
        and tl.panel_open
        and tl.enabled
        and tl.submenu_focused
        and runtime.timeline_controls is not None
        and key not in (pygame.K_UP, pygame.K_DOWN)
    )
    if timeline_submenu_keys:
        return runtime.timeline_controls
    return runtime.controls


def test_key_routing_main_when_strip_open_not_in_submenu() -> None:
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    main = MagicMock()
    timeline = MagicMock()
    runtime.controls = main
    runtime.timeline_controls = timeline
    runtime.session.timeline.enabled = True
    runtime.session.timeline.panel_open = True
    runtime.session.timeline.submenu_focused = False

    assert _key_handler_for_session(runtime) is main


def test_key_routing_timeline_when_submenu_focused() -> None:
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    main = MagicMock()
    timeline = MagicMock()
    runtime.controls = main
    runtime.timeline_controls = timeline
    runtime.overlay = TuningOverlay()
    runtime.overlay.notify_input()
    runtime.session.timeline.enabled = True
    runtime.session.timeline.panel_open = True
    runtime.session.timeline.submenu_focused = True

    assert _key_handler_for_session(runtime, pygame.K_RETURN) is timeline
    assert _key_handler_for_session(runtime, pygame.K_UP) is main
    assert _key_handler_for_session(runtime, pygame.K_DOWN) is main


def test_key_routing_main_when_overlay_hidden_despite_submenu() -> None:
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    main = MagicMock()
    timeline = MagicMock()
    runtime.controls = main
    runtime.timeline_controls = timeline
    runtime.overlay = TuningOverlay()
    runtime.session.timeline.enabled = True
    runtime.session.timeline.panel_open = True
    runtime.session.timeline.submenu_focused = True

    assert _key_handler_for_session(runtime) is main


@patch("cleave.viz.app._draw_timeline_overlay")
@patch("cleave.viz.app._draw_tuning_overlay")
@patch("cleave.viz.app._composite_live_render_overlay")
@patch("cleave.viz.app.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app._composite_ordered")
@patch("cleave.viz.app.apply_effect_modifiers")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_skips_timeline_when_overlay_hidden(
    _mock_visibility: MagicMock,
    _mock_effects: MagicMock,
    _mock_composite: MagicMock,
    _mock_fade_alpha: MagicMock,
    _mock_live_overlay: MagicMock,
    _mock_draw_tuning: MagicMock,
    mock_draw_timeline: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _timeline_open_runtime(compositor)

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True)
    mock_draw_timeline.assert_not_called()


@patch("cleave.viz.app._draw_timeline_overlay")
@patch("cleave.viz.app._draw_tuning_overlay")
@patch("cleave.viz.app._composite_live_render_overlay")
@patch("cleave.viz.app.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app._composite_ordered")
@patch("cleave.viz.app.apply_effect_modifiers")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_draws_timeline_when_overlay_visible_and_panel_open(
    _mock_visibility: MagicMock,
    _mock_effects: MagicMock,
    _mock_composite: MagicMock,
    _mock_fade_alpha: MagicMock,
    _mock_live_overlay: MagicMock,
    _mock_draw_tuning: MagicMock,
    mock_draw_timeline: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _timeline_open_runtime(compositor)
    runtime.overlay.notify_input()

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True)
    mock_draw_timeline.assert_called_once()


def test_esc_hide_clears_submenu_focus_preserves_panel_open() -> None:
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    overlay = TuningOverlay()
    overlay.notify_input()
    runtime.overlay = overlay
    runtime.session.timeline.enabled = True
    runtime.session.timeline.panel_open = True
    runtime.session.timeline.submenu_focused = True

    runtime.controls.consume_hide_overlay.return_value = True
    if runtime.controls.consume_hide_overlay():
        overlay.hide_immediately()
        runtime.session.timeline.submenu_focused = False

    assert runtime.session.timeline.panel_open is True
    assert runtime.session.timeline.submenu_focused is False
    assert overlay.is_visible() is False


@patch("cleave.viz.app._draw_timeline_overlay")
@patch("cleave.viz.app._draw_tuning_overlay")
@patch("cleave.viz.app._composite_live_render_overlay")
@patch("cleave.viz.app.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app._composite_ordered")
@patch("cleave.viz.app.apply_effect_modifiers")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_restores_timeline_after_overlay_shown_again(
    _mock_visibility: MagicMock,
    _mock_effects: MagicMock,
    _mock_composite: MagicMock,
    _mock_fade_alpha: MagicMock,
    _mock_live_overlay: MagicMock,
    _mock_draw_tuning: MagicMock,
    mock_draw_timeline: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _timeline_open_runtime(compositor)
    overlay = runtime.overlay

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True)
    mock_draw_timeline.assert_not_called()

    overlay.notify_input()
    app.tick_frame(1.0, paused=True, draw_overlay=True)
    mock_draw_timeline.assert_called_once()
    assert runtime.session.timeline.panel_open is True
