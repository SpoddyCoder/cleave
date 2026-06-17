"""Render post-FX row mutations for live tuning."""

from __future__ import annotations

from collections.abc import Callable

from cleave.viz.overlay import TuningViewState, find_row_by_kind, row_kind
from cleave.viz.row_semantics import RENDER_POST_FX_SUB_ROW_KINDS, RowKind
from cleave.viz.session import TuningSession


class RenderPostFxControls:
    """Mutations for render post-FX rows."""

    def __init__(
        self,
        session: TuningSession,
        *,
        get_focus_index: Callable[[], int],
        set_focus_index: Callable[[int], None],
        build_view_state: Callable[..., TuningViewState],
        is_paused: Callable[[], bool],
    ) -> None:
        self.session = session
        self._get_focus_index = get_focus_index
        self._set_focus_index = set_focus_index
        self._build_view_state = build_view_state
        self._is_paused = is_paused

    def _render_post_fx_header_index(self) -> int:
        view = self._build_view_state(paused=self._is_paused())
        return find_row_by_kind(view, RowKind.RENDER_POST_FX_HEADER)

    def _refocus_render_post_fx_header_if_sub_row(self) -> None:
        view = self._build_view_state(paused=self._is_paused())
        if row_kind(view, self._get_focus_index()) in RENDER_POST_FX_SUB_ROW_KINDS:
            self._set_focus_index(self._render_post_fx_header_index())

    def set_expanded(self, expanded: bool) -> None:
        pp = self.session.render_post_fx
        if pp.expanded == expanded:
            return
        pp.expanded = expanded
        if not expanded:
            self._refocus_render_post_fx_header_if_sub_row()

    def set_enabled(self, enabled: bool) -> None:
        pp = self.session.render_post_fx
        if pp.enabled == enabled:
            return
        pp.enabled = enabled
        if not enabled:
            self.session.render_post_fx_solo = False
            pp.expanded = False
            self._refocus_render_post_fx_header_if_sub_row()

    def enter_solo(self) -> None:
        if self.session.render_post_fx_solo:
            return
        self.session.render_post_fx_solo = True

    def exit_solo(self) -> None:
        if not self.session.render_post_fx_solo:
            return
        self.session.render_post_fx_solo = False

    def set_fade_in(self, fade_in: float) -> None:
        self.session.render_post_fx.fade_in = max(0.0, fade_in)

    def set_fade_out(self, fade_out: float) -> None:
        self.session.render_post_fx.fade_out = max(0.0, fade_out)
