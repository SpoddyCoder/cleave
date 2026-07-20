"""Motif library: short musical phrases of concurrent layer chords."""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from cleave.timeline_presets.chords import (
    ChordVocab,
    effective_stack_density_level,
)

# Minimum spacing between layer visibility transitions.
MIN_SWITCH_GAP_BARS = 2
MIN_SWITCH_GAP_SEC = 6.0
# Prefer planned switches onto nearby song markers (generation soft latch).
SOFT_LATCH_PROXIMITY_SEC = 5.0


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


def _pick_quartet(vocab: ChordVocab, index: int) -> str:
    if not vocab.quartets:
        return _pick_trio(vocab, index)
    return vocab.quartets[index % len(vocab.quartets)]


def _pick_tutti(vocab: ChordVocab) -> str:
    assert vocab.tutti_id is not None
    return vocab.tutti_id


def _prefer_quartets(vocab: ChordVocab) -> bool:
    """Use 4-stacks once density for cardinality 4 has been raised."""
    return bool(vocab.quartets) and effective_stack_density_level(
        len(vocab.slots), 4, vocab.density_bias
    ) >= 1


def _prefer_trios(vocab: ChordVocab) -> bool:
    """Use 3-stacks once density bias raises trio preference above bias 0."""
    # Require positive bias so normal (bias 0) keeps duo_breathe as solo-duo-solo;
    # at n>=4 trio density is already raised without bias.
    return (
        bool(vocab.trios)
        and vocab.density_bias > 0
        and effective_stack_density_level(
            len(vocab.slots), 3, vocab.density_bias
        )
        >= 1
    )


def _resolve_solo_hold(vocab: ChordVocab, rng: random.Random, rotation: int) -> tuple[str, ...]:
    return (_pick_single(vocab, rotation),)


def _resolve_duo_breathe(vocab: ChordVocab, rng: random.Random, rotation: int) -> tuple[str, ...]:
    solo = _pick_single(vocab, rotation)
    mid = (
        _pick_trio(vocab, rotation)
        if _prefer_trios(vocab)
        else _pick_duo(vocab, rotation)
    )
    return (solo, mid, solo)


def _resolve_call_response(vocab: ChordVocab, rng: random.Random, rotation: int) -> tuple[str, ...]:
    a = _pick_single(vocab, rotation)
    b = _pick_single(vocab, rotation + 1)
    return (a, b, a, b)


def _resolve_stack_up(vocab: ChordVocab, rng: random.Random, rotation: int) -> tuple[str, ...]:
    solo = _pick_single(vocab, rotation)
    duo = _pick_duo(vocab, rotation)
    if _prefer_quartets(vocab):
        return (solo, duo, _pick_quartet(vocab, rotation))
    if vocab.trios:
        return (solo, duo, _pick_trio(vocab, rotation))
    return (solo, duo)


def _resolve_shed(vocab: ChordVocab, rng: random.Random, rotation: int) -> tuple[str, ...]:
    if _prefer_quartets(vocab):
        return (
            _pick_quartet(vocab, rotation),
            _pick_duo(vocab, rotation),
            _pick_single(vocab, rotation),
        )
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


def _index_after_gap(
    bars: Sequence[float],
    from_idx: int,
    min_gap_bars: int,
    min_gap_sec: float,
) -> int | None:
    """First index >= from_idx + min_gap_bars that also meets the seconds floor."""
    if not bars or from_idx < 0:
        return None
    target = from_idx + min_gap_bars
    while target < len(bars):
        if bars[target] - bars[from_idx] >= min_gap_sec - 1e-9:
            return target
        target += 1
    return None


def _effective_step_bars(
    phrase_bars: Sequence[float],
    min_gap_bars: int,
    min_gap_sec: float,
) -> int:
    """Bar-index step that satisfies both gap floors across the phrase grid."""
    step = min_gap_bars
    if len(phrase_bars) < 2:
        return step
    for i in range(len(phrase_bars)):
        j = step
        while (
            i + j < len(phrase_bars)
            and phrase_bars[i + j] - phrase_bars[i] < min_gap_sec - 1e-9
        ):
            j += 1
        if i + j < len(phrase_bars):
            step = max(step, j)
    return step


def switch_gap_ok(
    prev_t: float,
    t: float,
    bars: Sequence[float],
    min_gap_bars: int,
    min_gap_sec: float,
) -> bool:
    """True when ``t`` meets second and bar-index floors relative to ``prev_t``."""
    if t - prev_t < min_gap_sec - 1e-9:
        return False
    if not bars:
        return True
    prev_idx = _nearest_bar_index(prev_t, bars)
    t_idx = _nearest_bar_index(t, bars)
    return t_idx - prev_idx >= min_gap_bars


def _marker_claimed(marker: float, claimed: set[float]) -> bool:
    return any(abs(marker - c) < 1e-9 for c in claimed)


