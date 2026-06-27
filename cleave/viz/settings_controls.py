"""Settings row mutations for live tuning."""

from __future__ import annotations

from dataclasses import replace

from cleave.config import CleaveConfig
from cleave.config_schema import (
    UI_WIDTH_MODES,
    VISUALIZER_RENDER_MODES,
    clamp_ui_fade,
    clamp_ui_width,
)
from cleave.viz.session import TuningSession


class SettingsControls:
    """Mutations for settings rows."""

    def __init__(
        self,
        session: TuningSession,
        cfg: CleaveConfig,
    ) -> None:
        self.session = session
        self.cfg = cfg

    def set_expanded(self, expanded: bool) -> None:
        settings = self.session.settings
        if settings.expanded == expanded:
            return
        settings.expanded = expanded

    def cycle_render_mode(self, *, forward: bool) -> None:
        modes = VISUALIZER_RENDER_MODES
        current = self.cfg.visualizer.render_mode
        try:
            index = modes.index(current)
        except ValueError:
            index = 0
        if forward:
            new_mode = modes[(index + 1) % len(modes)]
        else:
            new_mode = modes[(index - 1) % len(modes)]
        self.cfg.visualizer = replace(self.cfg.visualizer, render_mode=new_mode)

    def cycle_ui_width_mode(self, *, forward: bool) -> None:
        modes = UI_WIDTH_MODES
        current = self.cfg.visualizer.ui_width_mode
        try:
            index = modes.index(current)
        except ValueError:
            index = 0
        if forward:
            new_mode = modes[(index + 1) % len(modes)]
        else:
            new_mode = modes[(index - 1) % len(modes)]
        self.cfg.visualizer = replace(self.cfg.visualizer, ui_width_mode=new_mode)

    def adjust_ui_fade(self, *, forward: bool, ctrl: bool) -> None:
        step = 5.0 if ctrl else 1.0
        delta = step if forward else -step
        current = self.cfg.visualizer.ui_fade
        new_value = clamp_ui_fade(current + delta)
        self.cfg.visualizer = replace(self.cfg.visualizer, ui_fade=new_value)

    def adjust_ui_width(self, *, forward: bool, ctrl: bool) -> None:
        step = 5 if ctrl else 1
        delta = step if forward else -step
        current = self.cfg.visualizer.ui_width
        new_value = clamp_ui_width(current + delta)
        self.cfg.visualizer = replace(self.cfg.visualizer, ui_width=new_value)
