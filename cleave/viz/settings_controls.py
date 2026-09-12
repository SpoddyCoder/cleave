"""Settings row mutations for live tuning."""

from __future__ import annotations

from dataclasses import replace

from cleave.config import CleaveConfig
from cleave.config_schema.editor import (
    UI_WIDTH_MODES,
    EDITOR_PREVIEW_QUALITIES,
    clamp_editor_height,
    clamp_editor_width,
    clamp_residual_latency_ms,
    clamp_ui_fade,
    clamp_ui_width,
    clamp_upscale,
    editor_display_size,
)
from cleave.user_config import persist_editor_settings
from cleave.viz.modal import ModalHost, ModalLabeledLine
from cleave.viz.session import TuningSession

_EDITOR_WINDOW_CONFIRM_MESSAGE = (
    "Restart the application for changes to take effect."
)


class SettingsControls:
    """Mutations for settings rows."""

    def __init__(
        self,
        session: TuningSession,
        cfg: CleaveConfig,
        modal_host: ModalHost,
    ) -> None:
        self.session = session
        self.cfg = cfg
        self._modal = modal_host

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

    def set_residual_latency_ms(self, ms: int) -> None:
        self.cfg.editor = replace(
            self.cfg.editor,
            residual_latency_ms=clamp_residual_latency_ms(ms),
        )

    def adjust_editor_window_width(self, *, forward: bool, ctrl: bool) -> None:
        step = 100 if ctrl else 10
        delta = step if forward else -step
        current = self.cfg.editor.width
        new_value = clamp_editor_width(current + delta)
        self.cfg.editor = replace(self.cfg.editor, width=new_value)

    def adjust_editor_window_height(self, *, forward: bool, ctrl: bool) -> None:
        step = 100 if ctrl else 10
        delta = step if forward else -step
        current = self.cfg.editor.height
        new_value = clamp_editor_height(current + delta)
        self.cfg.editor = replace(self.cfg.editor, height=new_value)

    def adjust_editor_window_upscale(self, *, forward: bool, ctrl: bool) -> None:
        step = 0.5 if ctrl else 0.1
        delta = step if forward else -step
        current = self.cfg.editor.upscale
        new_value = clamp_upscale(round(current + delta, 1))
        self.cfg.editor = replace(self.cfg.editor, upscale=new_value)

    def prompt_apply_editor_window(self) -> None:
        editor = self.cfg.editor
        display_w, display_h = editor_display_size(
            editor.width, editor.height, upscale=editor.upscale
        )
        self._modal.prompt_yes_no(
            _EDITOR_WINDOW_CONFIRM_MESSAGE,
            on_confirm=lambda: persist_editor_settings(self.cfg),
            labeled_lines=(
                ModalLabeledLine("width", str(editor.width)),
                ModalLabeledLine("height", str(editor.height)),
                ModalLabeledLine("upscale", f"{editor.upscale:.1f}"),
                ModalLabeledLine("display size", f"{display_w}x{display_h}"),
            ),
        )

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

    def adjust_ui_fade(self, *, forward: bool, ctrl: bool) -> None:
        step = 5.0 if ctrl else 1.0
        delta = step if forward else -step
        current = self.cfg.editor.ui_fade
        new_value = clamp_ui_fade(current + delta)
        self.cfg.editor = replace(self.cfg.editor, ui_fade=new_value)

    def adjust_ui_width(self, *, forward: bool, ctrl: bool) -> None:
        step = 5 if ctrl else 1
        delta = step if forward else -step
        current = self.cfg.editor.ui_width
        new_value = clamp_ui_width(current + delta)
        self.cfg.editor = replace(self.cfg.editor, ui_width=new_value)
