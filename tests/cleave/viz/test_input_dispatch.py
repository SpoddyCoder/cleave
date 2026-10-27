"""Unit tests for layered overlay keyboard dispatch."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pygame

from cleave.config_schema.layers import DEFAULT_LAYER_SLOTS
from tests.support.config import TEST_LAYER_STEMS
from cleave.stems import STEM_NAMES
from cleave.viz.app import LiveVisualizerRuntime, VisualizerSeed
from cleave.timeline import SlotCue, TimelineLane
from cleave.viz.focus_nav import MainFocus, TimelineFocus
from cleave.viz.inspector import InspectorRow
from cleave.viz.navigator import layer_node_id, visible_top_level_ids
from cleave.viz.input_dispatch import (
    HELP_SCROLL_LINE_PX,
    HELP_SCROLL_PAGE_PX,
    dispatch_keydown,
    dispatch_keyup,
    dispatch_should_notify_overlay,
    dispatch_window_event,
    key_handler_for_runtime,
)
from cleave.viz.shell_focus import CycleStop, ShellRegion
from cleave.viz.controls import SEEK_LONG, SEEK_TINY, TuningControls
from cleave.viz.layer_visibility import armed_recording_level
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.modal import ModalHost, ModalKind
from cleave.viz.tuning_panel_draw import TuningOverlay
from cleave.viz.timeline_controls import TimelineControls
from tests.support.compositor_mock import recording_compositor
from tests.support.viz import (
    keydown,
    make_playlist,
    make_test_cfg,
    press_layer_row,
    stub_playback_state,
)


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
        masked_compositor=MagicMock(),
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
    runtime.controls.bind_menu_bar(runtime.menu_bar)
    if submenu_focused:
        runtime.controls.set_shell_region(ShellRegion.TIMELINE)
    else:
        runtime.controls.focus_cursor = MainFocus(
            RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
        )
    runtime.modal_host = runtime.controls.modal_host
    runtime.timeline_controls = TimelineControls(
        session,
        playback,
        120.0,
        on_close=runtime.controls.close_timeline_panel,
        on_exit_submenu=runtime.controls.exit_timeline_submenu,
        on_focus_row=runtime.controls.set_timeline_focus_row,
    )
    return runtime


def test_ctrl_s_saves_immediately_from_timeline_context() -> None:
    runtime = _make_runtime()
    assert dispatch_keydown(
        keydown(pygame.K_s, mod=pygame.KMOD_CTRL),
        runtime,
    ) is True
    assert runtime.modal_host.view_state() is None


def test_ctrl_enter_drops_song_marker_from_timeline_context() -> None:
    runtime = _make_runtime()
    prior_focus = runtime.controls.focus_cursor
    runtime.controls.playback.player.seek(12.5)
    assert dispatch_keydown(
        keydown(pygame.K_RETURN, mod=pygame.KMOD_CTRL),
        runtime,
    ) is True
    markers = runtime.seed.session.song_markers
    assert markers.times == [12.5]
    assert markers.selected_index is None
    assert runtime.seed.session.timeline.panel_open is True
    assert runtime.controls.focus_cursor == prior_focus


def test_ctrl_enter_refused_while_recording() -> None:
    runtime = _make_runtime(recording=True)
    runtime.controls.playback.player.seek(12.5)
    assert dispatch_keydown(
        keydown(pygame.K_RETURN, mod=pygame.KMOD_CTRL),
        runtime,
    ) is True
    assert runtime.seed.session.song_markers.times == []


def test_ctrl_s_blocked_while_solo_active() -> None:
    runtime = _make_runtime(submenu_focused=False)
    runtime.controls.session.solo_slot = "layer_1"
    assert dispatch_keydown(
        keydown(pygame.K_s, mod=pygame.KMOD_CTRL),
        runtime,
    ) is True
    assert runtime.modal_host.view_state() is None


def test_h_toggles_help_when_timeline_submenu_focused() -> None:
    runtime = _make_runtime(help_visible=False)
    assert dispatch_keydown(keydown(pygame.K_h), runtime) is True
    assert runtime.seed.session.help_visible is True
    assert dispatch_keydown(keydown(pygame.K_h), runtime) is True
    assert runtime.seed.session.help_visible is False


def test_curation_dispatch_allows_help_toggle() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False, help_visible=False)
    runtime.seed.session.settings.editor_mode = "preset_curation"
    assert dispatch_keydown(keydown(pygame.K_h), runtime) is True
    assert runtime.seed.session.help_visible is True
    assert dispatch_keydown(keydown(pygame.K_h), runtime) is True
    assert runtime.seed.session.help_visible is False


def test_curation_dispatch_blocks_global_shortcuts() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False)
    runtime.seed.session.settings.editor_mode = "preset_curation"
    assert dispatch_keydown(
        keydown(pygame.K_s, mod=pygame.KMOD_CTRL),
        runtime,
    ) is True
    assert runtime.modal_host.view_state() is None


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
    assert runtime.controls.shell_focus.region is ShellRegion.NAVIGATOR
    assert isinstance(runtime.controls.focus_cursor, MainFocus)
    assert (
        runtime.controls.focus_cursor.descriptor.kind
        is RowKind.RENDER_TIMELINE_HEADER
    )


def test_second_esc_after_stop_requests_overlay_hide_on_main() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=True, recording=True)
    runtime.controls.shell_focus.region = ShellRegion.NAVIGATOR
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

    assert key_handler_for_runtime(runtime, pygame.K_UP) is timeline
    assert key_handler_for_runtime(runtime, pygame.K_DOWN) is timeline
    assert key_handler_for_runtime(runtime, pygame.K_RETURN) is timeline
    assert main.focus_cursor == TimelineFocus(0)
    assert dispatch_keydown(keydown(pygame.K_DOWN), runtime) is True
    assert isinstance(main.focus_cursor, TimelineFocus)
    assert main.focus_cursor.row == 1


def test_ctrl_arrows_seek_long_from_main_panel() -> None:
    runtime = _make_runtime(submenu_focused=False)
    player = runtime.playback.player
    player.seek(40.0)
    assert dispatch_keydown(
        keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL), runtime
    ) is True
    assert player.file_position_sec() == 40.0 + SEEK_LONG
    assert dispatch_keydown(
        keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL), runtime
    ) is True
    assert player.file_position_sec() == 40.0


def test_shift_arrows_seek_tiny_from_timeline_context() -> None:
    runtime = _make_runtime()
    player = runtime.playback.player
    player.seek(10.0)
    assert dispatch_keydown(
        keydown(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT), runtime
    ) is True
    assert player.file_position_sec() == 10.0 + SEEK_TINY
    assert dispatch_keydown(
        keydown(pygame.K_LEFT, mod=pygame.KMOD_SHIFT), runtime
    ) is True
    assert player.file_position_sec() == 10.0
    assert dispatch_keydown(
        keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL), runtime
    ) is True
    assert player.file_position_sec() == 10.0 + SEEK_LONG
    assert runtime.controls.shell_focus.region is ShellRegion.TIMELINE


def test_curation_mode_still_seeks_with_modifiers() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False)
    runtime.seed.session.settings.editor_mode = "preset_curation"
    player = runtime.playback.player
    player.seek(10.0)
    assert dispatch_keydown(
        keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL), runtime
    ) is True
    assert player.file_position_sec() == 10.0 + SEEK_LONG


def test_global_seek_arms_repeat_on_main_handler() -> None:
    runtime = _make_runtime(submenu_focused=False)
    dispatch_keydown(keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL), runtime)
    assert runtime.controls.key_repeat_armed is True
    dispatch_keyup(
        pygame.event.Event(pygame.KEYUP, key=pygame.K_RIGHT),
        runtime,
    )
    assert runtime.controls.key_repeat_armed is False


def test_global_seek_arms_repeat_on_timeline_handler() -> None:
    runtime = _make_runtime()
    dispatch_keydown(keydown(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT), runtime)
    assert runtime.timeline_controls.key_repeat_armed is True
    dispatch_keyup(
        pygame.event.Event(pygame.KEYUP, key=pygame.K_RIGHT),
        runtime,
    )
    assert runtime.timeline_controls.key_repeat_armed is False


def test_ctrl_arrows_seek_from_value_row_without_changing_value() -> None:
    runtime = _make_runtime(submenu_focused=False)
    runtime.controls.focus_cursor = MainFocus(
        RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
    )
    before = runtime.controls.session.layers["layer_1"].opacity_pct
    player = runtime.playback.player
    player.seek(40.0)
    assert dispatch_keydown(
        keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL), runtime
    ) is True
    assert player.file_position_sec() == 40.0 + SEEK_LONG
    assert runtime.controls.session.layers["layer_1"].opacity_pct == before


def test_shift_arrows_seek_from_track_header() -> None:
    runtime = _make_runtime(submenu_focused=False)
    runtime.controls.focus_cursor = MainFocus(
        RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    )
    player = runtime.playback.player
    player.seek(10.0)
    assert dispatch_keydown(
        keydown(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT), runtime
    ) is True
    assert player.file_position_sec() == 10.0 + SEEK_TINY


def test_global_seek_from_move_mode() -> None:
    runtime = _make_runtime(submenu_focused=False)
    press_layer_row(
        runtime.controls,
        RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"),
        keydown(pygame.K_m),
        runtime,
    )
    assert runtime.controls.layer_lifecycle.move_mode_slot == "layer_1"
    player = runtime.playback.player
    player.seek(20.0)
    assert dispatch_keydown(
        keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL), runtime
    ) is True
    assert player.file_position_sec() == 20.0 + SEEK_LONG
    assert runtime.controls.layer_lifecycle.move_mode_slot == "layer_1"


def test_global_seek_ignored_while_modal_open() -> None:
    runtime = _make_runtime(submenu_focused=False)
    runtime.modal_host.prompt_text(
        "Change text...",
        "ab",
        on_confirm=lambda _s: None,
    )
    player = runtime.playback.player
    player.seek(10.0)
    assert dispatch_keydown(
        keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL), runtime
    ) is True
    assert player.file_position_sec() == 10.0


def test_global_seek_while_recording_fills_range() -> None:
    runtime = _make_runtime(submenu_focused=True)
    session = runtime.seed.session
    session.timeline.armed_slots = {"layer_1"}
    session.layers["layer_1"].enabled = True
    player = runtime.playback.player
    player.seek(10.0)
    runtime.timeline_controls.handle_keydown(keydown(pygame.K_r))
    assert session.timeline.recording is True
    active_at_start = armed_recording_level(session, "layer_1", 10.0)
    assert dispatch_keydown(
        keydown(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT), runtime
    ) is True
    assert player.file_position_sec() == 10.0 + SEEK_TINY
    assert armed_recording_level(session, "layer_1", 11.0) == active_at_start


def test_notify_overlay_skipped_in_submenu() -> None:
    runtime = _make_runtime()
    assert dispatch_should_notify_overlay(keydown(pygame.K_LEFT), runtime) is False


def test_notify_overlay_when_main_context() -> None:
    runtime = _make_runtime(submenu_focused=False)
    assert dispatch_should_notify_overlay(keydown(pygame.K_LEFT), runtime) is True
    assert dispatch_should_notify_overlay(keydown(pygame.K_t), runtime) is False
    runtime.controls.focus_cursor = TimelineFocus(0)
    assert runtime.controls.shell_focus.region is ShellRegion.NAVIGATOR
    assert dispatch_should_notify_overlay(keydown(pygame.K_LEFT), runtime) is True


def test_h_does_not_toggle_help_while_text_editing() -> None:
    runtime = _make_runtime(
        submenu_focused=False, panel_open=False, help_visible=False
    )
    runtime.modal_host.prompt_text(
        "Change text...",
        "ab",
        on_confirm=lambda _s: None,
    )
    assert dispatch_keydown(keydown(pygame.K_h), runtime) is True
    assert runtime.seed.session.help_visible is False
    view = runtime.modal_host.view_state()
    assert view is not None
    assert view.editing is True
    assert view.draft == "ab"

    event = pygame.event.Event(pygame.TEXTINPUT, text="h")
    assert runtime.modal_host.handle_text_input(event.text) is True
    view = runtime.modal_host.view_state()
    assert view is not None
    assert view.draft == "abh"
    assert runtime.seed.session.help_visible is False


def test_f10_toggles_bar_focus_and_wakes_overlay() -> None:
    runtime = _make_runtime()
    assert runtime.overlay.visibility == 0.0
    assert dispatch_keydown(keydown(pygame.K_F10), runtime) is True
    assert runtime.menu_bar.focused is True
    assert runtime.overlay.visibility == 1.0
    assert dispatch_keydown(keydown(pygame.K_F10), runtime) is True
    assert runtime.menu_bar.focused is False


def test_alt_f_opens_file_menu_plain_f_does_not() -> None:
    runtime = _make_runtime()
    assert runtime.overlay.visibility == 0.0
    dispatch_keydown(
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LALT),
        runtime,
    )
    assert dispatch_keydown(
        keydown(pygame.K_f, mod=pygame.KMOD_ALT),
        runtime,
    ) is True
    dispatch_keyup(
        pygame.event.Event(pygame.KEYUP, key=pygame.K_LALT),
        runtime,
    )
    assert runtime.menu_bar.focused is True
    assert runtime.menu_bar.dropdown_open is True
    assert runtime.menu_bar.menu_index == 0
    assert runtime.overlay.visibility == 1.0
    assert dispatch_keydown(
        keydown(pygame.K_f, mod=pygame.KMOD_ALT),
        runtime,
    ) is True
    assert runtime.menu_bar.focused is True
    assert runtime.menu_bar.dropdown_open is True

    runtime = _make_runtime()
    assert dispatch_keydown(keydown(pygame.K_f), runtime) is True
    assert runtime.menu_bar.focused is False
    assert runtime.menu_bar.dropdown_open is False


def test_alt_tap_focuses_bar_and_wakes_overlay() -> None:
    runtime = _make_runtime()
    dispatch_keydown(
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LALT),
        runtime,
    )
    assert runtime.menu_bar.focused is False
    dispatch_keyup(
        pygame.event.Event(pygame.KEYUP, key=pygame.K_LALT),
        runtime,
    )
    assert runtime.menu_bar.focused is True
    assert runtime.overlay.visibility == 1.0


def test_alt_then_another_key_does_not_focus_bar() -> None:
    runtime = _make_runtime()
    dispatch_keydown(
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LALT),
        runtime,
    )
    assert dispatch_keydown(keydown(pygame.K_a), runtime) is True
    dispatch_keyup(
        pygame.event.Event(pygame.KEYUP, key=pygame.K_LALT),
        runtime,
    )
    assert runtime.menu_bar.focused is False


def test_focus_loss_cancels_alt_tap() -> None:
    runtime = _make_runtime()
    dispatch_keydown(
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LALT),
        runtime,
    )
    dispatch_window_event(
        pygame.event.Event(pygame.WINDOWFOCUSLOST),
        runtime,
    )
    dispatch_keyup(
        pygame.event.Event(pygame.KEYUP, key=pygame.K_LALT),
        runtime,
    )
    assert runtime.menu_bar.focused is False


def test_ctrl_r_runs_render_bare_r_stays_on_timeline() -> None:
    runtime = _make_runtime()
    runtime.seed.session.timeline.armed_slots = {"layer_1"}
    assert dispatch_keydown(
        keydown(pygame.K_r, mod=pygame.KMOD_CTRL),
        runtime,
    ) is True
    modal_view = runtime.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.YES_NO
    assert runtime.seed.session.timeline.recording is False

    runtime = _make_runtime()
    runtime.seed.session.timeline.armed_slots = {"layer_1"}
    assert dispatch_keydown(keydown(pygame.K_r), runtime) is True
    assert runtime.seed.session.timeline.recording is True
    assert runtime.modal_host.view_state() is None


def test_other_key_while_bar_focused_passes_through() -> None:
    runtime = _make_runtime()
    runtime.seed.session.timeline.armed_slots = {"layer_1"}
    assert dispatch_keydown(keydown(pygame.K_F10), runtime) is True
    assert runtime.menu_bar.focused is True
    assert dispatch_keydown(keydown(pygame.K_r), runtime) is True
    assert runtime.menu_bar.focused is False
    assert runtime.seed.session.timeline.recording is True


def test_menu_opens_in_curation_mode() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False)
    runtime.seed.session.settings.editor_mode = "preset_curation"
    runtime.controls.clear_config_dirty()
    before = runtime.controls.focus_cursor
    assert dispatch_keydown(keydown(pygame.K_F10), runtime) is True
    assert dispatch_keydown(keydown(pygame.K_DOWN), runtime) is True
    assert runtime.menu_bar.focused is True
    assert runtime.menu_bar.dropdown_open is True
    assert runtime.controls.focus_cursor == before
    assert (
        dispatch_keydown(keydown(pygame.K_q, mod=pygame.KMOD_CTRL), runtime)
        is False
    )


def test_tab_cycle_when_strip_open() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=True)
    controls = runtime.controls
    controls.shell_focus.region = ShellRegion.NAVIGATOR
    assert dispatch_keydown(keydown(pygame.K_TAB), runtime) is True
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    assert runtime.menu_bar.focused is False
    assert dispatch_keydown(keydown(pygame.K_TAB), runtime) is True
    assert isinstance(controls.focus_cursor, TimelineFocus)
    assert dispatch_keydown(keydown(pygame.K_TAB), runtime) is True
    assert runtime.menu_bar.focused is True
    assert dispatch_keydown(keydown(pygame.K_TAB), runtime) is True
    assert runtime.menu_bar.focused is False
    assert controls.shell_focus.region is ShellRegion.NAVIGATOR
    assert not isinstance(controls.focus_cursor, TimelineFocus)


def test_navigator_esc_hides_overlay() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False)
    controls = runtime.controls
    controls.shell_focus.region = ShellRegion.NAVIGATOR
    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert controls.consume_hide_overlay() is True
    assert controls.shell_focus.region is ShellRegion.NAVIGATOR


def test_navigator_esc_hides_overlay_in_preset_curation() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False)
    runtime.seed.session.settings.editor_mode = "preset_curation"
    controls = runtime.controls
    controls.shell_focus.region = ShellRegion.NAVIGATOR
    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert controls.consume_hide_overlay() is True
    assert controls.shell_focus.region is ShellRegion.NAVIGATOR


def test_inspector_esc_returns_to_navigator() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False)
    controls = runtime.controls
    controls.shell_focus.region = ShellRegion.INSPECTOR
    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert controls.shell_focus.region is ShellRegion.NAVIGATOR
    assert controls.consume_hide_overlay() is False


def test_tab_cycle_skips_timeline_when_strip_closed() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False)
    controls = runtime.controls
    controls.shell_focus.region = ShellRegion.INSPECTOR
    assert dispatch_keydown(keydown(pygame.K_TAB), runtime) is True
    assert runtime.menu_bar.focused is True
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert dispatch_keydown(keydown(pygame.K_TAB, mod=pygame.KMOD_SHIFT), runtime) is True
    assert runtime.menu_bar.focused is False
    assert controls.shell_focus.region is ShellRegion.INSPECTOR


def test_ctrl_up_down_cycles_visible_top_level_ids() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False)
    controls = runtime.controls
    ids = visible_top_level_ids(controls.session)
    assert list(ids) == ["settings", "project", "render", "layers", "song_markers"]
    seen = [controls.shell_focus.selected_id]
    leftover = controls.focus_cursor
    for _ in ids:
        assert (
            dispatch_keydown(keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL), runtime)
            is True
        )
        seen.append(controls.shell_focus.selected_id)
        assert controls.shell_focus.region is ShellRegion.NAVIGATOR
        if controls.shell_focus.selected_id == "render":
            assert controls.focus_cursor == leftover
        leftover = controls.focus_cursor
    assert seen == [*ids, ids[0]]
    assert dispatch_keydown(keydown(pygame.K_UP, mod=pygame.KMOD_CTRL), runtime) is True
    assert controls.shell_focus.selected_id == ids[-1]


def test_ctrl_up_down_do_nothing_while_menu_focused() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False)
    controls = runtime.controls
    assert dispatch_keydown(keydown(pygame.K_F10), runtime) is True
    assert runtime.menu_bar.focused is True
    selected = controls.shell_focus.selected_id
    region = controls.shell_focus.region
    focus = controls.focus_cursor
    assert dispatch_keydown(keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL), runtime) is True
    assert runtime.menu_bar.focused is True
    assert runtime.menu_bar.dropdown_open is False
    assert runtime.menu_bar.menu_index == 0
    assert controls.shell_focus.selected_id == selected
    assert controls.shell_focus.region is region
    assert controls.focus_cursor == focus
    assert dispatch_keydown(keydown(pygame.K_UP, mod=pygame.KMOD_CTRL), runtime) is True
    assert runtime.menu_bar.focused is True
    assert controls.shell_focus.selected_id == selected


def test_keyup_while_text_editing_disarms_modal_repeat() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False)
    runtime.modal_host.prompt_text(
        "Change text...",
        "hello",
        on_confirm=lambda _s: None,
    )
    assert dispatch_keydown(keydown(pygame.K_BACKSPACE), runtime) is True
    assert runtime.modal_host.text_key_repeat_armed is True
    dispatch_keyup(
        pygame.event.Event(pygame.KEYUP, key=pygame.K_BACKSPACE),
        runtime,
    )
    assert runtime.modal_host.text_key_repeat_armed is False
    assert runtime.controls.key_repeat_armed is False


def test_ctrl_l_adds_during_timeline_scope_digits_do_not_jump() -> None:
    runtime = _make_runtime(submenu_focused=True, panel_open=True)
    controls = runtime.controls
    controls.shell_focus.selected_id = "settings"
    controls.layer_lifecycle.can_add = lambda: True
    controls.layer_lifecycle.prompt_add = MagicMock()
    assert dispatch_keydown(keydown(pygame.K_l, mod=pygame.KMOD_CTRL), runtime) is True
    controls.layer_lifecycle.prompt_add.assert_called_once_with()
    assert controls.shell_focus.selected_id == "settings"

    assert dispatch_keydown(keydown(pygame.K_1), runtime) is True
    assert controls.shell_focus.selected_id == "settings"

    closed = _make_runtime(submenu_focused=False, panel_open=False, recording=True)
    closed.controls.shell_focus.selected_id = "settings"
    assert dispatch_keydown(keydown(pygame.K_1), closed) is True
    assert closed.controls.shell_focus.selected_id == "settings"


def test_inspector_arrows_step_value_while_strip_is_open() -> None:
    runtime = _make_runtime(submenu_focused=True, panel_open=True)
    session = runtime.seed.session
    session.timeline.lanes["layer_1"] = TimelineLane(
        baseline=None,
        cues=[SlotCue(4.0, 1.0), SlotCue(10.0, 0.0)],
    )
    session.timeline.selected_cue_t["layer_1"] = 4.0
    session.layers["layer_1"].opacity_pct = 50
    controls = runtime.controls
    controls.shell_focus.selected_id = layer_node_id("layer_1")
    controls.inspector.focus_row(
        InspectorRow(
            descriptor=RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1"),
            is_group=False,
            depth=1,
            navigable=True,
        )
    )
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    assert isinstance(controls.focus_cursor, MainFocus)
    assert session.timeline.panel_open is True
    assert session.timeline.focus_row == 0
    cues = dict(session.timeline.selected_cue_t)
    assert dispatch_keydown(keydown(pygame.K_RIGHT), runtime) is True
    assert session.layers["layer_1"].opacity_pct == 51
    assert session.timeline.selected_cue_t == cues

    assert dispatch_keydown(keydown(pygame.K_TAB), runtime) is True
    assert controls.shell_focus.region is ShellRegion.TIMELINE
    assert controls.focus_cursor == TimelineFocus(0)
    assert dispatch_keydown(keydown(pygame.K_RIGHT), runtime) is True
    assert session.timeline.selected_cue_t["layer_1"] == 10.0
    assert session.layers["layer_1"].opacity_pct == 51


def test_layer_digits_jump_from_inspector_while_strip_is_open() -> None:
    runtime = _make_runtime(submenu_focused=True, panel_open=True)
    controls = runtime.controls
    controls.set_shell_region(ShellRegion.INSPECTOR)
    controls.shell_focus.selected_id = "settings"
    assert runtime.seed.session.timeline.panel_open is True
    assert dispatch_keydown(keydown(pygame.K_2), runtime) is True
    assert controls.shell_focus.selected_id == layer_node_id("layer_2")
    assert controls.shell_focus.region is ShellRegion.INSPECTOR

    controls.set_shell_region(ShellRegion.TIMELINE)
    assert dispatch_keydown(keydown(pygame.K_1), runtime) is True
    assert controls.shell_focus.selected_id == layer_node_id("layer_2")
    assert controls.shell_focus.region is ShellRegion.TIMELINE


def test_tab_cycle_includes_help_when_open() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=True, help_visible=True)
    controls = runtime.controls
    controls.shell_focus.region = ShellRegion.NAVIGATOR
    assert dispatch_keydown(keydown(pygame.K_TAB), runtime) is True
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    assert dispatch_keydown(keydown(pygame.K_TAB), runtime) is True
    assert controls.shell_focus.region is ShellRegion.HELP
    assert controls.shell_focus.help_subject is CycleStop.INSPECTOR
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert runtime.menu_bar.focused is False
    assert dispatch_keydown(keydown(pygame.K_TAB), runtime) is True
    assert controls.shell_focus.region is ShellRegion.TIMELINE
    assert isinstance(controls.focus_cursor, TimelineFocus)
    assert dispatch_keydown(keydown(pygame.K_TAB), runtime) is True
    assert runtime.menu_bar.focused is True
    assert dispatch_keydown(keydown(pygame.K_TAB), runtime) is True
    assert runtime.menu_bar.focused is False
    assert controls.shell_focus.region is ShellRegion.NAVIGATOR


def test_tab_cycle_help_open_skips_closed_strip() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False, help_visible=True)
    controls = runtime.controls
    controls.shell_focus.region = ShellRegion.INSPECTOR
    assert dispatch_keydown(keydown(pygame.K_TAB), runtime) is True
    assert controls.shell_focus.region is ShellRegion.HELP
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert dispatch_keydown(keydown(pygame.K_TAB), runtime) is True
    assert runtime.menu_bar.focused is True
    assert dispatch_keydown(keydown(pygame.K_TAB, mod=pygame.KMOD_SHIFT), runtime) is True
    assert controls.shell_focus.region is ShellRegion.HELP
    assert runtime.menu_bar.focused is False


def test_help_keys_do_not_edit_inspector_or_timeline() -> None:
    runtime = _make_runtime(submenu_focused=True, panel_open=True, help_visible=True)
    session = runtime.seed.session
    session.timeline.lanes["layer_1"] = TimelineLane(
        baseline=None,
        cues=[SlotCue(4.0, 1.0), SlotCue(10.0, 0.0)],
    )
    session.timeline.selected_cue_t["layer_1"] = 4.0
    session.layers["layer_1"].opacity_pct = 50
    session.layers["layer_1"].enabled = True
    controls = runtime.controls
    controls.shell_focus.selected_id = layer_node_id("layer_1")
    controls.inspector.focus_row(
        InspectorRow(
            descriptor=RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1"),
            is_group=False,
            depth=1,
            navigable=True,
        )
    )
    controls.set_shell_region(ShellRegion.HELP)
    assert controls.shell_focus.help_subject is CycleStop.INSPECTOR
    assert controls.shell_focus.region is ShellRegion.HELP
    focus_row = session.timeline.focus_row
    cursor = controls.shell_focus.inspector_cursor
    runtime.shell_host = SimpleNamespace(scroll_help=MagicMock())
    assert dispatch_keydown(keydown(pygame.K_RIGHT), runtime) is True
    assert dispatch_keydown(keydown(pygame.K_LEFT), runtime) is True
    assert session.layers["layer_1"].opacity_pct == 50
    assert session.timeline.selected_cue_t["layer_1"] == 4.0
    assert dispatch_keydown(keydown(pygame.K_DOWN), runtime) is True
    assert dispatch_keydown(keydown(pygame.K_UP), runtime) is True
    assert controls.shell_focus.inspector_cursor == cursor
    assert session.timeline.focus_row == focus_row
    assert controls.shell_focus.region is ShellRegion.HELP
    runtime.shell_host.scroll_help.assert_any_call(HELP_SCROLL_LINE_PX)
    runtime.shell_host.scroll_help.assert_any_call(-HELP_SCROLL_LINE_PX)
    assert dispatch_keydown(keydown(pygame.K_PAGEDOWN), runtime) is True
    runtime.shell_host.scroll_help.assert_any_call(HELP_SCROLL_PAGE_PX)
    assert dispatch_keydown(keydown(pygame.K_e), runtime) is True
    assert dispatch_keydown(keydown(pygame.K_DELETE), runtime) is True
    assert session.layers["layer_1"].enabled is True
    assert "layer_1" in session.layers
    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert session.help_visible is False
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    assert controls.consume_hide_overlay() is False


def test_h_toggle_does_not_move_region_until_help_is_focused() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False, help_visible=False)
    controls = runtime.controls
    controls.set_shell_region(ShellRegion.INSPECTOR)
    assert dispatch_keydown(keydown(pygame.K_h), runtime) is True
    assert runtime.seed.session.help_visible is True
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    assert dispatch_keydown(keydown(pygame.K_h), runtime) is True
    assert runtime.seed.session.help_visible is False
    assert controls.shell_focus.region is ShellRegion.INSPECTOR


def test_h_while_help_focused_restores_subject() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=True, help_visible=True)
    controls = runtime.controls
    controls.set_shell_region(ShellRegion.TIMELINE)
    stored = controls.session.timeline.focus_row
    controls.set_shell_region(ShellRegion.HELP)
    assert controls.shell_focus.help_subject is CycleStop.TIMELINE
    assert not isinstance(controls.focus_cursor, TimelineFocus)
    assert dispatch_keydown(keydown(pygame.K_h), runtime) is True
    assert runtime.seed.session.help_visible is False
    assert controls.shell_focus.region is ShellRegion.TIMELINE
    assert controls.focus_cursor == TimelineFocus(stored)


def test_esc_from_help_falls_back_when_timeline_subject_strip_is_closed() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=True, help_visible=True)
    controls = runtime.controls
    controls.set_shell_region(ShellRegion.TIMELINE)
    controls.set_shell_region(ShellRegion.HELP)
    controls.session.timeline.panel_open = False
    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert runtime.seed.session.help_visible is False
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    assert not isinstance(controls.focus_cursor, TimelineFocus)


def test_esc_from_help_restores_menu_subject() -> None:
    runtime = _make_runtime(submenu_focused=False, panel_open=False, help_visible=True)
    controls = runtime.controls
    controls.set_shell_region(ShellRegion.INSPECTOR)
    runtime.menu_bar.focus()
    controls.set_shell_region(ShellRegion.HELP, menu_focused=True)
    assert controls.shell_focus.help_subject is CycleStop.MENU
    runtime.menu_bar.blur()
    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert runtime.seed.session.help_visible is False
    assert runtime.menu_bar.focused is True
    assert controls.shell_focus.region is ShellRegion.NAVIGATOR
    assert controls.consume_hide_overlay() is False


def test_ctrl_down_from_timeline_moves_to_navigator() -> None:
    runtime = _make_runtime(submenu_focused=True, panel_open=True)
    controls = runtime.controls
    controls.shell_focus.selected_id = "settings"
    assert dispatch_keydown(keydown(pygame.K_DOWN, mod=pygame.KMOD_CTRL), runtime) is True
    assert controls.shell_focus.region is ShellRegion.NAVIGATOR
    assert isinstance(controls.focus_cursor, MainFocus)
    assert controls.shell_focus.selected_id == "project"
    assert runtime.seed.session.timeline.panel_open is True
    assert runtime.seed.session.timeline.focus_row == 0