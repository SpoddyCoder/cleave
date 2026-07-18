"""Tests for cleave.viz.tap_sync."""

from __future__ import annotations

import pytest

from cleave.viz.tap_sync import MIN_TAP_COUNT, infer_residual_delay_sec


def test_infer_residual_delay_median_of_nearest_beat_deltas() -> None:
    beats = (0.0, 1.0, 2.0, 3.0)
    taps = (0.2, 1.2, 2.2, 3.2)
    assert infer_residual_delay_sec(taps, beats) == pytest.approx(0.2)


def test_infer_residual_delay_clamps_high() -> None:
    beats = (0.0, 10.0, 20.0, 30.0)
    taps = (5.0, 15.0, 25.0, 35.0)
    assert infer_residual_delay_sec(taps, beats) == pytest.approx(2.0)


def test_infer_residual_delay_clamps_low() -> None:
    beats = (1.0, 2.0, 3.0, 4.0)
    taps = (0.0, 0.1, 0.2, 0.3)
    assert infer_residual_delay_sec(taps, beats) == pytest.approx(0.0)


def test_infer_residual_delay_requires_min_taps() -> None:
    beats = (0.0, 1.0, 2.0, 3.0)
    assert infer_residual_delay_sec((0.2, 1.2, 2.2), beats) == 0.0
    assert infer_residual_delay_sec((), beats) == 0.0


def test_infer_residual_delay_empty_beats() -> None:
    taps = tuple(0.2 + i for i in range(MIN_TAP_COUNT))
    assert infer_residual_delay_sec(taps, ()) == 0.0
