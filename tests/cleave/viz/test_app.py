"""Tests for VisualizerApp frame tick ordering."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pygame

from cleave.config_schema import DEFAULT_LAYER_SLOTS
from tests.support.config import TEST_LAYER_STEMS
from cleave.extract import STEM_NAMES
from cleave.stem_pcm import LIVE_PROJECTM_FPS, samples_per_frame
from cleave.viz.app import (
    LiveVisualizerRuntime,
    VisualizerApp,
    VisualizerSeed,
    _live_overlay_ui_active,
    _timeline_strip_fade,
    _timeline_strip_visible,
    _tuning_view_state_needed,
)
from cleave.viz.focus_nav import MainFocus, TimelineFocus
from cleave.viz.input_dispatch import key_handler_for_runtime
from cleave.viz.row_semantics import RowDescriptor, RowKind
from tests.support.config import default_render_post_fx_runtime
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.config import default_render_post_fx_runtime
from cleave.viz.modal import ModalHost
from cleave.viz.tuning_panel_draw import TuningOverlay
from tests.support.compositor_mock import recording_compositor
from tests.support.viz import make_test_cfg


def _minimal_runtime(compositor: MagicMock, *, upscale: float = 2.0) -> LiveVisualizerRuntime:
    display_w = int(1280 * upscale)
    display_h = int(720 * upscale)
    session = TuningSession(layer_z_order=[], layers={})
    session.render_post_fx = default_render_post_fx_runtime(
        enabled=False, expanded=False, fade_in=0.0, fade_out=0.0
    )
    controls = MagicMock()
    controls.build_view_state.return_value = MagicMock()
    controls.tap_sync.active = False
    controls.tap_sync.showing_progress = False
    controls.tap_sync.progress_view.return_value = None
    overlay = TuningOverlay()
    modal_host = ModalHost()
    seed = VisualizerSeed(
        project_dir=MagicMock(),
        audio_path=MagicMock(),
        width=1280,
        height=720,
        upscale=upscale,
        display_width=display_w,
        display_height=display_h,
        window_title="test",
        session=session,
        cfg=MagicMock(),
        pcm_bank=MagicMock(),
        duration_sec=120.0,
        signals=None,
        effect_runtime=MagicMock(),
        preset_root=MagicMock(),
        playlists={},
    )
    runtime = LiveVisualizerRuntime(
        seed=seed,
        layers=[],
        layers_by_slot={},
        compositor=compositor,
        post_process=MagicMock(),
        controls=controls,
        timeline_controls=MagicMock(),
        modal_host=modal_host,
        mix_player=MagicMock(),
        playback=MagicMock(),
        overlay=overlay,
        help_overlay=MagicMock(),
        timeline_overlay=MagicMock(),
        overlay_surface=pygame.Surface((display_w, display_h), pygame.SRCALPHA),
    )
    runtime.seed.session.timeline.enabled = False
    runtime.seed.session.timeline.panel_open = False
    return runtime


def _run_seed(*, upscale: float = 2.0) -> VisualizerSeed:
    display_w = int(1280 * upscale)
    display_h = int(720 * upscale)
    cfg = make_test_cfg(("layer_1",))
    return VisualizerSeed(
        project_dir=MagicMock(),
        audio_path=MagicMock(),
        width=1280,
        height=720,
        upscale=upscale,
        display_width=display_w,
        display_height=display_h,
        window_title="test",
        session=MagicMock(),
        cfg=cfg,
        pcm_bank=MagicMock(),
        duration_sec=120.0,
        signals=None,
        effect_runtime=MagicMock(),
        preset_root=MagicMock(),
        playlists={},
    )


def _timeline_open_runtime(compositor: MagicMock) -> LiveVisualizerRuntime:
    runtime = _minimal_runtime(compositor)
    runtime.overlay = TuningOverlay()
    runtime.seed.session.layer_z_order = list(DEFAULT_LAYER_SLOTS)
    runtime.seed.session.layers = {
        slot: LayerRuntime(
            playlist=MagicMock(),
            browse_floor=MagicMock(),
            stem=TEST_LAYER_STEMS[slot],
        )
        for slot in DEFAULT_LAYER_SLOTS
    }
    runtime.seed.session.timeline.enabled = True
    runtime.seed.session.timeline.panel_open = True
    return runtime


@patch("cleave.viz.app.OverlayDrawer.draw_tuning")
@patch("cleave.viz.frame_finish._composite_render_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
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
    runtime.overlay.notify_input()
    call_order: list[str] = []

    compositor.apply_frame_fade.side_effect = lambda *_a, **_k: call_order.append(
        "apply_frame_fade"
    )
    compositor.present_content.side_effect = lambda: call_order.append("present_content")
    mock_live_overlay.side_effect = lambda *_a, **_k: call_order.append("content_overlay")
    mock_draw_tuning.side_effect = lambda *_a, **_k: call_order.append("draw_overlay")

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)

    mock_fade_alpha.assert_called_once()
    assert call_order == [
        "apply_frame_fade",
        "content_overlay",
        "present_content",
        "draw_overlay",
    ]


def _heavy_init_side_effect(
    seed: VisualizerSeed,
    compositor: MagicMock,
    post_process: MagicMock,
    overlay_surface: pygame.Surface,
    on_progress=None,
) -> LiveVisualizerRuntime:
    if on_progress is not None:
        on_progress("Building layers...")
    controls = MagicMock()
    controls.build_view_state.return_value = MagicMock()
    controls.tick = MagicMock()
    controls.consume_hide_overlay.return_value = False
    playback = MagicMock()
    playback.paused = False
    mix_player = MagicMock()
    modal_host = ModalHost()
    return LiveVisualizerRuntime(
        seed=seed,
        layers=[],
        layers_by_slot={},
        compositor=compositor,
        post_process=post_process,
        controls=controls,
        timeline_controls=MagicMock(),
        modal_host=modal_host,
        mix_player=mix_player,
        playback=playback,
        overlay=MagicMock(),
        help_overlay=MagicMock(),
        timeline_overlay=MagicMock(),
        overlay_surface=overlay_surface,
    )


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.draw_loading_screen")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_boot_order_audio_starts_after_first_frame(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_draw_loading: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    compositor = recording_compositor()
    seed = _run_seed()

    call_order: list[str] = []
    overlay_surface = pygame.Surface((seed.display_width, seed.display_height), pygame.SRCALPHA)

    def cheap_side_effect(rt: VisualizerSeed) -> tuple[MagicMock, MagicMock, pygame.Surface]:
        call_order.append("init_cheap")
        return compositor, MagicMock(), overlay_surface

    def heavy_with_start(
        rt: VisualizerSeed,
        comp: MagicMock,
        post: MagicMock,
        surface: pygame.Surface,
        on_progress=None,
    ) -> LiveVisualizerRuntime:
        live = _heavy_init_side_effect(rt, comp, post, surface, on_progress)
        live.mix_player.start.side_effect = lambda: call_order.append("mix_start")
        return live

    mock_init_cheap.side_effect = cheap_side_effect
    mock_init_heavy.side_effect = heavy_with_start
    mock_draw_loading.side_effect = lambda *_a, **_k: call_order.append("loading_screen")
    mock_tick_frame.side_effect = lambda *_a, **_k: call_order.append("tick_frame")

    quit_event = MagicMock()
    quit_event.type = pygame.QUIT
    mock_pygame.event.get.side_effect = [[], [quit_event]]
    mock_pygame.QUIT = pygame.QUIT
    mock_pygame.K_t = pygame.K_t
    mock_pygame.time.Clock.return_value.tick.return_value = 33

    app = VisualizerApp(seed)
    app.run()

    mock_init_cheap.assert_called_once_with(seed)
    mock_init_heavy.assert_called_once()
    mock_tick_frame.assert_called()
    assert mock_tick_frame.call_args_list[0] == call(
        0.0,
        paused=False,
        n_pcm=samples_per_frame(LIVE_PROJECTM_FPS),
        dt_sec=0.0,
    )
    assert isinstance(app._runtime, LiveVisualizerRuntime)
    app._runtime.mix_player.start.assert_called_once()
    assert call_order.index("tick_frame") < call_order.index("mix_start")
    assert mock_draw_loading.call_count >= 1


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.draw_loading_screen")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_pygame_quit_clean_exits_via_try_quit(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_draw_loading: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    compositor = recording_compositor()
    seed = _run_seed()

    mock_init_cheap.side_effect = lambda rt: (
        compositor,
        MagicMock(),
        pygame.Surface((seed.display_width, seed.display_height), pygame.SRCALPHA),
    )
    controls = MagicMock()
    controls.try_quit.return_value = True
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.consume_hide_overlay.return_value = False

    def heavy_with_controls(
        rt: VisualizerSeed,
        comp: MagicMock,
        post: MagicMock,
        surface: pygame.Surface,
        on_progress=None,
    ) -> LiveVisualizerRuntime:
        live = _heavy_init_side_effect(rt, comp, post, surface, on_progress)
        live.controls = controls
        return live

    mock_init_heavy.side_effect = heavy_with_controls
    mock_tick_frame.side_effect = lambda *_a, **_k: None

    quit_event = MagicMock()
    quit_event.type = pygame.QUIT
    mock_pygame.event.get.side_effect = [[], [quit_event]]
    mock_pygame.QUIT = pygame.QUIT
    mock_pygame.time.Clock.return_value.tick.return_value = 33

    app = VisualizerApp(seed)
    app.run()

    assert controls.try_quit.call_count == 1
    controls.consume_pending_exit.assert_called()
    assert isinstance(app._runtime, LiveVisualizerRuntime)
    app._runtime.overlay.notify_input.assert_not_called()


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.draw_loading_screen")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_ctrl_q_clean_exits(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_draw_loading: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    compositor = recording_compositor()
    seed = _run_seed()

    mock_init_cheap.side_effect = lambda rt: (
        compositor,
        MagicMock(),
        pygame.Surface((seed.display_width, seed.display_height), pygame.SRCALPHA),
    )
    controls = MagicMock()
    controls.try_quit.return_value = True
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.consume_hide_overlay.return_value = False

    def heavy_with_controls(
        rt: VisualizerSeed,
        comp: MagicMock,
        post: MagicMock,
        surface: pygame.Surface,
        on_progress=None,
    ) -> LiveVisualizerRuntime:
        live = _heavy_init_side_effect(rt, comp, post, surface, on_progress)
        live.controls = controls
        return live

    mock_init_heavy.side_effect = heavy_with_controls
    mock_tick_frame.side_effect = lambda *_a, **_k: None

    quit_key = pygame.event.Event(
        pygame.KEYDOWN, key=pygame.K_q, mod=pygame.KMOD_CTRL
    )
    mock_pygame.event.get.side_effect = [[], [quit_key]]
    mock_pygame.QUIT = pygame.QUIT
    mock_pygame.KEYDOWN = pygame.KEYDOWN
    mock_pygame.K_q = pygame.K_q
    mock_pygame.KMOD_CTRL = pygame.KMOD_CTRL
    mock_pygame.time.Clock.return_value.tick.return_value = 33

    VisualizerApp(seed).run()

    assert controls.try_quit.call_count == 1


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.draw_loading_screen")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_pygame_quit_dirty_stays_open(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_draw_loading: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    compositor = recording_compositor()
    seed = _run_seed()

    mock_init_cheap.side_effect = lambda rt: (
        compositor,
        MagicMock(),
        pygame.Surface((seed.display_width, seed.display_height), pygame.SRCALPHA),
    )
    controls = MagicMock()
    controls.try_quit.return_value = False
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.consume_hide_overlay.return_value = False

    def heavy_with_controls(
        rt: VisualizerSeed,
        comp: MagicMock,
        post: MagicMock,
        surface: pygame.Surface,
        on_progress=None,
    ) -> LiveVisualizerRuntime:
        live = _heavy_init_side_effect(rt, comp, post, surface, on_progress)
        live.controls = controls
        return live

    mock_init_heavy.side_effect = heavy_with_controls
    mock_tick_frame.side_effect = lambda *_a, **_k: None

    quit_event = MagicMock()
    quit_event.type = pygame.QUIT
    mock_pygame.event.get.side_effect = [[], [quit_event], RuntimeError("still running")]
    mock_pygame.QUIT = pygame.QUIT
    mock_pygame.time.Clock.return_value.tick.return_value = 33

    app = VisualizerApp(seed)
    try:
        app.run()
        raise AssertionError("expected main loop to continue")
    except RuntimeError as exc:
        assert str(exc) == "still running"

    assert controls.try_quit.call_count == 1
    controls.consume_pending_exit.assert_called()
    assert isinstance(app._runtime, LiveVisualizerRuntime)
    app._runtime.overlay.notify_input.assert_called_once()


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.draw_loading_screen")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_main_loop_stays_open_without_quit_event(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_draw_loading: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    compositor = recording_compositor()
    seed = _run_seed()

    mock_init_cheap.side_effect = lambda rt: (
        compositor,
        MagicMock(),
        pygame.Surface((seed.display_width, seed.display_height), pygame.SRCALPHA),
    )
    controls = MagicMock()
    controls.try_quit.return_value = True
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.consume_hide_overlay.return_value = False

    def heavy_with_controls(
        rt: VisualizerSeed,
        comp: MagicMock,
        post: MagicMock,
        surface: pygame.Surface,
        on_progress=None,
    ) -> LiveVisualizerRuntime:
        live = _heavy_init_side_effect(rt, comp, post, surface, on_progress)
        live.controls = controls
        return live

    mock_init_heavy.side_effect = heavy_with_controls
    mock_tick_frame.side_effect = lambda *_a, **_k: None

    mock_pygame.event.get.side_effect = [[], RuntimeError("still running")]
    mock_pygame.QUIT = pygame.QUIT
    mock_pygame.time.Clock.return_value.tick.return_value = 33

    try:
        VisualizerApp(seed).run()
        raise AssertionError("expected main loop to continue")
    except RuntimeError as exc:
        assert str(exc) == "still running"

    controls.try_quit.assert_not_called()


@patch("cleave.viz.app.OverlayDrawer.draw_tuning")
@patch("cleave.viz.frame_finish._composite_render_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
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
    runtime.overlay.notify_input()
    call_order: list[str] = []

    compositor.apply_frame_fade.side_effect = lambda *_a, **_k: call_order.append(
        "apply_frame_fade"
    )
    compositor.present_content.side_effect = lambda: call_order.append("present_content")
    mock_live_overlay.side_effect = lambda *_a, **_k: call_order.append("content_overlay")
    mock_draw_tuning.side_effect = lambda *_a, **_k: call_order.append("draw_overlay")

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)

    mock_fade_alpha.assert_called_once()
    assert call_order == [
        "apply_frame_fade",
        "content_overlay",
        "present_content",
        "draw_overlay",
    ]


def _key_handler_for_session(runtime: LiveVisualizerRuntime, key: int | None = None):
    """Mirror VisualizerApp.run KEYDOWN/KEYUP routing."""
    if key is None:
        key = pygame.K_RETURN
    return key_handler_for_runtime(runtime, key)


def _keyup_handler_for_session(runtime: LiveVisualizerRuntime, key: int):
    return key_handler_for_runtime(runtime, key)


def test_key_routing_main_when_strip_open_not_in_submenu() -> None:
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    main = MagicMock()
    timeline = MagicMock()
    runtime.controls = main
    runtime.timeline_controls = timeline
    runtime.seed.session.timeline.enabled = True
    runtime.seed.session.timeline.panel_open = True
    runtime.controls.focus_cursor = MainFocus(RowDescriptor(RowKind.TRANSPORT))

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
    runtime.seed.session.timeline.enabled = True
    runtime.seed.session.timeline.panel_open = True
    runtime.controls.focus_cursor = TimelineFocus(0)

    assert _key_handler_for_session(runtime, pygame.K_RETURN) is timeline
    assert _key_handler_for_session(runtime, pygame.K_UP) is main
    assert _key_handler_for_session(runtime, pygame.K_DOWN) is main


def test_key_routing_timeline_when_overlay_hidden_and_submenu_focused() -> None:
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    main = MagicMock()
    timeline = MagicMock()
    runtime.controls = main
    runtime.timeline_controls = timeline
    runtime.overlay = TuningOverlay()
    runtime.seed.session.timeline.enabled = True
    runtime.seed.session.timeline.panel_open = True
    runtime.controls.focus_cursor = TimelineFocus(0)

    assert _key_handler_for_session(runtime, pygame.K_RETURN) is timeline
    assert _key_handler_for_session(runtime, pygame.K_UP) is main


def test_keyup_routing_main_for_vertical_nav_when_submenu_focused() -> None:
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    main = MagicMock()
    timeline = MagicMock()
    runtime.controls = main
    runtime.timeline_controls = timeline
    runtime.seed.session.timeline.enabled = True
    runtime.seed.session.timeline.panel_open = True
    runtime.controls.focus_cursor = TimelineFocus(0)

    assert _keyup_handler_for_session(runtime, pygame.K_UP) is main
    assert _keyup_handler_for_session(runtime, pygame.K_DOWN) is main
    assert _keyup_handler_for_session(runtime, pygame.K_RETURN) is timeline


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
@patch("cleave.viz.app.OverlayDrawer.draw_tuning")
@patch("cleave.viz.frame_finish._composite_render_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_skips_timeline_when_overlay_hidden_and_not_in_submenu(
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
    runtime.controls.focus_cursor = MainFocus(RowDescriptor(RowKind.TRANSPORT))

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_not_called()


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
@patch("cleave.viz.app.OverlayDrawer.draw_tuning")
@patch("cleave.viz.frame_finish._composite_render_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_draws_timeline_when_overlay_hidden_but_submenu_focused(
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
    runtime.controls.focus_cursor = TimelineFocus(0)

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_called_once()
    _mock_draw_tuning.assert_not_called()


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
@patch("cleave.viz.app.OverlayDrawer.draw_tuning")
@patch("cleave.viz.frame_finish._composite_render_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_skips_view_state_and_draw_tuning_when_overlay_hidden(
    _mock_visibility: MagicMock,
    _mock_effects: MagicMock,
    _mock_composite: MagicMock,
    _mock_fade_alpha: MagicMock,
    _mock_live_overlay: MagicMock,
    mock_draw_tuning: MagicMock,
    _mock_draw_timeline: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    runtime.controls.build_view_state = MagicMock()

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)

    runtime.controls.build_view_state.assert_not_called()
    mock_draw_tuning.assert_not_called()


@patch("cleave.viz.app.OverlayDrawer.draw_tuning")
@patch("cleave.viz.frame_finish._composite_render_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_draws_tuning_when_modal_active_and_panel_hidden(
    _mock_visibility: MagicMock,
    _mock_effects: MagicMock,
    _mock_composite: MagicMock,
    _mock_fade_alpha: MagicMock,
    _mock_live_overlay: MagicMock,
    mock_draw_tuning: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    runtime.controls.build_view_state = MagicMock(return_value=MagicMock())
    runtime.modal_host.prompt_yes_no("test?", on_confirm=lambda: None)

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)

    runtime.controls.build_view_state.assert_called_once()
    mock_draw_tuning.assert_called_once()


def test_live_overlay_ui_active_gating() -> None:
    assert not _live_overlay_ui_active(
        overlay_visibility=0.0,
        modal_active=False,
        timeline_strip_visible=False,
        tap_sync_progress=False,
    )
    assert _live_overlay_ui_active(
        overlay_visibility=0.5,
        modal_active=False,
        timeline_strip_visible=False,
        tap_sync_progress=False,
    )
    assert _live_overlay_ui_active(
        overlay_visibility=0.0,
        modal_active=True,
        timeline_strip_visible=False,
        tap_sync_progress=False,
    )
    assert _live_overlay_ui_active(
        overlay_visibility=0.0,
        modal_active=False,
        timeline_strip_visible=True,
        tap_sync_progress=False,
    )
    assert _live_overlay_ui_active(
        overlay_visibility=0.0,
        modal_active=False,
        timeline_strip_visible=False,
        tap_sync_progress=True,
    )


def test_tuning_view_state_needed_gating() -> None:
    assert not _tuning_view_state_needed(overlay_visibility=0.0, modal_active=False)
    assert _tuning_view_state_needed(overlay_visibility=0.5, modal_active=False)
    assert _tuning_view_state_needed(overlay_visibility=0.0, modal_active=True)
    assert not _tuning_view_state_needed(
        overlay_visibility=0.0, modal_active=False
    )


def test_timeline_strip_visible_while_submenu_focused_despite_hidden_overlay() -> None:
    tl = TuningSession(layer_z_order=[], layers={}).timeline
    tl.enabled = True
    tl.panel_open = True
    focus = TimelineFocus(0)

    assert _timeline_strip_visible(tl, overlay_visibility=0.0, focus_cursor=focus) is True
    assert _timeline_strip_visible(tl, overlay_visibility=1.0, focus_cursor=focus) is True
    assert _timeline_strip_fade(focus_cursor=focus, overlay_visibility=0.0) == 1.0

    focus = MainFocus(RowDescriptor(RowKind.TRANSPORT))
    assert _timeline_strip_visible(tl, overlay_visibility=0.0, focus_cursor=focus) is False
    assert _timeline_strip_fade(focus_cursor=focus, overlay_visibility=0.5) == 0.5


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
@patch("cleave.viz.app.OverlayDrawer.draw_tuning")
@patch("cleave.viz.frame_finish._composite_render_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
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
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_called_once()


def test_esc_hide_clears_submenu_focus_preserves_panel_open() -> None:
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    overlay = TuningOverlay()
    overlay.notify_input()
    runtime.overlay = overlay
    runtime.seed.session.timeline.enabled = True
    runtime.seed.session.timeline.panel_open = True
    runtime.controls.focus_cursor = TimelineFocus(0)

    def _exit_submenu() -> None:
        runtime.controls.focus_cursor = MainFocus(
            RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
        )

    runtime.controls.consume_hide_overlay.return_value = True
    runtime.controls.exit_timeline_submenu = _exit_submenu
    if runtime.controls.consume_hide_overlay():
        overlay.hide_immediately()
        runtime.controls.exit_timeline_submenu()

    assert runtime.seed.session.timeline.panel_open is True
    assert not isinstance(runtime.controls.focus_cursor, TimelineFocus)
    assert overlay.is_visible() is False


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
@patch("cleave.viz.app.OverlayDrawer.draw_tuning")
@patch("cleave.viz.frame_finish._composite_render_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
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
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_not_called()

    overlay.notify_input()
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_called_once()
    assert runtime.seed.session.timeline.panel_open is True