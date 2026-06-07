"""Shared clamps and per-driver pulse envelope constants."""

from __future__ import annotations

EFFECT_PCT_MIN = 0
EFFECT_PCT_MAX = 100


def clamp_effect_pct(value: int | float) -> int:
    return max(EFFECT_PCT_MIN, min(EFFECT_PCT_MAX, int(round(float(value)))))

PULSE_DECAY: dict[str, float] = {
    "onset": 0.92,
    "sub_bass": 0.96,
    "mid_bass": 0.94,
    "rms": 0.96,
    "centroid": 0.98,
}

PULSE_GAIN: dict[str, float] = {
    "onset": 1.0,
    "sub_bass": 1.0,
    "mid_bass": 1.0,
    "rms": 1.0,
    "centroid": 1.0,
}
