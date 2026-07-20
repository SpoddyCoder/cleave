"""Focus-driven live tuning input for the Milkdrop visualizer overlay."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from cleave.config import CleaveConfig, clamp_beat_sensitivity, clamp_effect_pct
from cleave.config_schema import clamp_easter_egg
from cleave.config_schema import PRESET_SWITCHING_MODES, PRESET_SWITCHING_ROTATION_SETS
from cleave.blend_modes import BLEND_MODES, BlendMode
from cleave.extract import STEM_SOURCES
from cleave.song_markers import format_marker_time, place_marker
from cleave.preset_curation import PresetCurationIndex
from cleave.preset_playlist import is_top_level_browse_dir
from cleave.timeline import snap_placement_time
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.editor_mode_controls import EditorModeController, is_preset_curation_mode
from cleave.viz.post_fx import sync_live_compositor_format
from cleave.viz.preset_curation_controls import PresetCurationController
from cleave.viz.key_repeat import KeyRepeatController, add_current_preset_key_pressed, delete_key_pressed, mod_ctrl, mod_shift
from cleave.viz.modal import ModalHost
from cleave.viz.panel_notification import PanelNotificationHost
from cleave.viz.playback import PlaybackState, current_sec, seek, seek_to, toggle_pause
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.render_overlay_controls import RenderOverlayControls
from cleave.viz.render_post_fx_bindings import RenderPostFxBindings
from cleave.viz.render_post_fx_controls import RenderPostFxControls
from cleave.viz.settings_controls import SettingsControls
from cleave.viz.tap_sync_controls import TapSyncControls, TapSyncUiSnapshot
from cleave.viz.timeline_phase_controls import TimelinePhaseController
from cleave.viz.preset_seed_controls import PresetSeedController
from cleave.viz.timeline_preset_controls import TimelinePresetController
from cleave.viz.timeline_snap_controls import TimelineSnapController
from cleave.viz.user_presets import (
    resolve_user_preset_dest,
    user_preset_item_display_name,
    user_preset_referenced_on_disk,
)
from cleave.viz.focus_nav import (
    FocusCursor,
    MainFocus,
    TimelineFocus,
    cursor_main_descriptor,
    move_focus,
    move_quick_focus,
    timeline_strip_in_ring,
)
from cleave.viz.row_fields import (
    RowPresentStyle,
    ROW_FIELDS,
    apply_field_horizontal,
)
from cleave.viz.row_semantics import (
    PRESET_FILE_ROW_KINDS,
    REPEAT_ROW_KINDS,
    RowDescriptor,
    RowKind,
    row_behavior,
    row_triggers_layer_delete,
    section_lock_blocks_mutation,
)
from cleave.viz.session import TuningSession
from cleave.viz.tuning_view_state import TuningViewState, TuningViewStateBuilder

if TYPE_CHECKING:
    from cleave.gl_compositor import GlCompositor
    from cleave.gl_post_process import GlPostProcess
    from cleave.viz.wiring import LayerManager

NOTIFICATION_TIMELINE_ENABLED_TEXT = "Timeline controls layer visibility"
NOTIFICATION_TIMELINE_DISABLED_TEXT = "Layer panel controls visibility"
NOTIFICATION_TIMELINE_PRESET_SWITCHING_TEXT = (
    "Enable timeline for timeline preset switching"
)
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
        beat_times: Sequence[float] = (),
        bar_times: Sequence[float] = (),
    ) -> None:
        self.session = session
        self.cfg = cfg
        self.preset_root = preset_root
        self.project_dir = project_dir
        self.playback = playback
        self.duration_sec = duration_sec
        self._beat_times = tuple(beat_times)
        self._bar_times = tuple(bar_times)
        self._layer_bindings = layer_bindings
        self._render_post_fx_bindings = render_post_fx_bindings
        self._layer_manager = layer_manager
        self._compositor = compositor
        self._post_process = post_process
        self._modal_host = modal_host if modal_host is not None else ModalHost()

        self._focus_cursor: FocusCursor = MainFocus(
            RowDescriptor(RowKind.TRANSPORT)
        )
        self.move_mode_slot: str | None = None
        self._move_mode_original_z_order: list[str] | None = None
        self._notification_host = PanelNotificationHost()
        self._key_repeat = KeyRepeatController()
        self._hide_overlay_requested = False
        self._overlay_get_visible: Callable[[], bool] | None = None
        self._overlay_hide: Callable[[], None] | None = None
        self._overlay_show: Callable[[], None] | None = None

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
            move_mode_signature=self._move_mode_signature_payload,
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
            on_notification=self.show_notification,
        )
        layers_by_slot = (
            layer_manager.layers_by_slot if layer_manager is not None else {}
        )
        on_switching = (
            None
            if layer_bindings is None
            else layer_bindings.on_preset_switching_change
        )
        self._preset_seed = PresetSeedController(
            session,
            self._modal_host,
            layers_by_slot,
            on_preset_switching_change=on_switching,
        )
        self._timeline_phase = TimelinePhaseController(
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
        self._view_state = TuningViewStateBuilder(
            session,
            playback,
            duration_sec,
            preset_root,
            curation_index,
            get_focus_cursor=lambda: self.focus_cursor,
            get_move_mode_slot=lambda: self.move_mode_slot,
            config_save=self._config_save,
            get_notification=self._notification_host.active,
        )
        self._render_overlay = RenderOverlayControls(session)
        self._render_post_fx = RenderPostFxControls(
            session, bindings=render_post_fx_bindings
        )
        self._settings = SettingsControls(session, cfg)
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
        self._editor_mode = EditorModeController(
            session,
            cfg,
            self._config_save,
            self._modal_host,
            project_dir=project_dir,
            layer_bindings=layer_bindings,
            layer_manager=layer_manager,
            on_mode_changed=self._on_editor_mode_changed,
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

    def _on_residual_latency_changed(self) -> None:
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

    def _move_mode_signature_payload(self) -> dict[str, list[str]] | None:
        if self.move_mode_slot is not None and self._move_mode_original_z_order is not None:
            return {"layer_z_order": list(self._move_mode_original_z_order)}
        return None

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

        if is_preset_curation_mode(self.session):
            return self._handle_curation_keydown(event)

        if self._tap_sync.active:
            return self._tap_sync.handle_keydown(event) or True

        if event.key == pygame.K_SPACE:
            toggle_pause(self.playback, self.duration_sec)
            return True

        if event.key == pygame.K_t:
            if self.move_mode_slot is not None:
                return True
            tl = self.session.timeline
            if tl.panel_open:
                self.close_timeline_panel()
            else:
                self._open_timeline_panel(enter_submenu=True)
            return True

        if self.move_mode_slot is not None:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self._cancel_move_mode()
                return True
            if event.key == pygame.K_UP:
                self._swap_stem_in_z_order(self.move_mode_slot, -1)
                return True
            if event.key == pygame.K_DOWN:
                self._swap_stem_in_z_order(self.move_mode_slot, 1)
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
                    self._parent_directory(slot)
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
                    self._delete_song_marker(desc.marker_index)
                return True
            if kind == RowKind.TRACK_USER_PRESET_ITEM:
                slot = self.focus_descriptor.slot
                desc = self.focus_descriptor
                if slot is not None and desc.preset_index is not None:
                    if section_lock_blocks_mutation(
                        self.session, self.focus_descriptor
                    ):
                        return True
                    self._delete_user_preset(slot, desc.preset_index)
                return True
            if row_triggers_layer_delete(kind):
                slot = self.focus_descriptor.slot
                if slot is not None:
                    self._delete_layer(slot)
                return True

        if event.key == pygame.K_m:
            kind = self.focus_descriptor.kind
            if kind == RowKind.TRACK_HEADER:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    if (
                        self.session.layers[slot].locked
                        and row_behavior(kind).can_enter_move_mode
                    ):
                        return True
                    self._move_mode_original_z_order = list(
                        self.session.layer_z_order
                    )
                    self.move_mode_slot = slot
                return True

        if event.key == pygame.K_l:
            kind = self.focus_descriptor.kind
            if kind == RowKind.TRACK_HEADER:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    self._toggle_locked(slot)
                return True
            if kind == RowKind.RENDER_OVERLAY_HEADER:
                self._toggle_render_overlay_locked()
                return True
            if kind == RowKind.RENDER_POST_FX_HEADER:
                self._toggle_render_post_fx_locked()
                return True
            if kind == RowKind.RENDER_TIMELINE_HEADER:
                self._toggle_render_timeline_locked()
                return True

        if add_current_preset_key_pressed(event.key, event.mod):
            kind = self.focus_descriptor.kind
            slot = self.focus_descriptor.slot
            if (
                slot is not None
                and kind in {RowKind.TRACK_PRESET_DIR, RowKind.TRACK_PRESET}
                and self.session.layers[slot].preset_switching_rotation_set
                == "user_defined"
            ):
                if section_lock_blocks_mutation(
                    self.session, self.focus_descriptor
                ):
                    return True
                self._add_current_preset(slot)
                return True

        if event.key in (pygame.K_f, pygame.K_b, pygame.K_r):
            kind = self.focus_descriptor.kind
            slot = self.focus_descriptor.slot
            if slot is not None and kind in PRESET_FILE_ROW_KINDS:
                if section_lock_blocks_mutation(
                    self.session, self.focus_descriptor
                ):
                    return True
                src = self._resolve_preset_file_path(slot, kind, self.focus_descriptor)
                if src is None or not src.is_file():
                    return True
                if event.key == pygame.K_f:
                    self._preset_curation.prompt_favourite(slot, src)
                elif event.key == pygame.K_b:
                    self._preset_curation.prompt_blacklist(
                        slot,
                        src,
                        from_user_preset=(kind == RowKind.TRACK_USER_PRESET_ITEM),
                        user_preset_index=self.focus_descriptor.preset_index,
                    )
                else:
                    self._preset_curation.prompt_restore(slot, src)
                return True

        if event.key == pygame.K_RETURN:
            kind = self.focus_descriptor.kind
            if kind == RowKind.SETTINGS_EDITOR_MODE:
                self._editor_mode.confirm_editor_mode_selection()
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
            if kind == RowKind.TRACK_USER_PRESET_ADD:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    if section_lock_blocks_mutation(
                        self.session, self.focus_descriptor
                    ):
                        return True
                    self._add_current_preset(slot)
                return True
            if kind == RowKind.LAYER_MANAGEMENT_ADD:
                self._add_layer()
                return True
            if kind == RowKind.LAYER_MANAGEMENT_DELETE:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    self._delete_layer(slot)
                return True
            if kind == RowKind.TIMELINE_PRESETS:
                self._timeline_presets.prompt(self.duration_sec)
                return True
            if kind == RowKind.TIMELINE_RESET:
                self._timeline_presets.prompt_reset()
                return True
            if kind == RowKind.TRACK_PRESET_SWITCHING_SEED:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    if section_lock_blocks_mutation(
                        self.session, self.focus_descriptor
                    ):
                        return True
                    self._preset_seed.prompt(slot)
                return True
            if kind == RowKind.TIMELINE_SNAP_TO_GRID:
                self._timeline_snap.prompt_grid()
                return True
            if kind == RowKind.TIMELINE_SNAP_TO_SONG_MARKERS:
                self._timeline_snap.prompt_song_markers()
                return True
            if kind == RowKind.TRACK_PRESET_DIR:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    if section_lock_blocks_mutation(
                        self.session, self.focus_descriptor
                    ):
                        return True
                    self._enter_directory(slot)
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

        if event.key in (pygame.K_f, pygame.K_b, pygame.K_r):
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
                src = self._resolve_preset_file_path(slot, kind, self.focus_descriptor)
                if src is None or not src.is_file():
                    return True
                if event.key == pygame.K_f:
                    self._preset_curation.prompt_favourite(slot, src)
                elif event.key == pygame.K_b:
                    self._preset_curation.prompt_blacklist(
                        slot,
                        src,
                        from_user_preset=(kind == RowKind.TRACK_USER_PRESET_ITEM),
                        user_preset_index=self.focus_descriptor.preset_index,
                    )
                else:
                    self._preset_curation.prompt_restore(slot, src)
                return True

        if event.key == pygame.K_RETURN:
            if self.focus_descriptor.kind == RowKind.SETTINGS_EDITOR_MODE:
                self._editor_mode.confirm_editor_mode_selection()
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
            self._editor_mode.sync_selection_to_mode()
        self._focus_cursor = cursor
        if isinstance(cursor, TimelineFocus):
            self.session.timeline.focus_row = cursor.row
            return
        if isinstance(cursor, MainFocus):
            desc = cursor.descriptor
            if (
                desc.kind == RowKind.SONG_MARKER_ITEM
                and desc.marker_index is not None
            ):
                self.session.song_markers.selected_index = desc.marker_index

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
            self.session,
            self._compositor,
            self._post_process,
        )

    def _normalize_focus_cursor(self) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        tl = self.session.timeline
        row_count = len(self.session.layer_z_order)
        if isinstance(self.focus_cursor, TimelineFocus):
            if not timeline_strip_in_ring(view):
                fallback_kind = (
                    RowKind.TRANSPORT
                    if is_preset_curation_mode(self.session)
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

    def _swap_stem_in_z_order(self, stem: str, direction: int) -> None:
        order = self.session.layer_z_order
        try:
            index = order.index(stem)
        except ValueError:
            return
        target = index + direction
        if target < 0 or target >= len(order):
            return
        order[index], order[target] = order[target], order[index]
        self._apply_preview_resolutions()

    def _apply_preview_resolutions(self) -> None:
        if self._layer_manager is not None:
            self._layer_manager.apply_preview_resolutions()

    def _confirm_move_mode(self) -> None:
        self.move_mode_slot = None
        self._move_mode_original_z_order = None

    def _rebuild_view(self) -> None:
        if self.move_mode_slot is not None:
            self._confirm_move_mode()

    def _add_layer(self) -> None:
        if self._layer_manager is None:
            return
        if not self._layer_manager.can_add():
            return
        self._modal_host.prompt_yes_no(
            "Add new Milkdrop visualisation layer?",
            on_confirm=self._confirm_add_layer,
        )

    def _confirm_add_layer(self) -> None:
        if self._layer_manager is None:
            return
        self._layer_manager.add_layer()
        self._rebuild_view()
        view_after = self.build_view_state(paused=self.playback.paused)
        if (
            self.focus_descriptor.kind == RowKind.LAYER_MANAGEMENT_ADD
            and not view_after.layout.contains_descriptor(self.focus_descriptor)
        ):
            self._apply_focus_cursor(
                MainFocus(RowDescriptor(RowKind.RENDER_OVERLAY_HEADER))
            )

    def _delete_layer(self, slot: str) -> None:
        if self._layer_manager is None:
            return
        if not self._layer_manager.can_remove():
            self.show_notification("Must have at least 1 layer")
            return
        self._modal_host.prompt_yes_no(
            "Delete this Milkdrop visualisation layer?",
            on_confirm=lambda: self._confirm_delete_layer(slot),
        )

    def _confirm_delete_layer(self, slot: str) -> None:
        if self._layer_manager is None:
            return
        view = self.build_view_state(paused=self.playback.paused)
        navigable = view.layout.navigable_descriptors(view)
        current = view.layout.resolve_navigable(self.focus_descriptor, view)
        try:
            nav_pos = navigable.index(current)
        except ValueError:
            nav_pos = 0
        self._layer_manager.remove_layer(slot)
        self._rebuild_view()
        view_after = self.build_view_state(paused=self.playback.paused)
        navigable_after = view_after.layout.navigable_descriptors(view_after)
        if navigable_after:
            self._apply_focus_cursor(
                MainFocus(
                    navigable_after[min(nav_pos, len(navigable_after) - 1)]
                )
            )
        self._normalize_focus_cursor()

    def _user_presets_dir(self) -> Path | None:
        if self.project_dir is None:
            return None
        return self.project_dir / "user-presets"

    def _user_preset_path_referenced(self, path: str) -> bool:
        target = Path(path).resolve()
        for layer in self.session.layers.values():
            for other in layer.user_presets:
                if Path(other).resolve() == target:
                    return True
        return False

    def _unlock_preset_after_modal(self, slot: str) -> None:
        if self._layer_bindings is not None:
            self._layer_bindings.unlock_preset_after_modal(slot)

    def _resolve_preset_file_path(
        self, slot: str, kind: RowKind, desc: RowDescriptor
    ) -> Path | None:
        layer = self.session.layers[slot]
        if kind == RowKind.TRACK_PRESET:
            return layer.playlist.current
        if kind == RowKind.TRACK_USER_PRESET_ITEM:
            index = desc.preset_index
            if index is None or index < 0 or index >= len(layer.user_presets):
                return None
            return Path(layer.user_presets[index])
        return None

    def _add_current_preset(self, slot: str) -> None:
        playlist = self.session.layers[slot].playlist
        if playlist.current is None:
            return
        src_path = playlist.current
        if self._layer_bindings is not None:
            self._layer_bindings.lock_preset_for_modal(slot)
        self._modal_host.prompt_yes_no(
            f"Add preset: {src_path.name}?",
            on_confirm=lambda: self._confirm_add_preset(slot, src_path),
            on_cancel=lambda: self._unlock_preset_after_modal(slot),
        )

    def _confirm_add_preset(self, slot: str, src_path: Path) -> None:
        try:
            dest_dir = self._user_presets_dir()
            if dest_dir is None:
                return
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path, needs_copy = resolve_user_preset_dest(dest_dir, src_path)
            if needs_copy:
                shutil.copy2(src_path, dest_path)
            self.session.layers[slot].user_presets.append(str(dest_path.resolve()))
            if self._layer_bindings is not None:
                self._layer_bindings.on_preset_switching_change(slot)
        finally:
            self._unlock_preset_after_modal(slot)

    def _delete_user_preset(self, slot: str, index: int) -> None:
        layer = self.session.layers[slot]
        if index < 0 or index >= len(layer.user_presets):
            return
        label = user_preset_item_display_name(layer.user_presets, index)
        self._modal_host.prompt_yes_no(
            f"Remove preset: {label}?",
            on_confirm=lambda: self._confirm_delete_preset(slot, index),
        )

    def _confirm_delete_preset(self, slot: str, index: int) -> None:
        layer = self.session.layers[slot]
        if index < 0 or index >= len(layer.user_presets):
            return
        removed = layer.user_presets.pop(index)
        removed_path = Path(removed).resolve()
        presets_dir = self._user_presets_dir()
        if presets_dir is not None:
            try:
                removed_path.relative_to(presets_dir.resolve())
            except ValueError:
                pass
            else:
                still_needed = self._user_preset_path_referenced(removed)
                if not still_needed and self.project_dir is not None:
                    still_needed = user_preset_referenced_on_disk(
                        self.project_dir,
                        removed_path,
                        skip_config=self._config_save.active_config_path,
                    )
                if not still_needed:
                    removed_path.unlink(missing_ok=True)
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def _cancel_move_mode(self) -> None:
        if self._move_mode_original_z_order is not None:
            self.session.layer_z_order[:] = self._move_mode_original_z_order
            self._apply_preview_resolutions()
        self.move_mode_slot = None
        self._move_mode_original_z_order = None

    def _apply_horizontal(self, key: int, mod: int, kind: RowKind) -> None:
        ctrl = mod_ctrl(mod)
        shift = mod_shift(mod)
        forward = key == pygame.K_RIGHT

        field = ROW_FIELDS.get(kind)
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

    def _step_directory(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        playlist = layer.playlist
        delta = 1 if forward else -1
        if playlist.step_sibling(delta, preset_root=self.preset_root):
            # Pack hop at preset_root: move the ascent floor with the playlist
            # so Ctrl+Left still works after diving into the new pack.
            if is_top_level_browse_dir(playlist.current_dir, self.preset_root):
                layer.browse_floor = playlist.current_dir.resolve()
            if self._layer_bindings is not None:
                self._layer_bindings.on_preset_change(slot, playlist)

    def _enter_directory(self, slot: str) -> None:
        layer = self.session.layers[slot]
        playlist = layer.playlist
        if playlist.enter_child(self.preset_root):
            if self._layer_bindings is not None:
                self._layer_bindings.on_preset_change(slot, playlist)

    def _parent_directory(self, slot: str) -> None:
        layer = self.session.layers[slot]
        playlist = layer.playlist
        if playlist.go_parent(
            self.preset_root, browse_floor=layer.browse_floor
        ):
            if self._layer_bindings is not None:
                self._layer_bindings.on_preset_change(slot, playlist)

    def _step_preset(self, slot: str, *, forward: bool, ctrl: bool) -> None:
        layer = self.session.layers[slot]
        playlist = layer.playlist
        if not playlist.paths:
            return
        if ctrl:
            playlist.step_by(10 if forward else -10)
        elif forward:
            playlist.next()
        else:
            playlist.prev()
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_change(slot, playlist)

    def _cycle_preset_switching(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        modes = PRESET_SWITCHING_MODES
        try:
            index = modes.index(layer.preset_switching)
        except ValueError:
            index = 0
        if forward:
            layer.preset_switching = modes[(index + 1) % len(modes)]
        else:
            layer.preset_switching = modes[(index - 1) % len(modes)]
        if (
            layer.preset_switching == "timeline"
            and not self.session.timeline.enabled
        ):
            self.show_notification(NOTIFICATION_TIMELINE_PRESET_SWITCHING_TEXT)
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def _cycle_preset_switching_rotation_set(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        rotation_sets = PRESET_SWITCHING_ROTATION_SETS
        try:
            index = rotation_sets.index(layer.preset_switching_rotation_set)
        except ValueError:
            index = 0
        if forward:
            layer.preset_switching_rotation_set = rotation_sets[(index + 1) % len(rotation_sets)]
        else:
            layer.preset_switching_rotation_set = rotation_sets[(index - 1) % len(rotation_sets)]
        if layer.preset_switching_rotation_set == "user_defined":
            layer.user_presets_expanded = True
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def _step_preset_duration(
        self, slot: str, *, forward: bool, ctrl: bool = False
    ) -> None:
        layer = self.session.layers[slot]
        step = 10.0 if ctrl else 1.0
        delta = step if forward else -step
        layer.preset_duration = max(5.0, min(300.0, layer.preset_duration + delta))
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def _step_soft_cut_duration(
        self, slot: str, *, forward: bool, ctrl: bool = False
    ) -> None:
        layer = self.session.layers[slot]
        step = 10.0 if ctrl else 1.0
        delta = step if forward else -step
        layer.soft_cut_duration = max(0.0, min(60.0, layer.soft_cut_duration + delta))
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def _step_easter_egg(self, slot: str, *, forward: bool, ctrl: bool = False) -> None:
        layer = self.session.layers[slot]
        step = 0.1 if ctrl else 0.01
        delta = step if forward else -step
        layer.easter_egg = clamp_easter_egg(layer.easter_egg + delta)
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def _cycle_preset_start_clean(self, slot: str, *, forward: bool) -> None:
        del forward
        layer = self.session.layers[slot]
        layer.preset_start_clean = not layer.preset_start_clean
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def _cycle_hard_cut_enabled(self, slot: str, *, forward: bool) -> None:
        del forward
        layer = self.session.layers[slot]
        layer.hard_cut_enabled = not layer.hard_cut_enabled
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def _cycle_preset_switching_shuffle(self, slot: str, *, forward: bool) -> None:
        del forward
        layer = self.session.layers[slot]
        layer.preset_switching_shuffle = not layer.preset_switching_shuffle
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def _step_hard_cut_duration(
        self, slot: str, *, forward: bool, ctrl: bool = False
    ) -> None:
        layer = self.session.layers[slot]
        step = 10.0 if ctrl else 1.0
        delta = step if forward else -step
        layer.hard_cut_duration = max(5.0, min(300.0, layer.hard_cut_duration + delta))
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def _set_hard_cut_sensitivity(self, slot: str, value: float) -> None:
        layer = self.session.layers[slot]
        layer.hard_cut_sensitivity = max(0.1, min(2.0, float(value)))
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def _cycle_blend(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        try:
            index = BLEND_MODES.index(layer.blend_mode)
        except ValueError:
            index = 0
        if forward:
            layer.blend_mode = BLEND_MODES[(index + 1) % len(BLEND_MODES)]
        else:
            layer.blend_mode = BLEND_MODES[(index - 1) % len(BLEND_MODES)]
        if self._layer_bindings is not None:
            self._layer_bindings.on_blend_change(slot, layer.blend_mode)

    def _cycle_stem(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        try:
            index = STEM_SOURCES.index(layer.stem)
        except ValueError:
            index = 0
        if forward:
            layer.stem = STEM_SOURCES[(index + 1) % len(STEM_SOURCES)]
        else:
            layer.stem = STEM_SOURCES[(index - 1) % len(STEM_SOURCES)]
        layer.effects = {}
        if self._layer_bindings is not None:
            self._layer_bindings.on_stem_change(slot, layer.stem)

    def _toggle_locked(self, slot: str) -> None:
        layer = self.session.layers[slot]
        layer.locked = not layer.locked

    def _toggle_render_overlay_locked(self) -> None:
        overlay = self.session.render_overlay
        overlay.locked = not overlay.locked

    def _toggle_render_post_fx_locked(self) -> None:
        post_fx = self.session.render_post_fx
        post_fx.locked = not post_fx.locked

    def _toggle_render_timeline_locked(self) -> None:
        timeline = self.session.timeline
        if timeline.recording:
            return
        timeline.locked = not timeline.locked

    def _set_expanded(self, slot: str, expanded: bool) -> None:
        layer = self.session.layers[slot]
        if layer.expanded == expanded:
            return
        layer.expanded = expanded

    def _set_render_timeline_enabled(self, enabled: bool) -> None:
        tl = self.session.timeline
        if tl.enabled == enabled:
            return
        tl.enabled = enabled
        if enabled:
            self._open_timeline_panel()
        else:
            self.close_timeline_panel()
        if self._layer_bindings is not None:
            self._layer_bindings.on_timeline_enabled_change()
        self.show_notification(
            NOTIFICATION_TIMELINE_ENABLED_TEXT
            if enabled
            else NOTIFICATION_TIMELINE_DISABLED_TEXT
        )

    def _enter_solo(self, slot: str) -> None:
        if self.session.solo_slot == slot:
            return
        self.session.solo_slot = slot
        if self._layer_bindings is not None:
            self._layer_bindings.on_solo_change()

    def _exit_solo(self, slot: str) -> None:
        if self.session.solo_slot != slot:
            return
        self.session.solo_slot = None
        if self._layer_bindings is not None:
            self._layer_bindings.on_solo_change()

    def _set_enabled(self, slot: str, enabled: bool) -> None:
        if self.session.timeline.enabled:
            self.show_notification("Timeline controls layer visibility")
            return
        layer = self.session.layers[slot]
        if layer.enabled == enabled:
            return
        layer.enabled = enabled
        if not enabled:
            layer.expanded = False
        if self._layer_bindings is not None:
            self._layer_bindings.on_layer_enabled_change(slot, layer.enabled)

    def _set_opacity(self, slot: str, pct: int) -> None:
        layer = self.session.layers[slot]
        layer.opacity_pct = max(0, min(100, pct))
        if self._layer_bindings is not None:
            self._layer_bindings.on_opacity_change(slot, layer.opacity_pct)

    def _set_effect(
        self, slot: str, effect_id: str, driver_slug: str, pct: int
    ) -> None:
        layer = self.session.layers[slot]
        clamped = clamp_effect_pct(pct)
        if clamped == 0:
            drivers = layer.effects.get(effect_id)
            if drivers is not None:
                drivers.pop(driver_slug, None)
                if not drivers:
                    layer.effects.pop(effect_id, None)
        else:
            layer.effects.setdefault(effect_id, {})[driver_slug] = clamped
        if self._layer_bindings is not None:
            self._layer_bindings.on_opacity_change(slot, layer.opacity_pct)

    def _set_effects_expanded(self, slot: str, expanded: bool) -> None:
        layer = self.session.layers[slot]
        if layer.effects_expanded == expanded:
            return
        layer.effects_expanded = expanded

    def _set_user_presets_expanded(self, slot: str, expanded: bool) -> None:
        layer = self.session.layers[slot]
        if layer.user_presets_expanded == expanded:
            return
        layer.user_presets_expanded = expanded

    def _set_song_markers_expanded(self, expanded: bool) -> None:
        markers = self.session.song_markers
        if markers.expanded == expanded:
            return
        markers.expanded = expanded

    def _set_beat_bar_grid_expanded(self, expanded: bool) -> None:
        tl = self.session.timeline
        if tl.beat_bar_grid_expanded == expanded:
            return
        tl.beat_bar_grid_expanded = expanded

    def _set_timeline_fades_expanded(self, expanded: bool) -> None:
        tl = self.session.timeline
        if tl.fades_expanded == expanded:
            return
        tl.fades_expanded = expanded

    def _set_timeline_presets_expanded(self, expanded: bool) -> None:
        tl = self.session.timeline
        if tl.timeline_presets_expanded == expanded:
            return
        tl.timeline_presets_expanded = expanded

    def _set_beat(self, slot: str, value: float) -> None:
        layer = self.session.layers[slot]
        layer.beat_sensitivity = clamp_beat_sensitivity(value)
        if self._layer_bindings is not None:
            self._layer_bindings.on_beat_change(slot, layer.beat_sensitivity)

    def _do_seek(self, delta_sec: float) -> None:
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

    def drop_song_marker(self) -> None:
        """Drop or replace a song marker at the playhead (session until Save)."""
        if self.session.timeline.recording:
            return
        t = snap_placement_time(
            current_sec(self.playback, self.duration_sec),
            self.session.timeline.placement_snap,
            beat_times=self._beat_times,
            bar_times=self._bar_times,
        )
        markers = self.session.song_markers
        prior_selected_time: float | None = None
        if (
            markers.selected_index is not None
            and 0 <= markers.selected_index < len(markers.times)
        ):
            prior_selected_time = markers.times[markers.selected_index]
        new_times, replaced_index, replaced_time = place_marker(markers.times, t)
        markers.times = list(new_times)
        markers.expanded = True
        self.session.timeline.panel_open = True
        # Never activate the newly placed marker; keep prior selection by time.
        if prior_selected_time is None:
            if markers.selected_index is not None and (
                markers.selected_index < 0
                or markers.selected_index >= len(markers.times)
            ):
                markers.selected_index = None
        elif (
            replaced_time is not None
            and replaced_time == prior_selected_time
            and replaced_index is not None
        ):
            markers.selected_index = replaced_index
        else:
            try:
                markers.selected_index = new_times.index(prior_selected_time)
            except ValueError:
                markers.selected_index = None
        if replaced_index is not None:
            assert replaced_time is not None
            self.show_notification(
                f"Song marker replaced "
                f"{format_marker_time(replaced_time)} -> "
                f"{format_marker_time(new_times[replaced_index])}"
            )
        else:
            self.show_notification(f"Song marker {format_marker_time(t)}")

    def _delete_song_marker(self, index: int) -> None:
        markers = self.session.song_markers
        if index < 0 or index >= len(markers.times):
            return
        label = format_marker_time(markers.times[index])
        self._modal_host.prompt_yes_no(
            f"Remove song marker {label}?",
            on_confirm=lambda: self._confirm_delete_song_marker(index),
        )

    def _confirm_delete_song_marker(self, index: int) -> None:
        markers = self.session.song_markers
        if index < 0 or index >= len(markers.times):
            return
        removed = markers.times.pop(index)
        if not markers.times:
            markers.selected_index = None
        elif markers.selected_index is None:
            pass
        elif markers.selected_index == index:
            markers.selected_index = min(index, len(markers.times) - 1)
        elif markers.selected_index > index:
            markers.selected_index -= 1
        self.show_notification(
            f"Song marker removed {format_marker_time(removed)}"
        )
        if markers.selected_index is not None:
            self._apply_focus_cursor(
                MainFocus(
                    RowDescriptor(
                        RowKind.SONG_MARKER_ITEM,
                        marker_index=markers.selected_index,
                    )
                )
            )
        else:
            self._apply_focus_cursor(
                MainFocus(RowDescriptor(RowKind.SONG_MARKERS_HEADER))
            )

    def show_notification(self, message: str) -> None:
        self._notification_host.show(message)

    def _open_timeline_panel(self, *, enter_submenu: bool = False) -> None:
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
