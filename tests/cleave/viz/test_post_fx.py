"""Tests for live render post-FX fade."""

from __future__ import annotations

import pytest

from cleave.easing import fade_alpha
from cleave.viz.post_fx import (
    apply_chroma_boost_rgb,
    chroma_boost_active,
    compress_highlight_luminance,
    highlight_desaturation_mix,
    highlight_rolloff_active,
    live_frame_fade_alpha,
)
from tests.support.config import default_render_post_fx_runtime

HIGHLIGHT_ROLLOFF_CURVES = ("rolloff", "smoothstep", "aces_fit")


def test_live_frame_fade_alpha_enabled() -> None:
    alpha = live_frame_fade_alpha(
        15.0, 100.0, 30.0, 4.0, enabled=True, solo=False
    )
    assert alpha == fade_alpha(15.0, 100.0, 30.0, 4.0)


def test_live_frame_fade_alpha_disabled() -> None:
    assert (
        live_frame_fade_alpha(0.0, 100.0, 30.0, 4.0, enabled=False, solo=False)
        == 1.0
    )


def test_live_frame_fade_alpha_solo() -> None:
    assert live_frame_fade_alpha(0.0, 100.0, 30.0, 4.0, enabled=True, solo=True) == 1.0


def test_highlight_rolloff_active() -> None:
    pp = default_render_post_fx_runtime(enabled=True)
    pp.highlight_rolloff.mode = "composite"
    assert highlight_rolloff_active(pp, solo=False) is True
    assert highlight_rolloff_active(pp, solo=True) is False
    pp.enabled = False
    assert highlight_rolloff_active(pp, solo=False) is False
    pp.highlight_rolloff.mode = "off"
    assert highlight_rolloff_active(pp, solo=False) is False


def test_compress_highlight_luminance_below_threshold() -> None:
    assert compress_highlight_luminance(0.5, 0.78, 0.65, 0.7, 0.4) == 0.5


def test_compress_highlight_luminance_reduces_bright_highlights() -> None:
    compressed = compress_highlight_luminance(0.95, 0.78, 0.65, 1.0, 0.4)
    assert compressed < 0.95
    assert compressed >= 0.65


def test_compress_highlight_luminance_full_strength_maps_white_to_ceiling() -> None:
    result = compress_highlight_luminance(1.0, 0.78, 0.65, 1.0, 0.4)
    assert abs(result - 0.65) < 0.01


def test_compress_highlight_luminance_strength_above_100_more_aggressive() -> None:
    at_100 = compress_highlight_luminance(1.0, 0.78, 0.65, 1.0, 0.4)
    at_200 = compress_highlight_luminance(1.0, 0.78, 0.65, 2.0, 0.4)
    assert at_200 <= at_100


def test_compress_highlight_luminance_ceiling_clamped_to_threshold() -> None:
    result = compress_highlight_luminance(1.0, 0.78, 0.90, 1.0, 0.4)
    assert result <= 0.78


@pytest.mark.parametrize("curve", HIGHLIGHT_ROLLOFF_CURVES)
def test_compress_highlight_luminance_reduces_bright_highlights_per_curve(
    curve: str,
) -> None:
    compressed = compress_highlight_luminance(0.95, 0.78, 0.65, 1.0, 0.4, curve=curve)
    assert compressed < 0.95
    assert compressed >= 0.65


@pytest.mark.parametrize("curve", HIGHLIGHT_ROLLOFF_CURVES)
def test_compress_highlight_luminance_full_strength_maps_white_to_ceiling_per_curve(
    curve: str,
) -> None:
    result = compress_highlight_luminance(1.0, 0.78, 0.65, 1.0, 0.4, curve=curve)
    assert abs(result - 0.65) < 0.01


def test_compress_highlight_luminance_curves_differ_at_same_inputs() -> None:
    results = {
        curve: compress_highlight_luminance(0.9, 0.78, 0.65, 1.0, 0.0, curve=curve)
        for curve in HIGHLIGHT_ROLLOFF_CURVES
    }
    assert len(set(results.values())) == len(HIGHLIGHT_ROLLOFF_CURVES)


def test_highlight_desaturation_mix_zero_below_threshold() -> None:
    assert highlight_desaturation_mix(0.5, 0.78, 0.3) == 0.0


def test_highlight_desaturation_mix_increases_with_luminance() -> None:
    low = highlight_desaturation_mix(0.80, 0.78, 0.5)
    high = highlight_desaturation_mix(0.95, 0.78, 0.5)
    assert high > low > 0.0


def _black_key_stack(
    layer_rgbs: tuple[tuple[float, float, float], ...],
    *,
    clamp: bool,
) -> tuple[float, float, float]:
    """Simulate black-key compositing: out = src + dst * (1 - src) per channel."""
    dst = [0.0, 0.0, 0.0]
    for src in layer_rgbs:
        out = [src[i] + dst[i] * (1.0 - src[i]) for i in range(3)]
        if clamp:
            out = [max(0.0, min(1.0, c)) for c in out]
        dst = out
    return (dst[0], dst[1], dst[2])


