"""Render overlay row mutations for live tuning."""

from __future__ import annotations

from collections.abc import Callable

from cleave.config import RENDER_OVERLAY_POSITIONS
from cleave.viz.focus_context import FocusContext
from cleave.viz.fonts import cycle_render_overlay_font
from cleave.viz.overlay import find_row_by_kind
from cleave.viz.row_semantics import (
    RENDER_OVERLAY_ALL_SUB_ROW_KINDS,
    RENDER_OVERLAY_BODY_NESTED_KINDS,
    RENDER_OVERLAY_TITLE_NESTED_KINDS,
    RowKind,
)
from cleave.viz.session import TuningSession


class RenderOverlayControls:
    """Mutations for render overlay rows."""

    def __init__(
        self,
        session: TuningSession,
        *,
        focus_context: FocusContext,
        focused_row_kind: Callable[[], RowKind | None],
    ) -> None:
        self.session = session
        self._focus = focus_context
        self._focused_row_kind = focused_row_kind

    def _render_overlay_header_index(self) -> int:
        view = self._focus.build_view_state(paused=self._focus.is_paused())
        return find_row_by_kind(view, RowKind.RENDER_OVERLAY_HEADER)

    def _render_overlay_title_header_index(self) -> int:
        view = self._focus.build_view_state(paused=self._focus.is_paused())
        return find_row_by_kind(view, RowKind.RENDER_OVERLAY_TITLE_HEADER)

    def _render_overlay_body_header_index(self) -> int:
        view = self._focus.build_view_state(paused=self._focus.is_paused())
        return find_row_by_kind(view, RowKind.RENDER_OVERLAY_BODY_HEADER)

    def set_expanded(self, expanded: bool) -> None:
        ro = self.session.render_overlay
        if ro.expanded == expanded:
            return
        focus_kind = self._focused_row_kind()
        ro.expanded = expanded
        if not expanded and focus_kind in RENDER_OVERLAY_ALL_SUB_ROW_KINDS:
            self._focus.set_focus_index(self._render_overlay_header_index())

    def set_enabled(self, enabled: bool) -> None:
        ro = self.session.render_overlay
        if ro.enabled == enabled:
            return
        focus_kind = self._focused_row_kind()
        ro.enabled = enabled
        if not enabled:
            self.session.render_overlay_solo = False
            ro.expanded = False
            if focus_kind in RENDER_OVERLAY_ALL_SUB_ROW_KINDS:
                self._focus.set_focus_index(self._render_overlay_header_index())

    def enter_solo(self) -> None:
        if self.session.render_overlay_solo:
            return
        self.session.render_overlay_solo = True

    def exit_solo(self) -> None:
        if not self.session.render_overlay_solo:
            return
        self.session.render_overlay_solo = False

    def cycle_position(self, *, forward: bool) -> None:
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

    def set_title_expanded(self, expanded: bool) -> None:
        ro = self.session.render_overlay
        if ro.title_expanded == expanded:
            return
        focus_kind = self._focused_row_kind()
        ro.title_expanded = expanded
        if not expanded and focus_kind in RENDER_OVERLAY_TITLE_NESTED_KINDS:
            self._focus.set_focus_index(self._render_overlay_title_header_index())

    def set_body_expanded(self, expanded: bool) -> None:
        ro = self.session.render_overlay
        if ro.body_expanded == expanded:
            return
        focus_kind = self._focused_row_kind()
        ro.body_expanded = expanded
        if not expanded and focus_kind in RENDER_OVERLAY_BODY_NESTED_KINDS:
            self._focus.set_focus_index(self._render_overlay_body_header_index())

    def set_title_font_size(self, size: int) -> None:
        self.session.render_overlay.title_font_size = max(1, size)

    def cycle_title_font(self, *, forward: bool) -> None:
        ro = self.session.render_overlay
        ro.title_font = cycle_render_overlay_font(ro.title_font, forward=forward)

    def set_title_margin_bottom(self, margin: int) -> None:
        self.session.render_overlay.title_margin_bottom = max(0, margin)

    def set_body_font_size(self, size: int) -> None:
        self.session.render_overlay.body_font_size = max(1, size)

    def cycle_body_font(self, *, forward: bool) -> None:
        ro = self.session.render_overlay
        ro.body_font = cycle_render_overlay_font(ro.body_font, forward=forward)

    def set_opacity(self, pct: int) -> None:
        self.session.render_overlay.opacity_pct = max(0, min(100, pct))

    def set_border_width(self, width: int) -> None:
        self.session.render_overlay.border_width = max(0, width)

    def set_start_delay(self, start_delay: float) -> None:
        self.session.render_overlay.start_delay = max(0.0, start_delay)

    def set_display_time(self, display_time: float) -> None:
        self.session.render_overlay.display_time = max(0.0, display_time)
