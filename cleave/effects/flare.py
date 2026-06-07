"""Per-layer bloom flare: onset delta and threshold burst (drums only)."""

from __future__ import annotations

from dataclasses import dataclass

from cleave.effects.constants import clamp_effect_pct
from cleave.effects.sampling import sample_normalized
from cleave.signals import Signals

FLARE_DELTA = 0.10
FLARE_THRESHOLD = 0.55
FLARE_DECAY = 0.75
FLARE_SMOOTH_DECAY = 0.92
FLARE_BLUR_RADIUS = 8.0
FLARE_INTENSITY_SCALE = 1.5


def update_smoothed(smoothed: float, raw: float) -> float:
    return max(smoothed * FLARE_SMOOTH_DECAY, raw)


def flare_triggered(raw: float, smoothed: float, prev_smoothed: float) -> bool:
    delta = smoothed - prev_smoothed
    return delta > FLARE_DELTA or raw > FLARE_THRESHOLD


def update_burst(
    burst: float,
    raw: float,
    *,
    smoothed: float,
    prev_smoothed: float,
) -> float:
    next_burst = burst * FLARE_DECAY
    if flare_triggered(raw, smoothed, prev_smoothed):
        next_burst = max(next_burst, 1.0)
    return next_burst


def bloom_strength(effect_pct: int, burst: float) -> float:
    mix = clamp_effect_pct(effect_pct) / 100.0
    return mix * burst


@dataclass
class FlareBurstState:
    burst: float = 0.0
    smoothed: float = 0.0

    def sample_and_update(
        self,
        signals: Signals,
        signal_stem: str,
        signal_key: str,
        t_sec: float,
    ) -> float:
        raw = sample_normalized(signals, signal_stem, signal_key, t_sec)
        prev_smoothed = self.smoothed
        self.smoothed = update_smoothed(self.smoothed, raw)
        self.burst = update_burst(
            self.burst,
            raw,
            smoothed=self.smoothed,
            prev_smoothed=prev_smoothed,
        )
        return self.burst
