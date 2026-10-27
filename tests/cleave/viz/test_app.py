"""Tests for VisualizerApp frame tick ordering."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock, call, patch

import pygame

from cleave.config import EditorConfig
from cleave.config_schema.editor import (
    DEFAULT_EDITOR_HEIGHT,
    DEFAULT_EDITOR_WIDTH,
    DEFAULT_INSPECTOR_WIDTH,
    DEFAULT_NAVIGATOR_WIDTH,
)
from cleave.config_schema.layers import DEFAULT_LAYER_SLOTS
from tests.support.config import TEST_LAYER_STEMS
from cleave.stems import STEM_NAMES
from cleave.stem_pcm import LIVE_PROJECTM_FPS, samples_per_frame
from cleave.viz.app import (
    LiveVisualizerRuntime,
    VisualizerApp,
    VisualizerSeed,
    _live_overlay_ui_active,
    _timeline_strip_fade,
    _timeline_strip_visible,
    init_gl_resources_cheap,
    init_gl_resources_render,
)
from cleave.viz.focus_nav import MainFocus, TimelineFocus
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.input_dispatch import key_handler_for_runtime
from cleave.viz.row_kinds import RowDescriptor, RowKind
from tests.support.config import default_render_post_fx_runtime
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.config import default_render_post_fx_runtime
from cleave.viz.modal import ModalHost
from cleave.viz.panel_notification import PanelNotificationActive
from cleave.viz.ui_fade import UiFade
from tests.support.compositor_mock import recording_compositor
from tests.support.viz import make_test_cfg


def _silence_tap_sync(controls: MagicMock) -> None:
    controls.tap_sync.active = False
    controls.tap_sync.showing_progress = False
    controls.tap_sync.progress_view.return_value = None
    # A MagicMock message is not None, so draw_ui would push a toast and call
    # ImGui. These run() doubles have no ImGui context.
    controls.notification_active.return_value = PanelNotificationActive(
        persistent_message=None,
        persistent_elapsed_sec=0.0,
        message=None,
        remaining_sec=0.0,
        elapsed_sec=0.0,
    )


def _assert_warmup_tick(tick_call: object) -> None:
    from cleave.viz.shell_layout import ShellLayout

    kwargs = tick_call.kwargs  # type: ignore[attr-defined]
    layout = kwargs["layout"]
    assert isinstance(layout, ShellLayout)
    assert tick_call == call(
        0.0,
        paused=False,
        n_pcm=samples_per_frame(LIVE_PROJECTM_FPS),
        dt_sec=0.0,
        layout=layout,
    )


def _minimal_runtime(compositor: MagicMock, *, upscale: float = 2.0) -> LiveVisualizerRuntime:
    display_w = int(1280 * upscale)
    display_h = int(720 * upscale)
    session = TuningSession(layer_z_order=[], layers={})
    post_fx = default_render_post_fx_runtime(enabled=False)
    session.render_post_fx = replace(
        post_fx,
        fade=replace(
            post_fx.fade,
            fade_in=replace(post_fx.fade.fade_in, end=0.0),
            fade_out=replace(post_fx.fade.fade_out, start=0.0),
        ),
    )
    controls = MagicMock()
    controls.build_view_state.return_value = MagicMock()
    _silence_tap_sync(controls)
    controls.project_render.busy = False
    ui_fade = UiFade()
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
    seed.cfg.editor = EditorConfig()
    runtime = LiveVisualizerRuntime(
        seed=seed,
        layers=[],
        layers_by_slot={},
        compositor=compositor,
        post_process=MagicMock(),
        masked_compositor=MagicMock(),
        controls=controls,
        timeline_controls=MagicMock(),
        modal_host=modal_host,
        mix_player=MagicMock(),
        playback=MagicMock(),
        ui_fade=ui_fade,
        timeline_overlay=MagicMock(),
        overlay_surface=pygame.Surface((display_w, display_h), pygame.SRCALPHA),
    )
    runtime.seed.session.timeline.enabled = False
    runtime.seed.session.timeline.panel_open = False
    return runtime


def _run_seed(
    *,
    upscale: float = 2.0,
    width: int = 1280,
    height: int = 720,
) -> VisualizerSeed:
    display_w = int(width * upscale)
    display_h = int(height * upscale)
    cfg = make_test_cfg(("layer_1",))
    return VisualizerSeed(
        project_dir=MagicMock(),
        audio_path=MagicMock(),
        width=width,
        height=height,
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


def _boot_window(seed: VisualizerSeed, compositor: MagicMock) -> MagicMock:
    window = MagicMock()
    window.display_width = seed.display_width
    window.display_height = seed.display_height
    window.quit_requested = False
    window.compositor = compositor
    window.overlay_surface = pygame.Surface(
        (seed.display_width, seed.display_height), pygame.SRCALPHA
    )
    return window


def _timeline_open_runtime(compositor: MagicMock) -> LiveVisualizerRuntime:
    runtime = _minimal_runtime(compositor)
    runtime.ui_fade = UiFade()
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


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
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
    mock_draw_timeline: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    runtime.seed.session.timeline.panel_open = True
    runtime.ui_fade.notify_input()
    call_order: list[str] = []

    compositor.apply_frame_fade.side_effect = lambda *_a, **_k: call_order.append(
        "apply_frame_fade"
    )
    compositor.present_content.side_effect = lambda: call_order.append("present_content")
    mock_live_overlay.side_effect = lambda *_a, **_k: call_order.append("content_overlay")
    mock_draw_timeline.side_effect = lambda *_a, **_k: call_order.append("draw_overlay")

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
    masked_compositor: MagicMock,
    overlay_surface: pygame.Surface,
    on_progress=None,
) -> LiveVisualizerRuntime:
    if on_progress is not None:
        on_progress("Building layers...")
    controls = MagicMock()
    controls.build_view_state.return_value = MagicMock()
    _silence_tap_sync(controls)
    controls.tick = MagicMock()
    controls.consume_hide_overlay.return_value = False
    controls.key_repeat_armed = False
    controls.project_render.busy = False
    timeline_controls = MagicMock()
    timeline_controls.key_repeat_armed = False
    playback = MagicMock()
    playback.paused = False
    mix_player = MagicMock()
    modal_host = ModalHost()
    ui_fade = MagicMock()
    ui_fade.visibility = 0.0  # UiFade starts hidden; menu draw compares this
    return LiveVisualizerRuntime(
        seed=seed,
        layers=[],
        layers_by_slot={},
        compositor=compositor,
        post_process=post_process,
        masked_compositor=masked_compositor,
        controls=controls,
        timeline_controls=timeline_controls,
        modal_host=modal_host,
        mix_player=mix_player,
        playback=playback,
        ui_fade=ui_fade,
        timeline_overlay=MagicMock(),
        overlay_surface=overlay_surface,
    )


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_boot_order_audio_starts_after_first_frame(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    seed = _run_seed()
    loading_compositor = MagicMock()
    window = _boot_window(seed, loading_compositor)

    call_order: list[str] = []
    overlay_surface = pygame.Surface((seed.display_width, seed.display_height), pygame.SRCALPHA)

    def cheap_side_effect(
        rt: VisualizerSeed,
        compositor: MagicMock | None = None,
    ) -> tuple[MagicMock, MagicMock, MagicMock, pygame.Surface]:
        call_order.append("init_cheap")
        return compositor, MagicMock(), MagicMock(), overlay_surface

    def heavy_with_start(
        rt: VisualizerSeed,
        comp: MagicMock,
        post: MagicMock,
        masked: MagicMock,
        surface: pygame.Surface,
        on_progress=None,
    ) -> LiveVisualizerRuntime:
        live = _heavy_init_side_effect(rt, comp, post, masked, surface, on_progress)
        live.mix_player.start.side_effect = lambda: call_order.append("mix_start")
        return live

    mock_init_cheap.side_effect = cheap_side_effect
    mock_init_heavy.side_effect = heavy_with_start
    window.update.side_effect = lambda *_a, **_k: call_order.append("loading_screen")
    mock_tick_frame.side_effect = lambda *_a, **_k: call_order.append("tick_frame")

    quit_event = MagicMock()
    quit_event.type = pygame.QUIT
    mock_pygame.event.get.side_effect = [[], [quit_event]]
    mock_pygame.QUIT = pygame.QUIT
    mock_pygame.K_t = pygame.K_t
    mock_pygame.time.Clock.return_value.tick.return_value = 33

    app = VisualizerApp(seed)
    app.run(window)

    loading_compositor.destroy.assert_called_once()
    window.adopt_display_size.assert_not_called()
    mock_pygame.display.set_mode.assert_not_called()
    mock_init_cheap.assert_called_once_with(seed, compositor=loading_compositor)
    mock_init_heavy.assert_called_once()
    mock_tick_frame.assert_called()
    _assert_warmup_tick(mock_tick_frame.call_args_list[0])
    assert isinstance(app._runtime, LiveVisualizerRuntime)
    app._runtime.mix_player.start.assert_called_once()
    assert call_order.index("tick_frame") < call_order.index("mix_start")
    assert call_order.count("loading_screen") >= 1


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_pygame_quit_clean_exits_via_try_quit(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    seed = _run_seed()
    window = _boot_window(seed, MagicMock())

    mock_init_cheap.side_effect = lambda rt, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface((seed.display_width, seed.display_height), pygame.SRCALPHA),
    )
    controls = MagicMock()
    _silence_tap_sync(controls)
    controls.try_quit.return_value = True
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.consume_hide_overlay.return_value = False
    controls.project_render.busy = False

    def heavy_with_controls(
        rt: VisualizerSeed,
        comp: MagicMock,
        post: MagicMock,
        masked: MagicMock,
        surface: pygame.Surface,
        on_progress=None,
    ) -> LiveVisualizerRuntime:
        live = _heavy_init_side_effect(rt, comp, post, masked, surface, on_progress)
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
    app.run(window)

    assert controls.try_quit.call_count == 1
    controls.consume_pending_exit.assert_called()
    assert isinstance(app._runtime, LiveVisualizerRuntime)
    app._runtime.ui_fade.notify_input.assert_not_called()


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_ctrl_q_clean_exits(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    seed = _run_seed()
    window = _boot_window(seed, MagicMock())

    mock_init_cheap.side_effect = lambda rt, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface((seed.display_width, seed.display_height), pygame.SRCALPHA),
    )
    controls = MagicMock()
    _silence_tap_sync(controls)
    controls.pending_exit = False
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.consume_hide_overlay.return_value = False
    controls.project_render.busy = False
    controls.handle_move_mode_keydown.return_value = False
    controls.navigator.handle_keydown.return_value = False
    controls.navigator.handle_hotkey.return_value = False
    controls.inspector.handle_keydown.return_value = False
    controls.inspector.handle_hotkey.return_value = False

    def request_quit() -> None:
        controls.pending_exit = True

    controls.request_quit.side_effect = request_quit

    def heavy_with_controls(
        rt: VisualizerSeed,
        comp: MagicMock,
        post: MagicMock,
        masked: MagicMock,
        surface: pygame.Surface,
        on_progress=None,
    ) -> LiveVisualizerRuntime:
        live = _heavy_init_side_effect(rt, comp, post, masked, surface, on_progress)
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

    VisualizerApp(seed).run(window)

    assert controls.request_quit.call_count == 1


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_pygame_quit_dirty_stays_open(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    seed = _run_seed()
    window = _boot_window(seed, MagicMock())

    mock_init_cheap.side_effect = lambda rt, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface((seed.display_width, seed.display_height), pygame.SRCALPHA),
    )
    controls = MagicMock()
    _silence_tap_sync(controls)
    controls.try_quit.return_value = False
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.consume_hide_overlay.return_value = False
    controls.project_render.busy = False

    def heavy_with_controls(
        rt: VisualizerSeed,
        comp: MagicMock,
        post: MagicMock,
        masked: MagicMock,
        surface: pygame.Surface,
        on_progress=None,
    ) -> LiveVisualizerRuntime:
        live = _heavy_init_side_effect(rt, comp, post, masked, surface, on_progress)
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
        app.run(window)
        raise AssertionError("expected main loop to continue")
    except RuntimeError as exc:
        assert str(exc) == "still running"

    assert controls.try_quit.call_count == 1
    controls.consume_pending_exit.assert_called()
    assert isinstance(app._runtime, LiveVisualizerRuntime)
    app._runtime.ui_fade.notify_input.assert_called_once()


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_main_loop_stays_open_without_quit_event(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    seed = _run_seed()
    window = _boot_window(seed, MagicMock())

    mock_init_cheap.side_effect = lambda rt, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface((seed.display_width, seed.display_height), pygame.SRCALPHA),
    )
    controls = MagicMock()
    _silence_tap_sync(controls)
    controls.try_quit.return_value = True
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.consume_hide_overlay.return_value = False
    controls.project_render.busy = False

    def heavy_with_controls(
        rt: VisualizerSeed,
        comp: MagicMock,
        post: MagicMock,
        masked: MagicMock,
        surface: pygame.Surface,
        on_progress=None,
    ) -> LiveVisualizerRuntime:
        live = _heavy_init_side_effect(rt, comp, post, masked, surface, on_progress)
        live.controls = controls
        return live

    mock_init_heavy.side_effect = heavy_with_controls
    mock_tick_frame.side_effect = lambda *_a, **_k: None

    mock_pygame.event.get.side_effect = [[], RuntimeError("still running")]
    mock_pygame.QUIT = pygame.QUIT
    mock_pygame.time.Clock.return_value.tick.return_value = 33

    try:
        VisualizerApp(seed).run(window)
        raise AssertionError("expected main loop to continue")
    except RuntimeError as exc:
        assert str(exc) == "still running"

    controls.try_quit.assert_not_called()


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_resizes_when_loading_window_size_differs(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    seed = _run_seed()
    loading = MagicMock()
    window = _boot_window(seed, loading)
    window.display_width = seed.display_width // 2
    window.display_height = seed.display_height // 2

    mock_init_cheap.side_effect = lambda rt, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface((seed.display_width, seed.display_height), pygame.SRCALPHA),
    )
    mock_init_heavy.side_effect = _heavy_init_side_effect
    mock_tick_frame.side_effect = lambda *_a, **_k: None
    mock_pygame.event.get.side_effect = [[], RuntimeError("still running")]
    mock_pygame.QUIT = pygame.QUIT
    mock_pygame.time.Clock.return_value.tick.return_value = 33

    try:
        VisualizerApp(seed).run(window)
    except RuntimeError:
        pass

    window.adopt_display_size.assert_called_once_with(
        seed.display_width, seed.display_height
    )
    loading.destroy.assert_called_once()
    mock_pygame.display.set_mode.assert_not_called()
    mock_init_cheap.assert_called_once_with(seed, compositor=loading)


@patch("cleave.viz.app._tick_frame_live_overlay")
@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_holds_content_and_overlay_while_project_render_busy(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
    mock_live_overlay: MagicMock,
) -> None:
    seed = _run_seed()
    window = _boot_window(seed, MagicMock())

    mock_init_cheap.side_effect = lambda rt, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface((seed.display_width, seed.display_height), pygame.SRCALPHA),
    )
    controls = MagicMock()
    _silence_tap_sync(controls)
    controls.try_quit.return_value = True
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.consume_hide_overlay.return_value = False
    controls.project_render.busy = True

    def heavy_with_controls(
        rt: VisualizerSeed,
        comp: MagicMock,
        post: MagicMock,
        masked: MagicMock,
        surface: pygame.Surface,
        on_progress=None,
    ) -> LiveVisualizerRuntime:
        live = _heavy_init_side_effect(rt, comp, post, masked, surface, on_progress)
        live.controls = controls
        return live

    mock_init_heavy.side_effect = heavy_with_controls
    mock_tick_frame.side_effect = lambda *_a, **_k: None
    mock_pygame.event.get.side_effect = [[], RuntimeError("still running")]
    mock_pygame.QUIT = pygame.QUIT
    mock_pygame.time.Clock.return_value.tick.return_value = 33

    app = VisualizerApp(seed)
    try:
        app.run(window)
        raise AssertionError("expected main loop to continue")
    except RuntimeError as exc:
        assert str(exc) == "still running"

    mock_tick_frame.assert_called_once()
    _assert_warmup_tick(mock_tick_frame.call_args)
    assert isinstance(app._runtime, LiveVisualizerRuntime)
    app._runtime.compositor.present_content.assert_called()
    mock_live_overlay.assert_called()


@patch("cleave.viz.app._make_masked_compositor")
@patch("cleave.viz.app.GlPostProcess")
@patch("cleave.viz.app._make_compositor")
def test_init_gl_resources_cheap_reuses_loading_compositor(
    mock_make_compositor: MagicMock,
    mock_post_cls: MagicMock,
    mock_make_masked: MagicMock,
) -> None:
    seed = _run_seed()
    loading = MagicMock()
    post = MagicMock()
    mock_post_cls.return_value = post
    mock_make_masked.return_value = MagicMock()

    compositor, post_process, _masked, overlay = init_gl_resources_cheap(
        seed, compositor=loading
    )

    mock_make_compositor.assert_not_called()
    loading.destroy.assert_not_called()
    loading.set_display_size.assert_called_once_with(
        seed.display_width, seed.display_height
    )
    loading.set_content_size.assert_called_once_with(seed.width, seed.height)
    loading.set_color_format.assert_called_once()
    post.init.assert_called_once()
    assert compositor is loading
    assert post_process is post
    assert overlay.get_size() == (seed.display_width, seed.display_height)


@patch("cleave.viz.app.LayerFramePipeline.build", return_value=([], {}))
@patch("cleave.viz.app.GlMaskedCompositor")
@patch("cleave.viz.app.GlPostProcess")
@patch("cleave.viz.app.GlCompositor")
@patch("cleave.viz.app._compositor_color_format")
def test_init_gl_resources_render_content_canvas_matches_output(
    mock_format: MagicMock,
    mock_gl: MagicMock,
    mock_post: MagicMock,
    mock_masked: MagicMock,
    _mock_build: MagicMock,
) -> None:
    seed = _run_seed()
    mock_format.return_value = MagicMock()
    mock_gl.return_value = MagicMock()
    mock_post.return_value = MagicMock()
    mock_masked.return_value = MagicMock()
    output_w, output_h = 1080, 1920

    init_gl_resources_render(seed, output_width=output_w, output_height=output_h)

    mock_gl.assert_called_once()
    assert mock_gl.call_args.args[:2] == (output_w, output_h)
    assert mock_gl.call_args.kwargs["display_width"] == output_w
    assert mock_gl.call_args.kwargs["display_height"] == output_h
    mock_masked.assert_called_once()
    assert mock_masked.call_args.args[:2] == (output_w, output_h)


@patch("cleave.viz.app.GlMaskedCompositor")
@patch("cleave.viz.app.GlPostProcess")
@patch("cleave.viz.app.GlCompositor")
@patch("cleave.viz.app._compositor_color_format")
def test_init_gl_resources_cheap_uses_editor_canvas_not_render_output(
    mock_format: MagicMock,
    mock_gl: MagicMock,
    mock_post: MagicMock,
    mock_masked: MagicMock,
) -> None:
    seed = _run_seed(
        upscale=1.0,
        width=DEFAULT_EDITOR_WIDTH,
        height=DEFAULT_EDITOR_HEIGHT,
    )
    seed.cfg = replace(
        seed.cfg,
        render_width=1080,
        render_height=1920,
        editor=replace(
            seed.cfg.editor,
            width=DEFAULT_EDITOR_WIDTH,
            height=DEFAULT_EDITOR_HEIGHT,
        ),
    )
    seed.session.project.render.width = 1080
    seed.session.project.render.height = 1920
    mock_format.return_value = MagicMock()
    mock_gl.return_value = MagicMock()
    mock_post.return_value = MagicMock()
    mock_masked.return_value = MagicMock()

    init_gl_resources_cheap(seed)

    mock_gl.assert_called_once()
    assert mock_gl.call_args.args[:2] == (DEFAULT_EDITOR_WIDTH, DEFAULT_EDITOR_HEIGHT)
    assert mock_gl.call_args.kwargs["display_width"] == DEFAULT_EDITOR_WIDTH
    assert mock_gl.call_args.kwargs["display_height"] == DEFAULT_EDITOR_HEIGHT
    mock_masked.assert_called_once()
    assert mock_masked.call_args.args[:2] == (
        DEFAULT_EDITOR_WIDTH,
        DEFAULT_EDITOR_HEIGHT,
    )


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
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
    mock_draw_timeline: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor, upscale=1.0)
    runtime.seed.session.timeline.panel_open = True
    runtime.ui_fade.notify_input()
    call_order: list[str] = []

    compositor.apply_frame_fade.side_effect = lambda *_a, **_k: call_order.append(
        "apply_frame_fade"
    )
    compositor.present_content.side_effect = lambda: call_order.append("present_content")
    mock_live_overlay.side_effect = lambda *_a, **_k: call_order.append("content_overlay")
    mock_draw_timeline.side_effect = lambda *_a, **_k: call_order.append("draw_overlay")

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
    runtime.controls.focus_cursor = MainFocus(RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER))

    assert _key_handler_for_session(runtime) is main


def test_key_routing_timeline_when_submenu_focused() -> None:
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    main = MagicMock()
    timeline = MagicMock()
    runtime.controls = main
    runtime.timeline_controls = timeline
    runtime.ui_fade = UiFade()
    runtime.ui_fade.notify_input()
    runtime.seed.session.timeline.enabled = True
    runtime.seed.session.timeline.panel_open = True
    runtime.controls.focus_cursor = TimelineFocus(0)
    runtime.controls.shell_focus.region = ShellRegion.TIMELINE

    assert _key_handler_for_session(runtime, pygame.K_RETURN) is timeline
    assert _key_handler_for_session(runtime, pygame.K_UP) is timeline
    assert _key_handler_for_session(runtime, pygame.K_DOWN) is timeline


def test_key_routing_timeline_when_overlay_hidden_and_submenu_focused() -> None:
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    main = MagicMock()
    timeline = MagicMock()
    runtime.controls = main
    runtime.timeline_controls = timeline
    runtime.ui_fade = UiFade()
    runtime.seed.session.timeline.enabled = True
    runtime.seed.session.timeline.panel_open = True
    runtime.controls.focus_cursor = TimelineFocus(0)
    runtime.controls.shell_focus.region = ShellRegion.TIMELINE

    assert _key_handler_for_session(runtime, pygame.K_RETURN) is timeline
    assert _key_handler_for_session(runtime, pygame.K_UP) is timeline


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
    runtime.controls.shell_focus.region = ShellRegion.TIMELINE

    assert _keyup_handler_for_session(runtime, pygame.K_UP) is timeline
    assert _keyup_handler_for_session(runtime, pygame.K_DOWN) is timeline
    assert _keyup_handler_for_session(runtime, pygame.K_RETURN) is timeline


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
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
    mock_draw_timeline: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _timeline_open_runtime(compositor)
    runtime.controls.focus_cursor = TimelineFocus(0)
    runtime.controls.shell_focus.region = ShellRegion.NAVIGATOR

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_not_called()


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
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
    mock_draw_timeline: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _timeline_open_runtime(compositor)
    runtime.controls.focus_cursor = MainFocus(
        RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
    )
    runtime.controls.shell_focus.region = ShellRegion.TIMELINE

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_called_once()
    assert mock_draw_timeline.call_args.kwargs["visibility"] == 1.0
    assert mock_draw_timeline.call_args.args[3].submenu_focused is True


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
@patch("cleave.viz.frame_finish._composite_render_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_skips_view_state_and_timeline_when_overlay_hidden(
    _mock_visibility: MagicMock,
    _mock_effects: MagicMock,
    _mock_composite: MagicMock,
    _mock_fade_alpha: MagicMock,
    _mock_live_overlay: MagicMock,
    mock_draw_timeline: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    runtime.controls.build_view_state = MagicMock()

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)

    runtime.controls.build_view_state.assert_not_called()
    mock_draw_timeline.assert_not_called()


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
@patch("cleave.viz.frame_finish._composite_render_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_skips_tuning_when_only_a_modal_is_active(
    _mock_visibility: MagicMock,
    _mock_effects: MagicMock,
    _mock_composite: MagicMock,
    _mock_fade_alpha: MagicMock,
    _mock_live_overlay: MagicMock,
    mock_draw_timeline: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    runtime.controls.build_view_state = MagicMock(return_value=MagicMock())
    runtime.modal_host.prompt_yes_no("test?", on_confirm=lambda: None)

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)

    runtime.controls.build_view_state.assert_not_called()
    mock_draw_timeline.assert_not_called()


@patch("cleave.viz.frame_finish._composite_render_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_insets_panels_by_full_menu_bar_height_when_faded(
    _mock_visibility: MagicMock,
    _mock_effects: MagicMock,
    _mock_composite: MagicMock,
    _mock_fade_alpha: MagicMock,
    _mock_live_overlay: MagicMock,
) -> None:
    pygame.init()
    from types import SimpleNamespace

    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    fade = runtime.ui_fade
    fade.notify_input()
    fade._idle_sec = fade._hold_idle_sec + fade._fade_duration_sec * 0.6
    app = VisualizerApp(runtime)
    shell = SimpleNamespace(menu_bar_height_px=23, set_layout=MagicMock())
    app._shell = shell
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)

    from cleave.viz.shell_host import menu_bar_height_px
    from cleave.viz.shell_layout import ShellLayout

    display_w, display_h = runtime.overlay_surface.get_size()
    editor = runtime.seed.cfg.editor
    expected = ShellLayout.compute(
        display_w,
        display_h,
        23,
        menu_bar_height_px(),
        0,
        nav_width=editor.navigator_width,
        insp_width=editor.inspector_width,
        docked=editor.shell_layout_mode == "docked",
    )
    assert editor.navigator_width == DEFAULT_NAVIGATOR_WIDTH
    assert editor.inspector_width == DEFAULT_INSPECTOR_WIDTH
    runtime.compositor.set_present_rect.assert_called_with(expected.visualiser)
    shell.set_layout.assert_called_once()
    assert shell.set_layout.call_args.args[0].visualiser == expected.visualiser


def test_live_overlay_ui_active_gating() -> None:
    assert not _live_overlay_ui_active(
        overlay_visibility=0.0,
        timeline_strip_visible=False,
    )
    assert _live_overlay_ui_active(
        overlay_visibility=0.5,
        timeline_strip_visible=False,
    )
    assert _live_overlay_ui_active(
        overlay_visibility=0.0,
        timeline_strip_visible=True,
    )


def test_timeline_strip_visible_while_timeline_region_despite_hidden_overlay() -> None:
    tl = TuningSession(layer_z_order=[], layers={}).timeline
    tl.enabled = True
    tl.panel_open = True

    assert (
        _timeline_strip_visible(
            tl, overlay_visibility=0.0, region=ShellRegion.TIMELINE
        )
        is True
    )
    assert (
        _timeline_strip_visible(
            tl, overlay_visibility=1.0, region=ShellRegion.TIMELINE
        )
        is True
    )
    assert _timeline_strip_fade(region=ShellRegion.TIMELINE, overlay_visibility=0.0) == 1.0

    assert (
        _timeline_strip_visible(
            tl, overlay_visibility=0.0, region=ShellRegion.NAVIGATOR
        )
        is False
    )
    assert (
        _timeline_strip_visible(
            tl, overlay_visibility=0.5, region=ShellRegion.INSPECTOR
        )
        is True
    )
    assert _timeline_strip_fade(region=ShellRegion.NAVIGATOR, overlay_visibility=0.5) == 0.5
    assert _timeline_strip_fade(region=ShellRegion.INSPECTOR, overlay_visibility=0.5) == 0.5


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
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
    mock_draw_timeline: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _timeline_open_runtime(compositor)
    runtime.controls.focus_cursor = TimelineFocus(0)
    runtime.controls.shell_focus.region = ShellRegion.NAVIGATOR
    runtime.ui_fade.notify_input()

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_called_once()
    assert mock_draw_timeline.call_args.kwargs["visibility"] == 1.0
    assert mock_draw_timeline.call_args.args[3].submenu_focused is False


def test_esc_hide_clears_submenu_focus_preserves_panel_open() -> None:
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor)
    fade = UiFade()
    fade.notify_input()
    runtime.ui_fade = fade
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
        fade.hide_immediately()
        runtime.controls.exit_timeline_submenu()

    assert runtime.seed.session.timeline.panel_open is True
    assert not isinstance(runtime.controls.focus_cursor, TimelineFocus)
    assert fade.is_visible() is False


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
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
    mock_draw_timeline: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _timeline_open_runtime(compositor)
    fade = runtime.ui_fade

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_not_called()

    fade.notify_input()
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_called_once()
    assert runtime.seed.session.timeline.panel_open is True