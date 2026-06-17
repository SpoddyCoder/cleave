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
    DEFAULT_RENDER_OVERLAY_FONT,
    DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
    DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
    DEFAULT_RENDER_OVERLAY_POSITION,
    DEFAULT_RENDER_OVERLAY_START_DELAY,
    DEFAULT_RENDER_POST_FX_FADE_IN,
    DEFAULT_RENDER_POST_FX_FADE_OUT,
    VIZ_CONFIG_FILENAME,
    RENDER_OVERLAY_POSITIONS,
    RenderOverlayPosition,
    clamp_beat_sensitivity,
    clamp_effect_pct,
)
from cleave.effects.registry import effect_row_count
from cleave.viz.fonts import cycle_render_overlay_font
from cleave.blend_modes import BLEND_MODES, BlendMode
from cleave.preset_playlist import (
    PresetPlaylist,
    directory_display,
    preset_filename_display,
)
from cleave.timeline import TimelineCue
from cleave.viz.confirm import (
    ConfirmDialog,
    ConfirmRequest,
    SaveChoiceDialog,
    SaveChoiceRequest,
    UnsavedQuitDialog,
    UnsavedQuitRequest,
)
from cleave.viz.key_repeat import KeyRepeatController, mod_ctrl, mod_shift
from cleave.viz.playback import PlaybackState, current_sec, seek, toggle_pause
from cleave.viz.row_semantics import (
    REPEAT_ROW_KINDS,
    RENDER_OVERLAY_ALL_SUB_ROW_KINDS,
    RENDER_OVERLAY_BODY_NESTED_KINDS,
    RENDER_OVERLAY_TITLE_NESTED_KINDS,
    RENDER_POST_FX_SUB_ROW_KINDS,
    RENDER_TIMELINE_SUB_ROW_KINDS,
    RowKind,
)
from cleave.viz.overlay import (
    RenderOverlayBlock,
    RenderPostFxBlock,
    RenderTimelineBlock,
    TrackBlock,
    TuningViewState,
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
_DEFAULT_SAVE_FILENAME = "unnamed-1.yaml"


def config_path_display(path: Path | None, *, dirty: bool = False) -> str:
    """Active config path for the config header row (truncation happens at draw time)."""
    label = path.as_posix() if path is not None else VIZ_CONFIG_FILENAME
    if dirty:
        label += "*"
    return label


def allow_overwrite_for_path(
    active_path: Path | None,
    *,
    repo_root_example: Path,
) -> bool:
    """Hide overwrite only for the repo-root template cleave-viz.yaml."""
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
    title_font: str
    title_margin_bottom: int
    body_font_size: int
    body_font: str
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
        title_font=DEFAULT_RENDER_OVERLAY_FONT,
        title_margin_bottom=DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        body_font_size=DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
        body_font=DEFAULT_RENDER_OVERLAY_FONT,
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
class TimelineRuntime:
    enabled: bool = True
    cues: list[TimelineCue] = field(default_factory=list)
    panel_open: bool = False
    submenu_focused: bool = False
    focus_row: int = 0
    armed_stems: set[str] = field(default_factory=set)
    recording: bool = False
    record_buffer: list[TimelineCue] = field(default_factory=list)
    record_baseline: dict[str, bool] = field(default_factory=dict)
    record_start_sec: float | None = None
    preview_active: bool = False
    monitor: dict[str, bool] = field(default_factory=dict)
    override_stems: set[str] = field(default_factory=set)
    override_visible: dict[str, bool] = field(default_factory=dict)


def default_timeline_runtime() -> TimelineRuntime:
    return TimelineRuntime()


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
    timeline: TimelineRuntime = field(default_factory=default_timeline_runtime)
    help_visible: bool = False


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
        on_timeline_enabled_change: Callable[[], None] | None = None,
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
            else Path(VIZ_CONFIG_FILENAME)
        )
        self._on_preset_change = on_preset_change
        self._on_blend_change = on_blend_change
        self._on_opacity_change = on_opacity_change
        self._on_layer_enabled_change = on_layer_enabled_change
        self._on_timeline_enabled_change = on_timeline_enabled_change
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
        self._save_choice = SaveChoiceDialog()
        self._unsaved_quit = UnsavedQuitDialog()
        self._hide_overlay_requested = False
        self._config_dirty = False
        self._pending_exit = False
        self._quit_after_save = False
        view = self.build_view_state(paused=self.playback.paused)
        self.focus_index = find_row_by_kind(view, RowKind.TRANSPORT)

    @property
    def config_dirty(self) -> bool:
        return self._config_dirty

    def mark_config_dirty(self) -> None:
        self._config_dirty = True

    def clear_config_dirty(self) -> None:
        self._config_dirty = False

    def consume_hide_overlay(self) -> bool:
        requested = self._hide_overlay_requested
        self._hide_overlay_requested = False
        return requested

    def handle_modal_keydown(self, event: pygame.event.Event) -> bool:
        """Return True when a modal dialog consumed the event."""
        if event.type != pygame.KEYDOWN:
            return False
        if self._confirm.active:
            self._confirm.handle_keydown(event)
            return True
        if self._save_choice.active:
            if event.key == pygame.K_ESCAPE and self._quit_after_save:
                self._quit_after_save = False
            self._save_choice.handle_keydown(event)
            return True
        if self._unsaved_quit.active:
            self._unsaved_quit.handle_keydown(event)
            return True
        return False

    @property
    def pending_exit(self) -> bool:
        return self._pending_exit

    def consume_pending_exit(self) -> bool:
        """Return True once when quit was deferred (e.g. Don't save from unsaved dialog)."""
        if self._pending_exit:
            self._pending_exit = False
            return True
        return False

    def try_quit(self) -> bool:
        """Handle a quit request. Return True when the app should exit now."""
        if self._pending_exit:
            return True
        if not self._config_dirty:
            return True
        if not self._unsaved_quit.active:
            self._unsaved_quit.prompt(
                UnsavedQuitRequest(
                    on_save=self._quit_save,
                    on_discard=self._quit_discard,
                )
            )
        return False

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Handle a key down event for the main tuning tree."""
        if event.type != pygame.KEYDOWN:
            return True

        if self.handle_modal_keydown(event):
            return True

        if self._input_blocked():
            return True

        if event.key == pygame.K_SPACE:
            toggle_pause(self.playback, self.duration_sec)
            return True

        if event.key == pygame.K_t:
            if self.move_mode_stem is not None:
                return True
            tl = self.session.timeline
            if tl.panel_open:
                self._close_timeline_panel()
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
                if self.session.solo_stem is not None:
                    return True
                self._prompt_save()
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
        if position_sec is None:
            position_sec = current_sec(self.playback, self.duration_sec)

        from cleave.viz.layer import effective_layer_enabled

        tracks: dict[str, TrackBlock] = {}
        for stem in self.session.layer_z_order:
            layer = self.session.layers[stem]
            if self.session.timeline.enabled:
                visible = effective_layer_enabled(
                    self.session, stem, position_sec
                )
            else:
                visible = layer.enabled
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
                visible=visible,
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
        save_choice_active = False
        save_choice_focus_overwrite = True
        unsaved_quit_active = False
        unsaved_quit_focus = 0
        if self._confirm.active:
            confirm_message = self._confirm.message
            confirm_focus_yes = self._confirm.focus_yes
        if self._save_choice.active:
            save_choice_active = True
            save_choice_focus_overwrite = self._save_choice.focus_overwrite
        if self._unsaved_quit.active:
            unsaved_quit_active = True
            unsaved_quit_focus = self._unsaved_quit.focus_index

        ro = self.session.render_overlay
        pp = self.session.render_post_fx
        tl = self.session.timeline
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
            save_choice_active=save_choice_active,
            save_choice_focus_overwrite=save_choice_focus_overwrite,
            unsaved_quit_active=unsaved_quit_active,
            unsaved_quit_focus=unsaved_quit_focus,
            allow_overwrite=self._allow_overwrite(),
            active_config_label=config_path_display(
                self._active_config_path, dirty=self._config_dirty
            ),
            solo_stem=self.session.solo_stem,
            solo_active=self.session.solo_stem is not None,
            render_overlay=RenderOverlayBlock(
                enabled=ro.enabled,
                expanded=ro.expanded,
                position=ro.position,
                title_expanded=ro.title_expanded,
                body_expanded=ro.body_expanded,
                title_font_size=ro.title_font_size,
                title_font=ro.title_font,
                title_margin_bottom=ro.title_margin_bottom,
                body_font_size=ro.body_font_size,
                body_font=ro.body_font,
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
            render_timeline=RenderTimelineBlock(
                enabled=tl.enabled,
                expanded=tl.panel_open,
            ),
            timeline_submenu_focused=tl.submenu_focused,
            timeline_recording=tl.recording,
            timeline_override_active=bool(tl.override_stems),
            help_visible=self.session.help_visible,
        )

    def _allow_overwrite(self) -> bool:
        return allow_overwrite_for_path(
            self._active_config_path,
            repo_root_example=self._repo_root_example,
        )

    def _input_blocked(self) -> bool:
        return time.monotonic() < self._input_blocked_until

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
        if self._on_z_order_change is not None:
            self._on_z_order_change(list(self.session.layer_z_order))
        self.mark_config_dirty()
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

        if stem is not None and kind in REPEAT_ROW_KINDS and self.session.layers[stem].locked:
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
        elif kind == RowKind.RENDER_OVERLAY_TITLE_FONT:
            self._cycle_render_overlay_title_font(forward=forward)
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
        elif kind == RowKind.RENDER_OVERLAY_BODY_FONT:
            self._cycle_render_overlay_body_font(forward=forward)
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
        elif kind == RowKind.RENDER_TIMELINE_HEADER:
            if ctrl:
                self._set_render_timeline_enabled(forward)
                return
            if forward:
                self._open_timeline_panel()
            else:
                self._close_timeline_panel()

    def _step_directory(self, stem: str, *, forward: bool) -> None:
        layer = self.session.layers[stem]
        playlist = layer.playlist
        delta = 1 if forward else -1
        if playlist.step_sibling(delta, preset_root=self.preset_root):
            self.mark_config_dirty()
            if self._on_preset_change is not None:
                self._on_preset_change(stem, playlist)

    def _enter_directory(self, stem: str) -> None:
        layer = self.session.layers[stem]
        playlist = layer.playlist
        if playlist.enter_child(self.preset_root):
            self.mark_config_dirty()
            if self._on_preset_change is not None:
                self._on_preset_change(stem, playlist)

    def _parent_directory(self, stem: str) -> None:
        layer = self.session.layers[stem]
        playlist = layer.playlist
        if playlist.go_parent(self.preset_root):
            self.mark_config_dirty()
            if self._on_preset_change is not None:
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
        self.mark_config_dirty()
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
        self.mark_config_dirty()
        if self._on_blend_change is not None:
            self._on_blend_change(stem, layer.blend_mode)

    def _toggle_locked(self, stem: str) -> None:
        layer = self.session.layers[stem]
        layer.locked = not layer.locked
        self.mark_config_dirty()

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
        if not expanded and focus_kind in RENDER_OVERLAY_ALL_SUB_ROW_KINDS:
            self.focus_index = self._render_overlay_header_index()

    def _set_render_overlay_enabled(self, enabled: bool) -> None:
        ro = self.session.render_overlay
        if ro.enabled == enabled:
            return
        focus_kind = self._focused_row_kind()
        ro.enabled = enabled
        self.mark_config_dirty()
        if not enabled:
            self.session.render_overlay_solo = False
            ro.expanded = False
            if focus_kind in RENDER_OVERLAY_ALL_SUB_ROW_KINDS:
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
        self.mark_config_dirty()

    def _set_render_overlay_title_expanded(self, expanded: bool) -> None:
        ro = self.session.render_overlay
        if ro.title_expanded == expanded:
            return
        focus_kind = self._focused_row_kind()
        ro.title_expanded = expanded
        if not expanded and focus_kind in RENDER_OVERLAY_TITLE_NESTED_KINDS:
            self.focus_index = self._render_overlay_title_header_index()

    def _set_render_overlay_body_expanded(self, expanded: bool) -> None:
        ro = self.session.render_overlay
        if ro.body_expanded == expanded:
            return
        focus_kind = self._focused_row_kind()
        ro.body_expanded = expanded
        if not expanded and focus_kind in RENDER_OVERLAY_BODY_NESTED_KINDS:
            self.focus_index = self._render_overlay_body_header_index()

    def _set_render_overlay_title_font_size(self, size: int) -> None:
        self.session.render_overlay.title_font_size = max(1, size)
        self.mark_config_dirty()

    def _cycle_render_overlay_title_font(self, *, forward: bool) -> None:
        ro = self.session.render_overlay
        ro.title_font = cycle_render_overlay_font(ro.title_font, forward=forward)
        self.mark_config_dirty()

    def _set_render_overlay_title_margin_bottom(self, margin: int) -> None:
        self.session.render_overlay.title_margin_bottom = max(0, margin)
        self.mark_config_dirty()

    def _set_render_overlay_body_font_size(self, size: int) -> None:
        self.session.render_overlay.body_font_size = max(1, size)
        self.mark_config_dirty()

    def _cycle_render_overlay_body_font(self, *, forward: bool) -> None:
        ro = self.session.render_overlay
        ro.body_font = cycle_render_overlay_font(ro.body_font, forward=forward)
        self.mark_config_dirty()

    def _set_render_overlay_opacity(self, pct: int) -> None:
        self.session.render_overlay.opacity_pct = max(0, min(100, pct))
        self.mark_config_dirty()

    def _set_render_overlay_border_width(self, width: int) -> None:
        self.session.render_overlay.border_width = max(0, width)
        self.mark_config_dirty()

    def _set_render_overlay_start_delay(self, start_delay: float) -> None:
        self.session.render_overlay.start_delay = max(0.0, start_delay)
        self.mark_config_dirty()

    def _set_render_overlay_display_time(self, display_time: float) -> None:
        self.session.render_overlay.display_time = max(0.0, display_time)

    def _render_post_fx_header_index(self) -> int:
        view = self.build_view_state(paused=self.playback.paused)
        return find_row_by_kind(view, RowKind.RENDER_POST_FX_HEADER)

    def _refocus_render_post_fx_header_if_sub_row(self) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        if row_kind(view, self.focus_index) in RENDER_POST_FX_SUB_ROW_KINDS:
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
        self.mark_config_dirty()
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
        self.mark_config_dirty()

    def _set_render_post_fx_fade_out(self, fade_out: float) -> None:
        self.session.render_post_fx.fade_out = max(0.0, fade_out)
        self.mark_config_dirty()

    def _render_timeline_header_index(self) -> int:
        view = self.build_view_state(paused=self.playback.paused)
        return find_row_by_kind(view, RowKind.RENDER_TIMELINE_HEADER)

    def _refocus_render_timeline_header_if_sub_row(self) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        if row_kind(view, self.focus_index) in RENDER_TIMELINE_SUB_ROW_KINDS:
            self.focus_index = self._render_timeline_header_index()

    def _set_render_timeline_enabled(self, enabled: bool) -> None:
        tl = self.session.timeline
        if tl.enabled == enabled:
            return
        tl.enabled = enabled
        self.mark_config_dirty()
        if not enabled:
            self._close_timeline_panel()
        if self._on_timeline_enabled_change is not None:
            self._on_timeline_enabled_change()

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
        if self.session.timeline.enabled:
            now = time.monotonic()
            self._toast_message = "Timeline controls layer visibility"
            self._toast_deadline = now + TOAST_DURATION_SEC
            return
        layer = self.session.layers[stem]
        if layer.enabled == enabled:
            return
        layer.enabled = enabled
        self.mark_config_dirty()
        if not enabled:
            layer.expanded = False
            self._refocus_track_header_if_sub_row(stem)
        if self._on_layer_enabled_change is not None:
            self._on_layer_enabled_change(stem, layer.enabled)

    def _set_opacity(self, stem: str, pct: int) -> None:
        layer = self.session.layers[stem]
        layer.opacity_pct = max(0, min(100, pct))
        self.mark_config_dirty()
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
        self.mark_config_dirty()
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
        self.mark_config_dirty()
        if self._on_beat_change is not None:
            self._on_beat_change(stem, layer.beat_sensitivity)

    def _do_seek(self, delta_sec: float) -> None:
        if self._on_seek is not None:
            self._on_seek(delta_sec)
        else:
            seek(self.playback, delta_sec, self.duration_sec)

    def _prompt_save(self) -> None:
        if not self._allow_overwrite():
            self._trigger_save_new()
            return

        self._save_choice.prompt(
            SaveChoiceRequest(
                on_overwrite=self._prompt_overwrite,
                on_save_as_new=self._trigger_save_new,
            )
        )

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
            self.clear_config_dirty()
        self._show_save_toast(f"Config saved to {filename}")
        self._finish_quit_after_save()

    def _quit_save(self) -> None:
        self._quit_after_save = True
        self._prompt_save()

    def _quit_discard(self) -> None:
        self._pending_exit = True

    def _finish_quit_after_save(self) -> None:
        if self._quit_after_save:
            self._quit_after_save = False
            self.clear_config_dirty()
            self._pending_exit = True

    def _prompt_overwrite(self) -> None:
        active_path = self._active_config_path
        basename = (
            active_path.name
            if active_path is not None
            else VIZ_CONFIG_FILENAME
        )
        message = f"Overwrite {basename}?"

        def on_confirm() -> None:
            target = active_path or Path(VIZ_CONFIG_FILENAME)
            if self._on_overwrite_config is not None:
                written = self._on_overwrite_config(target)
            else:
                written = basename
            if not written:
                written = basename
            self.clear_config_dirty()
            self._show_save_toast(f"Config overwritten: {written}")
            self._finish_quit_after_save()

        def on_cancel() -> None:
            if self._quit_after_save:
                self._quit_after_save = False

        self._confirm.prompt(
            ConfirmRequest(message=message, on_confirm=on_confirm, on_cancel=on_cancel)
        )

    def show_toast(self, message: str) -> None:
        now = time.monotonic()
        self._toast_message = message
        self._toast_deadline = now + TOAST_DURATION_SEC
        self._input_blocked_until = now + TOAST_DURATION_SEC

    def _open_timeline_panel(self, *, enter_submenu: bool = False) -> None:
        tl = self.session.timeline
        if not tl.enabled:
            self.show_toast("Enable timeline in Render: TIMELINE (Ctrl+Right)")
            return
        tl.panel_open = True
        if enter_submenu:
            tl.submenu_focused = True
            tl.focus_row = 0
        else:
            tl.submenu_focused = False

    def _close_timeline_panel(self) -> None:
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

    def _show_save_toast(self, message: str) -> None:
        print(message, file=sys.stderr)
        self.show_toast(message)
