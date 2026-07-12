"""Tests for procedural timeline preset generation (per-lane)."""

from __future__ import annotations

import random
import statistics

import pytest

from cleave.timeline import Timeline, TimelineLane, lane_visible_at
from cleave.timeline_presets import (
    MIN_SWITCH_GAP_BARS,
    ALL_BUILDERS,
    build_arc_cues,
    build_breathing_cues,
    build_dialogue_cues,
    build_pulse_cues,
)
from cleave.timeline_presets.busyness import chord_cost, in_climax_window
from cleave.timeline_presets.motifs import hamming_distance

_DURATIONS = (3.0, 5.0, 12.0, 30.0, 90.0, 180.0)
_BAR_SEC = 2.0


def _slots(n: int) -> list[str]:
    return [f"layer_{i}" for i in range(1, n + 1)]


def _bar_times_for(duration_sec: float, bar_sec: float = _BAR_SEC) -> list[float]:
    bars: list[float] = []
    t = 0.0
    while t < duration_sec - 1e-9:
        bars.append(t)
        t += bar_sec
    return bars


def _inherits_false(slots: list[str]) -> dict[str, bool]:
    return {slot: False for slot in slots}


def _timeline(lanes: dict[str, TimelineLane]) -> Timeline:
    return Timeline(lanes=lanes)


def _visible_at(
    lanes: dict[str, TimelineLane],
    slots: list[str],
    t: float,
) -> dict[str, bool]:
    inherits = _inherits_false(slots)
    return _timeline(lanes).visible_state_at(slots, t, inherits)


def _all_transition_times(lanes: dict[str, TimelineLane]) -> list[float]:
    times = sorted({cue.t for lane in lanes.values() for cue in lane.cues})
    return times


def _assert_lanes_cover_slots(lanes: dict[str, TimelineLane], slots: list[str]) -> None:
    assert set(lanes) == set(slots)
    for slot in slots:
        assert lanes[slot].baseline is not None


def _assert_never_zero(
    lanes: dict[str, TimelineLane],
    slots: list[str],
    duration_sec: float,
) -> None:
    sample_times = [0.0]
    for t in _all_transition_times(lanes):
        sample_times.append(t)
        sample_times.append(max(0.0, t - 1e-6))
        sample_times.append(t + 1e-6)
    sample_times.append(duration_sec)
    sample_times.append(max(0.0, duration_sec - 1e-6))
    for t in sample_times:
        if t < 0.0 or t > duration_sec:
            continue
        state = _visible_at(lanes, slots, t)
        assert any(state.values()), f"zero layers active at t={t}"


def _assert_cues_on_bars(
    lanes: dict[str, TimelineLane],
    bar_times: list[float],
) -> None:
    if not bar_times:
        return
    for lane in lanes.values():
        for cue in lane.cues:
            assert any(abs(cue.t - b) < 1e-9 for b in bar_times), (
                f"cue t={cue.t} not on bar grid {bar_times[:8]}..."
            )


def _assert_min_bar_gap(
    lanes: dict[str, TimelineLane],
    bar_times: list[float],
) -> None:
    times = _all_transition_times(lanes)
    if len(times) < 2 or len(bar_times) < 2:
        return
    for prev, cur in zip(times, times[1:]):
        prev_idx = min(range(len(bar_times)), key=lambda i: (abs(bar_times[i] - prev), bar_times[i]))
        cur_idx = min(range(len(bar_times)), key=lambda i: (abs(bar_times[i] - cur), bar_times[i]))
        assert cur_idx - prev_idx >= MIN_SWITCH_GAP_BARS


def _active_count_at(
    lanes: dict[str, TimelineLane],
    slots: list[str],
    t: float,
) -> int:
    state = _visible_at(lanes, slots, t)
    return sum(1 for v in state.values() if v)


def _sample_active_counts(
    lanes: dict[str, TimelineLane],
    slots: list[str],
    duration_sec: float,
    step: float = 2.0,
) -> list[int]:
    counts: list[int] = []
    t = 0.0
    while t <= duration_sec:
        counts.append(_active_count_at(lanes, slots, t))
        t += step
    return counts


