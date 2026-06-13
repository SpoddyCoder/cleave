"""Focus-driven live tuning input for the Milkdrop visualizer overlay."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from cleave.config import (
    DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY,
    DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
    DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
    DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
    DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
    DEFAULT_RENDER_OVERLAY_POSITION,
    DEFAULT_RENDER_OVERLAY_START_DELAY,
    DEFAULT_RENDER_POST_FX_FADE_IN,
    DEFAULT_RENDER_POST_FX_FADE_OUT,
    DEFAULT_VIZ_CONFIG_FILENAME,
    PROJECT_VIZ_CONFIG_FILENAME,
    RENDER_OVERLAY_POSITIONS,
    RenderOverlayPosition,
    clamp_beat_sensitivity,
    clamp_effect_pct,
)
from cleave.effects.registry import effect_row_count
from cleave.blend_modes import BLEND_MODES, BlendMode
from cleave.preset_playlist import (
    PresetPlaylist,
    directory_display,
    preset_filename_display,
)
from cleave.viz.confirm import ConfirmDialog, ConfirmRequest
from cleave.viz.key_repeat import KeyRepeatController, mod_ctrl, mod_shift
from cleave.viz.playback import PlaybackState, current_sec, seek, toggle_pause
from cleave.viz.overlay import (
    RenderOverlayBlock,
    RenderPostFxBlock,
    RowKind,
    TrackBlock,
    TuningViewState,
    _RENDER_OVERLAY_TITLE_NESTED_KINDS,
    find_row,
    find_row_by_kind,
    navigable_row_indices,
    quick_nav_row_indices,
    row_effect,
    row_kind,
    row_stem,
)

TOAST_DURATION_SEC = 5.0
SEEK_SHORT = 10
SEEK_LONG = 30

_REPEAT_ROW_KINDS = frozenset(
    {
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_EFFECT,
        RowKind.RENDER_OVERLAY_POSITION,
        RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE,
        RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        RowKind.RENDER_OVERLAY_BODY_FONT_SIZE,
        RowKind.RENDER_OVERLAY_OPACITY,
        RowKind.RENDER_OVERLAY_BORDER_WIDTH,
        RowKind.RENDER_OVERLAY_START_DELAY,
        RowKind.RENDER_OVERLAY_DISPLAY_TIME,
        RowKind.RENDER_POST_FX_FADE_IN,
        RowKind.RENDER_POST_FX_FADE_OUT,
    }
)

_RENDER_OVERLAY_SUB_ROW_KINDS = frozenset(
    {
        RowKind.RENDER_OVERLAY_POSITION,
        RowKind.RENDER_OVERLAY_TITLE_HEADER,
        RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE,
        RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        RowKind.RENDER_OVERLAY_BODY_HEADER,
        RowKind.RENDER_OVERLAY_BODY_FONT_SIZE,
        RowKind.RENDER_OVERLAY_OPACITY,
        RowKind.RENDER_OVERLAY_BORDER_WIDTH,
        RowKind.RENDER_OVERLAY_START_DELAY,
        RowKind.RENDER_OVERLAY_DISPLAY_TIME,
    }
)

_RENDER_POST_FX_SUB_ROW_KINDS = frozenset(
    {
        RowKind.RENDER_POST_FX_FADE_IN,
        RowKind.RENDER_POST_FX_FADE_OUT,
    }
)
_DEFAULT_SAVE_FILENAME = "unnamed-1.yaml"


def config_path_display(path: Path | None) -> str:
    """Active config path for the footer header (truncation happens at draw time)."""
    return path.as_posix() if path is not None else PROJECT_VIZ_CONFIG_FILENAME


def allow_overwrite_for_path(
    active_path: Path | None,
    *,
    repo_root_example: Path,
) -> bool:
    """Hide overwrite only for the repo-root template cleave-viz-default.yaml."""
    if active_path is None:
        return False
    return active_path.resolve() != repo_root_example.resolve()


@dataclass
class RenderOverlayRuntime:
    enabled: bool
    expanded: bool
    position: RenderOverlayPosition
    title_expanded: bool
    body_expanded: bool
    title_font_size: int
    title_margin_bottom: int
    body_font_size: int
    opacity_pct: int
    border_width: int
    start_delay: float
    display_time: float


def default_render_overlay_runtime() -> RenderOverlayRuntime:
    return RenderOverlayRuntime(
        enabled=True,
        expanded=False,
        position=DEFAULT_RENDER_OVERLAY_POSITION,
        title_expanded=False,
        body_expanded=False,
        title_font_size=DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
        title_margin_bottom=DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        body_font_size=DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
        opacity_pct=int(round(DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY * 100)),
        border_width=DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
        start_delay=DEFAULT_RENDER_OVERLAY_START_DELAY,
        display_time=DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    )


@dataclass
class RenderPostFxRuntime:
    enabled: bool
    expanded: bool
    fade_in: float
    fade_out: float


def default_render_post_fx_runtime() -> RenderPostFxRuntime:
    return RenderPostFxRuntime(
        enabled=True,
        expanded=False,
        fade_in=DEFAULT_RENDER_POST_FX_FADE_IN,
        fade_out=DEFAULT_RENDER_POST_FX_FADE_OUT,
    )


@dataclass
class LayerRuntime:
    playlist: PresetPlaylist
    browse_floor: Path
    opacity_pct: int = 100
    effects: dict[str, dict[str, int]] = field(default_factory=dict)
    effects_expanded: bool = False
    blend_mode: BlendMode = "black-key"
    beat_sensitivity: float = 1.0
    enabled: bool = True
    expanded: bool = False
    locked: bool = False


@dataclass
class TuningSession:
    layer_z_order: list[str]
    layers: dict[str, LayerRuntime] = field(default_factory=dict)
    solo_stem: str | None = None
    render_overlay: RenderOverlayRuntime = field(default_factory=default_render_overlay_runtime)
    render_overlay_solo: bool = False
    render_post_fx: RenderPostFxRuntime = field(
        default_factory=default_render_post_fx_runtime
    )
    render_post_fx_solo: bool = False


class TuningControls:
    """Keyboard focus machine for the live tuning tree overlay."""

    def __init__(
        self,
        session: TuningSession,
        preset_root: Path,
        playback: PlaybackState,
        duration_sec: float,
        *,
        on_preset_change: Callable[[str, PresetPlaylist], None] | None = None,
        on_blend_change: Callable[[str, BlendMode], None] | None = None,
        on_opacity_change: Callable[[str, int], None] | None = None,
        on_layer_enabled_change: Callable[[str, bool], None] | None = None,
        on_solo_change: Callable[[], None] | None = None,
        on_beat_change: Callable[[str, float], None] | None = None,
        on_z_order_change: Callable[[list[str]], None] | None = None,
        on_seek: Callable[[float], None] | None = None,
        on_save_new_config: Callable[[], Path | None] | None = None,
        on_overwrite_config: Callable[[Path], str | None] | None = None,
        launch_config_path: Path | None = None,
        repo_root_example: Path | None = None,
    ) -> None:
        self.session = session
        self.preset_root = preset_root
        self.playback = playback
        self.duration_sec = duration_sec
        self._active_config_path = launch_config_path
        self._repo_root_example = (
            repo_root_example
            if repo_root_example is not None
            else Path(DEFAULT_VIZ_CONFIG_FILENAME)
        )
        self._on_preset_change = on_preset_change
        self._on_blend_change = on_blend_change
        self._on_opacity_change = on_opacity_change
        self._on_layer_enabled_change = on_layer_enabled_change
        self._on_solo_change = on_solo_change
        self._on_beat_change = on_beat_change
        self._on_z_order_change = on_z_order_change
        self._on_seek = on_seek
        self._on_save_new_config = on_save_new_config
        self._on_overwrite_config = on_overwrite_config

        self.focus_index = 0
        self.move_mode_stem: str | None = None
        self._move_mode_original_z_order: list[str] | None = None
        self._toast_message: str | None = None
        self._toast_deadline = 0.0
        self._input_blocked_until = 0.0
        self._key_repeat = KeyRepeatController()
        self._confirm = ConfirmDialog()
        self._hide_overlay_requested = False
        view = self.build_view_state(paused=self.playback.paused)
        self.focus_index = find_row_by_kind(view, RowKind.TRANSPORT)

    def consume_hide_overlay(self) -> bool:
        requested = self._hide_overlay_requested
        self._hide_overlay_requested = False
        return requested

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Handle a key down event. Return False when the caller should quit (Ctrl+Q)."""
        if event.type != pygame.KEYDOWN:
            return True

        if self._confirm.active:
            self._confirm.handle_keydown(event)
            return True

        if event.key == pygame.K_q and mod_ctrl(event.mod):
            return False

        if self._input_blocked():
            return True

        if event.key == pygame.K_SPACE:
            toggle_pause(self.playback, self.duration_sec)
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

        if event.key in (pygame.K_UP, pygame.K_DOWN) and mod_ctrl(event.mod):
            self._move_quick_focus(-1 if event.key == pygame.K_UP else 1)
            return True

        if event.key == pygame.K_UP:
            self._move_focus(-1)
            return True
        if event.key == pygame.K_DOWN:
            self._move_focus(1)
            return True

        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            view = self.build_view_state(paused=self.playback.paused)
            kind = row_kind(view, self.focus_index)
            self._apply_horizontal(event.key, event.mod, kind)
            repeat = kind in _REPEAT_ROW_KINDS
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
            if kind == RowKind.SAVE_AS_NEW_CONFIG:
                if self.session.solo_stem is not None:
                    return True
                self._trigger_save_new()
                return True
            if kind == RowKind.OVERWRITE_CONFIG and self._allow_overwrite():
                if self.session.solo_stem is not None:
                    return True
                self._prompt_overwrite()
                return True

        return True

    def handle_keyup(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP:
            self._key_repeat.on_keyup(event.key)

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
        tracks: dict[str, TrackBlock] = {}
        for stem in self.session.layer_z_order:
            layer = self.session.layers[stem]
            tracks[stem] = TrackBlock(
                stem=stem,
                preset_dir_label=directory_display(
                    layer.playlist, self.preset_root
                ),
                preset_label=preset_filename_display(layer.playlist),
                blend_mode=layer.blend_mode,
                opacity_pct=layer.opacity_pct,
                effects=dict(layer.effects),
                effects_expanded=layer.effects_expanded,
                beat_sensitivity=layer.beat_sensitivity,
                enabled=layer.enabled,
                expanded=layer.expanded,
                locked=layer.locked,
                preset_empty=not layer.playlist.paths,
            )

        toast_remaining = 0.0
        toast_message: str | None = None
        if self._toast_message is not None:
            toast_remaining = max(0.0, self._toast_deadline - time.monotonic())
            if toast_remaining > 0:
                toast_message = self._toast_message

        confirm_message: str | None = None
        confirm_focus_yes = True
        if self._confirm.active:
            confirm_message = self._confirm.message
            confirm_focus_yes = self._confirm.focus_yes

        if position_sec is None:
            position_sec = current_sec(self.playback, self.duration_sec)

        ro = self.session.render_overlay
        pp = self.session.render_post_fx
        return TuningViewState(
            layer_z_order=tuple(self.session.layer_z_order),
            tracks=tracks,
            paused=paused,
            position_sec=position_sec,
            focus_index=self.focus_index,
            move_mode_stem=self.move_mode_stem,
            toast_message=toast_message,
            toast_remaining_sec=toast_remaining,
            confirm_message=confirm_message,
            confirm_focus_yes=confirm_focus_yes,
            allow_overwrite=self._allow_overwrite(),
            active_config_label=config_path_display(self._active_config_path),
            solo_stem=self.session.solo_stem,
            solo_active=self.session.solo_stem is not None,
            render_overlay=RenderOverlayBlock(
                enabled=ro.enabled,
                expanded=ro.expanded,
                position=ro.position,
                title_expanded=ro.title_expanded,
                body_expanded=ro.body_expanded,
                title_font_size=ro.title_font_size,
                title_margin_bottom=ro.title_margin_bottom,
                body_font_size=ro.body_font_size,
                opacity_pct=ro.opacity_pct,
                border_width=ro.border_width,
                start_delay=ro.start_delay,
                display_time=ro.display_time,
                solo=self.session.render_overlay_solo,
            ),
            render_post_fx=RenderPostFxBlock(
                enabled=pp.enabled,
                expanded=pp.expanded,
                fade_in=pp.fade_in,
                fade_out=pp.fade_out,
                solo=self.session.render_post_fx_solo,
            ),
        )

    def _allow_overwrite(self) -> bool:
        return allow_overwrite_for_path(
            self._active_config_path,
            repo_root_example=self._repo_root_example,
        )

    def _input_blocked(self) -> bool:
        return time.monotonic() < self._input_blocked_until

    def _move_focus(self, delta: int) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        navigable = navigable_row_indices(view)
        if not navigable:
            return
        try:
            pos = navigable.index(self.focus_index)
        except ValueError:
            pos = 0
        self.focus_index = navigable[(pos + delta) % len(navigable)]

    def _move_quick_focus(self, delta: int) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        quick = quick_nav_row_indices(view)
        if not quick:
            return
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
        if self._on_z_order_change is not None:
            self._on_z_order_change(list(self.session.layer_z_order))
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
            self._set_render_overlay_title_expanded(forward)
            return

        if kind == RowKind.RENDER_OVERLAY_BODY_HEADER:
            self._set_render_overlay_body_expanded(forward)
            return

        if stem is not None and kind in _REPEAT_ROW_KINDS and self.session.layers[stem].locked:
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
                    self._enter_render_overlay_solo()
                else:
                    self._exit_render_overlay_solo()
                return
            if ctrl:
                self._set_render_overlay_enabled(forward)
                return
            self._set_render_overlay_expanded(forward)
        elif kind == RowKind.RENDER_OVERLAY_POSITION:
            self._cycle_render_overlay_position(forward=forward)
        elif kind == RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE:
            step = 10 if ctrl else 1
            delta = step if forward else -step
            self._set_render_overlay_title_font_size(
                self.session.render_overlay.title_font_size + delta
            )
        elif kind == RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM:
            step = 10 if ctrl else 1
            delta = step if forward else -step
            self._set_render_overlay_title_margin_bottom(
                self.session.render_overlay.title_margin_bottom + delta
            )
        elif kind == RowKind.RENDER_OVERLAY_BODY_FONT_SIZE:
            step = 10 if ctrl else 1
            delta = step if forward else -step
            self._set_render_overlay_body_font_size(
                self.session.render_overlay.body_font_size + delta
            )
        elif kind == RowKind.RENDER_OVERLAY_OPACITY:
            step = 10 if ctrl else 1
            delta = step if forward else -step
            self._set_render_overlay_opacity(
                self.session.render_overlay.opacity_pct + delta
            )
        elif kind == RowKind.RENDER_OVERLAY_BORDER_WIDTH:
            step = 10 if ctrl else 1
            delta = step if forward else -step
            self._set_render_overlay_border_width(
                self.session.render_overlay.border_width + delta
            )
        elif kind == RowKind.RENDER_OVERLAY_START_DELAY:
            step = 30.0 if ctrl else 1.0
            delta = step if forward else -step
            self._set_render_overlay_start_delay(
                self.session.render_overlay.start_delay + delta
            )
        elif kind == RowKind.RENDER_OVERLAY_DISPLAY_TIME:
            step = 30.0 if ctrl else 1.0
            delta = step if forward else -step
            self._set_render_overlay_display_time(
                self.session.render_overlay.display_time + delta
            )
        elif kind == RowKind.RENDER_POST_FX_HEADER:
            if mod_shift(mod):
                if forward:
                    self._enter_render_post_fx_solo()
                else:
                    self._exit_render_post_fx_solo()
                return
            if ctrl:
                self._set_render_post_fx_enabled(forward)
                return
            self._set_render_post_fx_expanded(forward)
        elif kind == RowKind.RENDER_POST_FX_FADE_IN:
            step = 10.0 if ctrl else 1.0
            delta = step if forward else -step
            self._set_render_post_fx_fade_in(
                self.session.render_post_fx.fade_in + delta
            )
        elif kind == RowKind.RENDER_POST_FX_FADE_OUT:
            step = 10.0 if ctrl else 1.0
            delta = step if forward else -step
            self._set_render_post_fx_fade_out(
                self.session.render_post_fx.fade_out + delta
            )

    def _step_directory(self, stem: str, *, forward: bool) -> None:
        layer = self.session.layers[stem]
        playlist = layer.playlist
        delta = 1 if forward else -1
        if playlist.step_sibling(delta, preset_root=self.preset_root) and self._on_preset_change is not None:
            self._on_preset_change(stem, playlist)

    def _enter_directory(self, stem: str) -> None:
        layer = self.session.layers[stem]
        playlist = layer.playlist
        if playlist.enter_child(self.preset_root) and self._on_preset_change is not None:
            self._on_preset_change(stem, playlist)

    def _parent_directory(self, stem: str) -> None:
        layer = self.session.layers[stem]
        playlist = layer.playlist
        if playlist.go_parent(self.preset_root) and self._on_preset_change is not None:
            self._on_preset_change(stem, playlist)

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
        if self._on_preset_change is not None:
            self._on_preset_change(stem, playlist)

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
        if self._on_blend_change is not None:
            self._on_blend_change(stem, layer.blend_mode)

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
        if kind not in _REPEAT_ROW_KINDS:
            return
        if row_stem(view, self.focus_index) == stem:
            self.focus_index = self._track_header_index(stem)

    def _focused_row_kind(self) -> RowKind | None:
        view = self.build_view_state(paused=self.playback.paused)
        try:
            return row_kind(view, self.focus_index)
        except IndexError:
            return None

    def _render_overlay_header_index(self) -> int:
        view = self.build_view_state(paused=self.playback.paused)
        return find_row_by_kind(view, RowKind.RENDER_OVERLAY_HEADER)

    def _render_overlay_title_header_index(self) -> int:
        view = self.build_view_state(paused=self.playback.paused)
        return find_row_by_kind(view, RowKind.RENDER_OVERLAY_TITLE_HEADER)

    def _render_overlay_body_header_index(self) -> int:
        view = self.build_view_state(paused=self.playback.paused)
        return find_row_by_kind(view, RowKind.RENDER_OVERLAY_BODY_HEADER)

    def _set_render_overlay_expanded(self, expanded: bool) -> None:
        ro = self.session.render_overlay
        if ro.expanded == expanded:
            return
        focus_kind = self._focused_row_kind()
        ro.expanded = expanded
        if not expanded and focus_kind in _RENDER_OVERLAY_SUB_ROW_KINDS:
            self.focus_index = self._render_overlay_header_index()

    def _set_render_overlay_enabled(self, enabled: bool) -> None:
        ro = self.session.render_overlay
        if ro.enabled == enabled:
            return
        focus_kind = self._focused_row_kind()
        ro.enabled = enabled
        if not enabled:
            self.session.render_overlay_solo = False
            ro.expanded = False
            if focus_kind in _RENDER_OVERLAY_SUB_ROW_KINDS:
                self.focus_index = self._render_overlay_header_index()

    def _enter_render_overlay_solo(self) -> None:
        if self.session.render_overlay_solo:
            return
        self.session.render_overlay_solo = True

    def _exit_render_overlay_solo(self) -> None:
        if not self.session.render_overlay_solo:
            return
        self.session.render_overlay_solo = False

    def _cycle_render_overlay_position(self, *, forward: bool) -> None:
        ro = self.session.render_overlay
        positions = RENDER_OVERLAY_POSITIONS
        try:
            index = positions.index(ro.position)
        except ValueError:
            index = 0
        if forward:
            ro.position = positions[(index + 1) % len(positions)]
        else:
            ro.position = positions[(index - 1) % len(positions)]

    def _set_render_overlay_title_expanded(self, expanded: bool) -> None:
        ro = self.session.render_overlay
        if ro.title_expanded == expanded:
            return
        focus_kind = self._focused_row_kind()
        ro.title_expanded = expanded
        if not expanded and focus_kind in _RENDER_OVERLAY_TITLE_NESTED_KINDS:
            self.focus_index = self._render_overlay_title_header_index()

    def _set_render_overlay_body_expanded(self, expanded: bool) -> None:
        ro = self.session.render_overlay
        if ro.body_expanded == expanded:
            return
        focus_kind = self._focused_row_kind()
        ro.body_expanded = expanded
        if not expanded and focus_kind == RowKind.RENDER_OVERLAY_BODY_FONT_SIZE:
            self.focus_index = self._render_overlay_body_header_index()

    def _set_render_overlay_title_font_size(self, size: int) -> None:
        self.session.render_overlay.title_font_size = max(1, size)

    def _set_render_overlay_title_margin_bottom(self, margin: int) -> None:
        self.session.render_overlay.title_margin_bottom = max(0, margin)

    def _set_render_overlay_body_font_size(self, size: int) -> None:
        self.session.render_overlay.body_font_size = max(1, size)

    def _set_render_overlay_opacity(self, pct: int) -> None:
        self.session.render_overlay.opacity_pct = max(0, min(100, pct))

    def _set_render_overlay_border_width(self, width: int) -> None:
        self.session.render_overlay.border_width = max(0, width)

    def _set_render_overlay_start_delay(self, start_delay: float) -> None:
        self.session.render_overlay.start_delay = max(0.0, start_delay)

    def _set_render_overlay_display_time(self, display_time: float) -> None:
        self.session.render_overlay.display_time = max(0.0, display_time)

    def _render_post_fx_header_index(self) -> int:
        view = self.build_view_state(paused=self.playback.paused)
        return find_row_by_kind(view, RowKind.RENDER_POST_FX_HEADER)

    def _refocus_render_post_fx_header_if_sub_row(self) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        if row_kind(view, self.focus_index) in _RENDER_POST_FX_SUB_ROW_KINDS:
            self.focus_index = self._render_post_fx_header_index()

    def _set_render_post_fx_expanded(self, expanded: bool) -> None:
        pp = self.session.render_post_fx
        if pp.expanded == expanded:
            return
        pp.expanded = expanded
        if not expanded:
            self._refocus_render_post_fx_header_if_sub_row()

    def _set_render_post_fx_enabled(self, enabled: bool) -> None:
        pp = self.session.render_post_fx
        if pp.enabled == enabled:
            return
        pp.enabled = enabled
        if not enabled:
            self.session.render_post_fx_solo = False
            pp.expanded = False
            self._refocus_render_post_fx_header_if_sub_row()

    def _enter_render_post_fx_solo(self) -> None:
        if self.session.render_post_fx_solo:
            return
        self.session.render_post_fx_solo = True

    def _exit_render_post_fx_solo(self) -> None:
        if not self.session.render_post_fx_solo:
            return
        self.session.render_post_fx_solo = False

    def _set_render_post_fx_fade_in(self, fade_in: float) -> None:
        self.session.render_post_fx.fade_in = max(0.0, fade_in)

    def _set_render_post_fx_fade_out(self, fade_out: float) -> None:
        self.session.render_post_fx.fade_out = max(0.0, fade_out)

    def _enter_solo(self, stem: str) -> None:
        if self.session.solo_stem == stem:
            return
        self.session.solo_stem = stem
        if self._on_solo_change is not None:
            self._on_solo_change()

    def _exit_solo(self, stem: str) -> None:
        if self.session.solo_stem != stem:
            return
        self.session.solo_stem = None
        if self._on_solo_change is not None:
            self._on_solo_change()

    def _set_enabled(self, stem: str, enabled: bool) -> None:
        layer = self.session.layers[stem]
        if layer.enabled == enabled:
            return
        layer.enabled = enabled
        if not enabled:
            layer.expanded = False
            self._refocus_track_header_if_sub_row(stem)
        if self._on_layer_enabled_change is not None:
            self._on_layer_enabled_change(stem, layer.enabled)

    def _set_opacity(self, stem: str, pct: int) -> None:
        layer = self.session.layers[stem]
        layer.opacity_pct = max(0, min(100, pct))
        if self._on_opacity_change is not None:
            self._on_opacity_change(stem, layer.opacity_pct)

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
        if self._on_opacity_change is not None:
            self._on_opacity_change(stem, layer.opacity_pct)

    def _set_effects_expanded(self, stem: str, expanded: bool) -> None:
        layer = self.session.layers[stem]
        if layer.effects_expanded == expanded:
            return
        view = self.build_view_state(paused=self.playback.paused)
        effects_header_idx = find_row(view, stem, RowKind.TRACK_EFFECTS_HEADER)
        old_focus = self.focus_index
        effect_count = effect_row_count(stem)
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
        if self._on_beat_change is not None:
            self._on_beat_change(stem, layer.beat_sensitivity)

    def _do_seek(self, delta_sec: float) -> None:
        if self._on_seek is not None:
            self._on_seek(delta_sec)
        else:
            seek(self.playback, delta_sec, self.duration_sec)

    def _trigger_save_new(self) -> None:
        if self._on_save_new_config is not None:
            saved_path = self._on_save_new_config()
        else:
            saved_path = None
        if saved_path is None:
            filename = _DEFAULT_SAVE_FILENAME
        else:
            self._active_config_path = saved_path
            filename = saved_path.name
        self._show_save_toast(f"Config saved to {filename}")

    def _prompt_overwrite(self) -> None:
        active_path = self._active_config_path
        basename = (
            active_path.name
            if active_path is not None
            else PROJECT_VIZ_CONFIG_FILENAME
        )
        message = f"Overwrite {basename}?"

        def on_confirm() -> None:
            target = active_path or Path(PROJECT_VIZ_CONFIG_FILENAME)
            if self._on_overwrite_config is not None:
                written = self._on_overwrite_config(target)
            else:
                written = basename
            if not written:
                written = basename
            self._show_save_toast(f"Config overwritten: {written}")

        self._confirm.prompt(ConfirmRequest(message=message, on_confirm=on_confirm))

    def _show_save_toast(self, message: str) -> None:
        print(message, file=sys.stderr)
        now = time.monotonic()
        self._toast_message = message
        self._toast_deadline = now + TOAST_DURATION_SEC
        self._input_blocked_until = now + TOAST_DURATION_SEC
