"""Settings row mutations for live tuning."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from cleave.config import CleaveConfig, EditorConfig
from cleave.config_schema.editor import (
    UI_WIDTH_MODES,
    EDITOR_PREVIEW_QUALITIES,
    clamp_editor_height,
    clamp_editor_width,
    clamp_residual_latency_ms,
    clamp_ui_fade,
    clamp_ui_width,
    clamp_notification_display_sec,
    clamp_upscale,
)
from cleave.user_config import persist_editor_settings
from cleave.viz.session import TuningSession

EDITOR_WINDOW_RESTART_TOAST = (
    "Restart the application for changes to take effect."
)


class SettingsControls:
    """Mutations for settings rows."""

    def __init__(
        self,
        session: TuningSession,
        cfg: CleaveConfig,
        *,
        on_notification: Callable[[str], None] | None = None,
        on_notification_display_changed: Callable[[int], None] | None = None,
    ) -> None:
        self.session = session
        self.cfg = cfg
        self._on_notification = on_notification
        self._on_notification_display_changed = on_notification_display_changed

    def set_expanded(self, expanded: bool) -> None:
        settings = self.session.settings
        if settings.expanded == expanded:
            return
        settings.expanded = expanded

    def set_editor_window_expanded(self, expanded: bool) -> None:
        settings = self.session.settings
        if settings.editor_window_expanded == expanded:
            return
        settings.editor_window_expanded = expanded

    def set_ui_expanded(self, expanded: bool) -> None:
        settings = self.session.settings
        if settings.ui_expanded == expanded:
            return
        settings.ui_expanded = expanded

    def set_latency_compensation_expanded(self, expanded: bool) -> None:
        settings = self.session.settings
        if settings.latency_compensation_expanded == expanded:
            return
        settings.latency_compensation_expanded = expanded

    def adjust_residual_latency_ms(self, *, forward: bool, ctrl: bool) -> None:
        step = 50 if ctrl else 10
        delta = step if forward else -step
        current = self.cfg.editor.residual_latency_ms
        new_value = clamp_residual_latency_ms(current + delta)
        self.cfg.editor = replace(self.cfg.editor, residual_latency_ms=new_value)
        persist_editor_settings(self.cfg)

    def set_residual_latency_ms(self, ms: int) -> None:
        self.cfg.editor = replace(
            self.cfg.editor,
            residual_latency_ms=clamp_residual_latency_ms(ms),
        )
        persist_editor_settings(self.cfg)

    def adjust_editor_window_width(self, *, forward: bool, ctrl: bool) -> None:
        step = 100 if ctrl else 10
        delta = step if forward else -step
        current = self.cfg.editor.width
        self._commit_editor_window(
            replace(self.cfg.editor, width=clamp_editor_width(current + delta))
        )

    def adjust_editor_window_height(self, *, forward: bool, ctrl: bool) -> None:
        step = 100 if ctrl else 10
        delta = step if forward else -step
        current = self.cfg.editor.height
        self._commit_editor_window(
            replace(self.cfg.editor, height=clamp_editor_height(current + delta))
        )

    def adjust_editor_window_upscale(self, *, forward: bool, ctrl: bool) -> None:
        step = 0.5 if ctrl else 0.1
        delta = step if forward else -step
        current = self.cfg.editor.upscale
        self._commit_editor_window(
            replace(
                self.cfg.editor,
                upscale=clamp_upscale(round(current + delta, 1)),
            )
        )

    def _commit_editor_window(self, editor: EditorConfig) -> None:
        if editor == self.cfg.editor:
            return
        self.cfg.editor = editor
        persist_editor_settings(self.cfg)
        if self._on_notification is not None:
            self._on_notification(EDITOR_WINDOW_RESTART_TOAST)

    def cycle_preview_quality(self, *, forward: bool) -> None:
        modes = EDITOR_PREVIEW_QUALITIES
        current = self.cfg.editor.preview_quality
        try:
            index = modes.index(current)
        except ValueError:
            index = 0
        if forward:
            new_mode = modes[(index + 1) % len(modes)]
        else:
            new_mode = modes[(index - 1) % len(modes)]
        self.cfg.editor = replace(self.cfg.editor, preview_quality=new_mode)
        persist_editor_settings(self.cfg)

    def cycle_ui_width_mode(self, *, forward: bool) -> None:
        modes = UI_WIDTH_MODES
        current = self.cfg.editor.ui_width_mode
        try:
            index = modes.index(current)
        except ValueError:
            index = 0
        if forward:
            new_mode = modes[(index + 1) % len(modes)]
        else:
            new_mode = modes[(index - 1) % len(modes)]
        self.cfg.editor = replace(self.cfg.editor, ui_width_mode=new_mode)
        persist_editor_settings(self.cfg)

    def adjust_ui_fade(self, *, forward: bool, ctrl: bool) -> None:
        step = 5.0 if ctrl else 1.0
        delta = step if forward else -step
        current = self.cfg.editor.ui_fade
        new_value = clamp_ui_fade(current + delta)
        self.cfg.editor = replace(self.cfg.editor, ui_fade=new_value)
        persist_editor_settings(self.cfg)

    def adjust_notification_display_sec(self, *, forward: bool, ctrl: bool) -> None:
        step = 5 if ctrl else 1
        delta = step if forward else -step
        current = self.cfg.editor.notification_display_sec
        new_value = clamp_notification_display_sec(current + delta)
        if new_value == current:
            return
        self.cfg.editor = replace(
            self.cfg.editor, notification_display_sec=new_value
        )
        persist_editor_settings(self.cfg)
        if self._on_notification_display_changed is not None:
            self._on_notification_display_changed(new_value)

    def adjust_ui_width(self, *, forward: bool, ctrl: bool) -> None:
        step = 5 if ctrl else 1
        delta = step if forward else -step
        current = self.cfg.editor.ui_width
        new_value = clamp_ui_width(current + delta)
        self.cfg.editor = replace(self.cfg.editor, ui_width=new_value)
        persist_editor_settings(self.cfg)
