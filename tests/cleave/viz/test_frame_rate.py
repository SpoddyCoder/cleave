"""Tests for live visualizer frame rate measurement."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cleave.stem_pcm import LIVE_PROJECTM_FPS
from cleave.viz.frame_rate import (
    FPS_DISPLAY_LABEL,
    LIVE_PROJECTM_FPS_FLOOR,
    FrameRateMeter,
    ProjectMFpsGovernor,
    format_fps_display,
    format_fps_value,
)
from cleave.viz.layer import StemLayer


def test_format_fps_display() -> None:
    assert format_fps_value(29.87) == "30"
    assert format_fps_display(29.87) == f"{FPS_DISPLAY_LABEL}30"


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


def test_frame_rate_meter_display_fps_throttled() -> None:
    meter = FrameRateMeter(smoothing=1.0, display_interval_sec=1.0)
    with patch(
        "cleave.viz.frame_rate.time.perf_counter",
        side_effect=[0.0, 0.05, 0.5, 0.60],
    ):
        meter.begin_frame()
        assert meter.end_frame() == pytest.approx(20.0)
        assert meter.display_fps == pytest.approx(20.0)

        meter.begin_frame()
        assert meter.end_frame() == pytest.approx(10.0)
        assert meter.display_fps == pytest.approx(20.0)


def test_frame_rate_meter_display_fps_updates_after_interval() -> None:
    meter = FrameRateMeter(smoothing=1.0, display_interval_sec=1.0)
    with patch(
        "cleave.viz.frame_rate.time.perf_counter",
        side_effect=[0.0, 0.05, 1.0, 1.10],
    ):
        meter.begin_frame()
        assert meter.end_frame() == pytest.approx(20.0)
        assert meter.display_fps == pytest.approx(20.0)

        meter.begin_frame()
        assert meter.end_frame() == pytest.approx(10.0)
        assert meter.display_fps == pytest.approx(10.0)


def _mock_layers() -> list[StemLayer]:
    layer = StemLayer(
        slot="layer_1",
        pm=MagicMock(),
        fbo=MagicMock(),
        playlist=MagicMock(),
    )
    return [layer]


def test_projectm_fps_governor_spike_immunity() -> None:
    governor = ProjectMFpsGovernor(nominal_fps=60)
    governor.observe(60.0)
    governor.observe(10.0)
    assert governor.target_fps >= 57


def test_projectm_fps_governor_sustained_slowdown() -> None:
    governor = ProjectMFpsGovernor(nominal_fps=60)
    for _ in range(120):
        governor.observe(20.0)
    assert governor.target_fps < 55


def test_projectm_fps_governor_floor_clamp() -> None:
    governor = ProjectMFpsGovernor(nominal_fps=60, floor_fps=LIVE_PROJECTM_FPS_FLOOR)
    for _ in range(500):
        governor.observe(5.0)
    assert governor.target_fps == LIVE_PROJECTM_FPS_FLOOR


def test_projectm_fps_governor_recovery_after_dip() -> None:
    governor = ProjectMFpsGovernor(nominal_fps=60)
    for _ in range(120):
        governor.observe(20.0)
    dipped = governor.target_fps
    for _ in range(120):
        governor.observe(60.0)
    assert dipped < governor.target_fps
    assert governor.target_fps >= 55


def test_projectm_fps_governor_apply_if_changed_only_on_change() -> None:
    governor = ProjectMFpsGovernor(nominal_fps=LIVE_PROJECTM_FPS)
    layers = _mock_layers()
    assert governor.apply_if_changed(layers) is True
    layers[0].pm.set_fps.assert_called_once_with(LIVE_PROJECTM_FPS)

    governor.observe(60.0)
    assert governor.apply_if_changed(layers) is False
    layers[0].pm.set_fps.assert_called_once()

    for _ in range(200):
        governor.observe(10.0)
    assert governor.apply_if_changed(layers) is True
    assert layers[0].pm.set_fps.call_count == 2
    assert layers[0].pm.set_fps.call_args.args == (governor.target_fps,)
