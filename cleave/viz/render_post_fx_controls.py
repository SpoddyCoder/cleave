"""Render post-FX row mutations for live tuning."""

from __future__ import annotations

from cleave.viz.session import TuningSession


class RenderPostFxControls:
    """Mutations for render post-FX rows."""

    def __init__(self, session: TuningSession) -> None:
        self.session = session

    def set_expanded(self, expanded: bool) -> None:
        pp = self.session.render_post_fx
        if pp.expanded == expanded:
            return
        pp.expanded = expanded

    def set_enabled(self, enabled: bool) -> None:
        pp = self.session.render_post_fx
        if pp.enabled == enabled:
            return
        pp.enabled = enabled
        if not enabled:
            self.session.render_post_fx_solo = False
            pp.expanded = False

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
