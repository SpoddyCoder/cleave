"""Tests for cleave.resample."""

from __future__ import annotations

import numpy as np
import pytest

from cleave.resample import TARGET_HZ, resample_to_100hz


def test_resample_empty_duration_returns_empty_array() -> None:
    values = np.array([1.0, 2.0, 3.0])
    times = np.array([0.0, 0.01, 0.02])
    result = resample_to_100hz(values, times, duration_sec=0.0)
    assert result.dtype == np.float64
    assert result.size == 0


@pytest.mark.parametrize(
    ("duration_sec", "expected_n"),
    [
        (0.14, 14),
        (1.0, 100),
        (0.015, 2),
        (2.345, 235),
    ],
)
def test_resample_n_out_matches_duration(duration_sec: float, expected_n: int) -> None:
    values = np.linspace(0.0, 1.0, 5)
    times = np.linspace(0.0, duration_sec, 5)
    result = resample_to_100hz(values, times, duration_sec)
    assert len(result) == expected_n
    assert len(result) == max(0, round(duration_sec * TARGET_HZ))


def test_resample_linear_interpolation_at_known_points() -> None:
    times = np.array([0.0, 0.5, 1.0])
    values = np.array([0.0, 10.0, 20.0])
    result = resample_to_100hz(values, times, duration_sec=1.0)

    assert len(result) == 100
    assert result[0] == pytest.approx(0.0)
    assert result[50] == pytest.approx(10.0)
    assert result[25] == pytest.approx(5.0)
    assert result[75] == pytest.approx(15.0)


def test_resample_single_source_point() -> None:
    values = np.array([42.0])
    times = np.array([0.0])
    result = resample_to_100hz(values, times, duration_sec=0.03)
    assert len(result) == 3
    assert np.all(result == pytest.approx(42.0))


def test_resample_boundary_excludes_endpoint() -> None:
    times = np.array([0.0, 1.0])
    values = np.array([0.0, 100.0])
    result = resample_to_100hz(values, times, duration_sec=1.0)
    assert len(result) == 100
    last_grid_t = (len(result) - 1) / TARGET_HZ
    assert last_grid_t == pytest.approx(0.99)
    assert result[-1] == pytest.approx(99.0)