def _claim_marker(marker: float, claimed: set[float]) -> None:
    if not _marker_claimed(marker, claimed):
        claimed.add(marker)


def claim_marker_at_time(
    t: float,
    markers: Sequence[float],
    claimed: set[float],
) -> None:
    """If ``t`` coincides with a song marker, mark that marker claimed."""
    for marker in markers:
        if abs(t - marker) < 1e-9:
            _claim_marker(marker, claimed)
            return


def soft_latch_time(
    planned: float,
    markers: Sequence[float],
    claimed: set[float],
    *,
    bars: Sequence[float],
    prev_time: float | None,
    proximity: float = SOFT_LATCH_PROXIMITY_SEC,
    min_gap_bars: int = MIN_SWITCH_GAP_BARS,
    min_gap_sec: float = MIN_SWITCH_GAP_SEC,
) -> float:
    """Nudge ``planned`` onto the nearest unclaimed marker within proximity.

    Skips markers that would violate min switch gaps vs ``prev_time``.
    """
    best: tuple[float, float] | None = None
    for marker in markers:
        if _marker_claimed(marker, claimed):
            continue
        dist = abs(marker - planned)
        if dist > proximity + 1e-9:
            continue
        if prev_time is not None and not switch_gap_ok(
            prev_time, marker, bars, min_gap_bars, min_gap_sec
        ):
            continue
        if (
            best is None
            or dist < best[0] - 1e-12
            or (abs(dist - best[0]) < 1e-12 and marker < best[1])
        ):
            best = (dist, marker)
    if best is None:
        claim_marker_at_time(planned, markers, claimed)
        return planned
    _claim_marker(best[1], claimed)
    return best[1]


def _phrase_step_times(
    phrase_start: float,
    phrase_end: float,
    bar_times: Sequence[float],
) -> list[float]:
    """Bar times in the phrase, always including ``phrase_start`` when off-grid."""
    times = [t for t in bar_times if phrase_start <= t < phrase_end]
    if not times:
        return [phrase_start]
    if abs(times[0] - phrase_start) > 1e-9:
        return [phrase_start, *times]
    return times


def _soft_latch_states(
    states: list[tuple[float, frozenset[str]]],
    markers: Sequence[float],
    claimed: set[float],
    *,
    bars: Sequence[float],
    phrase_start: float,
    phrase_end: float,
    prev_time: float | None,
    proximity: float,
    min_gap_bars: int,
    min_gap_sec: float,
) -> list[tuple[float, frozenset[str]]]:
    in_phrase = [m for m in markers if phrase_start <= m < phrase_end]
    if not in_phrase:
        return states
    latched: list[tuple[float, frozenset[str]]] = []
    local_prev = prev_time
    for planned, active in states:
        t = soft_latch_time(
            planned,
            in_phrase,
            claimed,
            bars=bars,
            prev_time=local_prev,
            proximity=proximity,
            min_gap_bars=min_gap_bars,
            min_gap_sec=min_gap_sec,
        )
        latched.append((t, active))
        local_prev = t
    return latched