def _high_cost_fraction(
    lanes: dict[str, TimelineLane],
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
        n = _active_count_at(lanes, slots, t)
        if chord_cost(n) >= 4.0:
            high_steps += 1
        total_steps += 1
        t += step
    return high_steps / max(1, total_steps)


def _transition_hamming_distances(
    lanes: dict[str, TimelineLane],
    slots: list[str],
) -> list[int]:
    times = [0.0] + _all_transition_times(lanes)
    distances: list[int] = []
    prev_active: frozenset[str] | None = None
    for t in times:
        active = frozenset(
            slot for slot in slots if _visible_at(lanes, slots, t)[slot]
        )
        if prev_active is not None:
            distances.append(hamming_distance(prev_active, active))
        prev_active = active
    return distances


def _build(builder, slots, duration_sec, rng):
    bars = _bar_times_for(duration_sec)
    return builder(slots, duration_sec, rng, bar_times=bars), bars


@pytest.mark.parametrize("builder", ALL_BUILDERS)
@pytest.mark.parametrize("n", range(1, 9))
@pytest.mark.parametrize("duration_sec", _DURATIONS)
def test_preset_invariants(builder, n: int, duration_sec: float) -> None:
    slots = _slots(n)
    lanes, bars = _build(
        builder, slots, duration_sec, random.Random(n * 1000 + int(duration_sec))
    )
    assert lanes
    _assert_lanes_cover_slots(lanes, slots)
    _assert_never_zero(lanes, slots, duration_sec)
    _assert_cues_on_bars(lanes, bars)
    _assert_min_bar_gap(lanes, bars)
    if n == 1:
        assert lanes[slots[0]].baseline is True
        assert lanes[slots[0]].cues == []


@pytest.mark.parametrize("builder", ALL_BUILDERS)
def test_empty_slots_or_nonpositive_duration(builder) -> None:
    bars = _bar_times_for(60.0)
    assert builder([], 60.0, random.Random(1), bar_times=bars) == {}
    assert builder(["layer_1"], 0.0, random.Random(1), bar_times=bars) == {}
    assert builder(["layer_1"], -5.0, random.Random(1), bar_times=bars) == {}


@pytest.mark.parametrize("builder", ALL_BUILDERS)
def test_seeded_rng_is_deterministic(builder) -> None:
    slots = _slots(4)
    bars = _bar_times_for(90.0)
    a = builder(slots, 90.0, random.Random(12345), bar_times=bars)
    b = builder(slots, 90.0, random.Random(12345), bar_times=bars)
    c = builder(slots, 90.0, random.Random(99999), bar_times=bars)
    assert a == b
    assert a != c


def test_short_duration_still_never_zero() -> None:
    slots = _slots(4)
    for builder in ALL_BUILDERS:
        lanes, bars = _build(builder, slots, 4.0, random.Random(7))
        assert all(not lane.cues for lane in lanes.values())
        _assert_never_zero(lanes, slots, 4.0)
        assert sum(1 for lane in lanes.values() if lane.baseline) >= 1
        _assert_cues_on_bars(lanes, bars)


@pytest.mark.parametrize("builder", (build_breathing_cues, build_dialogue_cues))
@pytest.mark.parametrize("duration_sec", (60.0, 120.0, 180.0))
def test_low_characters_favor_sparse_layers(builder, duration_sec: float) -> None:
    slots = _slots(4)
    lanes, _bars = _build(builder, slots, duration_sec, random.Random(42))
    counts = _sample_active_counts(lanes, slots, duration_sec)
    assert statistics.median(counts) <= 2.0


@pytest.mark.parametrize("duration_sec", (60.0, 120.0, 180.0))
def test_high_cost_time_is_bounded(duration_sec: float) -> None:
    slots = _slots(4)
    for builder in ALL_BUILDERS:
        lanes, _bars = _build(builder, slots, duration_sec, random.Random(99))
        frac = _high_cost_fraction(lanes, slots, duration_sec)
        assert frac < 0.15, f"{builder.__name__} high-cost fraction {frac:.2f}"


@pytest.mark.parametrize("duration_sec", (90.0, 180.0))
def test_arc_resolves_without_full_tutti_at_end(duration_sec: float) -> None:
    slots = _slots(4)
    lanes, _bars = _build(build_arc_cues, slots, duration_sec, random.Random(7))
    end_state = _visible_at(lanes, slots, duration_sec)
    assert not all(end_state.values())


@pytest.mark.parametrize("duration_sec", (120.0, 180.0))
def test_arc_uses_climax_window(duration_sec: float) -> None:
    slots = _slots(4)
    lanes, _bars = _build(build_arc_cues, slots, duration_sec, random.Random(13))
    climax_hits = 0
    for t in [duration_sec * p for p in (0.71, 0.74, 0.76)]:
        if _active_count_at(lanes, slots, t) >= 3:
            climax_hits += 1
    assert climax_hits >= 1


@pytest.mark.parametrize("builder", ALL_BUILDERS)
def test_voice_leading_mostly_smooth(builder) -> None:
    slots = _slots(4)
    lanes, _bars = _build(builder, slots, 120.0, random.Random(55))
    distances = _transition_hamming_distances(lanes, slots)
    if not distances:
        return
    smooth = sum(1 for d in distances if d <= 2)
    assert smooth / len(distances) >= 0.75


def test_breathing_starts_with_one_layer() -> None:
    slots = _slots(5)
    lanes, _bars = _build(build_breathing_cues, slots, 120.0, random.Random(11))
    assert sum(1 for lane in lanes.values() if lane.baseline) == 1


def test_pulse_rotates_singles() -> None:
    slots = _slots(4)
    lanes, _bars = _build(build_pulse_cues, slots, 90.0, random.Random(21))
    solo_seen: set[str] = set()
    for t in _all_transition_times(lanes):
        if t == 0.0:
            continue
        active = [s for s in slots if lane_visible_at(lanes[s], t, inherit=False)]
        if len(active) == 1:
            solo_seen.add(active[0])
    assert len(solo_seen) >= 2


def test_lane_visible_at_with_all_false_inherits() -> None:
    slots = _slots(3)
    lanes, _bars = _build(build_dialogue_cues, slots, 60.0, random.Random(3))
    for slot in slots:
        lane_visible_at(lanes[slot], 0.0, inherit=False)


def test_in_climax_window_bounds() -> None:
    assert not in_climax_window(0.69)
    assert in_climax_window(0.75)
    assert not in_climax_window(0.78)


def test_empty_bar_times_returns_opening_only() -> None:
    slots = _slots(4)
    for builder in ALL_BUILDERS:
        lanes = builder(slots, 60.0, random.Random(1), bar_times=())
        assert all(not lane.cues for lane in lanes.values())
        _assert_never_zero(lanes, slots, 60.0)
