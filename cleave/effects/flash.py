"""Per-layer flash overlay: threshold burst from normalized stem signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cleave.effects.constants import clamp_effect_pct
from cleave.effects.handlers import EffectHandler
from cleave.effects.registry import EffectDef
from cleave.effects.sampling import sample_normalized
from cleave.signals import Signals

if TYPE_CHECKING:
    from cleave.effects.runtime import LayerModifiers

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
        row: EffectDef,
        t_sec: float,
    ) -> float:
        raw = sample_normalized(signals, row.signal_stem, row.signal_key, t_sec)
        self.burst = update_burst(self.burst, raw, driver_slug=row.driver_slug)
        return self.burst


def _update_flash(
    state: FlashBurstState,
    signals: Signals,
    row: EffectDef,
    t_sec: float,
) -> None:
    state.sample_and_update(signals, row, t_sec)


def _apply_flash(
    mod: LayerModifiers, pct: int, state: FlashBurstState
) -> LayerModifiers:
    mod.flash_alpha = max(mod.flash_alpha, flash_alpha(pct, state.burst))
    return mod


FLASH_HANDLER = EffectHandler[FlashBurstState](
    effect_id="flash",
    state_factory=FlashBurstState,
    update=_update_flash,
    apply=_apply_flash,
)
