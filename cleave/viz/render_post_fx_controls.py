"""Render post-FX row mutations for live tuning."""

from __future__ import annotations

from cleave.config_schema import (
    clamp_highlight_rolloff_ceiling_pct,
    clamp_highlight_rolloff_desaturation_pct,
    clamp_highlight_rolloff_softness_pct,
    clamp_highlight_rolloff_strength_pct,
    clamp_highlight_rolloff_threshold_pct,
)
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

    def set_highlight_rolloff_expanded(self, expanded: bool) -> None:
        pp = self.session.render_post_fx
        if pp.highlight_rolloff_expanded == expanded:
            return
        pp.highlight_rolloff_expanded = expanded

    def set_highlight_rolloff_enabled(self, enabled: bool) -> None:
        hr = self.session.render_post_fx.highlight_rolloff
        if hr.enabled == enabled:
            return
        hr.enabled = enabled

    def _enforce_ceiling_vs_threshold(self) -> None:
        hr = self.session.render_post_fx.highlight_rolloff
        hr.ceiling_pct = clamp_highlight_rolloff_ceiling_pct(
            hr.ceiling_pct, threshold_pct=hr.threshold_pct
        )

    def set_highlight_rolloff_threshold_pct(self, threshold_pct: int) -> None:
        hr = self.session.render_post_fx.highlight_rolloff
        hr.threshold_pct = clamp_highlight_rolloff_threshold_pct(threshold_pct)
        self._enforce_ceiling_vs_threshold()

    def set_highlight_rolloff_ceiling_pct(self, ceiling_pct: int) -> None:
        hr = self.session.render_post_fx.highlight_rolloff
        hr.ceiling_pct = clamp_highlight_rolloff_ceiling_pct(
            ceiling_pct, threshold_pct=hr.threshold_pct
        )

    def set_highlight_rolloff_strength_pct(self, strength_pct: int) -> None:
        self.session.render_post_fx.highlight_rolloff.strength_pct = (
            clamp_highlight_rolloff_strength_pct(strength_pct)
        )

    def set_highlight_rolloff_softness_pct(self, softness_pct: int) -> None:
        self.session.render_post_fx.highlight_rolloff.softness_pct = (
            clamp_highlight_rolloff_softness_pct(softness_pct)
        )

    def set_highlight_rolloff_desaturation_pct(self, desaturation_pct: int) -> None:
        self.session.render_post_fx.highlight_rolloff.desaturation_pct = (
            clamp_highlight_rolloff_desaturation_pct(desaturation_pct)
        )
