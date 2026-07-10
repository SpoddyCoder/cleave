"""Motif library: short musical phrases of concurrent layer chords."""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from cleave.timeline_presets.busyness import chord_cost_for_active
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


def _expand_flash_tutti(
    vocab: ChordVocab,
    rotation: int,
    phrase_start: float,
    phrase_end: float,
    min_gap: float,
    duration_sec: float,
    prev_time: float | None = None,
) -> list[tuple[float, frozenset[str]]]:
    if vocab.tutti_id is None:
        solo = vocab.active_for(_pick_single(vocab, rotation))
        return [(phrase_start, solo)]

    duo = vocab.active_for(_pick_duo(vocab, rotation))
    tutti = vocab.active_for(_pick_tutti(vocab))
    solo = vocab.active_for(_pick_single(vocab, rotation))

    window_start = 0.70 * duration_sec
    window_end = 0.78 * duration_sec
    overlap_start = max(phrase_start, window_start)
    overlap_end = min(phrase_end, window_end)

    earliest = phrase_start
    if prev_time is not None:
        earliest = max(earliest, prev_time + min_gap)

    if overlap_end > overlap_start:
        tutti_t = (overlap_start + overlap_end) * 0.5
    else:
        tutti_t = (phrase_start + phrase_end) * 0.5

    tutti_t = max(earliest, tutti_t)
    if tutti_t > overlap_end - 1e-6 and overlap_end > overlap_start:
        tutti_t = max(earliest, overlap_start)
    if tutti_t >= phrase_end - 1e-6:
        tutti_t = max(earliest, phrase_end - min_gap * 0.5)

    duo_t = tutti_t - min_gap
    solo_t = tutti_t + min_gap

    states: list[tuple[float, frozenset[str]]] = []
    if duo_t >= earliest and duo_t >= phrase_start and duo_t < tutti_t - 1e-6:
        states.append((duo_t, duo))
    states.append((tutti_t, tutti))
    if solo_t <= phrase_end - 1e-6 and solo_t > tutti_t + 1e-6:
        states.append((solo_t, solo))
    return states


def expand_motif(
    motif: MotifDef,
    vocab: ChordVocab,
    rng: random.Random,
    rotation: int,
    phrase_start: float,
    phrase_end: float,
    min_gap: float,
    *,
    duration_sec: float | None = None,
    prev_time: float | None = None,
) -> list[tuple[float, frozenset[str]]]:
    """Expand a motif into timed active sets within a phrase."""
    if motif.id == "flash_tutti":
        return _expand_flash_tutti(
            vocab,
            rotation,
            phrase_start,
            phrase_end,
            min_gap,
            duration_sec if duration_sec is not None else phrase_end,
            prev_time,
        )

    chord_ids = motif.resolve_steps(vocab, rng, rotation)
    weights = motif.weights[: len(chord_ids)]
    if len(weights) < len(chord_ids):
        weights = weights + (1.0,) * (len(chord_ids) - len(weights))

    phrase_len = phrase_end - phrase_start
    n = len(chord_ids)
    if n == 1 or phrase_len < min_gap:
        active = vocab.active_for(chord_ids[0])
        return [(phrase_start, active)]

    min_span = (n - 1) * min_gap
    if phrase_len < min_span:
        active = vocab.active_for(chord_ids[0])
        return [(phrase_start, active)]

    gap = phrase_len / n
    if gap < min_gap - 1e-9:
        gap = min_gap
        if gap * (n - 1) > phrase_len + 1e-9:
            active = vocab.active_for(chord_ids[0])
            return [(phrase_start, active)]

    states: list[tuple[float, frozenset[str]]] = []
    for i, chord_id in enumerate(chord_ids):
        t = phrase_start + i * gap
        if t >= phrase_end:
            break
        states.append((t, vocab.active_for(chord_id)))
    return states


def hamming_distance(a: frozenset[str], b: frozenset[str]) -> int:
    return len(a.symmetric_difference(b))


def motifs_for_profile(
    profile_motif_ids: Sequence[str],
) -> list[MotifDef]:
    return [MOTIFS[mid] for mid in profile_motif_ids if mid in MOTIFS]
