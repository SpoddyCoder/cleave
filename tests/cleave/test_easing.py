"""Tests for cleave.easing."""

from __future__ import annotations

import pytest

from cleave.easing import (
    FADE_CURVE_FNS,
    ease_out_cubic,
    ease_out_expo,
    fade_alpha,
    fade_ramp_alpha,
    linear,
    smoothstep,
)


def test_smoothstep_endpoints() -> None:
    assert smoothstep(0.0) == 0.0
    assert smoothstep(1.0) == 1.0


def test_fade_alpha_no_fades() -> None:
    assert fade_alpha(0.0, 10.0, 0.0, 0.0) == 1.0
    assert fade_alpha(5.0, 10.0, 0.0, 0.0) == 1.0
    assert fade_alpha(10.0, 10.0, 0.0, 0.0) == 1.0


def test_fade_alpha_fade_in() -> None:
    assert fade_alpha(0.0, 10.0, 2.0, 0.0) == 0.0
    assert fade_alpha(1.0, 10.0, 2.0, 0.0) == smoothstep(0.5)
    assert fade_alpha(2.0, 10.0, 2.0, 0.0) == 1.0
    assert fade_alpha(5.0, 10.0, 2.0, 0.0) == 1.0


def test_fade_alpha_fade_out() -> None:
    assert fade_alpha(8.0, 10.0, 0.0, 2.0) == 1.0
    assert fade_alpha(9.0, 10.0, 0.0, 2.0) == smoothstep(0.5)
    assert fade_alpha(10.0, 10.0, 0.0, 2.0) == 0.0


def test_fade_alpha_combined() -> None:
    duration = 10.0
    fade_in = 2.0
    fade_out = 2.0
    assert fade_alpha(1.0, duration, fade_in, fade_out) == smoothstep(0.5)
    assert fade_alpha(5.0, duration, fade_in, fade_out) == 1.0
    assert fade_alpha(9.0, duration, fade_in, fade_out) == smoothstep(0.5)


def test_linear_clamps_to_unit_interval() -> None:
    assert linear(-0.5) == 0.0
    assert linear(0.0) == 0.0
    assert linear(0.5) == 0.5
    assert linear(1.0) == 1.0
    assert linear(1.5) == 1.0


def test_fade_curve_fns_are_the_four_fade_curves() -> None:
    assert tuple(FADE_CURVE_FNS) == (
        "linear",
        "smoothstep",
        "ease_out_cubic",
        "ease_out_expo",
    )
    assert "ease_out_back" not in FADE_CURVE_FNS


def test_fade_ramp_alpha_zero_width_window() -> None:
    assert fade_ramp_alpha(4.9, 5.0, 5.0, "linear") == 0.0
    assert fade_ramp_alpha(5.0, 5.0, 5.0, "linear") == 1.0
    assert fade_ramp_alpha(4.0, 5.0, 4.0, "smoothstep") == 0.0
    assert fade_ramp_alpha(5.0, 5.0, 4.0, "ease_out_expo") == 1.0


def test_fade_ramp_alpha_outside_window() -> None:
    assert fade_ramp_alpha(1.0, 2.0, 6.0, "linear") == 0.0
    assert fade_ramp_alpha(2.0, 2.0, 6.0, "ease_out_cubic") == 0.0
    assert fade_ramp_alpha(6.0, 2.0, 6.0, "ease_out_expo") == 1.0
    assert fade_ramp_alpha(8.0, 2.0, 6.0, "smoothstep") == 1.0


@pytest.mark.parametrize(
    ("curve", "expected"),
    [
        ("linear", 0.5),
        ("smoothstep", smoothstep(0.5)),
        ("ease_out_cubic", ease_out_cubic(0.5)),
        ("ease_out_expo", ease_out_expo(0.5)),
    ],
)
def test_fade_ramp_alpha_midpoint_uses_named_curve(curve: str, expected: float) -> None:
    assert fade_ramp_alpha(5.0, 0.0, 10.0, curve) == expected


def test_fade_ramp_alpha_unknown_curve_uses_smoothstep() -> None:
    assert fade_ramp_alpha(5.0, 0.0, 10.0, "ease_out_back") == smoothstep(0.5)
    assert fade_ramp_alpha(5.0, 0.0, 10.0, "nope") == smoothstep(0.5)
