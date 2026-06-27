"""Focus-driven live tuning input for the Milkdrop visualizer overlay."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from cleave.config import CleaveConfig, clamp_beat_sensitivity, clamp_effect_pct
from cleave.config_schema import clamp_easter_egg
from cleave.config_schema import PRESET_SWITCHING_MODES
from cleave.blend_modes import BLEND_MODES, BlendMode
from cleave.extract import STEM_SOURCES
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.key_repeat import KeyRepeatController, delete_key_pressed, mod_ctrl, mod_shift
from cleave.viz.modal import ModalHost
from cleave.viz.panel_notification import PanelNotificationHost
from cleave.viz.playback import PlaybackState, seek, toggle_pause
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.render_overlay_controls import RenderOverlayControls
from cleave.viz.render_post_fx_controls import RenderPostFxControls
from cleave.viz.settings_controls import SettingsControls
from cleave.viz.focus_nav import (
    FocusCursor,
    MainFocus,
    TimelineFocus,
    cursor_main_descriptor,
    move_focus,
    timeline_strip_in_ring,
)
from cleave.viz.row_sections import (
    EXPAND_HEADER_KINDS,
    apply_expand_toggle,
    apply_panel_anchor_toggle,
)
from cleave.viz.row_semantics import (
    REPEAT_ROW_KINDS,
    RowDescriptor,
    RowKind,
    layer_lock_blocks_mutation,
    row_behavior,
    row_triggers_layer_delete,
)
from cleave.viz.session import TuningSession
from cleave.viz.tuning_view_state import TuningViewState, TuningViewStateBuilder

if TYPE_CHECKING:
    from cleave.viz.wiring import LayerManager

NOTIFICATION_TIMELINE_ENABLED_TEXT = "Timeline controls layer visibility"
NOTIFICATION_TIMELINE_DISABLED_TEXT = "Layer panel controls visibility"
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
        layer_bindings: LiveLayerBindings | None = None,
        on_save_new_config: Callable[[], Path | None] | None = None,
        on_overwrite_config: Callable[[Path], str | None] | None = None,
        launch_config_path: Path | None = None,
        repo_root_example: Path | None = None,
        modal_host: ModalHost | None = None,
        layer_manager: LayerManager | None = None,
    ) -> None:
        self.session = session
        self.cfg = cfg
        self.preset_root = preset_root
        self.playback = playback
        self.duration_sec = duration_sec
        self._layer_bindings = layer_bindings
        self._layer_manager = layer_manager
        self._modal_host = modal_host if modal_host is not None else ModalHost()

        self._focus_cursor: FocusCursor = MainFocus(
            RowDescriptor(RowKind.TRANSPORT)
        )
        self.move_mode_slot: str | None = None
        self._move_mode_original_z_order: list[str] | None = None
        self._notification_host = PanelNotificationHost()
        self._key_repeat = KeyRepeatController()
        self._hide_overlay_requested = False

        self._config_save = ConfigSaveController(
            session,
            cfg,
            self._modal_host,
            launch_config_path=launch_config_path,
            repo_root_example=repo_root_example,
            on_save_new_config=on_save_new_config,
            on_overwrite_config=on_overwrite_config,
            on_notification=self.show_notification,
            move_mode_signature=self._move_mode_signature_payload,
        )
        self._view_state = TuningViewStateBuilder(
            session,
            playback,
            duration_sec,
            preset_root,
            get_focus_cursor=lambda: self.focus_cursor,
            get_move_mode_slot=lambda: self.move_mode_slot,
            config_save=self._config_save,
            get_notification=self._notification_host.active,
        )
        self._render_overlay = RenderOverlayControls(session)
        self._render_post_fx = RenderPostFxControls(session)
        self._settings = SettingsControls(session, cfg)
        if session.timeline.enabled:
            self.show_notification(NOTIFICATION_TIMELINE_ENABLED_TEXT)

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
            if event.key == pygame.K_RETURN:
                self._confirm_move_mode()
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
                    if self._auto_preset_switching_blocks_browse(slot):
                        return True
                    if layer_lock_blocks_mutation(
                        kind, locked=self.session.layers[slot].locked
                    ):
                        return True
                    self._parent_directory(slot)
                return True

        if delete_key_pressed(event):
            kind = self.focus_descriptor.kind
            if row_triggers_layer_delete(kind):
                slot = self.focus_descriptor.slot
                if slot is not None:
                    self._delete_layer(slot)
                return True

        if event.key == pygame.K_RETURN and mod_ctrl(event.mod):
            kind = self.focus_descriptor.kind
            if kind == RowKind.TRACK_HEADER:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    self._toggle_locked(slot)
                return True

        if event.key == pygame.K_RETURN:
            kind = self.focus_descriptor.kind
            if kind == RowKind.LAYER_MANAGEMENT_ADD:
                self._add_layer()
                return True
            if kind == RowKind.LAYER_MANAGEMENT_DELETE:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    self._delete_layer(slot)
                return True
            if kind == RowKind.TRACK_PRESET_DIR:
                slot = self.focus_descriptor.slot
                if slot is not None:
                    if self._auto_preset_switching_blocks_browse(slot):
                        return True
                    if layer_lock_blocks_mutation(
                        kind, locked=self.session.layers[slot].locked
                    ):
                        return True
                    self._enter_directory(slot)
                return True
            if kind == RowKind.TRANSPORT:
                toggle_pause(self.playback, self.duration_sec)
                return True
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
            if kind == RowKind.CONFIG_HEADER:
                self.prompt_save_config()
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
        self._focus_cursor = cursor
        if isinstance(cursor, TimelineFocus):
            self.session.timeline.focus_row = cursor.row

    def _normalize_focus_cursor(self) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        tl = self.session.timeline
        row_count = len(self.session.layer_z_order)
        if isinstance(self.focus_cursor, TimelineFocus):
            if not timeline_strip_in_ring(view):
                self._apply_focus_cursor(
                    MainFocus(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))
                )
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
        if isinstance(self.focus_cursor, TimelineFocus):
            self._apply_focus_cursor(
                MainFocus(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))
            )
            if delta < 0:
                return
        view = self.build_view_state(paused=self.playback.paused)
        quick_indices = view.layout.quick_nav_indices()
        quick = [view.layout.descriptor(index) for index in quick_indices]
        if not quick:
            return
        if view.layout.contains_descriptor(self.focus_descriptor):
            current_index = view.layout.find_descriptor(self.focus_descriptor)
        else:
            resolved = view.layout.resolve_navigable(self.focus_descriptor, view)
            current_index = (
                view.layout.find_descriptor(resolved)
                if view.layout.contains_descriptor(resolved)
                else -1
            )
        if self.focus_descriptor in quick:
            pos = quick.index(self.focus_descriptor)
            self.focus_descriptor = quick[(pos + delta) % len(quick)]
            return
        if delta > 0:
            after = [
                desc
                for desc in quick
                if view.layout.find_descriptor(desc) > current_index
            ]
            self.focus_descriptor = after[0] if after else quick[0]
        else:
            before = [
                desc
                for desc in quick
                if view.layout.find_descriptor(desc) < current_index
            ]
            self.focus_descriptor = before[-1] if before else quick[-1]

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

    def _cancel_move_mode(self) -> None:
        if self._move_mode_original_z_order is not None:
            self.session.layer_z_order[:] = self._move_mode_original_z_order
            self._apply_preview_resolutions()
        self.move_mode_slot = None
        self._move_mode_original_z_order = None

    def _apply_horizontal(self, key: int, mod: int, kind: RowKind) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        slot = self.focus_descriptor.slot
        ctrl = mod_ctrl(mod)
        forward = key == pygame.K_RIGHT

        if kind in EXPAND_HEADER_KINDS and kind not in {
            RowKind.TRACK_HEADER,
            RowKind.RENDER_OVERLAY_HEADER,
            RowKind.RENDER_POST_FX_HEADER,
        }:
            apply_expand_toggle(self, kind, slot, forward)
            return

        if (
            slot is not None
            and kind in {RowKind.TRACK_PRESET_DIR, RowKind.TRACK_PRESET}
            and self._auto_preset_switching_blocks_browse(slot)
        ):
            return

        if (
            slot is not None
            and layer_lock_blocks_mutation(
                kind, locked=self.session.layers[slot].locked
            )
        ):
            return

        if kind == RowKind.TRACK_HEADER:
            if slot is None:
                return
            if mod_shift(mod):
                if forward:
                    self._enter_solo(slot)
                else:
                    self._exit_solo(slot)
                return
            if ctrl:
                if (
                    self.session.layers[slot].locked
                    and row_behavior(kind).can_enable_disable
                ):
                    return
                self._set_enabled(slot, forward)
                return
            apply_expand_toggle(self, kind, slot, forward)
        elif kind == RowKind.TRACK_PRESET_DIR:
            if slot is None:
                return
            if ctrl:
                if forward:
                    self._enter_directory(slot)
                else:
                    self._parent_directory(slot)
                return
            self._step_directory(slot, forward=forward)
        elif kind == RowKind.TRACK_PRESET:
            if slot is None:
                return
            self._step_preset(slot, forward=forward, ctrl=ctrl)
        elif kind == RowKind.TRACK_PRESET_SWITCHING_MODE:
            if slot is None:
                return
            self._cycle_preset_switching(slot, forward=forward)
        elif kind == RowKind.TRACK_PRESET_SWITCHING_SCOPE:
            return
        elif kind == RowKind.TRACK_PRESET_DURATION:
            if slot is None:
                return
            self._step_preset_duration(slot, forward=forward, ctrl=ctrl)
        elif kind == RowKind.TRACK_SOFT_CUT_DURATION:
            if slot is None:
                return
            self._step_soft_cut_duration(slot, forward=forward, ctrl=ctrl)
        elif kind == RowKind.TRACK_EASTER_EGG:
            if slot is None:
                return
            self._step_easter_egg(slot, forward=forward, ctrl=ctrl)
        elif kind == RowKind.TRACK_PRESET_START_CLEAN:
            if slot is None:
                return
            self._cycle_preset_start_clean(slot, forward=forward)
        elif kind == RowKind.TRACK_HARD_CUT_ENABLED:
            if slot is None:
                return
            self._cycle_hard_cut_enabled(slot, forward=forward)
        elif kind == RowKind.TRACK_HARD_CUT_DURATION:
            if slot is None:
                return
            self._step_hard_cut_duration(slot, forward=forward, ctrl=ctrl)
        elif kind == RowKind.TRACK_HARD_CUT_SENSITIVITY:
            if slot is None:
                return
            step = 0.1 if ctrl else 0.01
            delta = step if forward else -step
            self._set_hard_cut_sensitivity(
                slot, self.session.layers[slot].hard_cut_sensitivity + delta
            )
        elif kind == RowKind.TRACK_STEM:
            if slot is None:
                return
            self._cycle_stem(slot, forward=forward)
        elif kind == RowKind.TRACK_BLEND:
            if slot is None:
                return
            self._cycle_blend(slot, forward=forward)
        elif kind == RowKind.TRACK_OPACITY:
            if slot is None:
                return
            step = 10 if ctrl else 1
            delta = step if forward else -step
            self._set_opacity(slot, self.session.layers[slot].opacity_pct + delta)
        elif kind == RowKind.TRACK_EFFECT:
            if slot is None:
                return
            effect_id = self.focus_descriptor.effect_id
            driver_slug = self.focus_descriptor.driver_slug
            if effect_id is None or driver_slug is None:
                return
            step = 10 if ctrl else 1
            delta = step if forward else -step
            current = self.session.layers[slot].effects.get(effect_id, {}).get(
                driver_slug, 0
            )
            self._set_effect(slot, effect_id, driver_slug, current + delta)
        elif kind == RowKind.TRACK_BEAT:
            if slot is None:
                return
            step = 0.1 if ctrl else 0.01
            delta = step if forward else -step
            self._set_beat(slot, self.session.layers[slot].beat_sensitivity + delta)
        elif kind == RowKind.TRANSPORT:
            delta_sec = SEEK_LONG if ctrl else SEEK_SHORT
            if not forward:
                delta_sec = -delta_sec
            self._do_seek(delta_sec)
        elif kind == RowKind.RENDER_OVERLAY_HEADER:
            if mod_shift(mod):
                if forward:
                    self._render_overlay.enter_solo()
                else:
                    self._render_overlay.exit_solo()
                return
            if ctrl:
                self._render_overlay.set_enabled(forward)
                return
            apply_expand_toggle(self, kind, slot, forward)
        elif kind == RowKind.RENDER_OVERLAY_POSITION:
            self._render_overlay.cycle_position(forward=forward)
        elif kind == RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE:
            step = 10 if ctrl else 1
            delta = step if forward else -step
            self._render_overlay.set_title_font_size(
                self.session.render_overlay.title_font_size + delta
            )
        elif kind == RowKind.RENDER_OVERLAY_TITLE_FONT:
            self._render_overlay.cycle_title_font(forward=forward)
        elif kind == RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM:
            step = 10 if ctrl else 1
            delta = step if forward else -step
            self._render_overlay.set_title_margin_bottom(
                self.session.render_overlay.title_margin_bottom + delta
            )
        elif kind == RowKind.RENDER_OVERLAY_BODY_FONT_SIZE:
            step = 10 if ctrl else 1
            delta = step if forward else -step
            self._render_overlay.set_body_font_size(
                self.session.render_overlay.body_font_size + delta
            )
        elif kind == RowKind.RENDER_OVERLAY_BODY_FONT:
            self._render_overlay.cycle_body_font(forward=forward)
        elif kind == RowKind.RENDER_OVERLAY_OPACITY:
            step = 10 if ctrl else 1
            delta = step if forward else -step
            self._render_overlay.set_opacity(
                self.session.render_overlay.opacity_pct + delta
            )
        elif kind == RowKind.RENDER_OVERLAY_BORDER_WIDTH:
            step = 10 if ctrl else 1
            delta = step if forward else -step
            self._render_overlay.set_border_width(
                self.session.render_overlay.border_width + delta
            )
        elif kind == RowKind.RENDER_OVERLAY_START_DELAY:
            step = 30.0 if ctrl else 1.0
            delta = step if forward else -step
            self._render_overlay.set_start_delay(
                self.session.render_overlay.start_delay + delta
            )
        elif kind == RowKind.RENDER_OVERLAY_DISPLAY_TIME:
            step = 30.0 if ctrl else 1.0
            delta = step if forward else -step
            self._render_overlay.set_display_time(
                self.session.render_overlay.display_time + delta
            )
        elif kind == RowKind.RENDER_POST_FX_HEADER:
            if mod_shift(mod):
                if forward:
                    self._render_post_fx.enter_solo()
                else:
                    self._render_post_fx.exit_solo()
                return
            if ctrl:
                self._render_post_fx.set_enabled(forward)
                return
            apply_expand_toggle(self, kind, slot, forward)
        elif kind == RowKind.RENDER_POST_FX_FADE_IN:
            step = 10.0 if ctrl else 1.0
            delta = step if forward else -step
            self._render_post_fx.set_fade_in(
                self.session.render_post_fx.fade_in + delta
            )
        elif kind == RowKind.RENDER_POST_FX_FADE_OUT:
            step = 10.0 if ctrl else 1.0
            delta = step if forward else -step
            self._render_post_fx.set_fade_out(
                self.session.render_post_fx.fade_out + delta
            )
        elif kind == RowKind.RENDER_TIMELINE_HEADER:
            if ctrl:
                self._set_render_timeline_enabled(forward)
                return
            apply_panel_anchor_toggle(self, kind, forward)
        elif kind == RowKind.SETTINGS_RENDER_MODE:
            self._settings.cycle_render_mode(forward=forward)
            self._apply_preview_resolutions()
        elif kind == RowKind.SETTINGS_UI_WIDTH_MODE:
            self._settings.cycle_ui_width_mode(forward=forward)
        elif kind == RowKind.SETTINGS_UI_WIDTH:
            self._settings.adjust_ui_width(forward=forward, ctrl=ctrl)
        elif kind == RowKind.SETTINGS_UI_FADE:
            self._settings.adjust_ui_fade(forward=forward, ctrl=ctrl)

    def _step_directory(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        playlist = layer.playlist
        delta = 1 if forward else -1
        if playlist.step_sibling(delta, preset_root=self.preset_root):
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
        if playlist.go_parent(self.preset_root):
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

    def _auto_preset_switching_blocks_browse(self, slot: str) -> bool:
        return self.session.layers[slot].preset_switching != "none"

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

    def _set_preset_switching_expanded(self, slot: str, expanded: bool) -> None:
        layer = self.session.layers[slot]
        if layer.preset_switching_expanded == expanded:
            return
        layer.preset_switching_expanded = expanded

    def _set_effects_expanded(self, slot: str, expanded: bool) -> None:
        layer = self.session.layers[slot]
        if layer.effects_expanded == expanded:
            return
        layer.effects_expanded = expanded

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

    def show_notification(self, message: str) -> None:
        self._notification_host.show(message)

    def _open_timeline_panel(self, *, enter_submenu: bool = False) -> None:
        tl = self.session.timeline
        if not tl.enabled:
            self.show_notification("Enable timeline first")
            return
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
        self._apply_focus_cursor(
            MainFocus(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))
        )
