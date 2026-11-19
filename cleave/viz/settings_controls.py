"""Settings row mutations for live tuning."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from cleave.config import CleaveConfig, EditorPreviewQuality
from cleave.config_schema.editor import (
    COLUMN_SIDES,
    DEFAULT_HELP_WIDTH,
    DEFAULT_INSPECTOR_WIDTH,
    DEFAULT_NAVIGATOR_HEIGHT,
    DEFAULT_TIMELINE_HEIGHT,
    EDITOR_PREVIEW_QUALITIES,
    NAVIGATOR_EXPAND_CLICKS,
    clamp_audio_latency_ms,
    clamp_tap_latency_ms,
    clamp_navigator_height,
    clamp_timeline_height,
    clamp_ui_scale,
    clamp_shell_column_width,
    clamp_notification_display_sec,
)
from cleave.user_config import persist_editor_settings
from cleave.choice import step_choice
from cleave.viz.session import TuningSession
from cleave.viz.theme import (
    palette_for_theme,
    set_palette,
    set_ui_scale_percent,
    theme_ids,
)
from cleave.viz.tooltips import set_tooltips_enabled

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

    def adjust_audio_latency_ms(self, *, forward: bool, large: bool) -> None:
        step = 50 if large else 10
        delta = step if forward else -step
        current = self.cfg.editor.audio_latency_ms
        new_value = clamp_audio_latency_ms(current + delta)
        self.cfg.editor = replace(self.cfg.editor, audio_latency_ms=new_value)
        persist_editor_settings(self.cfg)

    def set_audio_latency_ms(self, ms: int) -> None:
        self.cfg.editor = replace(
            self.cfg.editor,
            audio_latency_ms=clamp_audio_latency_ms(ms),
        )
        persist_editor_settings(self.cfg)

    def adjust_tap_latency_ms(self, *, forward: bool, large: bool) -> None:
        step = 50 if large else 10
        delta = step if forward else -step
        current = self.cfg.editor.tap_latency_ms
        new_value = clamp_tap_latency_ms(current + delta)
        self.cfg.editor = replace(self.cfg.editor, tap_latency_ms=new_value)
        persist_editor_settings(self.cfg)

    def set_tap_latency_ms(self, ms: int) -> None:
        self.cfg.editor = replace(
            self.cfg.editor,
            tap_latency_ms=clamp_tap_latency_ms(ms),
        )
        persist_editor_settings(self.cfg)

    def step_preview_quality(self, *, delta: int) -> None:
        current = self.cfg.editor.preview_quality
        new_mode = step_choice(EDITOR_PREVIEW_QUALITIES, current, delta)
        if new_mode == current:
            return
        self.cfg.editor = replace(self.cfg.editor, preview_quality=new_mode)
        persist_editor_settings(self.cfg)

    def set_preview_quality(self, mode: EditorPreviewQuality) -> None:
        if mode == self.cfg.editor.preview_quality:
            return
        self.cfg.editor = replace(self.cfg.editor, preview_quality=mode)
        persist_editor_settings(self.cfg)

    def step_navigator_side(self, *, forward: bool) -> None:
        self._step_column_side("navigator_side", forward=forward)

    def step_help_side(self, *, forward: bool) -> None:
        self._step_column_side("help_side", forward=forward)

    def step_navigator_expand_click(self, *, forward: bool) -> None:
        current = self.cfg.editor.navigator_expand_click
        new_mode = step_choice(NAVIGATOR_EXPAND_CLICKS, current, 1 if forward else -1)
        if new_mode == current:
            return
        self.cfg.editor = replace(self.cfg.editor, navigator_expand_click=new_mode)
        persist_editor_settings(self.cfg)

    def set_highlight_new_page(self, on: bool) -> None:
        if self.cfg.editor.highlight_new_page == on:
            return
        self.cfg.editor = replace(self.cfg.editor, highlight_new_page=on)
        persist_editor_settings(self.cfg)

    def set_show_tooltips(self, on: bool) -> None:
        if self.cfg.editor.show_tooltips == on:
            return
        self.cfg.editor = replace(self.cfg.editor, show_tooltips=on)
        set_tooltips_enabled(on)
        persist_editor_settings(self.cfg)

    def set_crash_log(self, on: bool) -> None:
        """Save the crash log choice. It takes effect the next time the editor starts."""
        if self.cfg.editor.crash_log == on:
            return
        self.cfg.editor = replace(self.cfg.editor, crash_log=on)
        persist_editor_settings(self.cfg)

    def _step_column_side(self, field: str, *, forward: bool) -> None:
        current = getattr(self.cfg.editor, field)
        new_side = step_choice(COLUMN_SIDES, current, 1 if forward else -1)
        if new_side == current:
            return
        self.cfg.editor = replace(self.cfg.editor, **{field: new_side})
        persist_editor_settings(self.cfg)

    def set_shell_column_widths(self, insp: int, help_width: int) -> None:
        self.cfg.editor = replace(
            self.cfg.editor,
            inspector_width=clamp_shell_column_width(insp),
            help_width=clamp_shell_column_width(help_width),
        )
        persist_editor_settings(self.cfg)

    def set_navigator_height(self, height: int) -> None:
        self.cfg.editor = replace(
            self.cfg.editor, navigator_height=clamp_navigator_height(height)
        )
        persist_editor_settings(self.cfg)

    def set_timeline_height(self, height: int) -> None:
        self.cfg.editor = replace(
            self.cfg.editor, timeline_height=clamp_timeline_height(height)
        )
        persist_editor_settings(self.cfg)

    def reset_splitter(self, which: str) -> None:
        """Put one splitter back at its default: ``insp``, ``help``, ``nav``, or ``timeline``."""
        if which == "nav":
            self.set_navigator_height(DEFAULT_NAVIGATOR_HEIGHT)
        elif which == "timeline":
            self.set_timeline_height(DEFAULT_TIMELINE_HEIGHT)
        elif which == "insp":
            self.set_shell_column_widths(
                DEFAULT_INSPECTOR_WIDTH, self.cfg.editor.help_width
            )
        elif which == "help":
            self.set_shell_column_widths(
                self.cfg.editor.inspector_width, DEFAULT_HELP_WIDTH
            )

    def reset_panel_layout(self) -> None:
        """Put every column width and band height back at its default."""
        self.cfg.editor = replace(
            self.cfg.editor,
            inspector_width=DEFAULT_INSPECTOR_WIDTH,
            help_width=DEFAULT_HELP_WIDTH,
            navigator_height=DEFAULT_NAVIGATOR_HEIGHT,
            timeline_height=DEFAULT_TIMELINE_HEIGHT,
        )
        persist_editor_settings(self.cfg)

    def step_theme(self, *, forward: bool) -> None:
        current = self.cfg.editor.theme
        new_theme = step_choice(theme_ids(), current, 1 if forward else -1)
        if new_theme == current:
            return
        self.cfg.editor = replace(self.cfg.editor, theme=new_theme)
        set_palette(palette_for_theme(new_theme))
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

