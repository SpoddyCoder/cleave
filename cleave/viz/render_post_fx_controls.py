"""Render post-FX row mutations for live tuning."""

from __future__ import annotations

from cleave.config_schema.render import (
    CHROMA_BOOST_APPLY_MODES,
    CHROMA_BOOST_VARIANTS,
    FADE_CURVES,
    HIGHLIGHT_ROLLOFF_APPLY_MODES,
    HIGHLIGHT_ROLLOFF_CURVES,
    clamp_chroma_boost_amount_pct,
    clamp_fade_in_end,
    clamp_fade_out_start,
    clamp_fade_seconds,
    clamp_highlight_rolloff_ceiling_pct,
    clamp_highlight_rolloff_desaturation_pct,
    clamp_highlight_rolloff_softness_pct,
    clamp_highlight_rolloff_strength_pct,
    clamp_highlight_rolloff_threshold_pct,
    clamp_visual_limiter_ratio,
    clamp_visual_limiter_release,
    clamp_visual_limiter_threshold,
)
from cleave.viz.render_post_fx_bindings import RenderPostFxBindings
from cleave.viz.session import FadeSideRuntime, TuningSession


class RenderPostFxControls:
    """Mutations for render post-FX rows."""

    def __init__(
        self,
        session: TuningSession,
        *,
        bindings: RenderPostFxBindings | None = None,
    ) -> None:
        self.session = session
        self._bindings = bindings

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

    def set_fade_expanded(self, expanded: bool) -> None:
        fade = self.session.render_post_fx.fade
        if fade.expanded == expanded:
            return
        fade.expanded = expanded

    def set_fade_side_expanded(self, side: str, expanded: bool) -> None:
        window = self._fade_side(side)
        if window.expanded == expanded:
            return
        window.expanded = expanded

    def set_fade_start(self, side: str, value: float) -> None:
        window = self._fade_side(side)
        if side == "fade_in":
            window.start = clamp_fade_seconds(value)
            window.end = clamp_fade_in_end(window.end, start=window.start)
            return
        window.start = clamp_fade_out_start(value, end=window.end)

    def set_fade_end(self, side: str, value: float) -> None:
        window = self._fade_side(side)
        if side == "fade_in":
            window.end = clamp_fade_in_end(value, start=window.start)
            return
        window.end = clamp_fade_seconds(value)
        window.start = clamp_fade_out_start(window.start, end=window.end)

    def cycle_fade_type(self, side: str, *, forward: bool) -> None:
        curves = FADE_CURVES
        window = self._fade_side(side)
        try:
            index = curves.index(window.type)
        except ValueError:
            index = 0
        if forward:
            window.type = curves[(index + 1) % len(curves)]
        else:
            window.type = curves[(index - 1) % len(curves)]

    def _fade_side(self, side: str) -> FadeSideRuntime:
        fade = self.session.render_post_fx.fade
        if side == "fade_in":
            return fade.fade_in
        if side == "fade_out":
            return fade.fade_out
        raise ValueError(
            f"fade side must be 'fade_in' or 'fade_out', got {side!r}"
        )

    def set_highlight_rolloff_expanded(self, expanded: bool) -> None:
        pp = self.session.render_post_fx
        if pp.highlight_rolloff_expanded == expanded:
            return
        pp.highlight_rolloff_expanded = expanded

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

    def cycle_highlight_rolloff_mode(self, *, forward: bool) -> None:
        modes = HIGHLIGHT_ROLLOFF_APPLY_MODES
        hr = self.session.render_post_fx.highlight_rolloff
        old_mode = hr.mode
        try:
            index = modes.index(hr.mode)
        except ValueError:
            index = 0
        if forward:
            hr.mode = modes[(index + 1) % len(modes)]
        else:
            hr.mode = modes[(index - 1) % len(modes)]
        if hr.mode != old_mode and self._bindings is not None:
            paused = (
                self._bindings.is_paused()
                if self._bindings.is_paused is not None
                else False
            )
            if paused and self._bindings.on_highlight_rolloff_apply_mode_change:
                self._bindings.on_highlight_rolloff_apply_mode_change(
                    old_mode, hr.mode
                )

    def cycle_highlight_rolloff_curve(self, *, forward: bool) -> None:
        curves = HIGHLIGHT_ROLLOFF_CURVES
        hr = self.session.render_post_fx.highlight_rolloff
        try:
            index = curves.index(hr.curve)
        except ValueError:
            index = 0
        if forward:
            hr.curve = curves[(index + 1) % len(curves)]
        else:
            hr.curve = curves[(index - 1) % len(curves)]

    def set_chroma_boost_expanded(self, expanded: bool) -> None:
        pp = self.session.render_post_fx
        if pp.chroma_boost_expanded == expanded:
            return
        pp.chroma_boost_expanded = expanded

    def set_chroma_boost_amount_pct(self, amount_pct: int) -> None:
        self.session.render_post_fx.chroma_boost.amount_pct = (
            clamp_chroma_boost_amount_pct(amount_pct)
        )

    def cycle_chroma_boost_mode(self, *, forward: bool) -> None:
        modes = CHROMA_BOOST_APPLY_MODES
        cb = self.session.render_post_fx.chroma_boost
        old_mode = cb.mode
        try:
            index = modes.index(cb.mode)
        except ValueError:
            index = 0
        if forward:
            cb.mode = modes[(index + 1) % len(modes)]
        else:
            cb.mode = modes[(index - 1) % len(modes)]
        if cb.mode != old_mode and self._bindings is not None:
            paused = (
                self._bindings.is_paused()
                if self._bindings.is_paused is not None
                else False
            )
            if paused and self._bindings.on_chroma_boost_apply_mode_change:
                self._bindings.on_chroma_boost_apply_mode_change(old_mode, cb.mode)

    def cycle_chroma_boost_variant(self, *, forward: bool) -> None:
        variants = CHROMA_BOOST_VARIANTS
        cb = self.session.render_post_fx.chroma_boost
        try:
            index = variants.index(cb.variant)
        except ValueError:
            index = 0
        if forward:
            cb.variant = variants[(index + 1) % len(variants)]
        else:
            cb.variant = variants[(index - 1) % len(variants)]

    def set_limiter_expanded(self, expanded: bool) -> None:
        pp = self.session.render_post_fx
        if pp.limiter_expanded == expanded:
            return
        pp.limiter_expanded = expanded

    def set_limiter_enabled(self, enabled: bool) -> None:
        lim = self.session.render_post_fx.limiter
        if lim.enabled == enabled:
            return
        lim.enabled = enabled

    def set_limiter_threshold(self, value: float) -> None:
        lim = self.session.render_post_fx.limiter
        lim.threshold = clamp_visual_limiter_threshold(value)

    def set_limiter_ratio(self, value: float) -> None:
        lim = self.session.render_post_fx.limiter
        lim.ratio = clamp_visual_limiter_ratio(value)

    def set_limiter_release(self, value: float) -> None:
        lim = self.session.render_post_fx.limiter
        lim.release = clamp_visual_limiter_release(value)
