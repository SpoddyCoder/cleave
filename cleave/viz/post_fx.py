"""Live render post-FX for the visualizer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from cleave.config import CleaveConfig, render_hdr_compositing
from cleave.config_schema import DEFAULT_HIGHLIGHT_ROLLOFF_CURVE, HighlightRolloffCurve
from cleave.easing import fade_alpha
from cleave.gl_color_format import resolve_live_compositor_format
from cleave.viz.session import RenderPostFxRuntime, TuningSession

if TYPE_CHECKING:
    from cleave.gl_compositor import GlCompositor
    from cleave.gl_post_process import GlPostProcess

ACES_AT_ONE = 2.54 / 3.16

DISPLAY_SHOULDER_THRESHOLD = 0.90
DISPLAY_SHOULDER_CEILING = 0.84
DISPLAY_SHOULDER_STRENGTH = 0.35
DISPLAY_SHOULDER_SOFTNESS = 0.70
DISPLAY_SHOULDER_DESATURATION = 0.06
DISPLAY_SHOULDER_CURVE: HighlightRolloffCurve = "rolloff"


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _shoulder_filmic_lum(
    curve: HighlightRolloffCurve,
    norm: float,
    threshold: float,
    ceiling: float,
) -> float:
    span = ceiling - threshold
    if curve == "rolloff":
        reinhard = norm / (1.0 + norm)
        return threshold + span * (reinhard / 0.5)
    if curve == "smoothstep":
        return threshold + span * _smoothstep(norm)
    aces = (norm * (2.51 * norm + 0.03)) / (norm * (2.43 * norm + 0.59) + 0.14)
    return threshold + span * (aces / ACES_AT_ONE)


def _shoulder_filmic_lum_np(
    curve: HighlightRolloffCurve,
    norm: np.ndarray,
    threshold: float,
    ceiling: float,
) -> np.ndarray:
    span = ceiling - threshold
    if curve == "rolloff":
        reinhard = norm / (1.0 + norm)
        return threshold + span * (reinhard / 0.5)
    if curve == "smoothstep":
        return threshold + span * _smoothstep_np(norm)
    aces = (norm * (2.51 * norm + 0.03)) / (norm * (2.43 * norm + 0.59) + 0.14)
    return threshold + span * (aces / ACES_AT_ONE)


def highlight_rolloff_curve_index(curve: HighlightRolloffCurve) -> int:
    if curve == "rolloff":
        return 0
    if curve == "smoothstep":
        return 1
    return 2


def compress_highlight_luminance(
    lum: float,
    threshold: float,
    ceiling: float,
    strength: float,
    softness: float,
    curve: HighlightRolloffCurve = DEFAULT_HIGHLIGHT_ROLLOFF_CURVE,
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

    filmic_lum = _shoulder_filmic_lum(curve, norm, threshold, ceiling)

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


def _smoothstep_np(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _compress_highlight_luminance_np(
    lum: np.ndarray,
    threshold: float,
    ceiling: float,
    strength: float,
    softness: float,
    curve: HighlightRolloffCurve = DEFAULT_HIGHLIGHT_ROLLOFF_CURVE,
) -> np.ndarray:
    ceiling = min(ceiling, threshold)
    excess = np.maximum(lum - threshold, 0.0)
    headroom = max(1.0 - threshold, 1e-6)
    norm = np.minimum(excess / headroom, 1.0)

    knee_width = max(softness * headroom, 1e-6)
    knee_t = _smoothstep_np(np.minimum(excess / knee_width, 1.0))
    linear_lum = threshold + excess * (1.0 - knee_t)

    filmic_lum = _shoulder_filmic_lum_np(curve, norm, threshold, ceiling)

    past_knee = np.maximum(excess - knee_width, 0.0)
    shoulder_span = max(headroom - knee_width, 1e-6)
    shoulder_t = _smoothstep_np(np.minimum(past_knee / shoulder_span, 1.0))
    compressed = linear_lum * (1.0 - shoulder_t) + filmic_lum * shoulder_t

    eff_strength = float(np.clip(strength, 0.0, 2.0))
    if eff_strength <= 0.0:
        return lum
    if eff_strength <= 1.0:
        return np.where(lum <= threshold, lum, lum + (compressed - lum) * eff_strength)

    extra = eff_strength - 1.0
    aggressive = threshold + (ceiling - threshold) * norm
    full = lum + (compressed - lum)
    boosted = full + (aggressive - full) * extra
    return np.where(lum <= threshold, lum, boosted)


def apply_highlight_rolloff_rgb(
    rgb: np.ndarray,
    threshold: float,
    ceiling: float,
    strength: float,
    softness: float,
    desaturation: float,
    curve: HighlightRolloffCurve = DEFAULT_HIGHLIGHT_ROLLOFF_CURVE,
) -> np.ndarray:
    """Vectorized highlight rolloff on float RGB (H, W, 3) in 0..1."""
    if strength <= 0.0:
        return rgb

    lum = (
        0.2126 * rgb[..., 0]
        + 0.7152 * rgb[..., 1]
        + 0.0722 * rgb[..., 2]
    )
    new_lum = _compress_highlight_luminance_np(
        lum, threshold, ceiling, strength, softness, curve
    )

    scale = np.ones_like(lum)
    active = lum > 1e-4
    scale[active] = new_lum[active] / lum[active]
    out = rgb * scale[..., np.newaxis]

    if desaturation > 0.0:
        span = max(1.0 - threshold, 1e-6)
        t = _smoothstep_np(np.maximum((new_lum - threshold) / span, 0.0))
        desat_t = np.where(new_lum > threshold, desaturation * t, 0.0)
        out = out * (1.0 - desat_t)[..., np.newaxis] + new_lum[..., np.newaxis] * desat_t[
            ..., np.newaxis
        ]

    return out


def apply_highlight_rolloff_rgba(
    rgba: np.ndarray,
    threshold: float,
    ceiling: float,
    strength: float,
    softness: float,
    desaturation: float,
    curve: HighlightRolloffCurve = DEFAULT_HIGHLIGHT_ROLLOFF_CURVE,
) -> bytes:
    """Apply highlight rolloff to uint8 RGBA (H, W, 4); returns GL upload bytes."""
    rgb = rgba[..., :3].astype(np.float32) / 255.0
    rgb_out = apply_highlight_rolloff_rgb(
        rgb, threshold, ceiling, strength, softness, desaturation, curve
    )
    out = rgba.copy()
    out[..., :3] = np.clip(rgb_out * 255.0, 0.0, 255.0).astype(np.uint8)
    return out.tobytes()


def effective_hdr_compositing(
    cfg: CleaveConfig,
    session: TuningSession | None = None,
) -> bool:
    """True when the live/offline path should use RGBA16F compositing."""
    if session is not None:
        from cleave.viz.editor_mode_controls import is_preset_curation_mode

        if is_preset_curation_mode(session):
            return False
    return render_hdr_compositing(cfg)


def hdr_display_shoulder_active(
    cfg: CleaveConfig,
    session: TuningSession | None = None,
) -> bool:
    return effective_hdr_compositing(cfg, session)


def sync_live_compositor_format(
    cfg: CleaveConfig,
    session: TuningSession,
    compositor: GlCompositor,
    post_process: GlPostProcess,
) -> None:
    """Match compositor/post-process attachments to editor mode (8-bit in curation)."""
    from cleave.viz.editor_mode_controls import is_preset_curation_mode

    fmt = resolve_live_compositor_format(
        render_hdr_compositing(cfg),
        preset_curation=is_preset_curation_mode(session),
    )
    compositor.set_color_format(fmt)
    post_process.set_color_format(fmt)


def apply_hdr_display_shoulder(
    post_process: GlPostProcess,
    texture_id: int,
    width: int,
    height: int,
) -> None:
    post_process.apply_highlight_rolloff(
        texture_id,
        width,
        height,
        DISPLAY_SHOULDER_THRESHOLD,
        DISPLAY_SHOULDER_CEILING,
        DISPLAY_SHOULDER_STRENGTH,
        DISPLAY_SHOULDER_SOFTNESS,
        DISPLAY_SHOULDER_DESATURATION,
        highlight_rolloff_curve_index(DISPLAY_SHOULDER_CURVE),
    )


def highlight_rolloff_active(pp: RenderPostFxRuntime, *, solo: bool) -> bool:
    return pp.enabled and pp.highlight_rolloff.mode != "off" and not solo


def chroma_boost_variant_index(variant: str) -> int:
    if variant == "saturation":
        return 0
    return 1


def apply_chroma_boost_rgb(
    rgb: np.ndarray,
    amount_pct: int,
    variant: str,
) -> np.ndarray:
    """Vectorized chroma boost on float RGB (H, W, 3) in 0..1."""
    if amount_pct <= 0:
        return rgb

    amount = amount_pct / 100.0
    lum = (
        0.2126 * rgb[..., 0]
        + 0.7152 * rgb[..., 1]
        + 0.0722 * rgb[..., 2]
    )
    if variant == "saturation":
        factor = 1.0 + amount
        return lum[..., np.newaxis] + (rgb - lum[..., np.newaxis]) * factor

    maxc = np.max(rgb, axis=-1)
    minc = np.min(rgb, axis=-1)
    sat = (maxc - minc) / (maxc + 1e-6)
    weight = 1.0 - sat
    factor = 1.0 + amount * weight
    return lum[..., np.newaxis] + (rgb - lum[..., np.newaxis]) * factor[..., np.newaxis]


def apply_chroma_boost_rgba(
    rgba: np.ndarray,
    amount_pct: int,
    variant: str,
) -> bytes:
    """Apply chroma boost to uint8 RGBA (H, W, 4); returns GL upload bytes."""
    rgb = rgba[..., :3].astype(np.float32) / 255.0
    rgb_out = apply_chroma_boost_rgb(rgb, amount_pct, variant)
    out = rgba.copy()
    out[..., :3] = np.clip(rgb_out * 255.0, 0.0, 255.0).astype(np.uint8)
    return out.tobytes()


def chroma_boost_active(pp: RenderPostFxRuntime, *, solo: bool) -> bool:
    return (
        pp.enabled
        and pp.chroma_boost.mode != "off"
        and not solo
        and pp.chroma_boost.amount_pct > 0
    )


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
