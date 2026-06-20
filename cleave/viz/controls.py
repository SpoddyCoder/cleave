"""Focus-driven live tuning input for the Milkdrop visualizer overlay."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pygame

from cleave.config import CleaveConfig, clamp_beat_sensitivity, clamp_effect_pct
from cleave.effects.registry import effect_row_count
from cleave.blend_modes import BLEND_MODES, BlendMode
from cleave.extract import STEM_SOURCES
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.key_repeat import KeyRepeatController, mod_ctrl, mod_shift
from cleave.viz.modal import ModalHost
from cleave.viz.playback import PlaybackState, seek, toggle_pause
from cleave.viz.focus_context import FocusContext
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.render_overlay_controls import RenderOverlayControls
from cleave.viz.render_post_fx_controls import RenderPostFxControls
from cleave.viz.row_semantics import REPEAT_ROW_KINDS, RowDescriptor, RowKind
from cleave.viz.overlay import (
    TuningViewState,
    build_row_layout,
    find_row,
    find_row_by_kind,
    navigable_row_indices,
    quick_nav_row_indices,
    row_count,
    row_descriptor,
    row_effect,
    row_kind,
    row_stem,
)
from cleave.viz.session import TuningSession
from cleave.viz.tuning_view_state import TuningViewStateBuilder

TOAST_DURATION_SEC = 5.0
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
    ) -> None:
        self.session = session
        self.cfg = cfg
        self.preset_root = preset_root
        self.playback = playback
        self.duration_sec = duration_sec
        self._layer_bindings = layer_bindings
        self._modal_host = modal_host if modal_host is not None else ModalHost()

        self.focus_index = 0
        self.move_mode_stem: str | None = None
        self._move_mode_original_z_order: list[str] | None = None
        self._toast_message: str | None = None
        self._toast_deadline = 0.0
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
            on_toast=self.show_toast,
            move_mode_signature=self._move_mode_signature_payload,
        )
        self._view_state = TuningViewStateBuilder(
            session,
            playback,
            duration_sec,
            preset_root,
            get_focus_index=lambda: self.focus_index,
            get_move_mode_stem=lambda: self.move_mode_stem,
            config_save=self._config_save,
            get_toast_message=lambda: self._toast_message,
            get_toast_deadline=lambda: self._toast_deadline,
        )
        def set_focus_index(index: int) -> None:
            self.focus_index = index

        focus_context = FocusContext(
            get_focus_index=lambda: self.focus_index,
            set_focus_index=set_focus_index,
            build_view_state=self.build_view_state,
            is_paused=lambda: self.playback.paused,
        )
        self._render_overlay = RenderOverlayControls(
            session,
            focus_context=focus_context,
            focused_row_kind=self._focused_row_kind,
        )
        self._render_post_fx = RenderPostFxControls(session, focus_context=focus_context)

        view = self.build_view_state(paused=self.playback.paused)
        self.focus_index = find_row_by_kind(view, RowKind.TRANSPORT)

    def _move_mode_signature_payload(self) -> dict[str, list[str]] | None:
        if self.move_mode_stem is not None and self._move_mode_original_z_order is not None:
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
            if self.move_mode_stem is not None:
                return True
            tl = self.session.timeline
            if tl.panel_open:
                self.close_timeline_panel()
            else:
                self._open_timeline_panel(enter_submenu=True)
            return True

        if self.move_mode_stem is not None:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self._cancel_move_mode()
                return True
            if event.key == pygame.K_UP:
                self._swap_stem_in_z_order(self.move_mode_stem, -1)
                return True
            if event.key == pygame.K_DOWN:
                self._swap_stem_in_z_order(self.move_mode_stem, 1)
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
            view = self.build_view_state(paused=self.playback.paused)
            kind = row_kind(view, self.focus_index)
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
                        row_kind(self.build_view_state(paused=self.playback.paused), self.focus_index),
                    ),
                )
            return True

        if event.key == pygame.K_BACKSPACE:
            view = self.build_view_state(paused=self.playback.paused)
            kind = row_kind(view, self.focus_index)
            if kind == RowKind.TRACK_PRESET_DIR:
                stem = row_stem(view, self.focus_index)
                if stem is not None:
                    self._parent_directory(stem)
                return True

        if event.key == pygame.K_RETURN and mod_ctrl(event.mod):
            view = self.build_view_state(paused=self.playback.paused)
            kind = row_kind(view, self.focus_index)
            if kind == RowKind.TRACK_HEADER:
                stem = row_stem(view, self.focus_index)
                if stem is not None:
                    self._toggle_locked(stem)
                return True

        if event.key == pygame.K_RETURN:
            view = self.build_view_state(paused=self.playback.paused)
            kind = row_kind(view, self.focus_index)
            if kind == RowKind.TRACK_PRESET_DIR:
                stem = row_stem(view, self.focus_index)
                if stem is not None:
                    self._enter_directory(stem)
                return True
            if kind == RowKind.TRANSPORT:
                toggle_pause(self.playback, self.duration_sec)
                return True
            if kind == RowKind.TRACK_HEADER:
                stem = row_stem(view, self.focus_index)
                if stem is not None:
                    if self.session.layers[stem].locked:
                        return True
                    self._move_mode_original_z_order = list(
                        self.session.layer_z_order
                    )
                    self.move_mode_stem = stem
                return True
            if kind == RowKind.SAVE_CONFIG:
                if self.session.solo_slot is not None:
                    return True
                self._config_save.prompt_save()
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
        if self._toast_message is not None and time.monotonic() >= self._toast_deadline:
            self._toast_message = None

    def build_view_state(
        self,
        *,
        paused: bool,
        position_sec: float | None = None,
    ) -> TuningViewState:
        return self._view_state.build(paused=paused, position_sec=position_sec)

    def _timeline_row_count(self) -> int:
        return len(self.session.layer_z_order)

    def _timeline_submenu_active(self) -> bool:
        tl = self.session.timeline
        return tl.panel_open and tl.enabled and self._timeline_row_count() > 0

    def _move_focus(self, delta: int) -> None:
        tl = self.session.timeline
        row_count = self._timeline_row_count()

        if tl.submenu_focused:
            if row_count == 0:
                tl.submenu_focused = False
            elif delta < 0:
                if tl.focus_row == 0:
                    self.exit_timeline_submenu()
                    return
                tl.focus_row -= 1
                return
            elif tl.focus_row >= row_count - 1:
                tl.submenu_focused = False
                view = self.build_view_state(paused=self.playback.paused)
                self.focus_index = find_row_by_kind(view, RowKind.TRANSPORT)
                return
            else:
                tl.focus_row += 1
                return

        view = self.build_view_state(paused=self.playback.paused)
        navigable = navigable_row_indices(view)
        if not navigable:
            return
        try:
            pos = navigable.index(self.focus_index)
        except ValueError:
            pos = 0

        if self._timeline_submenu_active():
            timeline_header = find_row_by_kind(view, RowKind.RENDER_TIMELINE_HEADER)
            transport = find_row_by_kind(view, RowKind.TRANSPORT)
            if delta > 0 and self.focus_index == timeline_header:
                tl.submenu_focused = True
                tl.focus_row = 0
                return
            if delta < 0 and self.focus_index == transport:
                tl.submenu_focused = True
                tl.focus_row = row_count - 1
                return

        self.focus_index = navigable[(pos + delta) % len(navigable)]

    def _move_quick_focus(self, delta: int) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        quick = quick_nav_row_indices(view)
        if not quick:
            return
        tl = self.session.timeline
        if tl.submenu_focused:
            tl.submenu_focused = False
            timeline_header = find_row_by_kind(view, RowKind.RENDER_TIMELINE_HEADER)
            if delta < 0:
                self.focus_index = timeline_header
                return
            current = timeline_header
        else:
            current = self.focus_index
        if current in quick:
            pos = quick.index(current)
            self.focus_index = quick[(pos + delta) % len(quick)]
            return
        if delta > 0:
            after = [index for index in quick if index > current]
            self.focus_index = after[0] if after else quick[0]
        else:
            before = [index for index in quick if index < current]
            self.focus_index = before[-1] if before else quick[-1]

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

    def _confirm_move_mode(self) -> None:
        self.move_mode_stem = None
        self._move_mode_original_z_order = None

    def _cancel_move_mode(self) -> None:
        if self._move_mode_original_z_order is not None:
            self.session.layer_z_order[:] = self._move_mode_original_z_order
        self.move_mode_stem = None
        self._move_mode_original_z_order = None

    def _apply_horizontal(self, key: int, mod: int, kind: RowKind) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        stem = row_stem(view, self.focus_index)
        ctrl = mod_ctrl(mod)
        forward = key == pygame.K_RIGHT

        if kind == RowKind.TRACK_EFFECTS_HEADER:
            if stem is None:
                return
            self._set_effects_expanded(stem, forward)
            return

        if kind == RowKind.RENDER_OVERLAY_TITLE_HEADER:
            self._render_overlay.set_title_expanded(forward)
            return

        if kind == RowKind.RENDER_OVERLAY_BODY_HEADER:
            self._render_overlay.set_body_expanded(forward)
            return

        if (
            stem is not None
            and kind in REPEAT_ROW_KINDS
            and kind != RowKind.TRACK_STEM
            and self.session.layers[stem].locked
        ):
            return

        if kind == RowKind.TRACK_HEADER:
            if stem is None:
                return
            if mod_shift(mod):
                if forward:
                    self._enter_solo(stem)
                else:
                    self._exit_solo(stem)
                return
            if ctrl:
                if self.session.layers[stem].locked:
                    return
                self._set_enabled(stem, forward)
                return
            self._set_expanded(stem, forward)
        elif kind == RowKind.TRACK_PRESET_DIR:
            if stem is None:
                return
            if ctrl:
                if forward:
                    self._enter_directory(stem)
                else:
                    self._parent_directory(stem)
                return
            self._step_directory(stem, forward=forward)
        elif kind == RowKind.TRACK_PRESET:
            if stem is None:
                return
            self._step_preset(stem, forward=forward, ctrl=ctrl)
        elif kind == RowKind.TRACK_STEM:
            if stem is None:
                return
            self._cycle_stem(stem, forward=forward)
        elif kind == RowKind.TRACK_BLEND:
            if stem is None:
                return
            self._cycle_blend(stem, forward=forward)
        elif kind == RowKind.TRACK_OPACITY:
            if stem is None:
                return
            step = 10 if ctrl else 1
            delta = step if forward else -step
            self._set_opacity(stem, self.session.layers[stem].opacity_pct + delta)
        elif kind == RowKind.TRACK_EFFECT:
            if stem is None:
                return
            effect = row_effect(view, self.focus_index)
            if effect is None:
                return
            effect_id, driver_slug = effect
            step = 10 if ctrl else 1
            delta = step if forward else -step
            current = self.session.layers[stem].effects.get(effect_id, {}).get(
                driver_slug, 0
            )
            self._set_effect(stem, effect_id, driver_slug, current + delta)
        elif kind == RowKind.TRACK_BEAT:
            if stem is None:
                return
            step = 0.1 if ctrl else 0.01
            delta = step if forward else -step
            self._set_beat(stem, self.session.layers[stem].beat_sensitivity + delta)
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
            self._render_overlay.set_expanded(forward)
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
            self._render_post_fx.set_expanded(forward)
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
            if forward:
                self._open_timeline_panel()
            else:
                self.close_timeline_panel()

    def _step_directory(self, stem: str, *, forward: bool) -> None:
        layer = self.session.layers[stem]
        playlist = layer.playlist
        delta = 1 if forward else -1
        if playlist.step_sibling(delta, preset_root=self.preset_root):
            if self._layer_bindings is not None:
                self._layer_bindings.on_preset_change(stem, playlist)

    def _enter_directory(self, stem: str) -> None:
        layer = self.session.layers[stem]
        playlist = layer.playlist
        if playlist.enter_child(self.preset_root):
            if self._layer_bindings is not None:
                self._layer_bindings.on_preset_change(stem, playlist)

    def _parent_directory(self, stem: str) -> None:
        layer = self.session.layers[stem]
        playlist = layer.playlist
        if playlist.go_parent(self.preset_root):
            if self._layer_bindings is not None:
                self._layer_bindings.on_preset_change(stem, playlist)

    def _step_preset(self, stem: str, *, forward: bool, ctrl: bool) -> None:
        layer = self.session.layers[stem]
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
            self._layer_bindings.on_preset_change(stem, playlist)

    def _cycle_blend(self, stem: str, *, forward: bool) -> None:
        layer = self.session.layers[stem]
        try:
            index = BLEND_MODES.index(layer.blend_mode)
        except ValueError:
            index = 0
        if forward:
            layer.blend_mode = BLEND_MODES[(index + 1) % len(BLEND_MODES)]
        else:
            layer.blend_mode = BLEND_MODES[(index - 1) % len(BLEND_MODES)]
        if self._layer_bindings is not None:
            self._layer_bindings.on_blend_change(stem, layer.blend_mode)

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

    def _toggle_locked(self, stem: str) -> None:
        layer = self.session.layers[stem]
        layer.locked = not layer.locked

    def _set_expanded(self, stem: str, expanded: bool) -> None:
        layer = self.session.layers[stem]
        if layer.expanded == expanded:
            return
        layer.expanded = expanded
        if not expanded:
            self._refocus_track_header_if_sub_row(stem)

    def _track_header_index(self, stem: str) -> int:
        view = self.build_view_state(paused=self.playback.paused)
        return find_row(view, stem, RowKind.TRACK_HEADER)

    def _refocus_track_header_if_sub_row(self, stem: str) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        kind = row_kind(view, self.focus_index)
        if kind not in REPEAT_ROW_KINDS:
            return
        if row_stem(view, self.focus_index) == stem:
            self.focus_index = self._track_header_index(stem)

    def _focused_row_kind(self) -> RowKind | None:
        view = self.build_view_state(paused=self.playback.paused)
        try:
            return row_kind(view, self.focus_index)
        except IndexError:
            return None

    def _render_timeline_header_index(self) -> int:
        view = self.build_view_state(paused=self.playback.paused)
        return find_row_by_kind(view, RowKind.RENDER_TIMELINE_HEADER)

    def _focused_row_descriptor(self, view: TuningViewState) -> RowDescriptor | None:
        try:
            return row_descriptor(view, self.focus_index)
        except IndexError:
            return None

    def _restore_focus(self, descriptor: RowDescriptor | None) -> None:
        if descriptor is None:
            return
        view = self.build_view_state(paused=self.playback.paused)
        for index, row in enumerate(build_row_layout(view)):
            if row == descriptor:
                self.focus_index = index
                return
        self.focus_index = min(self.focus_index, row_count(view) - 1)

    def _set_render_timeline_enabled(self, enabled: bool) -> None:
        tl = self.session.timeline
        if tl.enabled == enabled:
            return
        view = self.build_view_state(paused=self.playback.paused)
        focused = self._focused_row_descriptor(view)
        tl.enabled = enabled
        if enabled:
            self._open_timeline_panel()
        else:
            self.close_timeline_panel()
        if self._layer_bindings is not None:
            self._layer_bindings.on_timeline_enabled_change()
        self._restore_focus(focused)

    def _enter_solo(self, stem: str) -> None:
        if self.session.solo_slot == stem:
            return
        self.session.solo_slot = stem
        if self._layer_bindings is not None:
            self._layer_bindings.on_solo_change()

    def _exit_solo(self, stem: str) -> None:
        if self.session.solo_slot != stem:
            return
        self.session.solo_slot = None
        if self._layer_bindings is not None:
            self._layer_bindings.on_solo_change()

    def _set_enabled(self, stem: str, enabled: bool) -> None:
        if self.session.timeline.enabled:
            now = time.monotonic()
            self._toast_message = "Timeline controls layer visibility"
            self._toast_deadline = now + TOAST_DURATION_SEC
            return
        layer = self.session.layers[stem]
        if layer.enabled == enabled:
            return
        layer.enabled = enabled
        if not enabled:
            layer.expanded = False
            self._refocus_track_header_if_sub_row(stem)
        if self._layer_bindings is not None:
            self._layer_bindings.on_layer_enabled_change(stem, layer.enabled)

    def _set_opacity(self, stem: str, pct: int) -> None:
        layer = self.session.layers[stem]
        layer.opacity_pct = max(0, min(100, pct))
        if self._layer_bindings is not None:
            self._layer_bindings.on_opacity_change(stem, layer.opacity_pct)

    def _set_effect(
        self, stem: str, effect_id: str, driver_slug: str, pct: int
    ) -> None:
        layer = self.session.layers[stem]
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
            self._layer_bindings.on_opacity_change(stem, layer.opacity_pct)

    def _set_effects_expanded(self, stem: str, expanded: bool) -> None:
        layer = self.session.layers[stem]
        if layer.effects_expanded == expanded:
            return
        view = self.build_view_state(paused=self.playback.paused)
        effects_header_idx = find_row(view, stem, RowKind.TRACK_EFFECTS_HEADER)
        old_focus = self.focus_index
        effect_count = effect_row_count(layer.stem)
        layer.effects_expanded = expanded
        view_after = self.build_view_state(paused=self.playback.paused)
        new_header_idx = find_row(view_after, stem, RowKind.TRACK_EFFECTS_HEADER)
        if not expanded:
            if old_focus > effects_header_idx and (
                row_stem(view, old_focus) == stem
                and row_kind(view, old_focus) == RowKind.TRACK_EFFECT
            ):
                self.focus_index = new_header_idx
            elif old_focus > effects_header_idx + effect_count:
                self.focus_index = old_focus - effect_count
            elif effects_header_idx < old_focus <= effects_header_idx + effect_count:
                self.focus_index = new_header_idx
        elif old_focus > effects_header_idx:
            self.focus_index = old_focus + effect_count

    def _set_beat(self, stem: str, value: float) -> None:
        layer = self.session.layers[stem]
        layer.beat_sensitivity = clamp_beat_sensitivity(value)
        if self._layer_bindings is not None:
            self._layer_bindings.on_beat_change(stem, layer.beat_sensitivity)

    def _do_seek(self, delta_sec: float) -> None:
        if self._layer_bindings is not None:
            self._layer_bindings.on_seek(delta_sec)
        else:
            seek(self.playback, delta_sec, self.duration_sec)

    def show_toast(self, message: str) -> None:
        now = time.monotonic()
        self._toast_message = message
        self._toast_deadline = now + TOAST_DURATION_SEC

    def _open_timeline_panel(self, *, enter_submenu: bool = False) -> None:
        tl = self.session.timeline
        if not tl.enabled:
            self.show_toast("Enable timeline first")
            return
        tl.panel_open = True
        if enter_submenu:
            tl.submenu_focused = True
            tl.focus_row = 0
        else:
            tl.submenu_focused = False

    def close_timeline_panel(self) -> None:
        tl = self.session.timeline
        if not tl.panel_open:
            return
        tl.panel_open = False
        tl.submenu_focused = False
        self.focus_index = self._render_timeline_header_index()

    def exit_timeline_submenu(self) -> None:
        tl = self.session.timeline
        tl.submenu_focused = False
        self.focus_index = self._render_timeline_header_index()
