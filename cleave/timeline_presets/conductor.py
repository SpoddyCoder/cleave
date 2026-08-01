"""Stem conductor: audio-derived phrase weights and continuous cue levels."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from cleave.blend_modes import BlendMode
from cleave.cue_roles import CUE_ROLE_BLEND, CueRole
from cleave.extract import StemSource
from cleave.signals import Signals
from cleave.timeline import LEVEL_QUANTUM, clamp_level, quantize_level

_STEM_PRESENCE: dict[StemSource, str] = {
    "drums": "onset_strength",
    "bass": "rms",
    "vocals": "rms",
    "other": "rms",
    "full_mix": "rms",
}
CONDUCTOR_LEVEL_FLOOR = LEVEL_QUANTUM  # an active slot is never dimmer
# Budget multipliers span a range centred on 1.0: the conductor moves weight
# between phrases rather than lowering it across the whole song.
CONDUCTOR_GAIN_MIN, CONDUCTOR_GAIN_MAX = 0.65, 1.35
# Lead level follows phrase energy relative to the song peak, so only genuinely
# quiet passages dim. A within-song rank would dim half of every song.
# Exponent > 1 steepens the curve so typical compressed masters still land
# across multiple LEVEL_QUANTUM steps after quantize (0.5 softens toward 1.0).
CONDUCTOR_CEILING_MIN = 0.5
CONDUCTOR_CEILING_EXPONENT = 2.0
CONDUCTOR_SILENCE_FLOOR = 0.08
# Neutral point of a standardised slot activity (rank fraction across phrases).
CONDUCTOR_ACTIVITY_MIDPOINT = 0.5
# Lowest fraction of the lead level a supporting slot may take, by density bias:
# denser staging keeps the whole stack visible instead of a lead plus ghosts.
# Floors must leave headroom below 1.0 after LEVEL_QUANTUM quantize; 0.75+ with
# a near-full lead ceiling collapses every active slot to 1.0.
CONDUCTOR_SUPPORT_FLOOR_BY_BIAS: dict[int, float] = {
    -2: 0.25,
    -1: 0.35,
    0: 0.45,
    1: 0.55,
    2: 0.70,
}
# Penalty on a slot's share of accumulated airtime above an even share.
AIRTIME_PENALTY = 1.0

DEFAULT_TIMELINE_PRESET_CONDUCTOR = False

_RAW_ACTIVITY_FLOOR = 1e-3
_ENERGY_FLAT_EPS = 1e-9
# Raw presence below this reads as absent, so a dead stem never ranks as a lead.
_SLOT_SILENCE_FLOOR = 0.02
# Percentile of a slot's own phrase presence that counts as "fully present".
_SLOT_SCALE_PERCENTILE = 80.0


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * float(t)


def _rank_fractions(values: np.ndarray) -> np.ndarray:
    """Within-series rank in ``0..1``; a flat or single-element series is neutral."""
    n = len(values)
    if n == 0:
        return values
    if n == 1 or float(np.nanmax(values) - np.nanmin(values)) <= _ENERGY_FLAT_EPS:
        return np.full(n, CONDUCTOR_ACTIVITY_MIDPOINT, dtype=np.float64)
    ranks = np.argsort(np.argsort(values)).astype(np.float64)
    return ranks / (n - 1)


def support_floor_for(density_bias: int) -> float:
    """Support-slot floor as a fraction of the lead level for ``density_bias``."""
    return CONDUCTOR_SUPPORT_FLOOR_BY_BIAS.get(
        density_bias, CONDUCTOR_SUPPORT_FLOOR_BY_BIAS[0]
    )


@dataclass(frozen=True)
class PhraseWeights:
    budget_gain: float
    slot_activity: dict[str, float]
    lead_ceiling: float
    near_silent: bool


def timeline_preset_conductor_display(conductor: bool) -> str:
    return "on" if conductor else "off"


def cycle_timeline_preset_conductor(value: bool, *, forward: bool) -> bool:
    options = (False, True)
    try:
        index = options.index(bool(value))
    except ValueError:
        index = options.index(DEFAULT_TIMELINE_PRESET_CONDUCTOR)
    delta = 1 if forward else -1
    return options[(index + delta) % len(options)]


class StemConductor:
    def __init__(
        self,
        *,
        signals: Signals,
        slot_stems: Mapping[str, StemSource],
        phrase_bounds: Sequence[tuple[float, float]],
        phrase_weights: Sequence[PhraseWeights],
        slot_scales: Mapping[str, float],
        support_floor: float,
    ) -> None:
        self._signals = signals
        self._slot_stems = dict(slot_stems)
        self._phrase_bounds = list(phrase_bounds)
        self._phrase_weights = list(phrase_weights)
        self._slot_scales = dict(slot_scales)
        self._support_floor = float(support_floor)

    @classmethod
    def build(
        cls,
        signals: Signals | None,
        slot_stems: Mapping[str, StemSource] | None,
        phrases: Sequence[tuple[float, float]],
        density_bias: int = 0,
    ) -> StemConductor | None:
        if signals is None or not slot_stems or not phrases:
            return None
        try:
            signals.array("full_mix", "rms")
            signals.array("full_mix", "onset_strength")
            for stem in slot_stems.values():
                signals.array(stem, _STEM_PRESENCE[stem])
        except KeyError:
            return None

        energies: list[float] = []
        for t0, t1 in phrases:
            rms = signals.window_mean("full_mix", "rms", t0, t1)
            onset = signals.window_mean("full_mix", "onset_strength", t0, t1)
            energies.append(0.65 * rms + 0.35 * onset)

        energy_arr = np.asarray(energies, dtype=np.float64)
        if not np.isfinite(energy_arr).any():
            return None
        peak = float(np.nanmax(energy_arr))
        if peak <= 0.0:
            return None
        if (
            len(energy_arr) >= 2
            and float(np.nanmax(energy_arr) - np.nanmin(energy_arr)) <= _ENERGY_FLAT_EPS
        ):
            return None

        rank_frac = _rank_fractions(energy_arr)

        # Standardise each slot within the song: raw envelopes are not comparable
        # across stems (drum onsets are spiky and low-mean, rms is dense and
        # high-mean), so activity means "busier than usual for this stem".
        slot_activity_series: dict[str, np.ndarray] = {}
        slot_scales: dict[str, float] = {}
        for slot, stem in slot_stems.items():
            key = _STEM_PRESENCE[stem]
            raw = np.asarray(
                [signals.window_mean(stem, key, t0, t1) for t0, t1 in phrases],
                dtype=np.float64,
            )
            slot_activity_series[slot] = np.where(
                raw < _SLOT_SILENCE_FLOOR, 0.0, _rank_fractions(raw)
            )
            slot_scales[slot] = max(
                float(np.nanpercentile(raw, _SLOT_SCALE_PERCENTILE)),
                _RAW_ACTIVITY_FLOOR,
            )

        phrase_weights: list[PhraseWeights] = []
        for i in range(len(phrases)):
            rank = float(rank_frac[i])
            energy = float(energy_arr[i])
            loudness = clamp_level(energy / peak) ** CONDUCTOR_CEILING_EXPONENT
            phrase_weights.append(
                PhraseWeights(
                    budget_gain=_lerp(CONDUCTOR_GAIN_MIN, CONDUCTOR_GAIN_MAX, rank),
                    slot_activity={
                        slot: float(series[i])
                        for slot, series in slot_activity_series.items()
                    },
                    lead_ceiling=_lerp(CONDUCTOR_CEILING_MIN, 1.0, loudness),
                    near_silent=energy < CONDUCTOR_SILENCE_FLOOR,
                )
            )

        return cls(
            signals=signals,
            slot_stems=slot_stems,
            phrase_bounds=phrases,
            phrase_weights=phrase_weights,
            slot_scales=slot_scales,
            support_floor=support_floor_for(density_bias),
        )

    def phrase_at(self, t: float) -> PhraseWeights:
        if not self._phrase_weights:
            raise ValueError("StemConductor has no phrases")
        for i, (t0, t1) in enumerate(self._phrase_bounds):
            if t0 <= t < t1:
                return self._phrase_weights[i]
        if t < self._phrase_bounds[0][0]:
            return self._phrase_weights[0]
        return self._phrase_weights[-1]

    def rotation_for(
        self,
        singles_slots: Sequence[str],
        weights: PhraseWeights,
        layer_airtime: Mapping[str, float],
    ) -> int:
        """Index of the slot that should lead: busiest stem, minus airtime hogging."""
        if not singles_slots:
            return 0
        total = sum(max(0.0, float(value)) for value in layer_airtime.values())
        even_share = 1.0 / len(singles_slots)
        best_i = 0
        best_score = float("-inf")
        for i, slot in enumerate(singles_slots):
            activity = weights.slot_activity.get(slot, 0.0)
            if total > 0.0:
                share = max(0.0, float(layer_airtime.get(slot, 0.0))) / total
            else:
                share = even_share
            score = activity - AIRTIME_PENALTY * (share - even_share)
            if score > best_score:
                best_score = score
                best_i = i
        return best_i

    def chord_score(self, active: frozenset[str], weights: PhraseWeights) -> float:
        """Mean slot activity centred on neutral, so chord size is not penalised."""
        if not active:
            return 0.0
        total = sum(
            weights.slot_activity.get(slot, 0.0) - CONDUCTOR_ACTIVITY_MIDPOINT
            for slot in active
        )
        return total / len(active)

    def cast_for_state(
        self,
        active: frozenset[str] | set[str],
        weights: PhraseWeights,
    ) -> dict[str, tuple[CueRole, BlendMode]]:
        """Assign one role and blend per active slot for a state.

        Near-silent phrases cast every active slot as bed. Otherwise drums with
        non-trivial activity become pulse; the highest-activity non-pulse slot
        is lead (solo states are always lead); remaining slots are bed. At most
        one lead; accent is never assigned.
        """
        if not active:
            return {}

        def _role(role: CueRole) -> tuple[CueRole, BlendMode]:
            return (role, CUE_ROLE_BLEND[role])

        if weights.near_silent:
            return {slot: _role("bed") for slot in active}

        if len(active) == 1:
            slot = next(iter(active))
            return {slot: _role("lead")}

        cast: dict[str, tuple[CueRole, BlendMode]] = {}
        pulse_slots: set[str] = set()
        for slot in active:
            if (
                self._slot_stems.get(slot) == "drums"
                and weights.slot_activity.get(slot, 0.0) > 0.0
            ):
                cast[slot] = _role("pulse")
                pulse_slots.add(slot)

        candidates = sorted(slot for slot in active if slot not in pulse_slots)
        if candidates:
            lead = max(
                candidates, key=lambda s: weights.slot_activity.get(s, 0.0)
            )
            cast[lead] = _role("lead")
            for slot in candidates:
                if slot != lead:
                    cast[slot] = _role("bed")
        return cast

    def level_states(
        self,
        states: Sequence[tuple[float, frozenset[str]]],
        duration_sec: float,
    ) -> list[tuple[float, dict[str, float]]]:
        if not states:
            return []
        out: list[tuple[float, dict[str, float]]] = []
        for i, (t, active) in enumerate(states):
            t1 = states[i + 1][0] if i + 1 < len(states) else float(duration_sec)
            weights = self.phrase_at(t)
            out.append((float(t), self._levels_for_state(t, t1, active, weights)))
        return out

    def _levels_for_state(
        self,
        t0: float,
        t1: float,
        active: frozenset[str],
        weights: PhraseWeights,
    ) -> dict[str, float]:
        if not active:
            return {}

        if weights.near_silent:
            lead = max(
                sorted(active), key=lambda s: weights.slot_activity.get(s, 0.0)
            )
            return {
                slot: (CONDUCTOR_LEVEL_FLOOR if slot == lead else 0.0)
                for slot in active
            }

        # Presence is each slot's window mean against its own "fully present"
        # scale, so the loudest slot in the state is comparable across stems.
        presence: dict[str, float] = {}
        for slot in active:
            stem = self._slot_stems[slot]
            key = _STEM_PRESENCE[stem]
            mean = self._signals.window_mean(stem, key, t0, t1)
            presence[slot] = clamp_level(mean / self._slot_scales[slot])

        peak = max(presence.values())
        levels: dict[str, float] = {}
        for slot, value in presence.items():
            relative = value / peak if peak > _RAW_ACTIVITY_FLOOR else 1.0
            shaped = _lerp(self._support_floor, 1.0, relative)
            level = quantize_level(clamp_level(shaped * weights.lead_ceiling))
            if level < CONDUCTOR_LEVEL_FLOOR:
                level = CONDUCTOR_LEVEL_FLOOR
            levels[slot] = level
        return levels
