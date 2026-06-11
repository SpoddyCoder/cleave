"""Tests for cleave.easing."""

from __future__ import annotations

from cleave.easing import fade_alpha, smoothstep


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
