"""Resample native-rate analysis frames to a uniform 100 Hz grid."""

from __future__ import annotations

import numpy as np

TARGET_HZ = 100.0


def resample_to_100hz(
    values: np.ndarray,
    times: np.ndarray,
    duration_sec: float,
) -> np.ndarray:
    """Linearly interpolate *values* onto a uniform 100 Hz time grid.

    Grid covers ``[0, duration_sec)`` with ``round(duration_sec * 100)`` samples
    (endpoint excluded), spaced at 1/100 second.
    """
    values = np.asarray(values, dtype=np.float64)
    times = np.asarray(times, dtype=np.float64)

    n_out = max(0, round(duration_sec * TARGET_HZ))
    if n_out == 0:
        return np.array([], dtype=np.float64)

    grid = np.arange(n_out, dtype=np.float64) / TARGET_HZ
    return np.interp(grid, times, values)
