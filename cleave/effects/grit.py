"""Per-layer film grain and chromatic aberration: envelope follow from signals."""

from __future__ import annotations

from dataclasses import dataclass

from cleave.effects.constants import clamp_effect_pct
from cleave.effects.pulse import update_envelope
from cleave.effects.sampling import sample_normalized
from cleave.signals import Signals

GRIT_SCALE = 0.4
ABERRATION_MAX_PX = 3.0


def grit_strength(effect_pct: int, envelope: float) -> float:
    mix = clamp_effect_pct(effect_pct) / 100.0
    return mix * envelope * GRIT_SCALE


def aberration_px(effect_pct: int, envelope: float) -> float:
    mix = clamp_effect_pct(effect_pct) / 100.0
    return ABERRATION_MAX_PX * envelope * mix


@dataclass
class GritState:
    envelope: float = 0.0

    def sample_and_update(
        self,
        signals: Signals,
        signal_stem: str,
        signal_key: str,
        driver_slug: str,
        t_sec: float,
    ) -> float:
        raw = sample_normalized(signals, signal_stem, signal_key, t_sec)
        self.envelope = update_envelope(
            self.envelope, raw, driver_slug=driver_slug
        )
        return self.envelope
