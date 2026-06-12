"""Tests for live render post-FX fade."""

from __future__ import annotations

from cleave.easing import fade_alpha
from cleave.viz.post_fx import live_frame_fade_alpha


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