def _channel_spread(rgb: tuple[float, float, float]) -> float:
    return max(rgb) - min(rgb)


_BRIGHT_STACK_LAYERS = (
    (1.5, 0.4, 0.2),
    (0.3, 1.3, 0.2),
    (0.2, 0.3, 1.5),
)


def test_black_key_stack_8bit_clamps_chroma_reference() -> None:
    rgb = _black_key_stack(_BRIGHT_STACK_LAYERS, clamp=True)
    assert rgb == pytest.approx((1.0, 1.0, 1.0), abs=1e-6)
    assert _channel_spread(rgb) == pytest.approx(0.0, abs=1e-6)


def test_black_key_stack_float_retains_chroma_reference() -> None:
    rgb = _black_key_stack(_BRIGHT_STACK_LAYERS, clamp=False)
    assert _channel_spread(rgb) > 0.1
    assert max(rgb) > 1.0


def test_apply_highlight_rolloff_rgb_display_shoulder_on_hot_hdr() -> None:
    import numpy as np

    from cleave.viz.post_fx import (
        DISPLAY_SHOULDER_CEILING,
        DISPLAY_SHOULDER_CURVE,
        DISPLAY_SHOULDER_DESATURATION,
        DISPLAY_SHOULDER_SOFTNESS,
        DISPLAY_SHOULDER_STRENGTH,
        DISPLAY_SHOULDER_THRESHOLD,
        apply_highlight_rolloff_rgb,
    )

    hot_hdr = (1.05, 1.0, 0.95)
    rgb = np.array([[hot_hdr]], dtype=np.float32)
    out = apply_highlight_rolloff_rgb(
        rgb,
        DISPLAY_SHOULDER_THRESHOLD,
        DISPLAY_SHOULDER_CEILING,
        DISPLAY_SHOULDER_STRENGTH,
        DISPLAY_SHOULDER_SOFTNESS,
        DISPLAY_SHOULDER_DESATURATION,
        DISPLAY_SHOULDER_CURVE,
    )
    pixel = tuple(out[0, 0])
    assert max(hot_hdr) > 1.0
    assert max(pixel) < 1.0
    assert _channel_spread(pixel) > 0.0


def test_apply_highlight_rolloff_rgb_matches_scalar_reference() -> None:
    import numpy as np

    from cleave.viz.post_fx import apply_highlight_rolloff_rgb

    rgb = np.array(
        [
            [[1.0, 1.0, 1.0], [0.5, 0.4, 0.3]],
            [[0.9, 0.85, 0.8], [0.2, 0.6, 0.1]],
        ],
        dtype=np.float32,
    )
    out = apply_highlight_rolloff_rgb(rgb, 0.78, 0.65, 0.7, 0.4, 0.3)

    for y in range(2):
        for x in range(2):
            lum = 0.2126 * rgb[y, x, 0] + 0.7152 * rgb[y, x, 1] + 0.0722 * rgb[y, x, 2]
            new_lum = compress_highlight_luminance(lum, 0.78, 0.65, 0.7, 0.4)
            if lum > 1e-4:
                expected = rgb[y, x] * (new_lum / lum)
            else:
                expected = rgb[y, x]
            desat_t = highlight_desaturation_mix(new_lum, 0.78, 0.3)
            expected = expected * (1.0 - desat_t) + new_lum * desat_t
            assert np.allclose(out[y, x], expected, atol=1e-5), (y, x, out[y, x], expected)


def test_chroma_boost_active() -> None:
    pp = default_render_post_fx_runtime(enabled=True)
    pp.chroma_boost.mode = "composite"
    pp.chroma_boost.amount_pct = 25
    assert chroma_boost_active(pp, solo=False) is True
    assert chroma_boost_active(pp, solo=True) is False
    pp.enabled = False
    assert chroma_boost_active(pp, solo=False) is False
    pp.enabled = True
    pp.chroma_boost.mode = "off"
    assert chroma_boost_active(pp, solo=False) is False
    pp.chroma_boost.mode = "composite"
    pp.chroma_boost.amount_pct = 0
    assert chroma_boost_active(pp, solo=False) is False


def test_apply_chroma_boost_rgb_saturation_increases_spread() -> None:
    import numpy as np

    rgb = np.array([[[0.4, 0.5, 0.6]]], dtype=np.float32)
    out = apply_chroma_boost_rgb(rgb, 50, "saturation")
    spread_in = float(np.max(rgb) - np.min(rgb))
    spread_out = float(np.max(out) - np.min(out))
    assert spread_out > spread_in


def test_apply_chroma_boost_rgb_vibrance_spares_saturated_pixels() -> None:
    import numpy as np

    saturated = np.array([[[1.0, 0.1, 0.1]]], dtype=np.float32)
    saturated_sat = apply_chroma_boost_rgb(saturated, 50, "saturation")
    saturated_vib = apply_chroma_boost_rgb(saturated, 50, "vibrance")

    saturated_sat_delta = float(np.abs(saturated_sat - saturated).sum())
    saturated_vib_delta = float(np.abs(saturated_vib - saturated).sum())
    assert saturated_vib_delta < saturated_sat_delta

