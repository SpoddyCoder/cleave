"""Tests for procedural timeline preset generation."""

from __future__ import annotations

import random
import statistics

import pytest

from cleave.timeline import TimelineCue, layer_visible_at, visible_state_at
from cleave.timeline_presets import (
    MIN_SWITCH_GAP_SEC,
    ALL_BUILDERS,
    build_arc_cues,
    build_breathing_cues,
    build_dialogue_cues,
    build_pulse_cues,
)
from cleave.timeline_presets.busyness import chord_cost, in_climax_window
from cleave.timeline_presets.motifs import hamming_distance

_DURATIONS = (3.0, 5.0, 12.0, 30.0, 90.0, 180.0)


def _slots(n: int) -> list[str]:
    return [f"layer_{i}" for i in range(1, n + 1)]


def _defaults_false(slots: list[str]) -> dict[str, bool]:
    return {slot: False for slot in slots}


def _assert_sorted(cues: list[TimelineCue]) -> None:
    times = [c.t for c in cues]
    assert times == sorted(times)


def _assert_never_zero(
    cues: list[TimelineCue],
    slots: list[str],
    duration_sec: float,
) -> None:
    defaults = _defaults_false(slots)
    sample_times = [0.0]
    for cue in cues:
        sample_times.append(cue.t)
        sample_times.append(max(0.0, cue.t - 1e-6))
        sample_times.append(cue.t + 1e-6)
    sample_times.append(duration_sec)
    sample_times.append(max(0.0, duration_sec - 1e-6))
    for t in sample_times:
        if t < 0.0 or t > duration_sec:
            continue
        state = visible_state_at(cues, defaults, slots, t)
        assert any(state.values()), f"zero layers active at t={t}"


def _assert_min_gap(cues: list[TimelineCue], duration_sec: float) -> None:
    if len(cues) < 2:
        return
    if duration_sec <= MIN_SWITCH_GAP_SEC:
        return
    for prev, cur in zip(cues, cues[1:]):
        assert cur.t - prev.t >= MIN_SWITCH_GAP_SEC - 1e-9


def _assert_first_cue_full(cues: list[TimelineCue], slots: list[str]) -> None:
    assert cues
    assert cues[0].t == 0.0
    assert set(cues[0].layers) == set(slots)


def _active_count_at(
    cues: list[TimelineCue],
    slots: list[str],
    t: float,
) -> int:
    defaults = _defaults_false(slots)
    state = visible_state_at(cues, defaults, slots, t)
    return sum(1 for v in state.values() if v)


def _sample_active_counts(
    cues: list[TimelineCue],
    slots: list[str],
    duration_sec: float,
    step: float = 2.0,
) -> list[int]:
    counts: list[int] = []
    t = 0.0
    while t <= duration_sec:
        counts.append(_active_count_at(cues, slots, t))
        t += step
    return counts


def _high_cost_fraction(
    cues: list[TimelineCue],
    slots: list[str],
    duration_sec: float,
    step: float = 2.0,
) -> float:
    if duration_sec <= 0.0:
        return 0.0
    high_steps = 0
    total_steps = 0
    t = 0.0
    while t <= duration_sec:
        n = _active_count_at(cues, slots, t)
        if chord_cost(n) >= 4.0:
            high_steps += 1
        total_steps += 1
        t += step
    return high_steps / max(1, total_steps)


def _transition_hamming_distances(
    cues: list[TimelineCue],
    slots: list[str],
    duration_sec: float,
) -> list[int]:
    defaults = _defaults_false(slots)
    distances: list[int] = []
    prev_active: frozenset[str] | None = None
    for cue in cues:
        if cue.t == 0.0:
            prev_active = frozenset(
                slot for slot in slots if layer_visible_at(cues, defaults, slot, 0.0)
            )
            continue
        active = frozenset(
            slot for slot in slots if layer_visible_at(cues, defaults, slot, cue.t)
        )
        if prev_active is not None:
            distances.append(hamming_distance(prev_active, active))
        prev_active = active
    return distances


@pytest.mark.parametrize("builder", ALL_BUILDERS)
@pytest.mark.parametrize("n", range(1, 9))
@pytest.mark.parametrize("duration_sec", _DURATIONS)
def test_preset_invariants(builder, n: int, duration_sec: float) -> None:
    slots = _slots(n)
    cues = builder(slots, duration_sec, random.Random(n * 1000 + int(duration_sec)))
    assert cues
    _assert_sorted(cues)
    _assert_first_cue_full(cues, slots)
    _assert_never_zero(cues, slots, duration_sec)
    _assert_min_gap(cues, duration_sec)
    if n == 1:
        assert len(cues) == 1
        assert cues[0].layers == {slots[0]: True}


