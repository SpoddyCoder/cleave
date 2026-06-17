"""Unit tests for layered overlay keyboard dispatch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pygame

from cleave.extract import STEM_NAMES
from cleave.viz.app import VisualizerRuntime
from cleave.viz.controls import TuningControls
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.input_dispatch import (
    dispatch_keydown,
    dispatch_should_notify_overlay,
    key_handler_for_runtime,
)
from cleave.viz.overlay import TuningOverlay
from cleave.viz.timeline_controls import TimelineControls
from tests.support.compositor_mock import recording_compositor
from tests.support.viz import keydown, make_playlist, make_test_cfg, stub_playback_state


def _make_runtime(
    *,
    submenu_focused: bool = True,
    panel_open: bool = True,
    recording: bool = False,
    help_visible: bool = False,
) -> VisualizerRuntime:
    preset_root = Path("/tmp/presets")
    session = TuningSession(
        layer_z_order=list(STEM_NAMES),
        layers={
            stem: LayerRuntime(
                playlist=make_playlist(stem),
                browse_floor=preset_root / stem,
            )
            for stem in STEM_NAMES
        },
    )
    session.help_visible = help_visible
    tl = session.timeline
    tl.enabled = True
    tl.panel_open = panel_open
    tl.submenu_focused = submenu_focused
    tl.recording = recording
    if recording:
        tl.armed_stems = {"drums"}
        tl.record_start_sec = 0.0
        tl.record_baseline = {"drums": True}

    playback = stub_playback_state()
    compositor = recording_compositor()
    runtime = VisualizerRuntime(
        project_dir=MagicMock(),
        audio_path=MagicMock(),
        width=1280,
        height=720,
        upscale=2.0,
        display_width=2560,
        display_height=1440,
        fps=30,
        window_title="test",
        session=session,
        cfg=MagicMock(),
        pcm_bank=MagicMock(),
        duration_sec=120.0,
        n_pcm=1024,
        signals=None,
        effect_runtime=MagicMock(),
        preset_root=preset_root,
        compositor=compositor,
        post_process=MagicMock(),
        overlay=TuningOverlay(),
    )
    runtime.controls = TuningControls(
        session,
        make_test_cfg(tuple(STEM_NAMES), preset_root=preset_root),
        preset_root=preset_root,
        playback=playback,
        duration_sec=120.0,
    )
    runtime.timeline_controls = TimelineControls(
        session,
        playback,
        120.0,
        on_close=lambda: (
            setattr(tl, "panel_open", False),
            setattr(tl, "submenu_focused", False),
        ),
    )
    return runtime


def test_h_toggles_help_when_timeline_submenu_focused() -> None:
    runtime = _make_runtime(help_visible=False)
    assert dispatch_keydown(keydown(pygame.K_h), runtime) is True
    assert runtime.session.help_visible is True
    assert dispatch_keydown(keydown(pygame.K_h), runtime) is True
    assert runtime.session.help_visible is False


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
    runtime.controls.session.layers["drums"].opacity_pct = 60
    assert (
        dispatch_keydown(
            keydown(pygame.K_q, mod=pygame.KMOD_CTRL),
            runtime,
        )
        is True
    )
    state = runtime.controls.build_view_state(paused=False)
    assert state.unsaved_quit_active is True


def test_ctrl_q_after_dont_save_exits() -> None:
    runtime = _make_runtime()
    runtime.controls.session.layers["drums"].opacity_pct = 60
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
    assert runtime.session.timeline.recording is False
    assert runtime.session.timeline.panel_open is True
    assert runtime.session.timeline.submenu_focused is True


def test_second_esc_after_stop_closes_submenu_panel() -> None:
    runtime = _make_runtime(recording=True)
    dispatch_keydown(keydown(pygame.K_ESCAPE), runtime)
    assert runtime.session.timeline.recording is False

    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert runtime.session.timeline.panel_open is False
    assert runtime.session.timeline.submenu_focused is False


def test_second_esc_after_stop_requests_overlay_hide_on_main() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=True, recording=True)
    dispatch_keydown(keydown(pygame.K_ESCAPE), runtime)
    assert runtime.session.timeline.recording is False

    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert runtime.controls.consume_hide_overlay() is True
    assert runtime.session.timeline.panel_open is True


def test_t_while_recording_is_noop() -> None:
    runtime = _make_runtime(recording=True)
    assert dispatch_keydown(keydown(pygame.K_t), runtime) is True
    assert runtime.session.timeline.panel_open is True
    assert runtime.session.timeline.submenu_focused is True


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
