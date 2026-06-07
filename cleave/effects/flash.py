"""Per-layer flash overlay: threshold burst from normalized stem signals."""

from __future__ import annotations

from dataclasses import dataclass

from cleave.effects.constants import clamp_effect_pct
from cleave.effects.sampling import sample_normalized
from cleave.signals import Signals

FLASH_DECAY = 0.82
FLASH_PEAK = 1.0
FLASH_BURST_SCALE = 1.8

FLASH_THRESHOLD_ONSET = 0.65
FLASH_THRESHOLD_CONTINUOUS = 0.50


def flash_threshold(driver_slug: str) -> float:
    if driver_slug == "onset":
        return FLASH_THRESHOLD_ONSET
    return FLASH_THRESHOLD_CONTINUOUS


def update_burst(burst: float, signal: float, *, driver_slug: str) -> float:
    threshold = flash_threshold(driver_slug)
    next_burst = burst * FLASH_DECAY
    if signal > threshold:
        next_burst = max(next_burst, (signal - threshold) * FLASH_BURST_SCALE)
    return next_burst


def flash_alpha(effect_pct: int, burst: float) -> float:
    mix = clamp_effect_pct(effect_pct) / 100.0
    return mix * burst * FLASH_PEAK


@dataclass
class FlashBurstState:
    burst: float = 0.0

    def sample_and_update(
        self,
        signals: Signals,
        signal_stem: str,
        signal_key: str,
        driver_slug: str,
        t_sec: float,
    ) -> float:
        raw = sample_normalized(signals, signal_stem, signal_key, t_sec)
        self.burst = update_burst(self.burst, raw, driver_slug=driver_slug)
        return self.burst
