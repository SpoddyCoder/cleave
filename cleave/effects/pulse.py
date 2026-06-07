"""Opacity pulse: envelope follow from normalized stem signals."""

from __future__ import annotations

from dataclasses import dataclass

from cleave.effects.constants import clamp_effect_pct
from cleave.effects.constants import PULSE_DECAY, PULSE_GAIN
from cleave.effects.sampling import sample_normalized
from cleave.signals import Signals


def update_envelope(envelope: float, raw: float, *, driver_slug: str) -> float:
    decay = PULSE_DECAY[driver_slug]
    gain = PULSE_GAIN[driver_slug]
    return max(envelope * decay, raw * gain)


def effective_opacity(
    base_opacity: float,
    effect_pct: int,
    smoothed_signal: float,
) -> float:
    mix = clamp_effect_pct(effect_pct) / 100.0
    factor = 1.0 + (smoothed_signal - 1.0) * mix
    return max(0.0, base_opacity * factor)


@dataclass
class PulseEnvelopeState:
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
