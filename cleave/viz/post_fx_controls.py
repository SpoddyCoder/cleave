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
from cleave.choice import step_choice
from cleave.viz.post_fx_bindings import PostFxBindings
from cleave.viz.session import (
    ChromaBoostRuntime,
    FadeSideRuntime,
    HighlightRolloffRuntime,
    TuningSession,
)


def _per_layer(block: HighlightRolloffRuntime | ChromaBoostRuntime) -> bool:
    return block.enabled and block.mode == "per_layer"


class PostFxControls:
    """Mutations for render post-FX rows."""

    def __init__(
        self,
        session: TuningSession,
        *,
        bindings: PostFxBindings | None = None,
    ) -> None:
        self.session = session
        self._bindings = bindings

    def enter_solo(self) -> None:
        if self.session.post_fx_solo:
            return
        self.session.post_fx_solo = True

    def exit_solo(self) -> None:
        if not self.session.post_fx_solo:
            return
        self.session.post_fx_solo = False

    def _paused(self) -> bool:
        bindings = self._bindings
        return (
            bindings is not None
            and bindings.is_paused is not None
            and bindings.is_paused()
        )

    def _sync_highlight_rolloff_per_layer(self, was_per_layer: bool) -> None:
        now = _per_layer(self.session.post_fx.highlight_rolloff)
        if now == was_per_layer or not self._paused():
            return
        assert self._bindings is not None
        if self._bindings.on_highlight_rolloff_per_layer_change is not None:
            self._bindings.on_highlight_rolloff_per_layer_change(now)

    def _sync_chroma_boost_per_layer(self, was_per_layer: bool) -> None:
        now = _per_layer(self.session.post_fx.chroma_boost)
        if now == was_per_layer or not self._paused():
            return
        assert self._bindings is not None
        if self._bindings.on_chroma_boost_per_layer_change is not None:
            self._bindings.on_chroma_boost_per_layer_change(now)

    def set_fade_enabled(self, enabled: bool) -> None:
        self.session.post_fx.fade.enabled = enabled

    def set_highlight_rolloff_enabled(self, enabled: bool) -> None:
        hr = self.session.post_fx.highlight_rolloff
        was_per_layer = _per_layer(hr)
        hr.enabled = enabled
        self._sync_highlight_rolloff_per_layer(was_per_layer)

    def set_chroma_boost_enabled(self, enabled: bool) -> None:
        cb = self.session.post_fx.chroma_boost
        was_per_layer = _per_layer(cb)
        cb.enabled = enabled
        self._sync_chroma_boost_per_layer(was_per_layer)

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

    def step_fade_type(self, side: str, *, delta: int) -> None:
        window = self._fade_side(side)
        window.type = step_choice(FADE_CURVES, window.type, delta)

    def _fade_side(self, side: str) -> FadeSideRuntime:
        fade = self.session.post_fx.fade
        if side == "fade_in":
            return fade.fade_in
        if side == "fade_out":
            return fade.fade_out
        raise ValueError(
            f"fade side must be 'fade_in' or 'fade_out', got {side!r}"
        )

    def _enforce_ceiling_vs_threshold(self) -> None:
        hr = self.session.post_fx.highlight_rolloff
        hr.ceiling_pct = clamp_highlight_rolloff_ceiling_pct(
            hr.ceiling_pct, threshold_pct=hr.threshold_pct
        )

    def set_highlight_rolloff_threshold_pct(self, threshold_pct: int) -> None:
        hr = self.session.post_fx.highlight_rolloff
        hr.threshold_pct = clamp_highlight_rolloff_threshold_pct(threshold_pct)
        self._enforce_ceiling_vs_threshold()

    def set_highlight_rolloff_ceiling_pct(self, ceiling_pct: int) -> None:
        hr = self.session.post_fx.highlight_rolloff
        hr.ceiling_pct = clamp_highlight_rolloff_ceiling_pct(
            ceiling_pct, threshold_pct=hr.threshold_pct
        )

    def set_highlight_rolloff_strength_pct(self, strength_pct: int) -> None:
        self.session.post_fx.highlight_rolloff.strength_pct = (
            clamp_highlight_rolloff_strength_pct(strength_pct)
        )

    def set_highlight_rolloff_softness_pct(self, softness_pct: int) -> None:
        self.session.post_fx.highlight_rolloff.softness_pct = (
            clamp_highlight_rolloff_softness_pct(softness_pct)
        )

    def set_highlight_rolloff_desaturation_pct(self, desaturation_pct: int) -> None:
        self.session.post_fx.highlight_rolloff.desaturation_pct = (
            clamp_highlight_rolloff_desaturation_pct(desaturation_pct)
        )

    def step_highlight_rolloff_mode(self, *, forward: bool) -> None:
        hr = self.session.post_fx.highlight_rolloff
        was_per_layer = _per_layer(hr)
        hr.mode = step_choice(
            HIGHLIGHT_ROLLOFF_APPLY_MODES, hr.mode, 1 if forward else -1
        )
        self._sync_highlight_rolloff_per_layer(was_per_layer)

    def step_highlight_rolloff_curve(self, *, forward: bool) -> None:
        hr = self.session.post_fx.highlight_rolloff
        hr.curve = step_choice(
            HIGHLIGHT_ROLLOFF_CURVES, hr.curve, 1 if forward else -1
        )

    def set_chroma_boost_amount_pct(self, amount_pct: int) -> None:
        self.session.post_fx.chroma_boost.amount_pct = (
            clamp_chroma_boost_amount_pct(amount_pct)
        )

    def step_chroma_boost_mode(self, *, forward: bool) -> None:
        cb = self.session.post_fx.chroma_boost
        was_per_layer = _per_layer(cb)
        cb.mode = step_choice(CHROMA_BOOST_APPLY_MODES, cb.mode, 1 if forward else -1)
        self._sync_chroma_boost_per_layer(was_per_layer)

    def step_chroma_boost_variant(self, *, forward: bool) -> None:
        cb = self.session.post_fx.chroma_boost
        cb.variant = step_choice(
            CHROMA_BOOST_VARIANTS, cb.variant, 1 if forward else -1
        )

    def set_limiter_enabled(self, enabled: bool) -> None:
        lim = self.session.post_fx.limiter
        if lim.enabled == enabled:
            return
        lim.enabled = enabled

    def set_limiter_threshold(self, value: float) -> None:
        lim = self.session.post_fx.limiter
        lim.threshold = clamp_visual_limiter_threshold(value)

    def set_limiter_ratio(self, value: float) -> None:
        lim = self.session.post_fx.limiter
        lim.ratio = clamp_visual_limiter_ratio(value)

    def set_limiter_release(self, value: float) -> None:
        lim = self.session.post_fx.limiter
        lim.release = clamp_visual_limiter_release(value)