def _expand_flash_tutti(
    vocab: ChordVocab,
    rotation: int,
    phrase_start: float,
    phrase_end: float,
    bar_times: Sequence[float],
    duration_sec: float,
    min_gap_bars: int,
    min_gap_sec: float,
    prev_time: float | None = None,
    *,
    song_marker_times: Sequence[float] = (),
    claimed_markers: set[float] | None = None,
    soft_latch_proximity: float = SOFT_LATCH_PROXIMITY_SEC,
) -> list[tuple[float, frozenset[str]]]:
    claimed = claimed_markers if claimed_markers is not None else set()
    if vocab.tutti_id is None:
        phrase_bars = _phrase_step_times(phrase_start, phrase_end, bar_times)
        solo = vocab.active_for(_pick_single(vocab, rotation))
        t0 = phrase_bars[0]
        states = [(t0, solo)]
        return _soft_latch_states(
            states,
            song_marker_times,
            claimed,
            bars=bar_times,
            phrase_start=phrase_start,
            phrase_end=phrase_end,
            prev_time=prev_time,
            proximity=soft_latch_proximity,
            min_gap_bars=min_gap_bars,
            min_gap_sec=min_gap_sec,
        )

    duo = vocab.active_for(_pick_duo(vocab, rotation))
    tutti = vocab.active_for(_pick_tutti(vocab))
    solo = vocab.active_for(_pick_single(vocab, rotation))

    bars = list(bar_times)
    if not bars:
        states = [(phrase_start, tutti)]
        return _soft_latch_states(
            states,
            song_marker_times,
            claimed,
            bars=bars,
            phrase_start=phrase_start,
            phrase_end=phrase_end,
            prev_time=prev_time,
            proximity=soft_latch_proximity,
            min_gap_bars=min_gap_bars,
            min_gap_sec=min_gap_sec,
        )

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
        earliest_idx = _index_after_gap(bars, prev_idx, min_gap_bars, min_gap_sec)
        if earliest_idx is None:
            states = [(phrase_start, duo)]
            return _soft_latch_states(
                states,
                song_marker_times,
                claimed,
                bars=bars,
                phrase_start=phrase_start,
                phrase_end=phrase_end,
                prev_time=prev_time,
                proximity=soft_latch_proximity,
                min_gap_bars=min_gap_bars,
                min_gap_sec=min_gap_sec,
            )
        earliest = bars[earliest_idx]

    tutti_idx = _nearest_bar_index(tutti_t, bars)
    if bars[tutti_idx] < earliest - 1e-9:
        tutti_idx = _nearest_bar_index(earliest, bars)
        if bars[tutti_idx] < earliest - 1e-9:
            tutti_idx = min(len(bars) - 1, tutti_idx + 1)
    tutti_t = bars[tutti_idx]

    duo_idx = 0
    for candidate in range(tutti_idx, -1, -1):
        if (
            tutti_idx - candidate >= min_gap_bars
            and tutti_t - bars[candidate] >= min_gap_sec - 1e-9
        ):
            duo_idx = candidate
            break
    solo_idx = _index_after_gap(bars, tutti_idx, min_gap_bars, min_gap_sec)
    duo_t = bars[duo_idx]
    solo_t = bars[solo_idx] if solo_idx is not None else bars[-1]

    states = []
    if (
        duo_t >= earliest - 1e-9
        and duo_t >= phrase_start - 1e-9
        and duo_t < tutti_t - 1e-9
    ):
        states.append((duo_t, duo))
    states.append((tutti_t, tutti))
    if (
        solo_idx is not None
        and solo_t <= phrase_end - 1e-9
        and solo_t > tutti_t + 1e-9
    ):
        states.append((solo_t, solo))
    return _soft_latch_states(
        states,
        song_marker_times,
        claimed,
        bars=bars,
        phrase_start=phrase_start,
        phrase_end=phrase_end,
        prev_time=prev_time,
        proximity=soft_latch_proximity,
        min_gap_bars=min_gap_bars,
        min_gap_sec=min_gap_sec,
    )


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
    min_gap_sec: float = MIN_SWITCH_GAP_SEC,
    song_marker_times: Sequence[float] = (),
    claimed_markers: set[float] | None = None,
    soft_latch_proximity: float = SOFT_LATCH_PROXIMITY_SEC,
) -> list[tuple[float, frozenset[str]]]:
    """Expand a motif into timed active sets within a phrase.

    Steps land on the bar grid (plus phrase start when off-grid). Planned
    times soft-latch onto nearby unclaimed song markers when provided.
    """
    claimed = claimed_markers if claimed_markers is not None else set()
    if motif.id == "flash_tutti":
        return _expand_flash_tutti(
            vocab,
            rotation,
            phrase_start,
            phrase_end,
            bar_times,
            duration_sec if duration_sec is not None else phrase_end,
            min_gap_bars,
            min_gap_sec,
            prev_time,
            song_marker_times=song_marker_times,
            claimed_markers=claimed,
            soft_latch_proximity=soft_latch_proximity,
        )

    chord_ids = motif.resolve_steps(vocab, rng, rotation)
    phrase_bars = _phrase_step_times(phrase_start, phrase_end, bar_times)

    n = len(chord_ids)
    step = _effective_step_bars(phrase_bars, min_gap_bars, min_gap_sec)
    if n == 1 or len(phrase_bars) < 1 + (n - 1) * step:
        states = [(phrase_bars[0], vocab.active_for(chord_ids[0]))]
    else:
        span = len(phrase_bars) - 1
        min_needed = (n - 1) * step
        if span < min_needed:
            states = [(phrase_bars[0], vocab.active_for(chord_ids[0]))]
        else:
            step = max(step, span // n)
            if step * (n - 1) > span:
                step = _effective_step_bars(phrase_bars, min_gap_bars, min_gap_sec)

            states = []
            for i, chord_id in enumerate(chord_ids):
                idx = min(i * step, len(phrase_bars) - 1)
                states.append((phrase_bars[idx], vocab.active_for(chord_id)))

    return _soft_latch_states(
        states,
        song_marker_times,
        claimed,
        bars=bar_times,
        phrase_start=phrase_start,
        phrase_end=phrase_end,
        prev_time=prev_time,
        proximity=soft_latch_proximity,
        min_gap_bars=min_gap_bars,
        min_gap_sec=min_gap_sec,
    )


def hamming_distance(a: frozenset[str], b: frozenset[str]) -> int:
    return len(a.symmetric_difference(b))


def motifs_for_profile(
    profile_motif_ids: Sequence[str],
) -> list[MotifDef]:
    return [MOTIFS[mid] for mid in profile_motif_ids if mid in MOTIFS]
