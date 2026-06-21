"""Settings row mutations for live tuning."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from cleave.config import CleaveConfig
from cleave.config_schema import VISUALIZER_RENDER_MODES
from cleave.viz.focus_context import FocusContext
from cleave.viz.overlay import find_row_by_kind
from cleave.viz.row_semantics import SETTINGS_SUB_ROW_KINDS, RowKind
from cleave.viz.session import TuningSession


class SettingsControls:
    """Mutations for settings rows."""

    def __init__(
        self,
        session: TuningSession,
        cfg: CleaveConfig,
        *,
        focus_context: FocusContext,
        focused_row_kind: Callable[[], RowKind | None],
    ) -> None:
        self.session = session
        self.cfg = cfg
        self._focus = focus_context
        self._focused_row_kind = focused_row_kind

    def _settings_header_index(self) -> int:
        view = self._focus.build_view_state(paused=self._focus.is_paused())
        return find_row_by_kind(view, RowKind.SETTINGS_HEADER)

    def set_expanded(self, expanded: bool) -> None:
        settings = self.session.settings
        if settings.expanded == expanded:
            return
        focus_kind = self._focused_row_kind()
        settings.expanded = expanded
        if not expanded and focus_kind in SETTINGS_SUB_ROW_KINDS:
            self._focus.set_focus_index(self._settings_header_index())

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
