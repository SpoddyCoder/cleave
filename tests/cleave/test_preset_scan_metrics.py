"""Unit tests for preset scan frame metrics and cache serialization."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from cleave.preset_scan_metrics import (
    LUMA_COVERAGE_CUTOFFS,
    METRICS_CACHE_VERSION,
    FrameMetrics,
    MetricsCache,
    PresetMetrics,
    frame_metrics_from_dict,
    frame_metrics_to_dict,
    load_metrics_cache,
    metrics_cache_from_dict,
    metrics_cache_to_dict,
    peak_metrics,
    preset_metrics_from_dict,
    preset_metrics_to_dict,
    sample_frame_metrics,
    write_metrics_cache,
)


def _frame(
    *,
    max_luma: float,
    mean_luma: float,
    coverage_16: float = 0.0,
) -> FrameMetrics:
    coverage = {cutoff: 0.0 for cutoff in LUMA_COVERAGE_CUTOFFS}
    coverage[16] = coverage_16
    return FrameMetrics(max_luma=max_luma, mean_luma=mean_luma, coverage=coverage)


def test_peak_metrics_empty() -> None:
    result = peak_metrics([], warmup_frames=5, window_frames=10)
    assert result.max_luma == 0.0
    assert result.mean_luma == 0.0
    assert result.coverage == {cutoff: 0.0 for cutoff in LUMA_COVERAGE_CUTOFFS}


def test_peak_metrics_skips_warmup_and_limits_window() -> None:
    frames = [
        _frame(max_luma=1.0, mean_luma=1.0, coverage_16=0.01),
        _frame(max_luma=2.0, mean_luma=2.0, coverage_16=0.02),
        _frame(max_luma=100.0, mean_luma=10.0, coverage_16=0.5),
        _frame(max_luma=50.0, mean_luma=30.0, coverage_16=0.3),
        _frame(max_luma=80.0, mean_luma=20.0, coverage_16=0.4),
    ]
    result = peak_metrics(frames, warmup_frames=2, window_frames=2)
    assert result.max_luma == 100.0
    assert result.mean_luma == 30.0
    assert result.coverage[16] == 0.5


def test_peak_metrics_unbounded_window_uses_all_post_warmup() -> None:
    frames = [
        _frame(max_luma=5.0, mean_luma=1.0),
        _frame(max_luma=10.0, mean_luma=3.0),
        _frame(max_luma=7.0, mean_luma=9.0),
    ]
    result = peak_metrics(frames, warmup_frames=1, window_frames=0)
    assert result.max_luma == 10.0
    assert result.mean_luma == 9.0


def test_peak_metrics_excludes_frames_outside_window() -> None:
    frames = [
        _frame(max_luma=1.0, mean_luma=1.0),
        _frame(max_luma=20.0, mean_luma=20.0),
        _frame(max_luma=5.0, mean_luma=5.0),
        _frame(max_luma=999.0, mean_luma=999.0),
    ]
    result = peak_metrics(frames, warmup_frames=1, window_frames=2)
    assert result.max_luma == 20.0
    assert result.mean_luma == 20.0


def test_peak_metrics_takes_peak_not_last() -> None:
    frames = [
        _frame(max_luma=200.0, mean_luma=5.0, coverage_16=0.9),
        _frame(max_luma=1.0, mean_luma=1.0, coverage_16=0.001),
    ]
    result = peak_metrics(frames, warmup_frames=0, window_frames=2)
    assert result.max_luma == 200.0
    assert result.mean_luma == 5.0
    assert result.coverage[16] == 0.9


def test_frame_metrics_json_round_trip() -> None:
    original = FrameMetrics(
        max_luma=123.5,
        mean_luma=12.3,
        coverage={cutoff: float(cutoff) / 256.0 for cutoff in LUMA_COVERAGE_CUTOFFS},
    )
    restored = frame_metrics_from_dict(frame_metrics_to_dict(original))
    assert restored == original


def test_preset_metrics_json_round_trip() -> None:
    original = PresetMetrics(
        path=Path("/tmp/example.milk"),
        load_failed=False,
        error=None,
        fps=30,
        frames=(
            _frame(max_luma=1.0, mean_luma=0.5, coverage_16=0.01),
            _frame(max_luma=2.0, mean_luma=1.5, coverage_16=0.02),
        ),
    )
    restored = preset_metrics_from_dict(preset_metrics_to_dict(original))
    assert restored == original


def test_metrics_cache_json_round_trip() -> None:
    original = MetricsCache(
        version=METRICS_CACHE_VERSION,
        probe_fps=30,
        fbo_size=(480, 270),
        presets=(
            PresetMetrics(
                path=Path("/tmp/a.milk"),
                load_failed=True,
                error="shader compile failed",
                fps=30,
                frames=(),
            ),
            PresetMetrics(
                path=Path("/tmp/b.milk"),
                load_failed=False,
                error=None,
                fps=30,
                frames=(_frame(max_luma=10.0, mean_luma=5.0, coverage_16=0.1),),
            ),
        ),
    )
    restored = metrics_cache_from_dict(metrics_cache_to_dict(original))
    assert restored == original


def test_write_and_load_metrics_cache() -> None:
    cache = MetricsCache(
        version=METRICS_CACHE_VERSION,
        probe_fps=30,
        fbo_size=(480, 270),
        presets=(
            PresetMetrics(
                path=Path("/tmp/c.milk"),
                load_failed=False,
                error=None,
                fps=30,
                frames=(_frame(max_luma=3.0, mean_luma=2.0),),
            ),
        ),
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "metrics.json"
        write_metrics_cache(path, cache)
        loaded = load_metrics_cache(path)
        assert loaded == cache
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["version"] == METRICS_CACHE_VERSION
        assert payload["probe_fps"] == 30


def test_metrics_cache_from_dict_rejects_bad_version() -> None:
    with pytest.raises(ValueError, match="unsupported metrics cache version"):
        metrics_cache_from_dict({"version": 99, "probe_fps": 30, "fbo_size": [1, 1], "presets": []})


@patch("cleave.preset_scan_metrics.glReadPixels")
def test_sample_frame_metrics_full_frame(mock_read_pixels) -> None:
    width, height = 4, 2
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[0, 0] = (255, 255, 255, 255)
    rgba[1, 3] = (128, 128, 128, 255)
    mock_read_pixels.return_value = rgba.tobytes()

    result = sample_frame_metrics(width, height)

    mock_read_pixels.assert_called_once()
    assert result.max_luma == pytest.approx(255.0)
    expected_mean = float(
        np.mean(
            0.2126 * rgba[..., 0].astype(np.float32)
            + 0.7152 * rgba[..., 1].astype(np.float32)
            + 0.0722 * rgba[..., 2].astype(np.float32)
        )
    )
    assert result.mean_luma == pytest.approx(expected_mean)
    assert result.coverage[8] == pytest.approx(0.25)
    assert result.coverage[192] == pytest.approx(0.125)
