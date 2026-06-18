"""Opacity pulse: envelope follow from normalized stem signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cleave.effects.constants import clamp_effect_pct
from cleave.effects.constants import PULSE_DECAY, PULSE_GAIN
from cleave.effects.handlers import EffectHandler
from cleave.effects.registry import EffectDef
from cleave.effects.sampling import sample_normalized
from cleave.signals import Signals

if TYPE_CHECKING:
    from cleave.effects.runtime import LayerModifiers


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
        row: EffectDef,
        t_sec: float,
    ) -> float:
        raw = sample_normalized(signals, row.signal_stem, row.signal_key, t_sec)
        self.envelope = update_envelope(
            self.envelope, raw, driver_slug=row.driver_slug
        )
        return self.envelope


def _update_pulse(
    state: PulseEnvelopeState,
    signals: Signals,
    row: EffectDef,
    t_sec: float,
) -> None:
    state.sample_and_update(signals, row, t_sec)


def _apply_pulse(
    mod: LayerModifiers, pct: int, state: PulseEnvelopeState
) -> LayerModifiers:
    mod.opacity = effective_opacity(mod.opacity, pct, state.envelope)
    return mod


PULSE_HANDLER = EffectHandler[PulseEnvelopeState](
    effect_id="pulse",
    state_factory=PulseEnvelopeState,
    update=_update_pulse,
    apply=_apply_pulse,
)
