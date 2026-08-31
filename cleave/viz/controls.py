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
from cleave.viz.key_repeat import KeyRepeatController, add_current_preset_key_pressed, delete_key_pressed, mod_ctrl, mod_shift
from cleave.viz.modal import ModalHost
from cleave.viz.panel_notification import PanelNotificationHost
from cleave.viz.playback import PlaybackState, current_sec, seek, seek_to, toggle_pause
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.render_overlay_controls import RenderOverlaysControls
from cleave.viz.render_pattern_mask_controls import RenderPatternMaskControls
from cleave.viz.render_post_fx_bindings import RenderPostFxBindings
from cleave.viz.render_post_fx_controls import RenderPostFxControls
from cleave.viz.settings_controls import SettingsControls
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
    move_focus,
    move_quick_focus,
    timeline_strip_in_ring,
)
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import (
    PRESET_FILE_ROW_KINDS,
    REPEAT_ROW_KINDS,
    ROW_SPECS,
    RowPresentStyle,
    apply_field_horizontal,
    row_spec,
    row_triggers_layer_delete,
    section_lock_blocks_mutation,
)
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
        on_save_new_config: Callable[[], Path | None] | None = None,
        on_overwrite_config: Callable[[Path], str | None] | None = None,
        launch_config_path: Path | None = None,
        repo_root_example: Path | None = None,
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

        self._focus_cursor: FocusCursor = MainFocus(
            RowDescriptor(RowKind.TRANSPORT)
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
            on_focus_after_add=self._focus_after_add_layer,
            on_capture_delete_nav=self._capture_delete_nav_pos,
            on_restore_delete_focus=self._restore_delete_focus,
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
            repo_root_example=repo_root_example,
            on_save_new_config=on_save_new_config,
            on_overwrite_config=on_overwrite_config,
            on_notification=self.show_notification,
            move_mode_signature=self.layer_lifecycle.signature_payload,
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
        )
        curation_index = PresetCurationIndex.build(preset_root)
        self._preset_curation = PresetCurationController(
            session,
            preset_root,
            self._modal_host,
            layer_bindings,
            curation_index,
        )
        layers_by_slot = (
            layer_manager.layers_by_slot if layer_manager is not None else {}
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
        )
        self.render_overlays = RenderOverlaysControls(session)
        self.render_post_fx = RenderPostFxControls(
            session, bindings=render_post_fx_bindings
        )
        self.render_pattern_mask = RenderPatternMaskControls(session)
        self.settings = SettingsControls(session, cfg)
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

    @property
    def tap_sync(self) -> TapSyncControls:
        return self._tap_sync

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
        )
        self.session.help_visible = False
        if self.session.timeline.panel_open:
            self.session.timeline.panel_open = False
        if isinstance(self.focus_cursor, TimelineFocus):
            self._apply_focus_cursor(
                MainFocus(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))
            )
        if self._overlay_hide is not None:
            self._overlay_hide()
        return snapshot

    def _restore_tap_sync_calibration_ui(self, snapshot: TapSyncUiSnapshot) -> None:
        self.session.help_visible = snapshot.help_visible
        self.session.timeline.panel_open = snapshot.timeline_panel_open
        self._apply_focus_cursor(snapshot.focus_cursor)
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
        return self._config_save.try_quit()

    def prompt_save_config(self) -> None:
        if self.session.solo_slot is not None:
            return
        self._config_save.prompt_save()

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Handle a key down event for the main tuning tree."""
        if event.type != pygame.KEYDOWN:
            return True

        if self.handle_modal_keydown(event):
            return True

        if is_preset_curation_mode(self.session.settings.editor_mode):
            return self._handle_curation_keydown(event)

        if self._tap_sync.active:
            return self._tap_sync.handle_keydown(event) or True

        if event.key == pygame.K_SPACE:
            toggle_pause(self.playback, self.duration_sec)
            return True

        if event.key == pygame.K_t:
            if self._in_move_mode:
                return True
            tl = self.session.timeline
            if tl.panel_open:
                self.close_timeline_panel()
            else:
                self.open_timeline_panel(enter_submenu=True)
            return True

        if self._in_move_mode:
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

        if event.key == pygame.K_ESCAPE:
            self._hide_overlay_requested = True
            return True

        if event.key in (pygame.K_UP, pygame.K_DOWN):
            delta = -1 if event.key == pygame.K_UP else 1
            if mod_ctrl(event.mod):
                self._move_quick_focus(delta)
            else:
                self._move_focus(delta)
            self._key_repeat.on_keydown(
                event.key,
                event.mod,
                accel=False,
                on_repeat=lambda key, mod: (
                    self._move_quick_focus(-1 if key == pygame.K_UP else 1)
                    if mod_ctrl(mod)
                    else self._move_focus(-1 if key == pygame.K_UP else 1)
                ),
            )
            return True

        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            kind = self.focus_descriptor.kind
            self._apply_horizontal(event.key, event.mod, kind)
            repeat = kind in REPEAT_ROW_KINDS
            if repeat and kind == RowKind.TRACK_PRESET_DIR and mod_ctrl(event.mod):
                repeat = False
            if repeat:
                self._key_repeat.on_keydown(
                    event.key,
                    event.mod,
                    on_repeat=lambda key, mod: self._apply_horizontal(
                        key,
                        mod,
                        self.focus_descriptor.kind,
                    ),
                )
            return True

        if event.key == pygame.K_BACKSPACE:
            kind = self.focus_descriptor.kind
            if kind == RowKind.TRACK_PRESET_DIR:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    if section_lock_blocks_mutation(
                        self.session, self.focus_descriptor
                    ):
                        return True
                    self.layer_mutations.parent_directory(slot)
                return True

        if delete_key_pressed(event):
            kind = self.focus_descriptor.kind
            if kind == RowKind.SONG_MARKER_ITEM:
                desc = self.focus_descriptor
                if desc.marker_index is not None:
                    if section_lock_blocks_mutation(
                        self.session, self.focus_descriptor
                    ):
                        return True
                    self.song_markers.prompt_delete(desc.marker_index)
                return True
            if kind == RowKind.TRACK_PRESET_LIST_ITEM:
                slot = self.focus_descriptor.slot
                desc = self.focus_descriptor
                if slot is not None and desc.preset_index is not None:
                    if section_lock_blocks_mutation(
                        self.session, self.focus_descriptor
                    ):
                        return True
                    self.preset_list.prompt_delete(slot, desc.preset_index)
                return True
            if row_triggers_layer_delete(kind):
                slot = self.focus_descriptor.slot
                if slot is not None:
                    self.layer_lifecycle.prompt_delete(slot)
                return True

        if event.key == pygame.K_m:
            kind = self.focus_descriptor.kind
            if kind == RowKind.TRACK_HEADER:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    if (
                        self.session.layers[slot].locked
                        and row_spec(kind).can_enter_move_mode
                    ):
                        return True
                    self.layer_lifecycle.enter_move_mode(slot)
                return True
            if kind == RowKind.TRACK_PRESET_LIST_ITEM:
                slot = self.focus_descriptor.slot
                index = self.focus_descriptor.preset_index
                if slot is not None and index is not None:
                    if section_lock_blocks_mutation(
                        self.session, self.focus_descriptor
                    ):
                        return True
                    self.preset_list.enter_move_mode(slot, index)
                return True

        if event.key == pygame.K_l:
            kind = self.focus_descriptor.kind
            if kind == RowKind.TRACK_HEADER:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    self._toggle_locked(slot)
                return True
            if kind == RowKind.RENDER_OVERLAYS_HEADER:
                self._toggle_render_overlay_locked()
                return True
            if kind == RowKind.RENDER_POST_FX_HEADER:
                self._toggle_render_post_fx_locked()
                return True
            if kind == RowKind.RENDER_PATTERN_MASK_HEADER:
                self._toggle_render_pattern_mask_locked()
                return True
            if kind == RowKind.RENDER_TIMELINE_HEADER:
                self._toggle_render_timeline_locked()
                return True

        if add_current_preset_key_pressed(event.key, event.mod):
            kind = self.focus_descriptor.kind
            slot = self.focus_descriptor.slot
            if (
                slot is not None
                and self.session.layers[slot].preset_switching == "on"
                and row_spec(kind).parent_group == "track"
            ):
                if section_lock_blocks_mutation(
                    self.session, self.focus_descriptor
                ):
                    return True
                self.preset_list.add_current(slot)
                return True

        if event.key in (pygame.K_f, pygame.K_b, pygame.K_r, pygame.K_c):
            kind = self.focus_descriptor.kind
            slot = self.focus_descriptor.slot
            if slot is not None and kind in PRESET_FILE_ROW_KINDS:
                if section_lock_blocks_mutation(
                    self.session, self.focus_descriptor
                ):
                    return True
                src = self.preset_list.resolve_file_path(
                    slot, kind, self.focus_descriptor
                )
                if src is None or not src.is_file():
                    return True
                if event.key == pygame.K_f:
                    self._preset_curation.prompt_favourite(slot, src)
                elif event.key == pygame.K_b:
                    self._preset_curation.prompt_blacklist(
                        slot,
                        src,
                        from_user_preset=(kind == RowKind.TRACK_PRESET_LIST_ITEM),
                        user_preset_index=self.focus_descriptor.preset_index,
                    )
                elif event.key == pygame.K_c:
                    self._preset_curation.prompt_cast(slot, src)
                else:
                    self._preset_curation.prompt_restore(slot, src)
                return True

        if event.key == pygame.K_RETURN:
            kind = self.focus_descriptor.kind
            if kind == RowKind.SETTINGS_EDITOR_MODE:
                self.editor_mode.confirm_editor_mode_selection()
                return True
            if kind == RowKind.SETTINGS_MEASURE_LATENCY:
                self._tap_sync.prompt_start()
                return True
            if kind == RowKind.SONG_MARKER_ITEM:
                desc = self.focus_descriptor
                if desc.marker_index is not None:
                    if section_lock_blocks_mutation(
                        self.session, self.focus_descriptor
                    ):
                        return True
                    times = self.session.song_markers.times
                    if 0 <= desc.marker_index < len(times):
                        self.seek_to(times[desc.marker_index])
                return True
            if kind == RowKind.TRACK_PRESET_LIST_ADD:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    if section_lock_blocks_mutation(
                        self.session, self.focus_descriptor
                    ):
                        return True
                    self.preset_list.add_current(slot)
                return True
            if kind == RowKind.TRACK_PRESET_LIST_POPULATE:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    if section_lock_blocks_mutation(
                        self.session, self.focus_descriptor
                    ):
                        return True
                    self.preset_list.prompt_populate(slot)
                return True
            if kind == RowKind.LAYER_MANAGEMENT_ADD:
                self.layer_lifecycle.prompt_add()
                return True
            if kind == RowKind.LAYER_MANAGEMENT_DELETE:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    self.layer_lifecycle.prompt_delete(slot)
                return True
            if kind == RowKind.TIMELINE_PRESETS:
                self._timeline_presets.prompt(self.duration_sec)
                return True
            if kind == RowKind.TIMELINE_RESET:
                self._timeline_presets.prompt_reset()
                return True
            if kind == RowKind.TIMELINE_SNAP_TO_BEATS:
                self._timeline_snap.prompt_beats()
                return True
            if kind == RowKind.TIMELINE_SNAP_TO_BARS:
                self._timeline_snap.prompt_bars()
                return True
            if kind == RowKind.TIMELINE_SNAP_TO_SONG_MARKERS:
                self._timeline_snap.prompt_song_markers()
                return True
            if kind == RowKind.TIMELINE_APPLY_SOFT_CUTS:
                self._timeline_cuts.prompt_soft()
                return True
            if kind == RowKind.TIMELINE_APPLY_HARD_CUTS:
                self._timeline_cuts.prompt_hard()
                return True
            if kind == RowKind.TRACK_PRESET_DIR:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    if section_lock_blocks_mutation(
                        self.session, self.focus_descriptor
                    ):
                        return True
                    self.layer_mutations.enter_directory(slot)
                return True
            if kind == RowKind.TRANSPORT:
                toggle_pause(self.playback, self.duration_sec)
                return True
            if kind == RowKind.CONFIG_HEADER:
                self.prompt_save_config()
                return True

        return True

    def _handle_curation_keydown(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_SPACE:
            toggle_pause(self.playback, self.duration_sec)
            return True

        if event.key == pygame.K_ESCAPE:
            self._hide_overlay_requested = True
            return True

        if event.key in (pygame.K_UP, pygame.K_DOWN):
            delta = -1 if event.key == pygame.K_UP else 1
            if mod_ctrl(event.mod):
                self._move_quick_focus(delta)
            else:
                self._move_focus(delta)
            self._key_repeat.on_keydown(
                event.key,
                event.mod,
                accel=False,
                on_repeat=lambda key, mod: (
                    self._move_quick_focus(-1 if key == pygame.K_UP else 1)
                    if mod_ctrl(mod)
                    else self._move_focus(-1 if key == pygame.K_UP else 1)
                ),
            )
            return True

        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            view = self.build_view_state(paused=self.playback.paused)
            desc = self.focus_descriptor
            if not view.layout.contains_descriptor(desc):
                return True
            kind = desc.kind
            # Layer header: expand/collapse only; no solo / enable-disable.
            if kind == RowKind.TRACK_HEADER and (
                mod_ctrl(event.mod) or mod_shift(event.mod)
            ):
                return True
            self._apply_horizontal(event.key, event.mod, kind)
            repeat = kind in REPEAT_ROW_KINDS
            if repeat and kind == RowKind.TRACK_PRESET_DIR and mod_ctrl(event.mod):
                repeat = False
            if repeat:
                self._key_repeat.on_keydown(
                    event.key,
                    event.mod,
                    on_repeat=lambda key, mod: self._apply_horizontal(
                        key,
                        mod,
                        self.focus_descriptor.kind,
                    ),
                )
            return True

        if event.key in (pygame.K_f, pygame.K_b, pygame.K_r, pygame.K_c):
            view = self.build_view_state(paused=self.playback.paused)
            desc = self.focus_descriptor
            if not view.layout.contains_descriptor(desc):
                return True
            kind = desc.kind
            slot = desc.slot
            if slot is not None and kind in PRESET_FILE_ROW_KINDS:
                if section_lock_blocks_mutation(
                    self.session, self.focus_descriptor
                ):
                    return True
                src = self.preset_list.resolve_file_path(
                    slot, kind, self.focus_descriptor
                )
                if src is None or not src.is_file():
                    return True
                if event.key == pygame.K_f:
                    self._preset_curation.prompt_favourite(slot, src)
                elif event.key == pygame.K_b:
                    self._preset_curation.prompt_blacklist(
                        slot,
                        src,
                        from_user_preset=(kind == RowKind.TRACK_PRESET_LIST_ITEM),
                        user_preset_index=self.focus_descriptor.preset_index,
                    )
                elif event.key == pygame.K_c:
                    self._preset_curation.prompt_cast(slot, src)
                else:
                    self._preset_curation.prompt_restore(slot, src)
                return True

        if event.key == pygame.K_RETURN:
            if self.focus_descriptor.kind == RowKind.SETTINGS_EDITOR_MODE:
                self.editor_mode.confirm_editor_mode_selection()
                return True

        return True

    def handle_keyup(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP:
            self._key_repeat.on_keyup(event.key)

    @property
    def key_repeat_armed(self) -> bool:
        return self._key_repeat.is_armed

    def tick(self, dt_sec: float) -> None:
        self._key_repeat.tick(dt_sec)
        self._notification_host.clear_expired()

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
        leaving_editor_mode = (
            isinstance(self._focus_cursor, MainFocus)
            and self._focus_cursor.descriptor.kind == RowKind.SETTINGS_EDITOR_MODE
            and not (
                isinstance(cursor, MainFocus)
                and cursor.descriptor.kind == RowKind.SETTINGS_EDITOR_MODE
            )
        )
        if leaving_editor_mode:
            self.editor_mode.sync_selection_to_mode()
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
        view = self.build_view_state(paused=self.playback.paused)
        if isinstance(self.focus_cursor, TimelineFocus):
            self._apply_focus_cursor(MainFocus(RowDescriptor(RowKind.TRANSPORT)))
        else:
            focus_desc = cursor_main_descriptor(self.focus_cursor)
            if not view.layout.contains_descriptor(focus_desc):
                resolved = view.layout.resolve_navigable(focus_desc, view)
                self._apply_focus_cursor(MainFocus(resolved))
        self._normalize_focus_cursor()

    def _sync_live_compositor_format(self) -> None:
        if self._compositor is None or self._post_process is None:
            return
        sync_live_compositor_format(
            self.cfg,
            self.session.settings.editor_mode,
            self._compositor,
            self._post_process,
            masked_compositor=self._masked_compositor,
        )

    def _normalize_focus_cursor(self) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        tl = self.session.timeline
        row_count = len(self.session.layer_z_order)
        if isinstance(self.focus_cursor, TimelineFocus):
            if not timeline_strip_in_ring(view):
                fallback_kind = (
                    RowKind.TRANSPORT
                    if is_preset_curation_mode(self.session.settings.editor_mode)
                    else RowKind.RENDER_TIMELINE_HEADER
                )
                self._apply_focus_cursor(MainFocus(RowDescriptor(fallback_kind)))
                return
            if row_count == 0:
                self._apply_focus_cursor(
                    MainFocus(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))
                )
            elif self.focus_cursor.row >= row_count:
                self._apply_focus_cursor(TimelineFocus(row_count - 1))
            return
        tl = self.session.timeline
        if tl.focus_row >= row_count:
            tl.focus_row = row_count - 1

    def _move_focus(self, delta: int) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        self._apply_focus_cursor(move_focus(self.focus_cursor, delta, view))

    def _move_quick_focus(self, delta: int) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        self._apply_focus_cursor(move_quick_focus(self.focus_cursor, delta, view))

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

    def _focus_after_add_layer(self) -> None:
        view_after = self.build_view_state(paused=self.playback.paused)
        if (
            self.focus_descriptor.kind == RowKind.LAYER_MANAGEMENT_ADD
            and not view_after.layout.contains_descriptor(self.focus_descriptor)
        ):
            self._apply_focus_cursor(
                MainFocus(RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER))
            )

    def _capture_delete_nav_pos(self) -> int:
        view = self.build_view_state(paused=self.playback.paused)
        navigable = view.layout.navigable_descriptors(view)
        current = view.layout.resolve_navigable(self.focus_descriptor, view)
        try:
            return navigable.index(current)
        except ValueError:
            return 0

    def _restore_delete_focus(self, nav_pos: int) -> None:
        view_after = self.build_view_state(paused=self.playback.paused)
        navigable_after = view_after.layout.navigable_descriptors(view_after)
        if navigable_after:
            self._apply_focus_cursor(
                MainFocus(
                    navigable_after[min(nav_pos, len(navigable_after) - 1)]
                )
            )
        self._normalize_focus_cursor()

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
        if marker_index is not None:
            self._apply_focus_cursor(
                MainFocus(
                    RowDescriptor(
                        RowKind.SONG_MARKER_ITEM,
                        marker_index=marker_index,
                    )
                )
            )
            return
        self._apply_focus_cursor(
            MainFocus(RowDescriptor(RowKind.SONG_MARKERS_HEADER))
        )

    def _apply_horizontal(self, key: int, mod: int, kind: RowKind) -> None:
        ctrl = mod_ctrl(mod)
        shift = mod_shift(mod)
        forward = key == pygame.K_RIGHT

        field = ROW_SPECS.get(kind)
        if (
            field is not None
            and field.present_style == RowPresentStyle.EXPAND_SUBHEADER
            and field.apply_horizontal is not None
        ):
            field.apply_horizontal(
                self, self.focus_descriptor, forward, ctrl, shift
            )
            return

        if section_lock_blocks_mutation(self.session, self.focus_descriptor):
            return

        apply_field_horizontal(
            self, self.focus_descriptor, forward, ctrl, shift
        )

    def _toggle_locked(self, slot: str) -> None:
        layer = self.session.layers[slot]
        layer.locked = not layer.locked

    def _toggle_render_overlay_locked(self) -> None:
        self.render_overlays.toggle_locked()

    def _toggle_render_post_fx_locked(self) -> None:
        post_fx = self.session.render_post_fx
        post_fx.locked = not post_fx.locked

    def _toggle_render_pattern_mask_locked(self) -> None:
        self.render_pattern_mask.toggle_locked()

    def _toggle_render_timeline_locked(self) -> None:
        timeline = self.session.timeline
        if timeline.recording:
            return
        timeline.locked = not timeline.locked

    def set_expanded(self, slot: str, expanded: bool) -> None:
        layer = self.session.layers[slot]
        if layer.expanded == expanded:
            return
        layer.expanded = expanded

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

    def set_effects_expanded(self, slot: str, expanded: bool) -> None:
        layer = self.session.layers[slot]
        if layer.effects_expanded == expanded:
            return
        layer.effects_expanded = expanded

    def set_preset_list_expanded(self, slot: str, expanded: bool) -> None:
        layer = self.session.layers[slot]
        if layer.preset_list_expanded == expanded:
            return
        layer.preset_list_expanded = expanded

    def set_beat_bar_grid_expanded(self, expanded: bool) -> None:
        tl = self.session.timeline
        if tl.beat_bar_grid_expanded == expanded:
            return
        tl.beat_bar_grid_expanded = expanded

    def set_snap_cues_expanded(self, expanded: bool) -> None:
        tl = self.session.timeline
        if tl.snap_cues_expanded == expanded:
            return
        tl.snap_cues_expanded = expanded

    def set_timeline_cuts_expanded(self, expanded: bool) -> None:
        tl = self.session.timeline
        if tl.cuts_expanded == expanded:
            return
        tl.cuts_expanded = expanded

    def set_timeline_presets_expanded(self, expanded: bool) -> None:
        tl = self.session.timeline
        if tl.timeline_presets_expanded == expanded:
            return
        tl.timeline_presets_expanded = expanded

    def set_visual_limiter_expanded(self, expanded: bool) -> None:
        tl = self.session.timeline
        if tl.visual_limiter_expanded == expanded:
            return
        tl.visual_limiter_expanded = expanded

    def set_visual_limiter_enabled(self, enabled: bool) -> None:
        lim = self.session.timeline.limiter
        if lim.enabled == enabled:
            return
        lim.enabled = enabled

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
        self._notification_host.show(message)

    def open_timeline_panel(self, *, enter_submenu: bool = False) -> None:
        tl = self.session.timeline
        tl.panel_open = True
        if enter_submenu:
            self._apply_focus_cursor(TimelineFocus(0))

    def close_timeline_panel(self) -> None:
        tl = self.session.timeline
        if not tl.panel_open:
            return
        tl.panel_open = False
        self._apply_focus_cursor(
            MainFocus(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))
        )

    def exit_timeline_submenu(self) -> None:
        if not isinstance(self.focus_cursor, TimelineFocus):
            return
        self._apply_focus_cursor(
            MainFocus(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))
        )