@pytest.mark.parametrize("builder", ALL_BUILDERS)
def test_empty_slots_or_nonpositive_duration(builder) -> None:
    assert builder([], 60.0, random.Random(1)) == []
    assert builder(["layer_1"], 0.0, random.Random(1)) == []
    assert builder(["layer_1"], -5.0, random.Random(1)) == []


@pytest.mark.parametrize("builder", ALL_BUILDERS)
def test_seeded_rng_is_deterministic(builder) -> None:
    slots = _slots(4)
    a = builder(slots, 90.0, random.Random(12345))
    b = builder(slots, 90.0, random.Random(12345))
    c = builder(slots, 90.0, random.Random(99999))
    assert a == b
    assert a != c


def test_short_duration_still_never_zero() -> None:
    slots = _slots(4)
    for builder in ALL_BUILDERS:
        cues = builder(slots, 4.0, random.Random(7))
        assert len(cues) == 1
        _assert_never_zero(cues, slots, 4.0)
        assert sum(1 for v in cues[0].layers.values() if v) >= 1


@pytest.mark.parametrize("builder", (build_breathing_cues, build_dialogue_cues))
@pytest.mark.parametrize("duration_sec", (60.0, 120.0, 180.0))
def test_low_characters_favor_sparse_layers(builder, duration_sec: float) -> None:
    slots = _slots(4)
    cues = builder(slots, duration_sec, random.Random(42))
    counts = _sample_active_counts(cues, slots, duration_sec)
    assert statistics.median(counts) <= 2.0


@pytest.mark.parametrize("duration_sec", (60.0, 120.0, 180.0))
def test_high_cost_time_is_bounded(duration_sec: float) -> None:
    slots = _slots(4)
    for builder in ALL_BUILDERS:
        cues = builder(slots, duration_sec, random.Random(99))
        frac = _high_cost_fraction(cues, slots, duration_sec)
        assert frac < 0.12, f"{builder.__name__} high-cost fraction {frac:.2f}"


@pytest.mark.parametrize("duration_sec", (90.0, 180.0))
def test_arc_resolves_without_full_tutti_at_end(duration_sec: float) -> None:
    slots = _slots(4)
    cues = build_arc_cues(slots, duration_sec, random.Random(7))
    defaults = _defaults_false(slots)
    end_state = visible_state_at(cues, defaults, slots, duration_sec)
    assert not all(end_state.values())


@pytest.mark.parametrize("duration_sec", (120.0, 180.0))
def test_arc_uses_climax_window(duration_sec: float) -> None:
    slots = _slots(4)
    cues = build_arc_cues(slots, duration_sec, random.Random(13))
    climax_hits = 0
    for t in [duration_sec * p for p in (0.71, 0.74, 0.76)]:
        if _active_count_at(cues, slots, t) >= 3:
            climax_hits += 1
    assert climax_hits >= 1


@pytest.mark.parametrize("builder", ALL_BUILDERS)
def test_voice_leading_mostly_smooth(builder) -> None:
    slots = _slots(4)
    cues = builder(slots, 120.0, random.Random(55))
    distances = _transition_hamming_distances(cues, slots, 120.0)
    if not distances:
        return
    smooth = sum(1 for d in distances if d <= 2)
    assert smooth / len(distances) >= 0.75


def test_breathing_starts_with_one_layer() -> None:
    slots = _slots(5)
    cues = build_breathing_cues(slots, 120.0, random.Random(11))
    assert sum(1 for v in cues[0].layers.values() if v) == 1


def test_pulse_rotates_singles() -> None:
    slots = _slots(4)
    cues = build_pulse_cues(slots, 90.0, random.Random(21))
    defaults = _defaults_false(slots)
    solo_seen: set[str] = set()
    for cue in cues:
        if cue.t == 0.0:
            continue
        active = [s for s in slots if layer_visible_at(cues, defaults, s, cue.t)]
        if len(active) == 1:
            solo_seen.add(active[0])
    assert len(solo_seen) >= 2


def test_layer_visible_at_with_all_false_defaults() -> None:
    slots = _slots(3)
    cues = build_dialogue_cues(slots, 60.0, random.Random(3))
    defaults = _defaults_false(slots)
    for slot in slots:
        layer_visible_at(cues, defaults, slot, 0.0)


def test_in_climax_window_bounds() -> None:
    assert not in_climax_window(0.69)
    assert in_climax_window(0.75)
    assert not in_climax_window(0.78)
