"""Live render post-FX for the visualizer."""

from __future__ import annotations

from cleave.easing import fade_alpha
from cleave.viz.session import RenderPostFxRuntime


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def compress_highlight_luminance(
    lum: float,
    threshold: float,
    ceiling: float,
    strength: float,
    softness: float,
) -> float:
    """Rec.709 luminance filmic highlight compression toward ceiling."""
    if lum <= threshold or strength <= 0.0:
        return lum

    ceiling = min(ceiling, threshold)
    excess = lum - threshold
    headroom = max(1.0 - threshold, 1e-6)
    norm = min(excess / headroom, 1.0)

    knee_width = max(softness * headroom, 1e-6)
    knee_t = _smoothstep(min(excess / knee_width, 1.0))

    linear_lum = threshold + excess * (1.0 - knee_t)

    reinhard = norm / (1.0 + norm)
    filmic_lum = threshold + (ceiling - threshold) * (reinhard / 0.5)

    past_knee = max(0.0, excess - knee_width)
    shoulder_span = max(headroom - knee_width, 1e-6)
    shoulder_t = _smoothstep(min(past_knee / shoulder_span, 1.0))
    compressed = linear_lum * (1.0 - shoulder_t) + filmic_lum * shoulder_t

    eff_strength = min(max(strength, 0.0), 2.0)
    if eff_strength <= 1.0:
        return lum + (compressed - lum) * eff_strength

    extra = eff_strength - 1.0
    aggressive = threshold + (ceiling - threshold) * norm
    full = lum + (compressed - lum)
    return full + (aggressive - full) * extra


def highlight_desaturation_mix(
    new_lum: float,
    threshold: float,
    desaturation: float,
) -> float:
    """Return mix factor [0, 1] toward luma-only color after compression."""
    if desaturation <= 0.0 or new_lum <= threshold:
        return 0.0
    span = max(1.0 - threshold, 1e-6)
    t = _smoothstep((new_lum - threshold) / span)
    return desaturation * t


def highlight_rolloff_active(pp: RenderPostFxRuntime, *, solo: bool) -> bool:
    return pp.highlight_rolloff.enabled and not solo


def live_frame_fade_alpha(
    t_sec: float,
    duration_sec: float,
    fade_in: float,
    fade_out: float,
    *,
    enabled: bool,
    solo: bool,
) -> float:
    if not enabled or solo:
        return 1.0
    return fade_alpha(t_sec, duration_sec, fade_in, fade_out)
