"""Tests for layer opacity mapping in the GL compositor."""

from __future__ import annotations

import pytest

from cleave.blend_modes import BLEND_MODES
from cleave.gl_compositor import GlCompositor

# Modes whose GL blend func uses GL_SRC_ALPHA (opacity stays in glColor alpha).
_OPACITY_VIA_ALPHA = frozenset({"add"})

# All other modes bake opacity into glColor RGB (SRC_COLOR-weighted blends).
_OPACITY_VIA_RGB = frozenset(mode for mode in BLEND_MODES if mode not in _OPACITY_VIA_ALPHA)


@pytest.mark.parametrize("blend_mode", sorted(_OPACITY_VIA_RGB))
def test_layer_gl_color_bakes_opacity_into_rgb(blend_mode: str) -> None:
    rgba = GlCompositor._layer_gl_color((0.8, 0.6, 0.4), 0.5, blend_mode)  # type: ignore[arg-type]
    assert rgba == pytest.approx((0.4, 0.3, 0.2, 1.0))


@pytest.mark.parametrize("blend_mode", sorted(_OPACITY_VIA_ALPHA))
def test_layer_gl_color_uses_alpha_channel(blend_mode: str) -> None:
    rgba = GlCompositor._layer_gl_color((0.8, 0.6, 0.4), 0.5, blend_mode)  # type: ignore[arg-type]
    assert rgba[:3] == pytest.approx((0.8, 0.6, 0.4))
    assert rgba[3] == pytest.approx(0.5)


def test_layer_gl_color_full_opacity_preserves_tint() -> None:
    tint = (0.9, 0.7, 0.5)
    for mode in BLEND_MODES:
        rgba = GlCompositor._layer_gl_color(tint, 1.0, mode)
        assert rgba == pytest.approx((*tint, 1.0))


@pytest.mark.parametrize("blend_mode", sorted(_OPACITY_VIA_RGB))
def test_layer_gl_color_hue_tint_multiplies_with_opacity_in_rgb(blend_mode: str) -> None:
    rgba = GlCompositor._layer_gl_color((1.2, 0.8, 0.6), 0.5, blend_mode)  # type: ignore[arg-type]
    assert rgba == pytest.approx((0.6, 0.4, 0.3, 1.0))


def test_layer_gl_color_add_keeps_hue_in_rgb_and_opacity_in_alpha() -> None:
    rgba = GlCompositor._layer_gl_color((1.2, 0.8, 0.6), 0.5, "add")
    assert rgba == pytest.approx((1.2, 0.8, 0.6, 0.5))


def test_layer_gl_color_unknown_mode_matches_black_key_rgb_scaling() -> None:
    """Runtime fallback blend is black-key; opacity must scale RGB."""
    rgba = GlCompositor._layer_gl_color((0.8, 0.6, 0.4), 0.5, "legacy")  # type: ignore[arg-type]
    assert rgba == pytest.approx((0.4, 0.3, 0.2, 1.0))


def test_blend_modes_partition_opacity_channel() -> None:
    assert _OPACITY_VIA_ALPHA | _OPACITY_VIA_RGB == frozenset(BLEND_MODES)
    assert not _OPACITY_VIA_ALPHA & _OPACITY_VIA_RGB


def test_flash_rgba_puts_strength_in_alpha_for_add_blend() -> None:
    """Flash draws a solid quad with add blend; strength must be glColor alpha."""
    flash_alpha = 0.35
    rgba = (240 / 255.0, 235 / 255.0, 230 / 255.0, flash_alpha)
    assert rgba[3] == pytest.approx(flash_alpha)
    assert rgba[:3] == pytest.approx((240 / 255.0, 235 / 255.0, 230 / 255.0))


@pytest.mark.parametrize(
    ("hue_rgb", "hue_mix", "expected"),
    [
        ((0.5, 0.7, 0.9), 0.0, (1.0, 1.0, 1.0)),
        ((0.5, 0.7, 0.9), 1.0, (0.5, 0.7, 0.9)),
        ((1.2, 0.8, 0.6), 0.5, (1.1, 0.9, 0.8)),
    ],
)
def test_lerp_tint_rgb_scales_hue_mix(
    hue_rgb: tuple[float, float, float],
    hue_mix: float,
    expected: tuple[float, float, float],
) -> None:
    result = GlCompositor._lerp_tint_rgb(hue_rgb, hue_mix)
    assert result == pytest.approx(expected)


def test_pulse_zero_opacity_can_still_leave_flash_visible() -> None:
    """Flash burst can outlast a pulse envelope; flash must not require layer opacity."""
    from cleave.effects.flash import flash_alpha
    from cleave.effects.pulse import effective_opacity

    assert effective_opacity(1.0, 100, 0.0) == 0.0
    assert flash_alpha(100, 0.15) >= 0.01
