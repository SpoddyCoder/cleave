"""Focus-driven live tuning input for the Milkdrop visualizer overlay."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from cleave.config import CleaveConfig
from cleave.signals import Signals
from cleave.preset_curation import PresetCurationIndex
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.layer_lifecycle_controls import LayerLifecycleController
from cleave.viz.layer_mutations import LayerMutations
from cleave.viz.editor_mode_controls import EditorModeController, is_preset_curation_mode
from cleave.viz.post_fx import sync_live_compositor_format
from cleave.viz.preset_curation_controls import PresetCurationController
from cleave.viz.preset_list_controls import PresetListController
from cleave.viz.key_repeat import KeyRepeatController
from cleave.viz.modal import ModalHost
from cleave.viz.panel_notification import (
    PanelNotificationActive,
    PanelNotificationHost,
)
from cleave.viz.playback import PlaybackState, current_sec, seek, seek_to, toggle_pause
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.render_overlay_controls import RenderOverlaysControls
from cleave.viz.render_pattern_mask_controls import RenderPatternMaskControls
from cleave.viz.render_post_fx_bindings import RenderPostFxBindings
from cleave.viz.render_post_fx_controls import RenderPostFxControls
from cleave.viz.settings_controls import SettingsControls
from cleave.viz.project_controls import ProjectControls
from cleave.viz.project_render_controls import ProjectRenderController
from cleave.viz.song_marker_controls import SongMarkerController
from cleave.viz.tap_sync_controls import TapSyncControls, TapSyncUiSnapshot
from cleave.viz.timeline_phase_controls import TimelinePhaseController
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
from cleave.viz.navigator import build_navigator, layer_node_id
from cleave.viz.navigator_controls import NavigatorControls
from cleave.viz.shell_focus import ShellFocusState, ShellRegion, reconcile_nav_id
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import section_lock_blocks_mutation
from cleave.viz.session import TuningSession
from cleave.viz.tuning_view_state import TuningViewState, TuningViewStateBuilder

if TYPE_CHECKING:
    from cleave.gl_compositor import GlCompositor
    from cleave.gl_masked_compositor import GlMaskedCompositor
    from cleave.gl_post_process import GlPostProcess
    from cleave.viz.wiring import LayerManager

NOTIFICATION_TIMELINE_ENABLED_TEXT = "Timeline controls layer visibility"
NOTIFICATION_TIMELINE_DISABLED_TEXT = "Layer panel controls visibility"
NOTIFICATION_RESIDUAL_LATENCY_UNCHANGED_TEXT = (
    "Existing marker and cue times unchanged"
)
SEEK_TINY = 2
SEEK_SHORT = 10
SEEK_LONG = 30


class TuningControls:
    """Keyboard focus machine for the live tuning tree overlay."""

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
        render_post_fx_bindings: RenderPostFxBindings | None = None,
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
    ) -> None:
        self.session = session
        self.cfg = cfg
        self.preset_root = preset_root
        self.project_dir = project_dir
        self.playback = playback
        self.duration_sec = duration_sec
        self._layer_bindings = layer_bindings
        self._render_post_fx_bindings = render_post_fx_bindings
        self._compositor = compositor
        self._post_process = post_process
        self._masked_compositor = masked_compositor
        self._modal_host = modal_host if modal_host is not None else ModalHost()

        self.shell_focus = ShellFocusState()
        self._focus_cursor: FocusCursor = MainFocus(
            RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
        )
        self._notification_host = PanelNotificationHost()
        self._key_repeat = KeyRepeatController()
        self._hide_overlay_requested = False
        self._overlay_get_visible: Callable[[], bool] | None = None
        self._overlay_hide: Callable[[], None] | None = None
        self._overlay_show: Callable[[], None] | None = None

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
            on_notification=self.show_notification,
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
        layers_by_slot = (
            layer_manager.layers_by_slot if layer_manager is not None else {}
        )
        self.preset_list = PresetListController(
            session,
            preset_root,
            project_dir,
            duration_sec,
            self._modal_host,
            layer_bindings,
            on_notification=self.show_notification,
            get_active_config_path=lambda: self._config_save.active_config_path,
            on_focus_preset_item=self._focus_preset_list_item,
            layers_by_slot=layers_by_slot,
        )
        curation_index = PresetCurationIndex.build(preset_root)
        self._preset_curation = PresetCurationController(
            session,
            preset_root,
            self._modal_host,
            layer_bindings,
            curation_index,
        )
        self._timeline_presets = TimelinePresetController(
            session,
            self._modal_host,
            beat_times,
            bar_times,
            signals=signals,
            on_notification=self.show_notification,
            on_repopulate=self.preset_list.repopulate,
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
        )
        self._timeline_cuts = TimelineCutController(
            session,
            self._modal_host,
            on_notification=self.show_notification,
        )
        self._view_state = TuningViewStateBuilder(
            session,
            playback,
            duration_sec,
            preset_root,
            curation_index,
            get_focus_cursor=lambda: self.focus_cursor,
            get_move_mode_slot=lambda: self.layer_lifecycle.move_mode_slot,
            get_move_mode_preset=lambda: self.preset_list.move_mode_preset,
            config_save=self._config_save,
            get_notification=self._notification_host.active,
            layers_by_slot=layers_by_slot,
            project_dir=project_dir,
        )
        self.render_overlays = RenderOverlaysControls(session)
        self.render_post_fx = RenderPostFxControls(
            session, bindings=render_post_fx_bindings
        )
        self.render_pattern_mask = RenderPatternMaskControls(session)
        self.settings = SettingsControls(
            session,
            cfg,
            on_notification=self.show_notification,
            on_notification_display_changed=self._notification_host.set_display_sec,
        )
        self.project = ProjectControls(
            session,
            duration_sec=duration_sec,
            on_compositor_format_changed=self._sync_live_compositor_format,
        )
        self.project_render = ProjectRenderController(
            session,
            cfg,
            self._modal_host,
            duration_sec=duration_sec,
            playback=playback,
            project_dir=project_dir,
        )
        self.layer_mutations = LayerMutations(
            session,
            preset_root=preset_root,
            duration_sec=duration_sec,
            get_layer_bindings=lambda: self._layer_bindings,
            on_notification=lambda message: self.show_notification(message),
        )
        self._tap_sync = TapSyncControls(
            cfg,
            playback,
            duration_sec,
            self._modal_host,
            on_notification=self.show_notification,
            on_apply_residual_latency=self._apply_residual_latency,
            on_calibration_ui_begin=self._begin_tap_sync_calibration_ui,
            on_calibration_ui_restore=self._restore_tap_sync_calibration_ui,
        )
        self._apply_residual_latency()
        self.editor_mode = EditorModeController(
            session,
            cfg,
            self._config_save,
            self._modal_host,
            project_dir=project_dir,
            layer_bindings=layer_bindings,
            layer_manager=layer_manager,
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
    def preset_curation(self) -> PresetCurationController:
        return self._preset_curation

    def bind_tap_sync_overlay(
        self,
        *,
        get_visible: Callable[[], bool],
        hide: Callable[[], None],
        show: Callable[[], None],
    ) -> None:
        self._overlay_get_visible = get_visible
        self._overlay_hide = hide
        self._overlay_show = show

    def _begin_tap_sync_calibration_ui(self) -> TapSyncUiSnapshot:
        snapshot = TapSyncUiSnapshot(
            help_visible=self.session.help_visible,
            timeline_panel_open=self.session.timeline.panel_open,
            focus_cursor=self.focus_cursor,
            overlay_visible=(
                self._overlay_get_visible()
                if self._overlay_get_visible is not None
                else True
            ),
            shell_region=self.shell_focus.region,
        )
        self.session.help_visible = False
        if self.session.timeline.panel_open:
            self.session.timeline.panel_open = False
        if (
            self.shell_focus.region is ShellRegion.TIMELINE
            or isinstance(self.focus_cursor, TimelineFocus)
        ):
            self.exit_timeline_submenu()
        if self._overlay_hide is not None:
            self._overlay_hide()
        return snapshot

    def _restore_tap_sync_calibration_ui(self, snapshot: TapSyncUiSnapshot) -> None:
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
        if snapshot.overlay_visible and self._overlay_show is not None:
            self._overlay_show()

    def _apply_residual_latency(self) -> None:
        latency_sec = self.cfg.editor.residual_latency_ms / 1000.0
        self.playback.player.set_residual_latency_sec(latency_sec)

    def on_residual_latency_changed(self) -> None:
        self._apply_residual_latency()
        if self._project_has_markers_or_cues():
            self.show_notification(NOTIFICATION_RESIDUAL_LATENCY_UNCHANGED_TEXT)

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

    def request_hide_overlay(self) -> None:
        self._hide_overlay_requested = True

    def consume_hide_overlay(self) -> bool:
        requested = self._hide_overlay_requested
        self._hide_overlay_requested = False
        return requested

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

    def try_quit(self) -> bool:
        if self.project_render.busy:
            self.project_render.abort()
        return self._config_save.try_quit()

    def request_quit(self) -> None:
        """Quit from the menu.

        A clean project sets pending exit so the loop can leave through
        ``consume_pending_exit``. A dirty project only opens the unsaved
        prompt; that dialog sets the flag after save or discard.
        """
        if self.try_quit():
            self._config_save.mark_pending_exit()

    def prompt_save_config(self) -> None:
        if self.session.solo_slot is not None:
            return
        self._config_save.save()

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Keys that no shell region claimed.

        Space pauses. Esc hides the UI. Modals and tap-sync own their keys.
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
            toggle_pause(self.playback, self.duration_sec)
            return True

        if event.key == pygame.K_ESCAPE:
            self.request_hide_overlay()
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
        self._key_repeat.on_keydown(key, mod, on_repeat=on_repeat, accel=accel)

    @property
    def key_repeat_armed(self) -> bool:
        return self._key_repeat.is_armed

    def tick(self, dt_sec: float) -> None:
        self._key_repeat.tick(dt_sec)
        self._notification_host.clear_expired()
        self.project_render.tick()

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
                # Drop in-progress cue flash so returning to a remembered
                # selection shows the settled tick, not a restart blink.
                tl.selected_cue_flash_start_ms = None
            tl.focus_row = cursor.row
            return
        if isinstance(cursor, MainFocus):
            self.song_markers.sync_focus(cursor.descriptor)

    def _on_editor_mode_changed(self) -> None:
        self._sync_live_compositor_format()
        self._view_state._structure = None
        if isinstance(self.focus_cursor, TimelineFocus):
            self.exit_timeline_submenu()
        self._normalize_focus_cursor()

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
        self.shell_focus.nav_expanded.add("layers")
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

    def _focus_preset_list_item(self, slot: str, index: int) -> None:
        self._apply_focus_cursor(
            MainFocus(
                RowDescriptor(
                    RowKind.TRACK_PRESET_LIST_ITEM,
                    slot=slot,
                    preset_index=index,
                )
            )
        )

    def _focus_song_marker(self, marker_index: int | None) -> None:
        focus = self.shell_focus
        if focus.selected_id != "song_markers":
            return
        if marker_index is None:
            focus.inspector_cursor = RowDescriptor(RowKind.SONG_MARKERS_HEADER)
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

    def toggle_render_overlay_locked(self) -> None:
        self.render_overlays.toggle_locked()

    def toggle_render_post_fx_locked(self) -> None:
        post_fx = self.session.render_post_fx
        post_fx.locked = not post_fx.locked

    def toggle_render_pattern_mask_locked(self) -> None:
        self.render_pattern_mask.toggle_locked()

    def toggle_render_timeline_locked(self) -> None:
        timeline = self.session.timeline
        if timeline.recording:
            return
        timeline.locked = not timeline.locked

    def set_render_timeline_enabled(self, enabled: bool) -> None:
        tl = self.session.timeline
        if tl.enabled == enabled:
            return
        tl.enabled = enabled
        if enabled:
            self.open_timeline_panel()
        else:
            self.close_timeline_panel()
        if self._layer_bindings is not None:
            self._layer_bindings.on_timeline_enabled_change()
        self.show_notification(
            NOTIFICATION_TIMELINE_ENABLED_TEXT
            if enabled
            else NOTIFICATION_TIMELINE_DISABLED_TEXT
        )

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

    def prompt_apply_timeline_preset(self) -> None:
        self._timeline_presets.prompt(self.duration_sec)

    def prompt_reset_timeline(self) -> None:
        self._timeline_presets.prompt_reset()

    def prompt_snap_cues(self) -> None:
        self._timeline_snap.prompt_cues()

    def prompt_snap_cues_to_song_markers(self) -> None:
        self._timeline_snap.prompt_song_markers()

    def prompt_apply_soft_cuts(self) -> None:
        self._timeline_cuts.prompt_soft()

    def prompt_apply_hard_cuts(self) -> None:
        self._timeline_cuts.prompt_hard()

    def prompt_remove_timeline_cuts(self) -> None:
        self._timeline_cuts.prompt_remove()

    def seek_song_marker(self, desc: RowDescriptor) -> None:
        if desc.marker_index is None:
            return
        if section_lock_blocks_mutation(self.session, desc):
            return
        times = self.session.song_markers.times
        if 0 <= desc.marker_index < len(times):
            self.seek_to(times[desc.marker_index])

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
                MainFocus(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))
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

    def exit_timeline_submenu(self) -> None:
        if self.shell_focus.region is ShellRegion.TIMELINE:
            self.set_shell_region(ShellRegion.NAVIGATOR)
            return
        if not isinstance(self.focus_cursor, TimelineFocus):
            return
        self._apply_focus_cursor(
            MainFocus(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))
        )
