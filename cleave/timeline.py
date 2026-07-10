"""Timeline cue evaluation and editing for per-slot layer visibility."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from cleave.extract import STEM_SOURCES, StemSource

RECORD_DEBOUNCE_SEC = 0.08

_STEM_SOURCE_ABBREVIATIONS = {
    "drums": "D",
    "bass": "B",
    "vocals": "V",
    "other": "O",
    "full_mix": "M",
}


@dataclass(frozen=True)
class TimelineCue:
    t: float
    layers: dict[str, bool]
    show_tick: bool = True


def stem_abbreviation(stem: StemSource) -> str:
    if stem not in _STEM_SOURCE_ABBREVIATIONS:
        allowed = ", ".join(STEM_SOURCES)
        raise ValueError(f"unknown stem: {stem!r} (expected one of: {allowed})")
    return _STEM_SOURCE_ABBREVIATIONS[stem]


def layer_visible_at(
    cues: list[TimelineCue],
    defaults: dict[str, bool],
    slot: str,
    t_sec: float,
) -> bool:
    if slot not in defaults:
        allowed = ", ".join(sorted(defaults))
        raise ValueError(f"unknown slot: {slot!r} (expected one of: {allowed})")
    visible = defaults[slot]
    for cue in sorted(cues, key=lambda c: c.t):
        if cue.t > t_sec:
            break
        if slot in cue.layers:
            visible = cue.layers[slot]
    return visible


def visible_state_at(
    cues: list[TimelineCue],
    defaults: dict[str, bool],
    slots: list[str],
    t_sec: float,
) -> dict[str, bool]:
    return {
        slot: layer_visible_at(cues, defaults, slot, t_sec) for slot in slots
    }


def _cue_modifies_armed_stem(cue: TimelineCue, armed_stems: set[str]) -> bool:
    return bool(set(cue.layers) & armed_stems)


def _merge_cues_at_same_t(cues: list[TimelineCue]) -> list[TimelineCue]:
    if not cues:
        return []
    merged: list[TimelineCue] = []
    current_t: float | None = None
    current_layers: dict[str, bool] = {}
    current_show_tick = True
    for cue in sorted(cues, key=lambda c: c.t):
        if current_t is None:
            current_t = cue.t
        elif cue.t != current_t:
            merged.append(
                TimelineCue(
                    t=current_t,
                    layers=dict(current_layers),
                    show_tick=current_show_tick,
                )
            )
            current_t = cue.t
            current_layers = {}
            current_show_tick = True
        current_layers.update(cue.layers)
        current_show_tick = current_show_tick and cue.show_tick
    if current_t is not None:
        merged.append(
            TimelineCue(
                t=current_t,
                layers=dict(current_layers),
                show_tick=current_show_tick,
            )
        )
    return merged


def punch_replace(
    cues: list[TimelineCue],
    armed_stems: set[str],
    start_sec: float,
    stop_sec: float,
    new_cues: list[TimelineCue],
) -> list[TimelineCue]:
    kept = [
        cue
        for cue in cues
        if not (
            start_sec <= cue.t <= stop_sec
            and _cue_modifies_armed_stem(cue, armed_stems)
        )
    ]
    combined = kept + list(new_cues)
    return _merge_cues_at_same_t(combined)


def should_accept_toggle(last_toggle_t: float | None, t_sec: float) -> bool:
    if last_toggle_t is None:
        return True
    return t_sec - last_toggle_t >= RECORD_DEBOUNCE_SEC


def _nearest_with_earlier_tie(t: float, candidates: Sequence[float]) -> float:
    return min(candidates, key=lambda c: (abs(c - t), c))


def snap_cues_to_beats(
    cues: Sequence[TimelineCue],
    beat_times: Sequence[float],
) -> list[TimelineCue]:
    """Rewrite cue times to the nearest beat; merge collisions at the same ``t``."""
    if not cues or not beat_times:
        return list(cues)

    beats = np.asarray(beat_times, dtype=np.float64)
    if beats.size == 1:
        sole = float(beats[0])
        snapped = [
            TimelineCue(t=sole, layers=dict(cue.layers), show_tick=cue.show_tick)
            for cue in cues
        ]
        return _merge_cues_at_same_t(snapped)

    first = float(beats[0])
    last = float(beats[-1])
    interval = float(np.median(np.diff(beats)))

    def snap_t(t: float) -> float:
        if first <= t <= last:
            idx = int(np.searchsorted(beats, t))
            candidates: list[float] = []
            if idx > 0:
                candidates.append(float(beats[idx - 1]))
            if idx < len(beats):
                candidates.append(float(beats[idx]))
            return _nearest_with_earlier_tie(t, candidates)
        raw = (t - first) / interval
        lo = int(np.floor(raw))
        return _nearest_with_earlier_tie(
            t,
            (first + lo * interval, first + (lo + 1) * interval),
        )

    snapped = [
        TimelineCue(
            t=snap_t(cue.t),
            layers=dict(cue.layers),
            show_tick=cue.show_tick,
        )
        for cue in cues
    ]
    return _merge_cues_at_same_t(snapped)
