"""Per-layer hue tint from vocal pitch (vocals only)."""

from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass

from cleave.effects.constants import clamp_effect_pct
from cleave.signals import Signals

PITCH_MIN_HZ = 80.0
PITCH_MAX_HZ = 800.0
HUE_LERP = 0.06
HUE_DECAY_UNVOICED = 0.03
NEUTRAL_HUE_DEG = 180.0
HUE_SAT = 0.55
HUE_VAL = 1.0


def pitch_to_hue(hz: float) -> float:
    t = (hz - PITCH_MIN_HZ) / (PITCH_MAX_HZ - PITCH_MIN_HZ)
    t = max(0.0, min(1.0, t))
    return t * 300.0


def lerp_hue(current: float, target: float, factor: float) -> float:
    diff = (target - current + 180.0) % 360.0 - 180.0
    return (current + diff * factor) % 360.0


def hue_rgb(hue_deg: float) -> tuple[float, float, float]:
    r, g, b = colorsys.hsv_to_rgb(hue_deg / 360.0, HUE_SAT, HUE_VAL)
    return (r, g, b)


def is_voiced_pitch(hz: float) -> bool:
    return not math.isnan(hz) and hz > 0.0


def hue_mix_pct(effect_pct: int) -> float:
    return clamp_effect_pct(effect_pct) / 100.0


def sample_pitch_hz(signals: Signals, stem: str, key: str, t_sec: float) -> float:
    """Interpolate pitch_hz at playback time (NaN when unvoiced)."""
    values = signals.array(stem, key)
    if len(values) == 0:
        return float("nan")

    sr = signals.sample_rate_hz
    t_max = (len(values) - 1) / sr
    t = min(max(t_sec, 0.0), t_max)
    pos = t * sr
    i = int(pos)
    if i >= len(values) - 1:
        return float(values[-1])
    frac = pos - i
    a = float(values[i])
    b = float(values[i + 1])
    if frac <= 0.0:
        return a
    if frac >= 1.0:
        return b
    if math.isnan(a) or math.isnan(b):
        return float("nan")
    return a * (1.0 - frac) + b * frac


def update_hue(state: HueState, pitch_hz: float) -> None:
    if is_voiced_pitch(pitch_hz):
        target = pitch_to_hue(pitch_hz)
        state.last_hue = target
        state.hue_deg = lerp_hue(state.hue_deg, target, HUE_LERP)
    else:
        state.hue_deg = lerp_hue(state.hue_deg, NEUTRAL_HUE_DEG, HUE_DECAY_UNVOICED)


@dataclass
class HueState:
    hue_deg: float = NEUTRAL_HUE_DEG
    last_hue: float = NEUTRAL_HUE_DEG

    def sample_and_update(
        self,
        signals: Signals,
        signal_stem: str,
        signal_key: str,
        t_sec: float,
    ) -> float:
        pitch_hz = sample_pitch_hz(signals, signal_stem, signal_key, t_sec)
        update_hue(self, pitch_hz)
        return self.hue_deg
