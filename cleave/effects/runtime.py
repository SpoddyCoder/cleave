"""Per-frame effect state and compositor modifiers."""

from __future__ import annotations

from dataclasses import dataclass, field

from cleave.effects.flash import FlashBurstState, flash_alpha
from cleave.effects.flare import FlareBurstState, bloom_strength
from cleave.effects.grit import GritState, aberration_px, grit_strength
from cleave.effects.hue import HueState, hue_mix_pct, hue_rgb
from cleave.effects.pulse import PulseEnvelopeState, effective_opacity
from cleave.effects.registry import effect_roster
from cleave.signals import Signals
from cleave.viz.controls import TuningSession


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

    _pulse_states: dict[tuple[str, str, str], PulseEnvelopeState] = field(
        default_factory=dict
    )
    _flash_states: dict[tuple[str, str, str], FlashBurstState] = field(
        default_factory=dict
    )
    _flare_states: dict[tuple[str, str, str], FlareBurstState] = field(
        default_factory=dict
    )
    _hue_states: dict[tuple[str, str, str], HueState] = field(
        default_factory=dict
    )
    _grit_states: dict[tuple[str, str, str], GritState] = field(
        default_factory=dict
    )

    def _pulse_state(self, stem: str, effect_id: str, driver_slug: str) -> PulseEnvelopeState:
        key = (stem, effect_id, driver_slug)
        if key not in self._pulse_states:
            self._pulse_states[key] = PulseEnvelopeState()
        return self._pulse_states[key]

    def _flash_state(self, stem: str, effect_id: str, driver_slug: str) -> FlashBurstState:
        key = (stem, effect_id, driver_slug)
        if key not in self._flash_states:
            self._flash_states[key] = FlashBurstState()
        return self._flash_states[key]

    def _flare_state(self, stem: str, effect_id: str, driver_slug: str) -> FlareBurstState:
        key = (stem, effect_id, driver_slug)
        if key not in self._flare_states:
            self._flare_states[key] = FlareBurstState()
        return self._flare_states[key]

    def _hue_state(self, stem: str, effect_id: str, driver_slug: str) -> HueState:
        key = (stem, effect_id, driver_slug)
        if key not in self._hue_states:
            self._hue_states[key] = HueState()
        return self._hue_states[key]

    def _grit_state(self, stem: str, effect_id: str, driver_slug: str) -> GritState:
        key = (stem, effect_id, driver_slug)
        if key not in self._grit_states:
            self._grit_states[key] = GritState()
        return self._grit_states[key]

    def update(self, session: TuningSession, signals: Signals | None, t_sec: float) -> None:
        """Advance envelope state from signals (call once per frame)."""
        if signals is None:
            return
        for stem, layer in session.layers.items():
            for row in effect_roster(stem):
                if row.effect_id != "pulse":
                    continue
                pct = layer.effects.get(row.effect_id, {}).get(row.driver_slug, 0)
                if pct <= 0:
                    continue
                state = self._pulse_state(stem, row.effect_id, row.driver_slug)
                state.sample_and_update(
                    signals,
                    row.signal_stem,
                    row.signal_key,
                    row.driver_slug,
                    t_sec,
                )
            for row in effect_roster(stem):
                if row.effect_id != "flash":
                    continue
                pct = layer.effects.get(row.effect_id, {}).get(row.driver_slug, 0)
                if pct <= 0:
                    continue
                state = self._flash_state(stem, row.effect_id, row.driver_slug)
                state.sample_and_update(
                    signals,
                    row.signal_stem,
                    row.signal_key,
                    row.driver_slug,
                    t_sec,
                )
            for row in effect_roster(stem):
                if row.effect_id != "flare":
                    continue
                pct = layer.effects.get(row.effect_id, {}).get(row.driver_slug, 0)
                if pct <= 0:
                    continue
                state = self._flare_state(stem, row.effect_id, row.driver_slug)
                state.sample_and_update(
                    signals,
                    row.signal_stem,
                    row.signal_key,
                    t_sec,
                )
            for row in effect_roster(stem):
                if row.effect_id != "hue":
                    continue
                pct = layer.effects.get(row.effect_id, {}).get(row.driver_slug, 0)
                if pct <= 0:
                    continue
                state = self._hue_state(stem, row.effect_id, row.driver_slug)
                state.sample_and_update(
                    signals,
                    row.signal_stem,
                    row.signal_key,
                    t_sec,
                )
            for row in effect_roster(stem):
                if row.effect_id != "grit":
                    continue
                pct = layer.effects.get(row.effect_id, {}).get(row.driver_slug, 0)
                if pct <= 0:
                    continue
                state = self._grit_state(stem, row.effect_id, row.driver_slug)
                state.sample_and_update(
                    signals,
                    row.signal_stem,
                    row.signal_key,
                    row.driver_slug,
                    t_sec,
                )

    def modifiers(self, session: TuningSession) -> dict[str, LayerModifiers]:
        out: dict[str, LayerModifiers] = {}
        for stem, layer in session.layers.items():
            base = layer.opacity_pct / 100.0
            opacity = base
            for row in effect_roster(stem):
                if row.effect_id != "pulse":
                    continue
                pct = layer.effects.get(row.effect_id, {}).get(row.driver_slug, 0)
                if pct <= 0:
                    continue
                state = self._pulse_state(stem, row.effect_id, row.driver_slug)
                opacity = effective_opacity(base, pct, state.envelope)
                base = opacity
            layer_flash_alpha = 0.0
            for row in effect_roster(stem):
                if row.effect_id != "flash":
                    continue
                pct = layer.effects.get(row.effect_id, {}).get(row.driver_slug, 0)
                if pct <= 0:
                    continue
                state = self._flash_state(stem, row.effect_id, row.driver_slug)
                layer_flash_alpha = max(
                    layer_flash_alpha, flash_alpha(pct, state.burst)
                )
            layer_bloom_strength = 0.0
            for row in effect_roster(stem):
                if row.effect_id != "flare":
                    continue
                pct = layer.effects.get(row.effect_id, {}).get(row.driver_slug, 0)
                if pct <= 0:
                    continue
                state = self._flare_state(stem, row.effect_id, row.driver_slug)
                layer_bloom_strength = max(
                    layer_bloom_strength, bloom_strength(pct, state.burst)
                )
            layer_hue_rgb = (1.0, 1.0, 1.0)
            layer_hue_mix = 0.0
            for row in effect_roster(stem):
                if row.effect_id != "hue":
                    continue
                pct = layer.effects.get(row.effect_id, {}).get(row.driver_slug, 0)
                if pct <= 0:
                    continue
                state = self._hue_state(stem, row.effect_id, row.driver_slug)
                layer_hue_rgb = hue_rgb(state.hue_deg)
                layer_hue_mix = hue_mix_pct(pct)
            layer_grit_strength = 0.0
            layer_aberration_px = 0.0
            for row in effect_roster(stem):
                if row.effect_id != "grit":
                    continue
                pct = layer.effects.get(row.effect_id, {}).get(row.driver_slug, 0)
                if pct <= 0:
                    continue
                state = self._grit_state(stem, row.effect_id, row.driver_slug)
                layer_grit_strength = max(
                    layer_grit_strength, grit_strength(pct, state.envelope)
                )
                layer_aberration_px = max(
                    layer_aberration_px, aberration_px(pct, state.envelope)
                )
            out[stem] = LayerModifiers(
                opacity=opacity,
                flash_alpha=layer_flash_alpha,
                bloom_strength=layer_bloom_strength,
                hue_rgb=layer_hue_rgb,
                hue_mix=layer_hue_mix,
                grit_strength=layer_grit_strength,
                aberration_px=layer_aberration_px,
            )
        return out

    def tick(
        self,
        session: TuningSession,
        signals: Signals | None,
        t_sec: float,
    ) -> dict[str, LayerModifiers]:
        self.update(session, signals, t_sec)
        return self.modifiers(session)
