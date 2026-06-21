"""Unit tests for layered overlay keyboard dispatch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pygame

from cleave.config_schema import DEFAULT_LAYER_SLOTS
from tests.support.config import TEST_LAYER_STEMS
from cleave.extract import STEM_NAMES
from cleave.viz.app import LiveVisualizerRuntime, VisualizerSeed
from cleave.viz.focus_nav import MainFocus, TimelineFocus
from cleave.viz.controls import TuningControls
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.input_dispatch import (
    dispatch_keydown,
    dispatch_should_notify_overlay,
    key_handler_for_runtime,
)
from cleave.viz.modal import ModalHost, ModalKind
from cleave.viz.tuning_panel_draw import TuningOverlay
from cleave.viz.timeline_controls import TimelineControls
from tests.support.compositor_mock import recording_compositor
from tests.support.viz import keydown, make_playlist, make_test_cfg, stub_playback_state


def _make_runtime(
    *,
    submenu_focused: bool = True,
    panel_open: bool = True,
    recording: bool = False,
    help_visible: bool = False,
) -> LiveVisualizerRuntime:
    preset_root = Path("/tmp/presets")
    session = TuningSession(
        layer_z_order=list(DEFAULT_LAYER_SLOTS),
        layers={
            slot: LayerRuntime(
                playlist=make_playlist(slot),
                browse_floor=preset_root / slot,
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
        },
    )
    session.help_visible = help_visible
    tl = session.timeline
    tl.enabled = True
    tl.panel_open = panel_open
    tl.recording = recording
    if recording:
        tl.armed_slots = {"layer_1"}
        tl.record_start_sec = 0.0
        tl.record_baseline = {"layer_1": True}

    seed = VisualizerSeed(
        project_dir=MagicMock(),
        audio_path=MagicMock(),
        width=1280,
        height=720,
        upscale=2.0,
        display_width=2560,
        display_height=1440,
        window_title="test",
        session=session,
        cfg=MagicMock(),
        pcm_bank=MagicMock(),
        duration_sec=120.0,
        signals=None,
        effect_runtime=MagicMock(),
        preset_root=preset_root,
        playlists={},
    )
    playback = stub_playback_state()
    compositor = recording_compositor()
    runtime = LiveVisualizerRuntime(
        seed=seed,
        layers=[],
        layers_by_slot={},
        compositor=compositor,
        post_process=MagicMock(),
        overlay=TuningOverlay(),
        help_overlay=MagicMock(),
        timeline_overlay=MagicMock(),
        overlay_surface=pygame.Surface((2560, 1440), pygame.SRCALPHA),
        controls=MagicMock(),
        timeline_controls=MagicMock(),
        modal_host=ModalHost(),
        mix_player=MagicMock(),
        playback=playback,
    )
    runtime.controls = TuningControls(
        session,
        make_test_cfg(tuple(STEM_NAMES), preset_root=preset_root),
        preset_root=preset_root,
        playback=playback,
        duration_sec=120.0,
    )
    if submenu_focused:
        runtime.controls.focus_cursor = TimelineFocus(0)
    else:
        runtime.controls.focus_cursor = MainFocus(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))
    runtime.modal_host = runtime.controls.modal_host
    runtime.timeline_controls = TimelineControls(
        session,
        playback,
        120.0,
        on_close=runtime.controls.close_timeline_panel,
        on_exit_submenu=runtime.controls.exit_timeline_submenu,
    )
    return runtime


def test_h_toggles_help_when_timeline_submenu_focused() -> None:
    runtime = _make_runtime(help_visible=False)
    assert dispatch_keydown(keydown(pygame.K_h), runtime) is True
    assert runtime.seed.session.help_visible is True
    assert dispatch_keydown(keydown(pygame.K_h), runtime) is True
    assert runtime.seed.session.help_visible is False


def test_ctrl_q_quit_from_timeline_context() -> None:
    runtime = _make_runtime()
    assert (
        dispatch_keydown(
            keydown(pygame.K_q, mod=pygame.KMOD_CTRL),
            runtime,
        )
        is False
    )


def test_ctrl_q_dirty_session_blocks_quit() -> None:
    runtime = _make_runtime()
    runtime.controls.session.layers["layer_1"].opacity_pct = 60
    assert (
        dispatch_keydown(
            keydown(pygame.K_q, mod=pygame.KMOD_CTRL),
            runtime,
        )
        is True
    )
    modal_view = runtime.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.UNSAVED_QUIT


def test_ctrl_q_after_dont_save_exits() -> None:
    runtime = _make_runtime()
    runtime.controls.session.layers["layer_1"].opacity_pct = 60
    dispatch_keydown(keydown(pygame.K_q, mod=pygame.KMOD_CTRL), runtime)
    runtime.controls.handle_modal_keydown(keydown(pygame.K_RIGHT))
    runtime.controls.handle_modal_keydown(keydown(pygame.K_RETURN))
    assert (
        dispatch_keydown(
            keydown(pygame.K_q, mod=pygame.KMOD_CTRL),
            runtime,
        )
        is False
    )


def test_esc_while_recording_stops_take_panel_stays_open() -> None:
    runtime = _make_runtime(recording=True)
    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert runtime.seed.session.timeline.recording is False
    assert runtime.seed.session.timeline.panel_open is True
    assert isinstance(runtime.controls.focus_cursor, TimelineFocus)


def test_second_esc_after_stop_closes_submenu_panel() -> None:
    runtime = _make_runtime(recording=True)
    dispatch_keydown(keydown(pygame.K_ESCAPE), runtime)
    assert runtime.seed.session.timeline.recording is False

    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert runtime.seed.session.timeline.panel_open is False
    assert not isinstance(runtime.controls.focus_cursor, TimelineFocus)


def test_second_esc_after_stop_requests_overlay_hide_on_main() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=True, recording=True)
    dispatch_keydown(keydown(pygame.K_ESCAPE), runtime)
    assert runtime.seed.session.timeline.recording is False

    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert runtime.controls.consume_hide_overlay() is True
    assert runtime.seed.session.timeline.panel_open is True


def test_t_while_recording_is_noop() -> None:
    runtime = _make_runtime(recording=True)
    assert dispatch_keydown(keydown(pygame.K_t), runtime) is True
    assert runtime.seed.session.timeline.panel_open is True
    assert isinstance(runtime.controls.focus_cursor, TimelineFocus)


def test_submenu_routing_up_down_to_tuning_enter_to_timeline() -> None:
    runtime = _make_runtime()
    main = runtime.controls
    timeline = runtime.timeline_controls

    assert key_handler_for_runtime(runtime, pygame.K_UP) is main
    assert key_handler_for_runtime(runtime, pygame.K_DOWN) is main
    assert key_handler_for_runtime(runtime, pygame.K_RETURN) is timeline


def test_notify_overlay_skipped_in_submenu() -> None:
    runtime = _make_runtime()
    assert dispatch_should_notify_overlay(keydown(pygame.K_LEFT), runtime) is False


def test_notify_overlay_when_main_context() -> None:
    runtime = _make_runtime(submenu_focused=False)
    assert dispatch_should_notify_overlay(keydown(pygame.K_LEFT), runtime) is True
    assert dispatch_should_notify_overlay(keydown(pygame.K_t), runtime) is False