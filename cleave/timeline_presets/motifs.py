"""Motif library: short musical phrases of concurrent layer chords."""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from cleave.timeline_presets.busyness import MIN_SWITCH_GAP_BARS
from cleave.timeline_presets.chords import ChordVocab


@dataclass(frozen=True)
class MotifDef:
    id: str
    max_cost: float
    resolve_steps: Callable[[ChordVocab, random.Random, int], tuple[str, ...]]
    weights: tuple[float, ...]
    climax_only: bool = False
    allows_boundary_jump: bool = False


def _pick_single(vocab: ChordVocab, index: int) -> str:
    return vocab.singles[index % len(vocab.singles)]


def _pick_duo(vocab: ChordVocab, index: int) -> str:
    if not vocab.duos:
        return _pick_single(vocab, index)
    return vocab.duos[index % len(vocab.duos)]


def _pick_trio(vocab: ChordVocab, index: int) -> str:
    if not vocab.trios:
        return _pick_duo(vocab, index)
    return vocab.trios[index % len(vocab.trios)]


def _pick_tutti(vocab: ChordVocab) -> str:
    assert vocab.tutti_id is not None
    return vocab.tutti_id


def _resolve_solo_hold(vocab: ChordVocab, rng: random.Random, rotation: int) -> tuple[str, ...]:
    return (_pick_single(vocab, rotation),)


def _resolve_duo_breathe(vocab: ChordVocab, rng: random.Random, rotation: int) -> tuple[str, ...]:
    solo = _pick_single(vocab, rotation)
    duo = _pick_duo(vocab, rotation)
    return (solo, duo, solo)


def _resolve_call_response(vocab: ChordVocab, rng: random.Random, rotation: int) -> tuple[str, ...]:
    a = _pick_single(vocab, rotation)
    b = _pick_single(vocab, rotation + 1)
    return (a, b, a, b)


def _resolve_stack_up(vocab: ChordVocab, rng: random.Random, rotation: int) -> tuple[str, ...]:
    solo = _pick_single(vocab, rotation)
    duo = _pick_duo(vocab, rotation)
    if vocab.trios:
        return (solo, duo, _pick_trio(vocab, rotation))
    return (solo, duo)


def _resolve_shed(vocab: ChordVocab, rng: random.Random, rotation: int) -> tuple[str, ...]:
    if vocab.trios:
        return (_pick_trio(vocab, rotation), _pick_duo(vocab, rotation), _pick_single(vocab, rotation))
    duo = _pick_duo(vocab, rotation)
    solo = _pick_single(vocab, rotation)
    return (duo, solo)


def _resolve_flash_tutti(vocab: ChordVocab, rng: random.Random, rotation: int) -> tuple[str, ...]:
    if vocab.tutti_id is None:
        return _resolve_duo_breathe(vocab, rng, rotation)
    duo = _pick_duo(vocab, rotation)
    solo = _pick_single(vocab, rotation)
    return (duo, _pick_tutti(vocab), solo)


def _resolve_rotate_solo(vocab: ChordVocab, rng: random.Random, rotation: int) -> tuple[str, ...]:
    n = len(vocab.singles)
    count = min(n, 4)
    return tuple(_pick_single(vocab, rotation + i) for i in range(count))


def _resolve_antiphony(vocab: ChordVocab, rng: random.Random, rotation: int) -> tuple[str, ...]:
    if len(vocab.groups) >= 2:
        return ("g0", "g1", "g0", "g1")
    return _resolve_call_response(vocab, rng, rotation)


MOTIFS: dict[str, MotifDef] = {
    "solo_hold": MotifDef(
        id="solo_hold",
        max_cost=1.0,
        resolve_steps=_resolve_solo_hold,
        weights=(1.0,),
    ),
    "duo_breathe": MotifDef(
        id="duo_breathe",
        max_cost=2.2,
        resolve_steps=_resolve_duo_breathe,
        weights=(0.4, 0.3, 0.3),
    ),
    "call_response": MotifDef(
        id="call_response",
        max_cost=1.0,
        resolve_steps=_resolve_call_response,
        weights=(0.25, 0.25, 0.25, 0.25),
    ),
    "stack_up": MotifDef(
        id="stack_up",
        max_cost=4.0,
        resolve_steps=_resolve_stack_up,
        weights=(0.35, 0.35, 0.30),
    ),
    "shed": MotifDef(
        id="shed",
        max_cost=4.0,
        resolve_steps=_resolve_shed,
        weights=(0.4, 0.35, 0.25),
    ),
    "flash_tutti": MotifDef(
        id="flash_tutti",
        max_cost=7.5,
        resolve_steps=_resolve_flash_tutti,
        weights=(0.35, 0.30, 0.35),
        climax_only=True,
        allows_boundary_jump=True,
    ),
    "rotate_solo": MotifDef(
        id="rotate_solo",
        max_cost=1.0,
        resolve_steps=_resolve_rotate_solo,
        weights=(0.25, 0.25, 0.25, 0.25),
    ),
    "antiphony": MotifDef(
        id="antiphony",
        max_cost=2.2,
        resolve_steps=_resolve_antiphony,
        weights=(0.25, 0.25, 0.25, 0.25),
        allows_boundary_jump=True,
    ),
}


