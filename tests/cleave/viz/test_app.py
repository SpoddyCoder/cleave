"""Tests for VisualizerApp frame tick ordering."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock, call, patch

import pygame
import pytest

from cleave.config import EditorConfig
from cleave.config_schema.editor import (
    DEFAULT_VISUALISER_HEIGHT,
    DEFAULT_VISUALISER_WIDTH,
    DEFAULT_INSPECTOR_WIDTH,
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
    _timeline_strip_visible,
    init_gl_resources_cheap,
    init_gl_resources_render,
)
from cleave.viz.focus_nav import MainFocus, TimelineFocus
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.input_dispatch import key_handler_for_runtime
from cleave.viz.row_kinds import RowDescriptor, RowKind
from tests.support.config import default_post_fx_runtime
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.config import default_post_fx_runtime
from cleave.viz.modal import ModalHost
from cleave.viz.panel_notification import PanelNotificationActive
from tests.support.compositor_mock import recording_compositor
from tests.support.viz import make_test_cfg


@pytest.fixture(autouse=True)
def _stub_shell_draw(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loop tests have no ImGui context. The shell stays drawn in the app."""
    monkeypatch.setattr(
        "cleave.viz.shell_host.draw_shell_frame",
        lambda *_args, **_kwargs: None,
    )


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
    controls.project_switch.active = False
    controls.project_switch.key_repeat_armed = False
    controls.project_switch.take_accepted.return_value = None
    controls.consume_pending_switch.return_value = False


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


# Window size in these tests: twice the 1280x720 visualiser content.
_DISPLAY = (2560, 1440)


def _minimal_runtime(
    compositor: MagicMock, *, display: tuple[int, int] = _DISPLAY
) -> LiveVisualizerRuntime:
    display_w, display_h = display
    session = TuningSession(layer_z_order=[], layers={})
    post_fx = default_post_fx_runtime(enabled=False)
    session.post_fx = replace(
        post_fx,
        fade=replace(
            post_fx.fade,
            fade_in=replace(post_fx.fade.fade_in, end=0.0),
            fade_out=replace(post_fx.fade.fade_out, start=0.0),
        ),
    )
    controls = MagicMock()
    controls.inline_edit.handle_keydown.return_value = False
    controls.inline_edit.handle_keyup.return_value = False
    controls.inline_edit.handle_text_input.return_value = False
    controls.build_view_state.return_value = MagicMock()
    _silence_tap_sync(controls)
    controls.project_render.busy = False
    modal_host = ModalHost()
    seed = VisualizerSeed(
        project_dir=MagicMock(),
        audio_path=MagicMock(),
        width=1280,
        height=720,
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
        timeline_overlay=MagicMock(),
        overlay_surface=pygame.Surface((display_w, display_h), pygame.SRCALPHA),
    )
    runtime.seed.session.timeline.enabled = False
    runtime.seed.session.timeline.panel_open = False
    return runtime


