"""Tests for procedural timeline preset generation."""

from __future__ import annotations

import random

import pytest

from cleave.timeline import TimelineCue, layer_visible_at, visible_state_at
from cleave.timeline_presets import (
    MIN_SWITCH_GAP_SEC,
    build_random_cues,
    build_slow_build_cues,
)

_BUILDERS = (build_slow_build_cues, build_random_cues)
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


@pytest.mark.parametrize("builder", _BUILDERS)
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


@pytest.mark.parametrize("n", range(2, 9))
@pytest.mark.parametrize("duration_sec", (12.0, 30.0, 90.0, 180.0))
def test_slow_build_ends_all_on(n: int, duration_sec: float) -> None:
    slots = _slots(n)
    cues = build_slow_build_cues(slots, duration_sec, random.Random(42 + n))
    defaults = _defaults_false(slots)
    state = visible_state_at(cues, defaults, slots, duration_sec)
    assert all(state.values())


@pytest.mark.parametrize("builder", _BUILDERS)
def test_empty_slots_or_nonpositive_duration(builder) -> None:
    assert builder([], 60.0, random.Random(1)) == []
    assert builder(["layer_1"], 0.0, random.Random(1)) == []
    assert builder(["layer_1"], -5.0, random.Random(1)) == []


@pytest.mark.parametrize("builder", _BUILDERS)
def test_seeded_rng_is_deterministic(builder) -> None:
    slots = _slots(4)
    a = builder(slots, 90.0, random.Random(12345))
    b = builder(slots, 90.0, random.Random(12345))
    c = builder(slots, 90.0, random.Random(99999))
    assert a == b
    assert a != c


def test_short_duration_still_never_zero() -> None:
    slots = _slots(4)
    for builder in _BUILDERS:
        cues = builder(slots, 4.0, random.Random(7))
        assert len(cues) == 1
        _assert_never_zero(cues, slots, 4.0)
        assert sum(1 for v in cues[0].layers.values() if v) >= 1


def test_slow_build_starts_with_one_layer() -> None:
    slots = _slots(5)
    cues = build_slow_build_cues(slots, 120.0, random.Random(11))
    assert sum(1 for v in cues[0].layers.values() if v) == 1


def test_layer_visible_at_with_all_false_defaults() -> None:
    slots = _slots(3)
    cues = build_random_cues(slots, 60.0, random.Random(3))
    defaults = _defaults_false(slots)
    for slot in slots:
        # Smoke: evaluation works with defaults all False when t=0 sets full state.
        layer_visible_at(cues, defaults, slot, 0.0)
