"""Per-frame effect state and compositor modifiers."""

from __future__ import annotations

from dataclasses import dataclass, field

from cleave.effects.handlers import handler_for
from cleave.effects.registry import effect_roster
from cleave.signals import Signals
from cleave.viz.session import TuningSession


@dataclass
class LayerModifiers:
    opacity: float = 1.0
    flash_alpha: float = 0.0
    bloom_strength: float = 0.0
    hue_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)
    hue_mix: float = 0.0
    grit_strength: float = 0.0
    aberration_px: float = 0.0


@dataclass
class EffectRuntime:
    """Owns per-row envelope state; tick updates signals then exposes modifiers."""

    _states: dict[tuple[str, str, str], object] = field(default_factory=dict)

    def _state(self, slot: str, effect_id: str, driver_slug: str) -> object:
        key = (slot, effect_id, driver_slug)
        if key not in self._states:
            self._states[key] = handler_for(effect_id).state_factory()
        return self._states[key]

    def update(self, session: TuningSession, signals: Signals | None, t_sec: float) -> None:
        """Advance envelope state from signals (call once per frame)."""
        if signals is None:
            return
        for slot, layer in session.layers.items():
            for row in effect_roster(layer.stem):
                pct = layer.effects.get(row.effect_id, {}).get(row.driver_slug, 0)
                if pct <= 0:
                    continue
                handler = handler_for(row.effect_id)
                state = self._state(slot, row.effect_id, row.driver_slug)
                handler.update(state, signals, row, t_sec)

    def modifiers(self, session: TuningSession) -> dict[str, LayerModifiers]:
        out: dict[str, LayerModifiers] = {}
        for slot, layer in session.layers.items():
            mod = LayerModifiers(opacity=layer.opacity_pct / 100.0)
            for row in effect_roster(layer.stem):
                pct = layer.effects.get(row.effect_id, {}).get(row.driver_slug, 0)
                if pct <= 0:
                    continue
                handler = handler_for(row.effect_id)
                state = self._state(slot, row.effect_id, row.driver_slug)
                mod = handler.apply(mod, pct, state)
            out[slot] = mod
        return out

    def tick(
        self,
        session: TuningSession,
        signals: Signals | None,
        t_sec: float,
    ) -> dict[str, LayerModifiers]:
        self.update(session, signals, t_sec)
        return self.modifiers(session)