def _run_seed(
    *,
    width: int = 1280,
    height: int = 720,
) -> VisualizerSeed:
    cfg = make_test_cfg(("layer_1",))
    return VisualizerSeed(
        project_dir=MagicMock(),
        audio_path=MagicMock(),
        width=width,
        height=height,
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
    window.display_width, window.display_height = _DISPLAY
    window.quit_requested = False
    window.apply_pending_resize.return_value = False
    window.compositor = compositor
    window.overlay_surface = pygame.Surface(
        _DISPLAY, pygame.SRCALPHA
    )
    return window


def _timeline_open_runtime(compositor: MagicMock) -> LiveVisualizerRuntime:
    runtime = _minimal_runtime(compositor)
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
@patch("cleave.viz.frame_finish._composite_overlay")
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
    controls.inline_edit.handle_keydown.return_value = False
    controls.inline_edit.handle_keyup.return_value = False
    controls.inline_edit.handle_text_input.return_value = False
    controls.build_view_state.return_value = MagicMock()
    _silence_tap_sync(controls)
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.value_nudge_armed = False
    controls.project_render.busy = False
    timeline_controls = MagicMock()
    timeline_controls.key_repeat_armed = False
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
        masked_compositor=masked_compositor,
        controls=controls,
        timeline_controls=timeline_controls,
        modal_host=modal_host,
        mix_player=mix_player,
        playback=playback,
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
    overlay_surface = pygame.Surface(_DISPLAY, pygame.SRCALPHA)

    def cheap_side_effect(
        rt: VisualizerSeed,
        display_size: tuple[int, int],
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
    assert app.run(window) is None

    loading_compositor.destroy.assert_not_called()
    mock_pygame.quit.assert_not_called()
    mock_pygame.display.set_mode.assert_not_called()
    mock_init_cheap.assert_called_once_with(
        seed, _DISPLAY, compositor=loading_compositor
    )
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

    mock_init_cheap.side_effect = lambda rt, display_size, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface(_DISPLAY, pygame.SRCALPHA),
    )
    controls = MagicMock()
    controls.inline_edit.handle_keydown.return_value = False
    controls.inline_edit.handle_keyup.return_value = False
    controls.inline_edit.handle_text_input.return_value = False
    _silence_tap_sync(controls)
    controls.try_quit.return_value = True
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.value_nudge_armed = False
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


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_carries_out_a_fullscreen_request_on_the_window(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    from cleave.viz.window_controls import WindowControls

    seed = _run_seed()
    window = _boot_window(seed, MagicMock())
    window.fullscreen = False

    def toggle() -> None:
        window.fullscreen = not window.fullscreen

    window.toggle_fullscreen.side_effect = toggle
    mock_init_cheap.side_effect = lambda rt, display_size, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface(_DISPLAY, pygame.SRCALPHA),
    )
    window_controls = WindowControls()
    window_controls.request_fullscreen_toggle()

    def heavy_with_window_controls(
        rt: VisualizerSeed,
        comp: MagicMock,
        post: MagicMock,
        masked: MagicMock,
        surface: pygame.Surface,
        on_progress=None,
    ) -> LiveVisualizerRuntime:
        live = _heavy_init_side_effect(rt, comp, post, masked, surface, on_progress)
        live.controls.window = window_controls
        live.controls.try_quit.return_value = True
        live.controls.consume_pending_exit.return_value = False
        return live

    mock_init_heavy.side_effect = heavy_with_window_controls
    mock_tick_frame.side_effect = lambda *_a, **_k: None
    quit_event = MagicMock()
    quit_event.type = pygame.QUIT
    mock_pygame.event.get.side_effect = [[], [quit_event]]
    mock_pygame.QUIT = pygame.QUIT
    mock_pygame.time.Clock.return_value.tick.return_value = 33

    VisualizerApp(seed).run(window)

    window.toggle_fullscreen.assert_called_once_with()
    assert window_controls.fullscreen is True
    assert window_controls.consume_fullscreen_toggle() is False
    window.sync_minimum_size.assert_called()


@patch("cleave.viz.app.current_sec", return_value=0.0)
@patch("cleave.viz.app.pygame")
@patch("cleave.viz.app.init_gl_resources_heavy")
@patch("cleave.viz.app.init_gl_resources_cheap")
@patch.object(VisualizerApp, "tick_frame")
def test_run_pending_switch_returns_target_and_keeps_compositor(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    from cleave.open_target import OpenTarget, OpenTargetKind

    seed = _run_seed()
    compositor = MagicMock()
    window = _boot_window(seed, compositor)
    target = OpenTarget(path=seed.project_dir, kind=OpenTargetKind.PROJECT)

    mock_init_cheap.side_effect = lambda rt, display_size, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface(_DISPLAY, pygame.SRCALPHA),
    )
    controls = MagicMock()
    controls.inline_edit.handle_keydown.return_value = False
    controls.inline_edit.handle_keyup.return_value = False
    controls.inline_edit.handle_text_input.return_value = False
    _silence_tap_sync(controls)
    controls.consume_pending_exit.return_value = False
    controls.consume_pending_switch.return_value = True
    controls.project_switch.take_accepted.return_value = target
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.value_nudge_armed = False
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
    mock_pygame.event.get.return_value = []
    mock_pygame.QUIT = pygame.QUIT
    mock_pygame.time.Clock.return_value.tick.return_value = 33

    assert VisualizerApp(seed).run(window) is target
    compositor.destroy.assert_not_called()
    mock_pygame.quit.assert_not_called()
    assert window.video_quit is not True


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

    mock_init_cheap.side_effect = lambda rt, display_size, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface(_DISPLAY, pygame.SRCALPHA),
    )
    controls = MagicMock()
    controls.inline_edit.handle_keydown.return_value = False
    controls.inline_edit.handle_keyup.return_value = False
    controls.inline_edit.handle_text_input.return_value = False
    _silence_tap_sync(controls)
    controls.pending_exit = False
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.value_nudge_armed = False
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

    mock_init_cheap.side_effect = lambda rt, display_size, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface(_DISPLAY, pygame.SRCALPHA),
    )
    controls = MagicMock()
    controls.inline_edit.handle_keydown.return_value = False
    controls.inline_edit.handle_keyup.return_value = False
    controls.inline_edit.handle_text_input.return_value = False
    _silence_tap_sync(controls)
    controls.try_quit.return_value = False
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.value_nudge_armed = False
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

    mock_init_cheap.side_effect = lambda rt, display_size, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface(_DISPLAY, pygame.SRCALPHA),
    )
    controls = MagicMock()
    controls.inline_edit.handle_keydown.return_value = False
    controls.inline_edit.handle_keyup.return_value = False
    controls.inline_edit.handle_text_input.return_value = False
    _silence_tap_sync(controls)
    controls.try_quit.return_value = True
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.value_nudge_armed = False
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
def test_run_keeps_open_window_size_on_project_switch(
    mock_tick_frame: MagicMock,
    mock_init_cheap: MagicMock,
    mock_init_heavy: MagicMock,
    mock_pygame: MagicMock,
    _mock_current_sec: MagicMock,
) -> None:
    seed = _run_seed()
    loading = MagicMock()
    window = _boot_window(seed, loading)
    dragged = (_DISPLAY[0] // 2, _DISPLAY[1] // 2)
    window.display_width, window.display_height = dragged

    mock_init_cheap.side_effect = lambda rt, display_size, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface(_DISPLAY, pygame.SRCALPHA),
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

    loading.destroy.assert_not_called()
    mock_pygame.display.set_mode.assert_not_called()
    mock_init_cheap.assert_called_once_with(seed, dragged, compositor=loading)


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

    mock_init_cheap.side_effect = lambda rt, display_size, compositor=None: (
        compositor,
        MagicMock(),
        MagicMock(),
        pygame.Surface(_DISPLAY, pygame.SRCALPHA),
    )
    controls = MagicMock()
    controls.inline_edit.handle_keydown.return_value = False
    controls.inline_edit.handle_keyup.return_value = False
    controls.inline_edit.handle_text_input.return_value = False
    _silence_tap_sync(controls)
    controls.try_quit.return_value = True
    controls.consume_pending_exit.return_value = False
    controls.tick = MagicMock()
    controls.key_repeat_armed = False
    controls.value_nudge_armed = False
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
        seed, _DISPLAY, compositor=loading
    )

    mock_make_compositor.assert_not_called()
    loading.destroy.assert_not_called()
    # The loading compositor keeps the window's display size.
    loading.set_display_size.assert_not_called()
    loading.set_content_size.assert_called_once_with(seed.width, seed.height)
    loading.set_color_format.assert_called_once()
    post.init.assert_called_once()
    assert compositor is loading
    assert post_process is post
    assert overlay.get_size() == _DISPLAY


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
        width=DEFAULT_VISUALISER_WIDTH,
        height=DEFAULT_VISUALISER_HEIGHT,
    )
    seed.cfg = replace(
        seed.cfg,
        render_width=1080,
        render_height=1920,
        editor=replace(
            seed.cfg.editor,
            visualiser_width=DEFAULT_VISUALISER_WIDTH,
            visualiser_height=DEFAULT_VISUALISER_HEIGHT,
        ),
    )
    seed.session.project.render.width = 1080
    seed.session.project.render.height = 1920
    mock_format.return_value = MagicMock()
    mock_gl.return_value = MagicMock()
    mock_post.return_value = MagicMock()
    mock_masked.return_value = MagicMock()

    init_gl_resources_cheap(seed, (DEFAULT_VISUALISER_WIDTH, DEFAULT_VISUALISER_HEIGHT))

    mock_gl.assert_called_once()
    assert mock_gl.call_args.args[:2] == (DEFAULT_VISUALISER_WIDTH, DEFAULT_VISUALISER_HEIGHT)
    assert mock_gl.call_args.kwargs["display_width"] == DEFAULT_VISUALISER_WIDTH
    assert mock_gl.call_args.kwargs["display_height"] == DEFAULT_VISUALISER_HEIGHT
    mock_masked.assert_called_once()
    assert mock_masked.call_args.args[:2] == (
        DEFAULT_VISUALISER_WIDTH,
        DEFAULT_VISUALISER_HEIGHT,
    )


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
@patch("cleave.viz.frame_finish._composite_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_overlay_order_when_display_matches_content(
    _mock_visibility: MagicMock,
    _mock_effects: MagicMock,
    _mock_composite: MagicMock,
    mock_fade_alpha: MagicMock,
    mock_live_overlay: MagicMock,
    mock_draw_timeline: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    runtime = _minimal_runtime(compositor, display=(1280, 720))
    runtime.seed.session.timeline.panel_open = True
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
    runtime.controls.focus_cursor = MainFocus(RowDescriptor(RowKind.OVERLAYS_HEADER))

    assert _key_handler_for_session(runtime) is main


def test_key_routing_timeline_when_submenu_focused() -> None:
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

    assert _key_handler_for_session(runtime, pygame.K_RETURN) is timeline
    assert _key_handler_for_session(runtime, pygame.K_UP) is timeline
    assert _key_handler_for_session(runtime, pygame.K_DOWN) is timeline


def test_key_routing_timeline_when_strip_focused() -> None:
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
@patch("cleave.viz.frame_finish._composite_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_skips_timeline_when_panel_closed(
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
    runtime.seed.session.timeline.panel_open = False
    runtime.controls.focus_cursor = TimelineFocus(0)
    runtime.controls.shell_focus.region = ShellRegion.NAVIGATOR

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_not_called()


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
@patch("cleave.viz.frame_finish._composite_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_draws_timeline_when_strip_focused(
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
        RowDescriptor(RowKind.TIMELINE_HEADER)
    )
    runtime.controls.shell_focus.region = ShellRegion.TIMELINE

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_called_once()
    assert mock_draw_timeline.call_args.kwargs["visibility"] == 1.0
    assert mock_draw_timeline.call_args.args[3].submenu_focused is True


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
@patch("cleave.viz.frame_finish._composite_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_skips_timeline_when_strip_closed(
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
@patch("cleave.viz.frame_finish._composite_overlay")
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
    runtime.modal_host.prompt_confirm("test?", "Confirm", on_confirm=lambda: None)

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)

    runtime.controls.build_view_state.assert_not_called()
    mock_draw_timeline.assert_not_called()


@patch("cleave.viz.frame_finish._composite_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_insets_panels_by_full_menu_bar_height(
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
        insp_width=editor.inspector_width,
        navigator_side=editor.navigator_side,
        help_side=editor.help_side,
    )
    assert editor.inspector_width == DEFAULT_INSPECTOR_WIDTH
    runtime.compositor.set_present_rect.assert_called_with(expected.visualiser)
    shell.set_layout.assert_called_once()
    assert shell.set_layout.call_args.args[0].visualiser == expected.visualiser


def test_live_overlay_ui_active_follows_the_open_strip() -> None:
    assert not _live_overlay_ui_active(timeline_strip_visible=False)
    assert _live_overlay_ui_active(timeline_strip_visible=True)


def test_timeline_strip_visible_while_panel_open() -> None:
    tl = TuningSession(layer_z_order=[], layers={}).timeline
    tl.enabled = True
    tl.panel_open = True
    assert _timeline_strip_visible(tl) is True
    tl.panel_open = False
    assert _timeline_strip_visible(tl) is False


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
@patch("cleave.viz.frame_finish._composite_overlay")
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

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_called_once()
    assert mock_draw_timeline.call_args.kwargs["visibility"] == 1.0
    assert mock_draw_timeline.call_args.args[3].submenu_focused is False


@patch("cleave.viz.app.OverlayDrawer.draw_timeline")
@patch("cleave.viz.frame_finish._composite_overlay")
@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch("cleave.viz.app.LayerFramePipeline.composite")
@patch("cleave.viz.app.LayerFramePipeline.render_frame")
@patch("cleave.viz.app.apply_layer_visibility")
def test_tick_frame_draws_open_timeline_immediately(
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

    app = VisualizerApp(runtime)
    app.tick_frame(1.0, paused=True, draw_overlay=True, n_pcm=735)
    mock_draw_timeline.assert_called_once()
    assert mock_draw_timeline.call_args.kwargs["visibility"] == 1.0
    assert runtime.seed.session.timeline.panel_open is True