"""Per-layer film grain and chromatic aberration: envelope follow from signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cleave.effects.constants import clamp_effect_pct
from cleave.effects.handlers import EffectHandler
from cleave.effects.pulse import update_envelope
from cleave.effects.registry import EffectDef
from cleave.effects.sampling import sample_normalized
from cleave.signals import Signals

if TYPE_CHECKING:
    from cleave.effects.runtime import LayerModifiers

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
        row: EffectDef,
        t_sec: float,
    ) -> float:
        raw = sample_normalized(signals, row.signal_stem, row.signal_key, t_sec)
        self.envelope = update_envelope(
            self.envelope, raw, driver_slug=row.driver_slug
        )
        return self.envelope


def _update_grit(
    state: GritState,
    signals: Signals,
    row: EffectDef,
    t_sec: float,
) -> None:
    state.sample_and_update(signals, row, t_sec)


def _apply_grit(mod: LayerModifiers, pct: int, state: GritState) -> LayerModifiers:
    mod.grit_strength = max(
        mod.grit_strength, grit_strength(pct, state.envelope)
    )
    mod.aberration_px = max(
        mod.aberration_px, aberration_px(pct, state.envelope)
    )
    return mod


GRIT_HANDLER = EffectHandler[GritState](
    effect_id="grit",
    state_factory=GritState,
    update=_update_grit,
    apply=_apply_grit,
)
