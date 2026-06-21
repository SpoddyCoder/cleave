"""Tests for live visualizer frame rate measurement."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cleave.viz.frame_rate import FrameRateMeter, format_fps_display


def test_format_fps_display() -> None:
    assert format_fps_display(29.87) == "FPS: 29.9"


def test_frame_rate_meter_first_frame() -> None:
    meter = FrameRateMeter()
    with patch("cleave.viz.frame_rate.time.perf_counter", side_effect=[0.0, 0.05]):
        meter.begin_frame()
        fps = meter.end_frame()
    assert fps == 20.0


def test_frame_rate_meter_smoothing() -> None:
    meter = FrameRateMeter(smoothing=0.5)
    with patch(
        "cleave.viz.frame_rate.time.perf_counter",
        side_effect=[0.0, 0.1, 0.1, 0.15],
    ):
        meter.begin_frame()
        assert meter.end_frame() == 10.0
        meter.begin_frame()
        fps = meter.end_frame()
    assert fps == pytest.approx(15.0)
