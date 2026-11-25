"""Stem conductor: how loud each phrase is, which stems are busy, and roles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from cleave.blend_modes import BlendMode
from cleave.cue_roles import CUE_ROLE_BLEND, CueRole
from cleave.stems import StemSource
from cleave.signals import Signals

_STEM_PRESENCE: dict[StemSource, str] = {
    "drums": "onset_strength",
    "bass": "rms",
    "vocals": "rms",
    "guitar": "rms",
    "piano": "rms",
    "other": "rms",
    "full_mix": "rms",
}
# Budget multipliers span a range centred on 1.0: the conductor moves weight
# between phrases rather than lowering it across the whole song.
CONDUCTOR_GAIN_MIN, CONDUCTOR_GAIN_MAX = 0.65, 1.35
CONDUCTOR_SILENCE_FLOOR = 0.08
# Neutral point of a standardised slot activity (rank fraction across phrases).
CONDUCTOR_ACTIVITY_MIDPOINT = 0.5
# Penalty on a slot's share of accumulated airtime above an even share.
AIRTIME_PENALTY = 1.0

DEFAULT_TIMELINE_PRESET_CONDUCTOR = False

_ENERGY_FLAT_EPS = 1e-9
# Raw presence below this reads as absent, so a dead stem never ranks as a lead.
_SLOT_SILENCE_FLOOR = 0.02


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


@dataclass(frozen=True)
class PhraseWeights:
    budget_gain: float
    slot_activity: dict[str, float]
    near_silent: bool


def timeline_preset_conductor_display(conductor: bool) -> str:
    return "on" if conductor else "off"


class StemConductor:
    def __init__(
        self,
        *,
        slot_stems: Mapping[str, StemSource],
        phrase_bounds: Sequence[tuple[float, float]],
        phrase_weights: Sequence[PhraseWeights],
    ) -> None:
        self._slot_stems = dict(slot_stems)
        self._phrase_bounds = list(phrase_bounds)
        self._phrase_weights = list(phrase_weights)

    @classmethod
    def build(
        cls,
        signals: Signals | None,
        slot_stems: Mapping[str, StemSource] | None,
        phrases: Sequence[tuple[float, float]],
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
        for slot, stem in slot_stems.items():
            key = _STEM_PRESENCE[stem]
            raw = np.asarray(
                [signals.window_mean(stem, key, t0, t1) for t0, t1 in phrases],
                dtype=np.float64,
            )
            slot_activity_series[slot] = np.where(
                raw < _SLOT_SILENCE_FLOOR, 0.0, _rank_fractions(raw)
            )

        phrase_weights: list[PhraseWeights] = []
        for i in range(len(phrases)):
            rank = float(rank_frac[i])
            energy = float(energy_arr[i])
            phrase_weights.append(
                PhraseWeights(
                    budget_gain=_lerp(CONDUCTOR_GAIN_MIN, CONDUCTOR_GAIN_MAX, rank),
                    slot_activity={
                        slot: float(series[i])
                        for slot, series in slot_activity_series.items()
                    },
                    near_silent=energy < CONDUCTOR_SILENCE_FLOOR,
                )
            )

        return cls(
            slot_stems=slot_stems,
            phrase_bounds=phrases,
            phrase_weights=phrase_weights,
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


    def cast_for_state(
        self,
        active: frozenset[str] | set[str],
        weights: PhraseWeights,
    ) -> dict[str, tuple[CueRole, BlendMode]]:
        """Assign one role and blend per active slot for a state.

        Near-silent phrases cast every active slot as bed. Otherwise drums with
        non-trivial activity become pulse; the highest-activity non-pulse slot
        is lead (solo states are always lead); remaining slots are bed. At most
        one lead. Accent is not assigned here; the accent post-pass writes
        ``role="accent"`` at standard song markers.
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


