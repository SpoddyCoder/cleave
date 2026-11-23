"""Editor controller: session, focus, and input routing to the feature controllers."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from cleave.config import CleaveConfig
from cleave.signals import Signals
from cleave.preset_library import PresetLibrary
from cleave.preset_list_entry import PresetListEntry
from cleave.viz.clip_presets import (
    ClipPresetPicker,
    clip_preset_view,
    is_each_clip,
    seed_timeline,
    sync_each_clip_layers,
    timeline_is_empty,
)
from cleave.viz.preset_schedule import each_clip_change, enter_each_clip
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.layer_lifecycle_controls import LayerLifecycleController
from cleave.viz.layer_mutations import LayerMutations
from cleave.viz.layer_problems import layer_issues
from cleave.viz.preset_clipboard import PresetClipboard, PresetEditTarget
from cleave.viz.preset_browser_controls import PresetBrowserControls
from cleave.viz.editor_mode_controls import (
    EditorModeController,
    curation_focus_slot,
    is_preset_curation_mode,
)
from cleave.viz.post_fx import sync_live_compositor_format
from cleave.viz.preset_curation_controls import PresetCurationController
from cleave.viz.preset_list_controls import PresetListController
from cleave.viz.preset_switching import layer_notification, panel_layer_number
from cleave.viz.preset_rescan_controls import PresetRescanController
from cleave.viz.key_repeat import KeyRepeatController
from cleave.viz.value_nudge import ValueNudgeHold
from cleave.viz.context_menu import ContextMenuState
from cleave.viz.inline_edit import InlineEditController
from cleave.viz.modal import ModalHost
from cleave.viz.panel_notification import (
    PanelNotificationActive,
    PanelNotificationHost,
)
from cleave.viz.playback import PlaybackState, current_sec, seek, seek_to
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.overlay_controls import OverlaysControls
from cleave.viz.pattern_mask_controls import PatternMaskControls
from cleave.viz.post_fx_bindings import PostFxBindings
from cleave.viz.post_fx_controls import PostFxControls
from cleave.viz.settings_controls import SettingsControls
from cleave.viz.theme_file_controls import ThemeFileControls
from cleave.viz.project_controls import ProjectControls
from cleave.viz.project_render_controls import ProjectRenderController
from cleave.viz.project_switch import ProjectSwitchController
from cleave.viz.song_marker_controls import SongMarkerController
from cleave.viz.av_sync_controls import AvSyncControls
from cleave.viz.calibration_clicks import CalibrationClicks, CalibrationUiSnapshot
from cleave.viz.latency_setup_controls import LatencySetupFlow
from cleave.viz.tap_sync_controls import TapSyncControls
from cleave.viz.transport_controls import TransportControls, hold_paused
from cleave.viz.welcome_host import CANCEL_LABEL, WelcomeFlow
from cleave.viz.window_controls import WindowControls
from cleave.viz.timeline_phase_controls import TimelinePhaseController
from cleave.viz.edit_history import (
    TIMELINE_SCOPE,
    EditHistory,
    EditScope,
    preset_list_scope_slot,
)
from cleave.viz.timeline_clip_edits import ClipEditor
from cleave.viz.timeline_preset_controls import TimelinePresetController
from cleave.viz.timeline_cut_controls import TimelineCutController
from cleave.viz.timeline_snap_controls import TimelineSnapController
from cleave.viz.focus_nav import (
    FocusCursor,
    MainFocus,
    TimelineFocus,
    cursor_main_descriptor,
)
from cleave.viz.inspector_controls import InspectorControls
from cleave.viz.navigator import (
    build_navigator,
    issue_target,
    initial_expanded_ids,
    layer_node_id,
    timeline_row_node_id,
    timeline_row_slot_of,
)
from cleave.viz.navigator_controls import NavigatorControls
from cleave.viz.page_history import PageHistory
from cleave.viz.shell_focus import (
    ShellFocusState,
    ShellRegion,
    reconcile_nav_id,
)
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import section_lock_blocks_mutation
from cleave.viz.session import TuningSession
from cleave.viz.tuning_view_state import TuningViewState, TuningViewStateBuilder
from cleave.viz.visualiser_resolution import VisualiserResolutionSync
from cleave.viz.still_capture import StillCaptureController

if TYPE_CHECKING:
    from cleave.gl_compositor import GlCompositor
    from cleave.gl_masked_compositor import GlMaskedCompositor
    from cleave.gl_post_process import GlPostProcess
    from cleave.viz.wiring import LayerManager

NOTIFICATION_TIMELINE_ENABLED_TEXT = "Timeline controls layer visibility"
NOTIFICATION_TIMELINE_DISABLED_TEXT = "Layer panel controls visibility"


def _layer_numbers(session: TuningSession, slots: Sequence[str]) -> str:
    numbers = [str(panel_layer_number(session.layer_z_order, slot)) for slot in slots]
    if len(numbers) == 1:
        return f"Layer {numbers[0]}"
    return f"Layers {', '.join(numbers[:-1])} and {numbers[-1]}"


def timeline_enabled_notification(
    session: TuningSession, enabled: bool
) -> str:
    """What turning the timeline on or off did, in a toast."""
    if enabled:
        return NOTIFICATION_TIMELINE_ENABLED_TEXT
    holding = [
        slot for slot in session.layer_z_order if is_each_clip(session, slot)
    ]
    if holding:
        verb = "holds its" if len(holding) == 1 else "hold their"
        return (
            f"{NOTIFICATION_TIMELINE_DISABLED_TEXT}. "
            f"{_layer_numbers(session, holding)} {verb} current preset "
            "until the timeline is back on"
        )
    return NOTIFICATION_TIMELINE_DISABLED_TEXT
LATENCY_PAGE_ID = "settings.latency"
NOTIFICATION_TAP_LATENCY_UNCHANGED_TEXT = (
    "Existing marker and clip times unchanged"
)
SEEK_TINY = 2
SEEK_SHORT = 10
SEEK_LONG = 30


class TuningControls:
    """Editor controller: owns the session and focus, and routes input to the ``*_controls`` feature controllers."""

    def __init__(
        self,
        session: TuningSession,
        cfg: CleaveConfig,
        preset_root: Path,
        playback: PlaybackState,
        duration_sec: float,
        *,
        project_dir: Path | None = None,
        layer_bindings: LiveLayerBindings | None = None,
        post_fx_bindings: PostFxBindings | None = None,
        on_save_config: Callable[[Path], str | None] | None = None,
        launch_config_path: Path | None = None,
        modal_host: ModalHost | None = None,
        layer_manager: LayerManager | None = None,
        compositor: GlCompositor | None = None,
        post_process: GlPostProcess | None = None,
        masked_compositor: GlMaskedCompositor | None = None,
        beat_times: Sequence[float] = (),
        bar_times: Sequence[float] = (),
        signals: Signals | None = None,
        library: PresetLibrary | None = None,
    ) -> None:
        self.session = session
        self.cfg = cfg
        self.preset_root = preset_root
        self.library = library if library is not None else PresetLibrary.in_memory()
        self.project_dir = project_dir
        self.playback = playback
        self.duration_sec = duration_sec
        self._layer_bindings = layer_bindings
        self._post_fx_bindings = post_fx_bindings
        self._compositor = compositor
        self._post_process = post_process
        self._masked_compositor = masked_compositor
        self._modal_host = modal_host if modal_host is not None else ModalHost()
        self.inline_edit = InlineEditController(
            self._modal_host.start_text_input,
            self._modal_host.stop_text_input,
        )

        self.context_menu = ContextMenuState()
        self.shell_focus = ShellFocusState(
            nav_expanded=set(initial_expanded_ids(session))
        )
        self.page_history = PageHistory()
        self._focus_cursor: FocusCursor = MainFocus(
            RowDescriptor(RowKind.TIMELINE_HEADER)
        )
        self._notification_host = PanelNotificationHost()
        self._key_repeat = KeyRepeatController()
        self.value_nudge = ValueNudgeHold(self)
        self.window = WindowControls()
        self.transport = TransportControls(
            playback,
            duration_sec,
            bar_times,
            self.inline_edit,
            self.seek_to,
        )
        self.layer_lifecycle = LayerLifecycleController(
            session,
            layer_manager,
            self._modal_host,
            layer_bindings,
            on_rebuild_view=self._rebuild_view,
            on_notification=self.show_notification,
            on_focus_after_add=self._focus_added_layer,
            on_focus_after_delete=self._focus_deleted_layer,
        )
        self.song_markers = SongMarkerController(
            session,
            self._modal_host,
            beat_times,
            bar_times,
            playback,
            duration_sec,
            on_notification=lambda message: self.show_notification(message),
            on_focus_marker=self._focus_song_marker,
        )
        self._config_save = ConfigSaveController(
            session,
            cfg,
            self._modal_host,
            project_dir=project_dir,
            launch_config_path=launch_config_path,
            on_save_config=on_save_config,
            on_notification=self.show_notification,
            move_mode_signature=self.layer_lifecycle.signature_payload,
        )
        self.project_switch = ProjectSwitchController(
            self._config_save,
            self._modal_host,
        )
        layers_by_slot = (
            layer_manager.layers_by_slot if layer_manager is not None else {}
        )
        self._clip_preset_pick = ClipPresetPicker(session, project_dir, self.library)
        self.edit_history = EditHistory(
            session,
            on_preset_list_change=lambda slot: self.preset_list.refresh_switching(slot),
            scope_locked=self._edit_scope_locked,
            before_commit=self._sync_each_clip_layers,
        )
        self.preset_list = PresetListController(
            session,
            preset_root,
            project_dir,
            duration_sec,
            self._modal_host,
            layer_bindings,
            on_notification=self.show_notification,
            history=self.edit_history,
            on_focus_preset_item=self._focus_preset_list_item,
            on_move_preset_selection=self._move_preset_list_selection,
            layers_by_slot=layers_by_slot,
            catalog=self.library,
        )
        self._preset_curation = PresetCurationController(
            session,
            self._modal_host,
            layer_bindings,
            self.library,
            on_notification=self.show_notification,
        )
        self.clip_editor = ClipEditor(
            session,
            self.edit_history,
            duration_sec=duration_sec,
            beat_times=beat_times,
            bar_times=bar_times,
            pick_preset=self._clip_preset_pick,
        )
        self._timeline_presets = TimelinePresetController(
            session,
            self._modal_host,
            beat_times,
            bar_times,
            signals=signals,
            on_notification=self.show_notification,
            on_repopulate=self.preset_list.repopulate,
            has_role_presets=self.preset_list.has_role_presets,
            history=self.edit_history,
        )
        self.timeline_phase = TimelinePhaseController(
            session,
            beat_times,
            on_notification=self.show_notification,
        )
        self._timeline_snap = TimelineSnapController(
            session,
            self._modal_host,
            beat_times,
            bar_times,
            on_notification=self.show_notification,
            history=self.edit_history,
        )
        self._timeline_cuts = TimelineCutController(
            session,
            self._modal_host,
            on_notification=self.show_notification,
            history=self.edit_history,
        )
        self._view_state = TuningViewStateBuilder(
            session,
            playback,
            duration_sec,
            preset_root,
            self.library,
            get_focus_cursor=lambda: self.focus_cursor,
            get_move_mode_slot=lambda: self.layer_lifecycle.move_mode_slot,
            get_move_mode_preset=lambda: self.preset_list.move_mode_preset,
            config_save=self._config_save,
            get_notification=self._notification_host.active,
            layers_by_slot=layers_by_slot,
        )
        self.overlays = OverlaysControls(session)
        self.post_fx = PostFxControls(
            session, bindings=post_fx_bindings
        )
        self.pattern_mask = PatternMaskControls(session)
        self.settings = SettingsControls(
            session,
            cfg,
            on_notification=self.show_notification,
            on_notification_display_changed=self._notification_host.set_display_sec,
        )
        self.theme_files = ThemeFileControls(
            cfg,
            self._modal_host,
            on_notification=self.show_notification,
        )
        self.project = ProjectControls(
            session,
            on_compositor_format_changed=self._sync_live_compositor_format,
        )
        self.visualiser_resolution = VisualiserResolutionSync(
            session,
            cfg,
            on_apply=lambda size: self.layer_lifecycle.apply_visualiser_resolution(
                size
            ),
        )
        self.still_capture = StillCaptureController(
            self._modal_host,
            project_dir=project_dir,
            project_slug=cfg.project_slug,
            playhead_sec=lambda: current_sec(self.playback, self.duration_sec),
            on_notification=self.show_notification,
        )
        self.project_render = ProjectRenderController(
            session,
            cfg,
            self._modal_host,
            duration_sec=duration_sec,
            playback=playback,
            project_dir=project_dir,
        )
        self.welcome = WelcomeFlow(self._modal_host)
        self.preset_rescan = PresetRescanController(
            self.library,
            preset_root,
            self._modal_host,
            hold_playback=lambda: hold_paused(self.playback, self.transport.toggle_pause),
            on_notification=self.show_notification,
        )
        self.layer_mutations = LayerMutations(
            session,
            preset_root=preset_root,
            duration_sec=duration_sec,
            get_layer_bindings=lambda: self._layer_bindings,
            on_notification=lambda message: self.show_notification(message),
            history=self.edit_history,
            on_enter_each_clip=self._enter_each_clip,
            confirm_each_clip=self._confirm_each_clip,
        )
        self.preset_browser = PresetBrowserControls(
            session,
            preset_root,
            self.library,
            self.layer_mutations,
            preset_list=self.preset_list,
            start_text_input=self._modal_host.start_text_input,
            stop_text_input=self._modal_host.stop_text_input,
            text_input_shared=lambda: (
                self._modal_host.active or self.inline_edit.text_target is not None
            ),
        )
        self.preset_clipboard = PresetClipboard(
            self.preset_list,
            self.layer_mutations,
            on_notification=self.show_notification,
        )
        calibration_clicks = CalibrationClicks(
            playback,
            duration_sec,
            on_ui_begin=self._begin_calibration_ui,
            on_ui_restore=self._restore_calibration_ui,
            on_seek=self.seek_to,
        )
        self._tap_sync = TapSyncControls(
            cfg,
            calibration_clicks,
            self._modal_host,
            on_notification=self.show_notification,
            on_apply_tap_latency=self._apply_measured_tap_latency,
        )
        self._av_sync = AvSyncControls(
            cfg,
            calibration_clicks,
            self._modal_host,
            on_notification=self.show_notification,
            on_preview_audio_latency=self._preview_audio_latency,
            on_apply_audio_latency=self._apply_measured_audio_latency,
        )
        self.latency_setup = LatencySetupFlow(
            self._modal_host,
            measure_audio_latency=lambda done: self._av_sync.prompt_start(
                on_close=done
            ),
            calibrate_tap_timing=lambda done: self._tap_sync.prompt_start(
                on_close=done
            ),
            busy=lambda: self.calibrating or self.welcome.active,
            hold_playback=lambda: hold_paused(
                self.playback, self.transport.toggle_pause
            ),
        )
        self._apply_latency()
        self.editor_mode = EditorModeController(
            session,
            cfg,
            self._config_save,
            self._modal_host,
            project_dir=project_dir,
            layer_bindings=layer_bindings,
            layer_manager=layer_manager,
            catalog=self.library,
            on_mode_changed=self._on_editor_mode_changed,
            on_notification=self.show_notification,
        )
        if session.timeline.enabled:
            self.show_notification(NOTIFICATION_TIMELINE_ENABLED_TEXT)
        self.navigator = NavigatorControls(self)
        self.inspector = InspectorControls(self)

    @property
    def tap_sync(self) -> TapSyncControls:
        return self._tap_sync

    @property
    def av_sync(self) -> AvSyncControls:
        return self._av_sync

    @property
    def calibrating(self) -> bool:
        """True while either latency calibration has the preview."""
        return self._tap_sync.active or self._av_sync.active

    @property
    def preset_curation(self) -> PresetCurationController:
        return self._preset_curation

    def _begin_calibration_ui(self) -> CalibrationUiSnapshot:
        snapshot = CalibrationUiSnapshot(
            help_visible=self.session.help_visible,
            timeline_panel_open=self.session.timeline.panel_open,
            focus_cursor=self.focus_cursor,
            shell_region=self.shell_focus.region,
        )
        self.close_help()
        if self.session.timeline.panel_open:
            self.session.timeline.panel_open = False
        if (
            self.shell_focus.region is ShellRegion.TIMELINE
            or isinstance(self.focus_cursor, TimelineFocus)
        ):
            self.exit_timeline_submenu()
        return snapshot

    def _restore_calibration_ui(self, snapshot: CalibrationUiSnapshot) -> None:
        self.session.help_visible = snapshot.help_visible
        self.session.timeline.panel_open = snapshot.timeline_panel_open
        if (
            snapshot.shell_region is ShellRegion.TIMELINE
            and snapshot.timeline_panel_open
        ):
            if isinstance(snapshot.focus_cursor, TimelineFocus):
                self.session.timeline.focus_row = snapshot.focus_cursor.row
            self.set_shell_region(ShellRegion.TIMELINE)
        else:
            self._apply_focus_cursor(snapshot.focus_cursor)
            # Exact snapshot: a saved strip cursor outside Timeline stays put.
            self.shell_focus.region = snapshot.shell_region

    def _apply_latency(self) -> None:
        editor = self.cfg.editor
        player = self.playback.player
        player.set_audio_latency_sec(editor.audio_latency_ms / 1000.0)
        player.set_tap_latency_sec(editor.tap_latency_ms / 1000.0)

    def _preview_audio_latency(self, latency_ms: int) -> None:
        """Try a draft audio latency on the player without saving it."""
        self.playback.player.set_audio_latency_sec(latency_ms / 1000.0)

    def _apply_measured_audio_latency(self, latency_ms: int) -> None:
        self.settings.set_audio_latency_ms(latency_ms)
        self.on_audio_latency_changed()
        self._show_latency_row(RowKind.SETTINGS_AUDIO_LATENCY_MS)

    def _apply_measured_tap_latency(self, latency_ms: int) -> None:
        self.settings.set_tap_latency_ms(latency_ms)
        self.on_tap_latency_changed()
        self._show_latency_row(RowKind.SETTINGS_TAP_LATENCY_MS)

    def show_issue(self, slot: str, index: int = 0) -> None:
        """Open the page for the layer's issue at *index* (problems, then
        notices; 0 is the first), on its row."""
        items = layer_issues(self.session, slot).items()
        if not 0 <= index < len(items):
            return
        target = issue_target(self.session, slot, items[index])
        self.navigator.select(target.page_id)
        focus = self.shell_focus
        if target.row is None or focus.selected_id != target.page_id:
            return
        self._apply_focus_cursor(MainFocus(target.row))
        focus.inspector_cursor = target.row
        focus.inspector_command_id = None
        self.set_shell_region(ShellRegion.INSPECTOR)

    def _show_latency_row(self, kind: RowKind) -> None:
        """Open Settings > Latency with the measured value focused."""
        self.navigator.open_page(LATENCY_PAGE_ID)
        focus = self.shell_focus
        if focus.selected_id != LATENCY_PAGE_ID:
            return
        focus.inspector_cursor = RowDescriptor(kind)
        focus.inspector_command_id = None
        self.set_shell_region(ShellRegion.INSPECTOR)

    def on_audio_latency_changed(self) -> None:
        self._apply_latency()

    def on_tap_latency_changed(self) -> None:
        self._apply_latency()
        if self._project_has_markers_or_cues():
            self.show_notification(NOTIFICATION_TAP_LATENCY_UNCHANGED_TEXT)

    def _project_has_markers_or_cues(self) -> bool:
        if self.session.song_markers.times:
            return True
        for lane in self.session.timeline.lanes.values():
            if lane.cues:
                return True
        return False

    @property
    def _in_move_mode(self) -> bool:
        return (
            self.layer_lifecycle.move_mode_slot is not None
            or self.preset_list.move_mode_preset is not None
        )

    @property
    def config_dirty(self) -> bool:
        return self._config_save.config_dirty

    def clear_config_dirty(self) -> None:
        self._config_save.clear_config_dirty()

    @property
    def modal_host(self) -> ModalHost:
        return self._modal_host

    @property
    def modal_active(self) -> bool:
        return self._modal_host.active

    def handle_modal_keydown(self, event: pygame.event.Event) -> bool:
        """Return True when a modal dialog consumed the event."""
        return self._modal_host.handle_keydown(event)

    @property
    def pending_exit(self) -> bool:
        return self._config_save.pending_exit

    def consume_pending_exit(self) -> bool:
        return self._config_save.consume_pending_exit()

    def consume_pending_switch(self) -> bool:
        return self._config_save.consume_pending_switch()

    @property
    def config_save(self) -> ConfigSaveController:
        return self._config_save

    def try_quit(self) -> bool:
        if self.project_render.busy:
            self.project_render.abort()
        self.welcome.abort()
        self.preset_rescan.abort()
        return self._config_save.try_quit()

    def request_quit(self) -> None:
        """Quit from the menu.

        A clean project sets pending exit so the loop can leave through
        ``consume_pending_exit``. A dirty project only opens the unsaved
        prompt; that dialog sets the flag after save or discard.
        """
        if self.try_quit():
            self._config_save.mark_pending_exit()

    def prompt_welcome(self) -> None:
        """Open the Welcome to Cleave step for whatever is still missing.

        Playback pauses while the step is open and resumes when it closes.
        When a preset pack was downloaded, Rescan presets runs next.
        """
        from cleave.first_run import PRESET_PACK_IDS, first_run_items, needed_items

        if self.welcome.active:
            return
        resume = hold_paused(self.playback, self.transport.toggle_pause)

        def closed() -> None:
            resume()
            if PRESET_PACK_IDS & self.welcome.downloaded:
                self.preset_rescan.start()

        self.welcome.start(
            needed_items(first_run_items()),
            on_close=closed,
            cancel_label=CANCEL_LABEL,
        )

    def prompt_about(self) -> None:
        """Open the About Cleave notice."""
        from cleave.about import ABOUT_TITLE, about_body
        from cleave.viz.brand import Logo

        self._modal_host.prompt_notice(
            ABOUT_TITLE, body=about_body(), banner=Logo.FULL
        )

    def prompt_save_config(self) -> None:
        if self.session.solo_slot is not None:
            return
        self._config_save.save()

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Keys that no shell region claimed.

        Space pauses. Modals and tap-sync own their keys.
        Navigator, inspector, and the timeline strip handle their own arrows.
        """
        if event.type != pygame.KEYDOWN:
            return True

        if self.handle_modal_keydown(event):
            return True

        if (
            not is_preset_curation_mode(self.session.settings.editor_mode)
            and self._tap_sync.active
        ):
            return self._tap_sync.handle_keydown(event) or True

        if event.key == pygame.K_SPACE:
            self.transport.toggle_pause()
            return True

        return True

    def handle_keyup(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP:
            self._key_repeat.on_keyup(event.key)

    def arm_key_repeat(
        self,
        key: int,
        mod: int,
        *,
        on_repeat: Callable[[int, int], None],
        accel: bool = True,
    ) -> None:
        self.value_nudge.release()
        self._key_repeat.on_keydown(key, mod, on_repeat=on_repeat, accel=accel)

    def begin_value_nudge(
        self, desc: RowDescriptor, forward: bool, repeatable: bool
    ) -> None:
        """Capture a side-arrow hold and stop any key repeat."""
        self._key_repeat.disarm()
        self.value_nudge.press(desc, forward, repeatable)

    def disarm_value_nudge(self) -> None:
        self.value_nudge.release()

    @property
    def key_repeat_armed(self) -> bool:
        return self._key_repeat.is_armed

    @property
    def value_nudge_armed(self) -> bool:
        return self.value_nudge.armed

    def tick(self, dt_sec: float) -> None:
        if not pygame.mouse.get_pressed()[0] or self._modal_host.active:
            self.value_nudge.release()
        self._key_repeat.tick(dt_sec)
        self._config_save.tick()
        self.page_history.observe(self.shell_focus.selected_id, dt_sec)
        self.inline_edit.tick(dt_sec)
        self.project_switch.tick(dt_sec)
        if self.project_switch.active and self.preset_browser.active:
            self.preset_browser.cancel()
        self.preset_browser.tick(dt_sec)
        self.value_nudge.tick(dt_sec)
        self.visualiser_resolution.tick(dt_sec)
        self._notification_host.clear_expired()
        self.project_render.tick()
        self.welcome.tick()
        self.preset_rescan.tick()
        self.latency_setup.tick()

    def build_view_state(
        self,
        *,
        paused: bool,
        position_sec: float | None = None,
        fps: float | None = None,
    ) -> TuningViewState:
        return self._view_state.build(
            paused=paused, position_sec=position_sec, fps=fps
        )

    @property
    def focus_descriptor(self) -> RowDescriptor:
        return cursor_main_descriptor(self.focus_cursor)

    @focus_descriptor.setter
    def focus_descriptor(self, descriptor: RowDescriptor) -> None:
        self._apply_focus_cursor(MainFocus(descriptor))

    @property
    def focus_cursor(self) -> FocusCursor:
        return self._focus_cursor

    @focus_cursor.setter
    def focus_cursor(self, cursor: FocusCursor) -> None:
        self._apply_focus_cursor(cursor)

    def _apply_focus_cursor(self, cursor: FocusCursor) -> None:
        self._focus_cursor = cursor
        if isinstance(cursor, TimelineFocus):
            tl = self.session.timeline
            if cursor.row != tl.focus_row:
                # Drop in-progress clip flash so returning to a remembered
                # selection shows the settled tick, not a restart blink.
                tl.selected_clip_flash_start_ms = None
            tl.focus_row = cursor.row
            self._select_timeline_row_page(cursor.row)
            return
        if isinstance(cursor, MainFocus):
            self.song_markers.sync_focus(cursor.descriptor)

    def _select_timeline_row_page(self, row: int) -> None:
        """Show the strip row at *row* in the inspector, like a navigator row."""
        order = self.session.layer_z_order
        if not 0 <= row < len(order):
            return
        self.shell_focus.selected_id = timeline_row_node_id(order[row])

    def _leave_timeline_row_page(self) -> None:
        """Return a timeline row page to the Timeline page once the strip closes."""
        if timeline_row_slot_of(self.shell_focus.selected_id) is not None:
            self.shell_focus.selected_id = "timeline"

    def _on_editor_mode_changed(self) -> None:
        self._sync_live_compositor_format()
        self._view_state.invalidate_structure()
        if isinstance(self.focus_cursor, TimelineFocus):
            self.exit_timeline_submenu()
        self._normalize_focus_cursor()
        self._focus_curation_preset()

    def _focus_curation_preset(self) -> None:
        """Open the curation layer with its Preset row focused, ready to browse."""
        slot = curation_focus_slot(self.session)
        if slot is None:
            return
        self.navigator.select(layer_node_id(slot))
        if self.shell_focus.selected_id != layer_node_id(slot):
            return
        descriptor = RowDescriptor(RowKind.TRACK_PRESET, slot=slot)
        self.set_shell_region(ShellRegion.INSPECTOR)
        self._apply_focus_cursor(MainFocus(descriptor))
        self.shell_focus.inspector_cursor = descriptor
        self.shell_focus.inspector_command_id = None

    def _sync_live_compositor_format(self) -> None:
        if self._compositor is None or self._post_process is None:
            return
        sync_live_compositor_format(
            self.session.project.compositor_hdr,
            self.session.settings.editor_mode,
            self._compositor,
            self._post_process,
            masked_compositor=self._masked_compositor,
        )

    def _normalize_focus_cursor(self) -> None:
        row_count = len(self.session.layer_z_order)
        if isinstance(self.focus_cursor, TimelineFocus):
            if row_count == 0:
                self._apply_focus_cursor(TimelineFocus(0))
            elif self.focus_cursor.row >= row_count:
                self._apply_focus_cursor(TimelineFocus(row_count - 1))
            return
        tl = self.session.timeline
        if row_count <= 0:
            tl.focus_row = 0
        elif tl.focus_row >= row_count:
            tl.focus_row = row_count - 1

    def handle_move_mode_keydown(self, event: pygame.event.Event) -> bool:
        """Reorder keys while move mode is active. True when consumed."""
        if not self._in_move_mode:
            return False
        if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self._cancel_move_mode()
            return True
        if event.key == pygame.K_UP:
            self._nudge_move_mode(-1)
            return True
        if event.key == pygame.K_DOWN:
            self._nudge_move_mode(1)
            return True
        if event.key == pygame.K_m:
            self._confirm_move_mode()
            return True
        if event.key in (pygame.K_RETURN, pygame.K_l):
            return True
        return False

    def _nudge_move_mode(self, direction: int) -> None:
        if self.preset_list.move_mode_preset is not None:
            self.preset_list.swap_item(direction)
            return
        slot = self.layer_lifecycle.move_mode_slot
        if slot is not None:
            self.layer_lifecycle.swap_stem_in_z_order(slot, direction)

    def _confirm_move_mode(self) -> None:
        self.layer_lifecycle.confirm_move_mode()
        self.preset_list.confirm_move_mode()

    def _cancel_move_mode(self) -> None:
        self.layer_lifecycle.cancel_move_mode()
        self.preset_list.cancel_move_mode()

    def _rebuild_view(self) -> None:
        self._confirm_move_mode()
        self.navigator.reconcile()

    def _focus_layer_inspector(self, node_id: str) -> None:
        self.navigator.select(node_id)
        self.navigator.activate()

    def _focus_added_layer(self) -> None:
        order = self.session.layer_z_order
        if not order:
            return
        self._focus_layer_inspector(layer_node_id(order[-1]))

    def _focus_deleted_layer(self, slot: str, prior_index: int | None) -> None:
        self.shell_focus.nav_expanded.add("layers")
        visible = tuple(
            node.id
            for node in build_navigator(
                self.session, self.shell_focus.nav_expanded
            )
        )
        target = reconcile_nav_id(
            visible,
            layer_node_id(slot),
            self.session.layer_z_order,
            prior_index=prior_index,
        )
        self.navigator.select(target)
        self.navigator.activate()
        self._clamp_timeline_focus_row()

    def _clamp_timeline_focus_row(self) -> None:
        row_count = len(self.session.layer_z_order)
        if isinstance(self.focus_cursor, TimelineFocus):
            if row_count <= 0:
                self._apply_focus_cursor(TimelineFocus(0))
                return
            if self.focus_cursor.row >= row_count:
                self._apply_focus_cursor(TimelineFocus(row_count - 1))
            return
        timeline = self.session.timeline
        if row_count <= 0:
            timeline.focus_row = 0
        elif timeline.focus_row >= row_count:
            timeline.focus_row = row_count - 1

    def _move_preset_list_selection(self, slot: str, index: int) -> None:
        """Move a selection already on one of *slot*'s list entries to *index*.

        A selection on any other row or page stays put.
        """
        cursor = self.shell_focus.inspector_cursor
        if (
            cursor is not None
            and cursor.kind is RowKind.TRACK_PRESET_LIST_ITEM
            and cursor.slot == slot
        ):
            self._focus_preset_list_item(slot, index)

    def _focus_preset_list_item(self, slot: str, index: int) -> None:
        """Keep the inspector selection on a preset row as it moves."""
        descriptor = RowDescriptor(
            RowKind.TRACK_PRESET_LIST_ITEM,
            slot=slot,
            preset_index=index,
        )
        self._apply_focus_cursor(MainFocus(descriptor))
        focus = self.shell_focus
        focus.inspector_cursor = descriptor
        focus.inspector_command_id = None

    def select_song_marker(self, index: int) -> None:
        """Select song marker *index* and show it on the Song Markers page."""
        if not 0 <= index < len(self.session.song_markers.markers):
            return
        self.navigator.select("timeline.song_markers")
        if self.shell_focus.selected_id != "timeline.song_markers":
            return
        self.song_markers.select(index)
        self._focus_song_marker(index)

    def _focus_song_marker(self, marker_index: int | None) -> None:
        focus = self.shell_focus
        if focus.selected_id != "timeline.song_markers":
            return
        if marker_index is None:
            focus.inspector_cursor = None
            focus.inspector_command_id = "timeline.snap_to_markers"
        else:
            focus.inspector_cursor = RowDescriptor(
                RowKind.SONG_MARKER_ITEM,
                marker_index=marker_index,
            )
            focus.inspector_command_id = None
        self.set_shell_region(ShellRegion.INSPECTOR)

    def toggle_layer_locked(self, slot: str) -> None:
        layer = self.session.layers[slot]
        layer.locked = not layer.locked

    def toggle_overlay_locked(self) -> None:
        self.overlays.toggle_locked()

    def toggle_post_fx_locked(self) -> None:
        post_fx = self.session.post_fx
        post_fx.locked = not post_fx.locked

    def toggle_pattern_mask_locked(self) -> None:
        self.pattern_mask.toggle_locked()

    def toggle_timeline_locked(self) -> None:
        timeline = self.session.timeline
        if timeline.recording:
            return
        timeline.locked = not timeline.locked

    def set_timeline_enabled(self, enabled: bool) -> None:
        if self.session.timeline.enabled == enabled:
            return
        label = "Turn timeline on" if enabled else "Turn timeline off"
        with self.edit_history.recording(label):
            self._apply_timeline_enabled(enabled)
        self._after_timeline_enabled_change(enabled)

    def _apply_timeline_enabled(self, enabled: bool) -> None:
        """Switch the timeline; the first time it goes on, seed it."""
        self.session.timeline.enabled = enabled
        if enabled and timeline_is_empty(self.session):
            seed_timeline(self.session)

    def _after_timeline_enabled_change(self, enabled: bool) -> None:
        if enabled:
            self.open_timeline_panel()
        else:
            self.close_timeline_panel()
        if self._layer_bindings is not None:
            self._layer_bindings.on_timeline_enabled_change()
        self.show_notification(timeline_enabled_notification(self.session, enabled))

    def _enter_each_clip(self, slot: str, previous: str) -> None:
        """A layer's presets now change on each clip: give its clips presets.

        Runs inside the trigger change's undo step. The timeline comes on if
        it is off.
        """
        session = self.session
        if not session.timeline.enabled:
            self._apply_timeline_enabled(True)
            self._after_timeline_enabled_change(True)
        enter_each_clip(session, slot, previous, self.duration_sec)

    def _confirm_each_clip(self, slot: str, apply: Callable[[], None]) -> None:
        """Run ``apply`` to move the layer to each clip, asking first when it
        would change clips, presets, or the timeline the user has set up."""
        change = each_clip_change(self.session, slot, self.duration_sec)
        if not change.destructive:
            apply()
            return
        number = panel_layer_number(self.session.layer_z_order, slot)
        self._modal_host.prompt_confirm(
            f"Change layer {number}'s presets on each clip?",
            "Change",
            apply,
            body=change.summary(),
        )

    def browse_clip_preset(self, slot: str) -> None:
        """Open the preset browser to replace the selected clip's preset."""
        clip = self.clip_editor.selected(slot)
        if clip is None or not is_each_clip(self.session, slot):
            return
        view = clip_preset_view(self.session, slot, clip, self.duration_sec)
        if view.empty:
            self.preset_browser.open(
                slot, on_choose=lambda path: self._choose_clip_preset(slot, path)
            )
        elif view.list_index is not None:
            self.preset_browser.open(slot, replace_index=view.list_index)

    def _choose_clip_preset(self, slot: str, path: Path) -> None:
        entry = self.preset_list.adopt(path)
        if entry is not None:
            self.clip_editor.set_preset(slot, entry)

    def browse_list_preset(self, slot: str, index: int) -> None:
        """Open the preset browser to replace the layer's list entry *index*."""
        self.preset_browser.open(slot, replace_index=index)

    def convert_to_each_clip(self, slot: str) -> None:
        """Cut a timer layer's row into clips and let each hold its preset."""
        self.layer_mutations.set_preset_switching_trigger(slot, "timeline")

    def _sync_each_clip_layers(self, before: EditSnapshot) -> None:
        for slot in sync_each_clip_layers(self.session, self.duration_sec, before):
            self.preset_list.refresh_switching(slot)

    def do_seek(self, delta_sec: float) -> None:
        if self._layer_bindings is not None:
            self._layer_bindings.on_seek(delta_sec)
        else:
            seek(self.playback, delta_sec, self.duration_sec)

    def seek_to(self, position_sec: float) -> None:
        """Absolute seek; routes through ``on_seek`` (PCM flush + preset re-apply)."""
        target = max(0.0, min(float(position_sec), self.duration_sec))
        current = current_sec(self.playback, self.duration_sec)
        if self._layer_bindings is not None:
            self._layer_bindings.on_seek(target - current)
        else:
            seek_to(self.playback, target, self.duration_sec)

    def show_notification(self, message: str) -> None:
        self._notification_host.show(
            message,
            display_sec=self.cfg.editor.notification_display_sec,
        )

    def dismiss_notification(self) -> None:
        self._notification_host.dismiss_timed()

    def notification_active(self) -> PanelNotificationActive:
        return self._notification_host.active()

    def prompt_generate_timeline(self) -> None:
        self._timeline_presets.prompt(self.duration_sec)

    def prompt_reset_timeline(self) -> None:
        self._timeline_presets.prompt_reset(self.duration_sec)

    def prompt_snap_cues(self) -> None:
        self._timeline_snap.prompt_cues()

    def prompt_snap_cues_to_song_markers(self) -> None:
        self._timeline_snap.prompt_song_markers()

    def prompt_set_cut_type(self) -> None:
        self._timeline_cuts.prompt()

    def preset_edit_target(self) -> PresetEditTarget | None:
        """The focused preset list entry or Milkdrop Preset row, for Cut, Copy, and Paste."""
        focus = self.shell_focus
        desc = focus.inspector_cursor
        if focus.region is not ShellRegion.INSPECTOR or desc is None:
            return None
        slot = desc.slot
        if slot is None or slot not in self.session.layers:
            return None
        if desc.kind is RowKind.TRACK_PRESET:
            index = None
        elif desc.kind is RowKind.TRACK_PRESET_LIST_ITEM:
            index = desc.preset_index
            if index is None or not 0 <= index < len(
                self.session.layers[slot].preset_list
            ):
                return None
        else:
            return None
        return PresetEditTarget(
            slot, index, section_lock_blocks_mutation(self.session, desc)
        )

    def _edit_scope_locked(self, scope: EditScope) -> bool:
        """True when the section an undo entry of *scope* changes is locked."""
        session = self.session
        if scope == TIMELINE_SCOPE:
            return bool(session.timeline.locked)
        slot = preset_list_scope_slot(scope)
        if slot is None or slot not in session.layers:
            return True
        return section_lock_blocks_mutation(
            session, RowDescriptor(RowKind.TRACK_PRESET_LIST_ITEM, slot=slot)
        )

    def undo(self) -> None:
        label = self.edit_history.undo()
        if label is not None:
            self.show_notification(f"Undid {label}")

    def redo(self) -> None:
        label = self.edit_history.redo()
        if label is not None:
            self.show_notification(f"Redid {label}")

    def seek_song_marker(self, desc: RowDescriptor) -> None:
        if desc.marker_index is None:
            return
        if section_lock_blocks_mutation(self.session, desc):
            return
        times = self.session.song_markers.times
        if 0 <= desc.marker_index < len(times):
            self.seek_to(times[desc.marker_index])

    def close_help(self) -> None:
        """Hide the help column. Focus stays where it is."""
        self.session.help_visible = False

    def set_shell_region(self, region: ShellRegion) -> None:
        """Give *region* keyboard scope and keep the strip cursor in sync.

        Entering Timeline selects the stored lane, clamped to the layer count.
        Leaving Timeline replaces a ``TimelineFocus`` cursor with the timeline
        header stand-in and leaves the stored lane in place.
        """
        if region is ShellRegion.TIMELINE:
            self.shell_focus.region = ShellRegion.TIMELINE
            self._apply_focus_cursor(
                TimelineFocus(self._clamped_timeline_focus_row())
            )
            return
        if isinstance(self.focus_cursor, TimelineFocus):
            self._apply_focus_cursor(
                MainFocus(RowDescriptor(RowKind.TIMELINE_HEADER))
            )
        self.shell_focus.region = region

    def _clamped_timeline_focus_row(self) -> int:
        row_count = len(self.session.layer_z_order)
        row = self.session.timeline.focus_row
        if row_count <= 0 or row < 0:
            return 0
        if row >= row_count:
            return row_count - 1
        return row

    def set_timeline_focus_row(self, row: int) -> None:
        """Move the strip lane to *row* without granting keyboard scope."""
        if self.shell_focus.region is ShellRegion.TIMELINE:
            self._apply_focus_cursor(TimelineFocus(row))
            return
        self.session.timeline.focus_row = row

    def open_timeline_panel(self, *, enter_submenu: bool = False) -> None:
        tl = self.session.timeline
        tl.panel_open = True
        if enter_submenu:
            self.set_shell_region(ShellRegion.TIMELINE)

    def close_timeline_panel(self) -> None:
        tl = self.session.timeline
        if not tl.panel_open:
            return
        tl.panel_open = False
        if self.shell_focus.region is ShellRegion.TIMELINE:
            self.set_shell_region(ShellRegion.NAVIGATOR)
        self._leave_timeline_row_page()

    def exit_timeline_submenu(self) -> None:
        if self.shell_focus.region is ShellRegion.TIMELINE:
            self.set_shell_region(ShellRegion.NAVIGATOR)
            return
        if not isinstance(self.focus_cursor, TimelineFocus):
            return
        self._apply_focus_cursor(
            MainFocus(RowDescriptor(RowKind.TIMELINE_HEADER))
        )