def motif_max_cost_resolved(
    motif: MotifDef,
    vocab: ChordVocab,
    rng: random.Random,
    rotation: int,
) -> float:
    steps = motif.resolve_steps(vocab, rng, rotation)
    return max(vocab.cost_for(step) for step in steps)


def _nearest_bar_index(t: float, bars: Sequence[float]) -> int:
    return min(range(len(bars)), key=lambda i: (abs(bars[i] - t), bars[i]))


def _expand_flash_tutti(
    vocab: ChordVocab,
    rotation: int,
    phrase_start: float,
    phrase_end: float,
    bar_times: Sequence[float],
    duration_sec: float,
    min_gap_bars: int,
    prev_time: float | None = None,
) -> list[tuple[float, frozenset[str]]]:
    if vocab.tutti_id is None:
        phrase_bars = [t for t in bar_times if phrase_start <= t < phrase_end]
        solo = vocab.active_for(_pick_single(vocab, rotation))
        t0 = phrase_bars[0] if phrase_bars else phrase_start
        return [(t0, solo)]

    duo = vocab.active_for(_pick_duo(vocab, rotation))
    tutti = vocab.active_for(_pick_tutti(vocab))
    solo = vocab.active_for(_pick_single(vocab, rotation))

    bars = list(bar_times)
    if not bars:
        return [(phrase_start, tutti)]

    window_start = 0.70 * duration_sec
    window_end = 0.78 * duration_sec
    window_bars = [
        t
        for t in bars
        if window_start <= t < window_end and phrase_start <= t < phrase_end
    ]
    if not window_bars:
        window_bars = [t for t in bars if phrase_start <= t < phrase_end]
    if not window_bars:
        window_bars = [t for t in bars if phrase_start <= t <= phrase_end]

    mid = (window_start + window_end) * 0.5
    tutti_t = min(window_bars, key=lambda t: (abs(t - mid), t))

    earliest = phrase_start
    if prev_time is not None:
        prev_idx = _nearest_bar_index(prev_time, bars)
        earliest_idx = min(len(bars) - 1, prev_idx + min_gap_bars)
        earliest = bars[earliest_idx]

    tutti_idx = _nearest_bar_index(tutti_t, bars)
    if bars[tutti_idx] < earliest - 1e-9:
        tutti_idx = _nearest_bar_index(earliest, bars)
        if bars[tutti_idx] < earliest - 1e-9:
            tutti_idx = min(len(bars) - 1, tutti_idx + 1)
    tutti_t = bars[tutti_idx]

    duo_idx = max(0, tutti_idx - min_gap_bars)
    solo_idx = min(len(bars) - 1, tutti_idx + min_gap_bars)
    duo_t = bars[duo_idx]
    solo_t = bars[solo_idx]

    states: list[tuple[float, frozenset[str]]] = []
    if (
        duo_t >= earliest - 1e-9
        and duo_t >= phrase_start - 1e-9
        and duo_t < tutti_t - 1e-9
    ):
        states.append((duo_t, duo))
    states.append((tutti_t, tutti))
    if solo_t <= phrase_end - 1e-9 and solo_t > tutti_t + 1e-9:
        states.append((solo_t, solo))
    return states


def expand_motif(
    motif: MotifDef,
    vocab: ChordVocab,
    rng: random.Random,
    rotation: int,
    phrase_start: float,
    phrase_end: float,
    bar_times: Sequence[float],
    *,
    duration_sec: float | None = None,
    prev_time: float | None = None,
    min_gap_bars: int = MIN_SWITCH_GAP_BARS,
) -> list[tuple[float, frozenset[str]]]:
    """Expand a motif into timed active sets on bar boundaries within a phrase."""
    if motif.id == "flash_tutti":
        return _expand_flash_tutti(
            vocab,
            rotation,
            phrase_start,
            phrase_end,
            bar_times,
            duration_sec if duration_sec is not None else phrase_end,
            min_gap_bars,
            prev_time,
        )

    chord_ids = motif.resolve_steps(vocab, rng, rotation)
    phrase_bars = [t for t in bar_times if phrase_start <= t < phrase_end]
    if not phrase_bars:
        phrase_bars = [phrase_start]

    n = len(chord_ids)
    if n == 1 or len(phrase_bars) < 1 + (n - 1) * min_gap_bars:
        return [(phrase_bars[0], vocab.active_for(chord_ids[0]))]

    span = len(phrase_bars) - 1
    min_needed = (n - 1) * min_gap_bars
    if span < min_needed:
        return [(phrase_bars[0], vocab.active_for(chord_ids[0]))]

    step = max(min_gap_bars, span // n)
    if step * (n - 1) > span:
        step = min_gap_bars

    states: list[tuple[float, frozenset[str]]] = []
    for i, chord_id in enumerate(chord_ids):
        idx = min(i * step, len(phrase_bars) - 1)
        states.append((phrase_bars[idx], vocab.active_for(chord_id)))
    return states


def hamming_distance(a: frozenset[str], b: frozenset[str]) -> int:
    return len(a.symmetric_difference(b))


def motifs_for_profile(
    profile_motif_ids: Sequence[str],
) -> list[MotifDef]:
    return [MOTIFS[mid] for mid in profile_motif_ids if mid in MOTIFS]
