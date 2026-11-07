"""Settings row mutations for live tuning."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from cleave.config import CleaveConfig, EditorConfig
from cleave.config_schema.editor import (
    COLUMN_SIDES,
    EDITOR_PREVIEW_QUALITIES,
    clamp_editor_height,
    clamp_editor_width,
    clamp_residual_latency_ms,
    clamp_navigator_height,
    clamp_ui_scale,
    clamp_shell_column_width,
    clamp_notification_display_sec,
    clamp_upscale,
)
from cleave.user_config import persist_editor_settings
from cleave.viz.session import TuningSession
from cleave.viz.shell_layout import navigator_row_px
from cleave.viz.theme import set_ui_scale_percent

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
        # Last drawn navigator height and stack band, so stepping the
        # navigator height starts from what is on screen.
        self._drawn_navigator_px = 0
        self._stack_band_px = 0

    def note_shell_stack(self, navigator_px: int, band_px: int) -> None:
        """Remember the frame's navigator height and navigator+inspector band."""
        self._drawn_navigator_px = max(0, int(navigator_px))
        self._stack_band_px = max(0, int(band_px))

    def adjust_residual_latency_ms(self, *, forward: bool, large: bool) -> None:
        step = 50 if large else 10
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

    def adjust_editor_window_width(self, *, forward: bool, large: bool) -> None:
        step = 100 if large else 10
        delta = step if forward else -step
        current = self.cfg.editor.width
        self._commit_editor_window(
            replace(self.cfg.editor, width=clamp_editor_width(current + delta))
        )

    def adjust_editor_window_height(self, *, forward: bool, large: bool) -> None:
        step = 100 if large else 10
        delta = step if forward else -step
        current = self.cfg.editor.height
        self._commit_editor_window(
            replace(self.cfg.editor, height=clamp_editor_height(current + delta))
        )

    def adjust_editor_window_upscale(self, *, forward: bool, large: bool) -> None:
        step = 0.5 if large else 0.1
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

    def cycle_navigator_side(self, *, forward: bool) -> None:
        self._cycle_column_side("navigator_side", forward=forward)

    def cycle_help_side(self, *, forward: bool) -> None:
        self._cycle_column_side("help_side", forward=forward)

    def _cycle_column_side(self, field: str, *, forward: bool) -> None:
        sides = COLUMN_SIDES
        current = getattr(self.cfg.editor, field)
        try:
            index = sides.index(current)
        except ValueError:
            index = 0
        step = 1 if forward else -1
        new_side = sides[(index + step) % len(sides)]
        self.cfg.editor = replace(self.cfg.editor, **{field: new_side})
        persist_editor_settings(self.cfg)

    def set_shell_column_widths(self, insp: int, help_width: int) -> None:
        self.cfg.editor = replace(
            self.cfg.editor,
            inspector_width=clamp_shell_column_width(insp),
            help_width=clamp_shell_column_width(help_width),
        )
        persist_editor_settings(self.cfg)

    def adjust_navigator_height(self, *, forward: bool, large: bool) -> None:
        """Step the navigator height from the drawn height.

        Fit to rows sits below the one-row minimum: Left from the minimum
        returns to fit, and a step from fit starts at the drawn height.
        """
        step = 50 if large else 10
        row = navigator_row_px()
        band = self._stack_band_px
        max_px = band - row if band >= row * 2 else None
        current = self.cfg.editor.navigator_height
        base = current if current > 0 else self._drawn_navigator_px
        if base <= 0:
            base = row
        if max_px is not None:
            base = min(base, max_px)
        base = max(row, base)
        if not forward and current > 0 and base <= row:
            new_value = 0
        else:
            new_value = base + (step if forward else -step)
            if max_px is not None:
                new_value = min(new_value, max_px)
            new_value = max(row, new_value)
        if new_value == current:
            return
        self.set_navigator_height(new_value)

    def set_navigator_height(self, height: int) -> None:
        self.cfg.editor = replace(
            self.cfg.editor, navigator_height=clamp_navigator_height(height)
        )
        persist_editor_settings(self.cfg)

    def adjust_ui_scale(self, *, forward: bool, large: bool) -> None:
        step = 50 if large else 10
        current = self.cfg.editor.ui_scale
        new_value = clamp_ui_scale(current + (step if forward else -step))
        if new_value == current:
            return
        self.cfg.editor = replace(self.cfg.editor, ui_scale=new_value)
        set_ui_scale_percent(new_value)
        persist_editor_settings(self.cfg)

    def adjust_notification_display_sec(self, *, forward: bool, large: bool) -> None:
        step = 5 if large else 1
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

