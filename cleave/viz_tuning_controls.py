"""Focus-driven live tuning input for the Milkdrop visualizer overlay."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from cleave.config import clamp_beat_sensitivity
from cleave.gl_compositor import BlendMode
from cleave.preset_playlist import (
    PresetPlaylist,
    directory_display,
    preset_filename_display,
)
from cleave.viz_confirm import ConfirmDialog, ConfirmRequest
from cleave.viz_key_repeat import KeyRepeatController
from cleave.viz_playback import PlaybackState, current_sec, seek, toggle_pause
from cleave.viz_tuning_overlay import (
    RowKind,
    TrackBlock,
    TuningViewState,
    navigable_row_indices,
    quick_nav_row_indices,
    row_kind,
    row_stem,
)

TOAST_DURATION_SEC = 5.0
SEEK_SHORT = 10
SEEK_LONG = 30

_BLEND_MODES: tuple[BlendMode, ...] = ("alpha", "add")
_REPEAT_ROW_KINDS = frozenset(
    {
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_BEAT,
    }
)
_DEFAULT_SAVE_FILENAME = "unnamed-1.cleave.config.yaml"


def config_path_display(path: Path | None) -> str:
    """Active config path for the footer header (truncation happens at draw time)."""
    return path.as_posix() if path is not None else "cleave.config.yaml"


def _mod_ctrl(mod: int) -> bool:
    return bool(mod & (pygame.KMOD_CTRL | pygame.KMOD_LCTRL | pygame.KMOD_RCTRL))


@dataclass
class LayerRuntime:
    playlist: PresetPlaylist
    opacity_pct: int = 100
    blend_mode: BlendMode = "alpha"
    beat_sensitivity: float = 1.0
    enabled: bool = True


@dataclass
class TuningSession:
    layer_z_order: list[str]
    layers: dict[str, LayerRuntime] = field(default_factory=dict)


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
        on_beat_change: Callable[[str, float], None] | None = None,
        on_z_order_change: Callable[[list[str]], None] | None = None,
        on_seek: Callable[[float], None] | None = None,
        on_save_new_config: Callable[[], Path | None] | None = None,
        on_overwrite_config: Callable[[Path], str | None] | None = None,
        launch_config_path: Path | None = None,
        allow_overwrite: bool = True,
    ) -> None:
        self.session = session
        self.preset_root = preset_root
        self.playback = playback
        self.duration_sec = duration_sec
        self._active_config_path = launch_config_path
        self._on_preset_change = on_preset_change
        self._on_blend_change = on_blend_change
        self._on_opacity_change = on_opacity_change
        self._on_layer_enabled_change = on_layer_enabled_change
        self._on_beat_change = on_beat_change
        self._on_z_order_change = on_z_order_change
        self._on_seek = on_seek
        self._on_save_new_config = on_save_new_config
        self._on_overwrite_config = on_overwrite_config
        self._allow_overwrite = allow_overwrite

        self.focus_index = 0
        self.move_mode_stem: str | None = None
        self._toast_message: str | None = None
        self._toast_deadline = 0.0
        self._input_blocked_until = 0.0
        self._key_repeat = KeyRepeatController()
        self._confirm = ConfirmDialog()

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Handle a key down event. Return False when the caller should quit (Esc)."""
        if event.type != pygame.KEYDOWN:
            return True

        if self._confirm.active:
            self._confirm.handle_keydown(event)
            return True

        if event.key == pygame.K_ESCAPE:
            return False

        if self._input_blocked():
            return True

        if event.key == pygame.K_SPACE:
            toggle_pause(self.playback, self.duration_sec)
            return True

        if self.move_mode_stem is not None:
            if event.key == pygame.K_UP:
                self._swap_stem_in_z_order(self.move_mode_stem, -1)
                return True
            if event.key == pygame.K_DOWN:
                self._swap_stem_in_z_order(self.move_mode_stem, 1)
                return True
            if event.key == pygame.K_RETURN:
                self._confirm_move_mode()
                return True

        if event.key in (pygame.K_UP, pygame.K_DOWN) and _mod_ctrl(event.mod):
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
            if kind in _REPEAT_ROW_KINDS:
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
                    self.move_mode_stem = stem
                return True
            if kind == RowKind.SAVE_AS_NEW_CONFIG:
                self._trigger_save_new()
                return True
            if kind == RowKind.OVERWRITE_CONFIG and self._allow_overwrite:
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
                beat_sensitivity=layer.beat_sensitivity,
                enabled=layer.enabled,
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
            allow_overwrite=self._allow_overwrite,
            active_config_label=config_path_display(self._active_config_path),
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

    def _apply_horizontal(self, key: int, mod: int, kind: RowKind) -> None:
        view = self.build_view_state(paused=self.playback.paused)
        stem = row_stem(view, self.focus_index)
        ctrl = _mod_ctrl(mod)
        forward = key == pygame.K_RIGHT

        if kind == RowKind.TRACK_HEADER:
            if stem is None:
                return
            self._toggle_enabled(stem)
        elif kind == RowKind.TRACK_PRESET_DIR:
            if stem is None:
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

    def _step_directory(self, stem: str, *, forward: bool) -> None:
        layer = self.session.layers[stem]
        playlist = layer.playlist
        delta = 1 if forward else -1
        if playlist.step_sibling(delta) and self._on_preset_change is not None:
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
        index = _BLEND_MODES.index(layer.blend_mode)
        if forward:
            layer.blend_mode = _BLEND_MODES[(index + 1) % len(_BLEND_MODES)]
        else:
            layer.blend_mode = _BLEND_MODES[(index - 1) % len(_BLEND_MODES)]
        if self._on_blend_change is not None:
            self._on_blend_change(stem, layer.blend_mode)

    def _toggle_enabled(self, stem: str) -> None:
        layer = self.session.layers[stem]
        layer.enabled = not layer.enabled
        if self._on_layer_enabled_change is not None:
            self._on_layer_enabled_change(stem, layer.enabled)

    def _set_opacity(self, stem: str, pct: int) -> None:
        layer = self.session.layers[stem]
        layer.opacity_pct = max(0, min(100, pct))
        if self._on_opacity_change is not None:
            self._on_opacity_change(stem, layer.opacity_pct)

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
        basename = active_path.name if active_path is not None else "cleave.config.yaml"
        message = f"Overwrite {basename}?"

        def on_confirm() -> None:
            target = active_path or Path("cleave.config.yaml")
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
