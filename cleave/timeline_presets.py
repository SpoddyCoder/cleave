"""Procedural timeline preset cue generation."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence

from cleave.timeline import TimelineCue

PHI = (1.0 + math.sqrt(5.0)) / 2.0
MIN_SWITCH_GAP_SEC = 6.0


def build_slow_build_cues(
    slots: Sequence[str],
    duration_sec: float,
    rng: random.Random | None = None,
) -> list[TimelineCue]:
    slot_list = list(slots)
    if not slot_list or duration_sec <= 0.0:
        return []
    rng = _rng(rng)
    n = len(slot_list)
    if n == 1:
        return [TimelineCue(t=0.0, layers={slot_list[0]: True})]

    times = _transition_times(duration_sec, n, rng)
    order = list(slot_list)
    rng.shuffle(order)

    active: set[str] = {order[0]}
    next_intro = 1
    states: list[tuple[float, frozenset[str]]] = [(0.0, frozenset(active))]

    step_count = len(times)
    for step_i, t in enumerate(times):
        progress = (step_i + 1) / step_count
        if step_i == step_count - 1:
            active = set(slot_list)
            next_intro = n
        else:
            target = _slow_build_target(n, progress)
            active, next_intro = _slow_build_step(
                active,
                order,
                next_intro,
                target=target,
                progress=progress,
                rng=rng,
            )
        states.append((t, frozenset(active)))

    # If no transitions fit, stay on the opening layer for the whole song.
    return _cues_from_states(slot_list, states)


def build_random_cues(
    slots: Sequence[str],
    duration_sec: float,
    rng: random.Random | None = None,
) -> list[TimelineCue]:
    slot_list = list(slots)
    if not slot_list or duration_sec <= 0.0:
        return []
    rng = _rng(rng)
    n = len(slot_list)
    if n == 1:
        return [TimelineCue(t=0.0, layers={slot_list[0]: True})]

    times = _transition_times(duration_sec, n, rng)
    active = set(_random_subset(slot_list, rng.randint(1, n), rng))
    states: list[tuple[float, frozenset[str]]] = [(0.0, frozenset(active))]

    for t in times:
        nxt = set(_random_subset(slot_list, rng.randint(1, n), rng))
        if nxt == active and n > 1:
            nxt = _force_different_set(active, slot_list, rng)
        active = nxt
        states.append((t, frozenset(active)))

    return _cues_from_states(slot_list, states)


def _rng(rng: random.Random | None) -> random.Random:
    return rng if rng is not None else random.Random()


def _transition_times(
    duration_sec: float,
    n_slots: int,
    rng: random.Random,
) -> list[float]:
    """Golden-ratio times in (0, duration), gap-filtered to MIN_SWITCH_GAP_SEC."""
    if duration_sec <= MIN_SWITCH_GAP_SEC:
        return []

    max_by_gap = int(duration_sec // MIN_SWITCH_GAP_SEC)
    # Density scales with duration and layer count without becoming frantic.
    density = max(n_slots, int(round(duration_sec / (MIN_SWITCH_GAP_SEC * 1.5))))
    target = max(1, min(max_by_gap, density))

    phase = rng.random()
    raw: list[float] = []
    for i in range(1, target * 4 + 8):
        frac = (phase + i / PHI) % 1.0
        t = frac * duration_sec
        if MIN_SWITCH_GAP_SEC <= t < duration_sec:
            raw.append(t)
    raw.sort()

    selected: list[float] = []
    for t in raw:
        if not selected or t - selected[-1] >= MIN_SWITCH_GAP_SEC:
            selected.append(t)
        if len(selected) >= target:
            break

    if not selected:
        # Guarantee one mid-song switch when the gap budget allows it.
        selected = [min(max(MIN_SWITCH_GAP_SEC, duration_sec / PHI), duration_sec - 1e-9)]
    return selected


def _slow_build_target(n: int, progress: float) -> int:
    return max(1, min(n, int(round(1.0 + progress * (n - 1)))))


def _slow_build_step(
    active: set[str],
    order: Sequence[str],
    next_intro: int,
    *,
    target: int,
    progress: float,
    rng: random.Random,
) -> tuple[set[str], int]:
    n = len(order)
    current = set(active)
    roll = rng.random()
    allow_dip = progress < 0.8 and len(current) > 1

    if next_intro < n and (len(current) < target or roll < 0.55):
        current.add(order[next_intro])
        next_intro += 1
        if len(current) > target and allow_dip and rng.random() < 0.45:
            removable = [s for s in current if s != order[next_intro - 1]]
            if removable:
                current.remove(rng.choice(removable))
    elif len(current) < target:
        for slot in order:
            if slot not in current:
                current.add(slot)
                next_intro = max(next_intro, order.index(slot) + 1)
                if len(current) >= target:
                    break
    elif allow_dip and roll < 0.3:
        if rng.random() < 0.55 and next_intro < n:
            current.add(order[next_intro])
            next_intro += 1
            removable = [s for s in current if s != order[next_intro - 1]]
            if removable:
                current.remove(rng.choice(removable))
        elif len(current) > 1:
            current.remove(rng.choice(list(current)))
    elif len(current) > target and allow_dip and roll < 0.4:
        while len(current) > max(1, target):
            current.remove(rng.choice(list(current)))

    if not current:
        current = {order[0]}
        next_intro = max(next_intro, 1)
    return current, next_intro


def _random_subset(
    slots: Sequence[str],
    count: int,
    rng: random.Random,
) -> list[str]:
    count = max(1, min(len(slots), count))
    return rng.sample(list(slots), count)


def _force_different_set(
    active: set[str],
    slots: Sequence[str],
    rng: random.Random,
) -> set[str]:
    nxt = set(active)
    off = [s for s in slots if s in active]
    on = [s for s in slots if s not in active]
    if on and off:
        nxt.remove(rng.choice(off))
        nxt.add(rng.choice(on))
    elif on:
        nxt.add(rng.choice(on))
    elif len(nxt) > 1:
        nxt.remove(rng.choice(list(nxt)))
    return nxt


def _cues_from_states(
    slots: Sequence[str],
    states: Sequence[tuple[float, frozenset[str]]],
) -> list[TimelineCue]:
    cues: list[TimelineCue] = []
    prev: frozenset[str] | None = None
    for t, active in states:
        if prev is None:
            layers = {slot: (slot in active) for slot in slots}
        else:
            layers = {
                slot: (slot in active)
                for slot in slots
                if (slot in active) != (slot in prev)
            }
            if not layers:
                continue
        cues.append(TimelineCue(t=float(t), layers=layers))
        prev = active
    return cues
