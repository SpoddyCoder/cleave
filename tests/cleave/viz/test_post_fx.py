"""Tests for live render post-FX fade."""

from __future__ import annotations

from cleave.easing import fade_alpha
from cleave.viz.post_fx import (
    compress_highlight_luminance,
    highlight_desaturation_mix,
    highlight_rolloff_active,
    live_frame_fade_alpha,
)
from tests.support.config import default_render_post_fx_runtime


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
    pp.highlight_rolloff.enabled = True
    assert highlight_rolloff_active(pp, solo=False) is True
    assert highlight_rolloff_active(pp, solo=True) is False
    pp.enabled = False
    assert highlight_rolloff_active(pp, solo=False) is True
    pp.highlight_rolloff.enabled = False
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


def test_highlight_desaturation_mix_zero_below_threshold() -> None:
    assert highlight_desaturation_mix(0.5, 0.78, 0.3) == 0.0


def test_highlight_desaturation_mix_increases_with_luminance() -> None:
    low = highlight_desaturation_mix(0.80, 0.78, 0.5)
    high = highlight_desaturation_mix(0.95, 0.78, 0.5)
    assert high > low > 0.0
