"""Short-section pattern-mask timeline arranger.

Self-contained parallel to the layers arranger. Frequent add/remove with
1-2 beat overlap is the point: the masked compositor sees a slot-set change
and runs its spatial transition. Character profiles are not used.
"""

from __future__ import annotations

import random
import statistics
from collections.abc import Mapping, Sequence
from typing import Literal, TypeVar

from cleave.blend_modes import BlendMode
from cleave.cue_roles import CUE_ROLE_BLEND, CueRole
from cleave.extract import StemSource
from cleave.signals import Signals
from cleave.song_markers import SongMarker
from cleave.timeline import TimelineLane
from cleave.timeline_presets.conductor import (
    AIRTIME_PENALTY,
    CONDUCTOR_ACTIVITY_MIDPOINT,
    PhraseWeights,
    StemConductor,
)
from cleave.timeline_presets.emit import cues_from_states, levels_from_active
from cleave.timeline_presets.grid import thin_bar_times_for_arrange

SECTION_BARS_MIN = 2
SECTION_BARS_MAX = 4
SECTION_SEC_MIN = 4.0

_MIN_STATE_GAP = 1e-3
_HIGH_ENERGY_GAIN = 1.15

_Action = Literal["add_one", "remove_one", "add_two", "hold"]

_ROLE_WEIGHTS: tuple[tuple[CueRole, float], ...] = (
    ("lead", 0.50),
    ("accent", 0.25),
    ("pulse", 0.15),
    ("bed", 0.10),
)


def compose_pattern_mask_timeline(
    slots: Sequence[str],
    duration_sec: float,
    rng: random.Random,
    bar_times: Sequence[float],
    song_marker_times: Sequence[float] = (),
    song_markers: Sequence[SongMarker] = (),
    density_bias: int = 0,
    signals: Signals | None = None,
    slot_stems: Mapping[str, StemSource] | None = None,
    beat_times: Sequence[float] = (),
) -> dict[str, TimelineLane]:
    slot_list = list(slots)
    if not slot_list or duration_sec <= 0.0:
        return {}
    if len(slot_list) == 1:
        return cues_from_states(
            slot_list,
            [(0.0, levels_from_active({slot_list[0]}))],
            [_cast_for_slots(slot_list, rng)],
        )

    markers = _normalized_markers(song_markers, song_marker_times, duration_sec)
    marker_times = [m.time for m in markers]
    bars = thin_bar_times_for_arrange(bar_times, duration_sec)
    sections = partition_pattern_mask_sections(
        bars, duration_sec, rng, marker_times
    )
    if not sections:
        opening = frozenset(slot_list[: min(2, len(slot_list))])
        return cues_from_states(
            slot_list,
            [(0.0, levels_from_active(opening))],
            [_cast_for_slots(opening, rng)],
        )

    conductor = StemConductor.build(
        signals, slot_stems, sections, density_bias=density_bias
    )
    beat_period = _beat_period(bars, beat_times)
    n_slots = len(slot_list)
    order = list(slot_list)
    rng.shuffle(order)

    airtime = {slot: 0.0 for slot in order}
    current: frozenset[str] = frozenset()
    levels: list[tuple[float, dict[str, float]]] = []
    casts: list[dict[str, tuple[CueRole, BlendMode]]] = []
    last_t = -1.0

    def _emit(
        t: float,
        active: frozenset[str],
        *,
        new_slots: frozenset[str],
    ) -> None:
        nonlocal last_t
        cue_t = 0.0 if not levels else float(t)
        if levels and cue_t <= last_t + _MIN_STATE_GAP * 0.5:
            cue_t = last_t + _MIN_STATE_GAP
        if cue_t >= duration_sec:
            return
        levels.append((cue_t, levels_from_active(active, 1.0)))
        casts.append(_cast_for_slots(new_slots, rng))
        last_t = cue_t

    for index, (start, end) in enumerate(sections):
        midpoint = (start + end) * 0.5
        weights = None if conductor is None else conductor.phrase_at(midpoint)
        budget_gain = 1.0 if weights is None else weights.budget_gain
        high_energy = budget_gain >= _HIGH_ENERGY_GAIN
        gesture = _gesture_at(start, markers)
        next_start = sections[index + 1][0] if index + 1 < len(sections) else None
        next_gesture = (
            _gesture_at(next_start, markers) if next_start is not None else None
        )
        near_crescendo = gesture == "crescendo" or next_gesture == "crescendo"
        near_diminuendo = gesture == "diminuendo" or next_gesture == "diminuendo"
        allow_five = near_crescendo or high_energy or density_bias >= 2
        target = _pick_target_count(
            rng,
            n_slots,
            density_bias=density_bias,
            near_crescendo=near_crescendo,
            near_diminuendo=near_diminuendo,
            allow_five=allow_five,
            budget_gain=budget_gain,
            near_silent=bool(weights is not None and weights.near_silent),
        )

        if index == 0:
            picked = _pick_slots(
                rng,
                order,
                target,
                weights,
                airtime,
                prefer_busy=True,
            )
            current = frozenset(picked)
            _emit(0.0, current, new_slots=current)
            _accumulate_airtime(airtime, current, end - start)
            continue

        action = _pick_action(rng, len(current), target, n_slots)
        added, removed = _resolve_mutation(
            rng,
            current,
            action,
            target,
            order,
            weights,
            airtime,
            allow_five=allow_five,
        )
        settled = (current | added) - removed
        if len(settled) < 2:
            settled = current if len(current) >= 2 else frozenset(order[:2])
            added = settled - current
            removed = current - settled

        for t, active, new_slots in _overlap_states(
            start,
            end,
            last_t,
            current,
            added,
            removed,
            settled,
            rng,
            beat_times,
            beat_period,
        ):
            _emit(t, active, new_slots=new_slots)

        current = settled
        _accumulate_airtime(airtime, current, max(0.0, end - start))

    if not levels:
        opening = frozenset(order[: min(2, n_slots)])
        return cues_from_states(
            slot_list,
            [(0.0, levels_from_active(opening))],
            [_cast_for_slots(opening, rng)],
        )
    return cues_from_states(slot_list, levels, casts)


def partition_pattern_mask_sections(
    bars: Sequence[float],
    duration_sec: float,
    rng: random.Random,
    song_marker_times: Sequence[float] = (),
) -> list[tuple[float, float]]:
    """Split the song into 2-4 bar sections; song markers always cut."""
    markers = [
        float(t) for t in song_marker_times if 0.0 < float(t) < duration_sec
    ]
    if not markers:
        return _partition_on_bars(bars, duration_sec, rng)

    sections: list[tuple[float, float]] = []
    for sec_start, sec_end in _section_bounds(markers, duration_sec):
        section_bars = [t for t in bars if sec_start <= t < sec_end]
        sections.extend(
            _partition_in_section(section_bars, sec_start, sec_end, rng)
        )
    return sections


def _normalized_markers(
    song_markers: Sequence[SongMarker],
    song_marker_times: Sequence[float],
    duration_sec: float,
) -> list[SongMarker]:
    by_time: dict[float, SongMarker] = {}
    source: Sequence[SongMarker]
    if song_markers:
        source = song_markers
    else:
        source = tuple(
            SongMarker(float(t), "standard") for t in song_marker_times
        )
    for marker in source:
        t = float(marker.time)
        if 0.0 < t < duration_sec and t not in by_time:
            by_time[t] = SongMarker(t, marker.marker_type)
    return [by_time[t] for t in sorted(by_time)]


def _gesture_at(
    t: float | None, markers: Sequence[SongMarker]
) -> str | None:
    if t is None:
        return None
    for marker in markers:
        if abs(marker.time - t) <= 1e-6:
            if marker.marker_type in ("crescendo", "diminuendo"):
                return marker.marker_type
            return None
    return None


def _section_bounds(
    markers: Sequence[float], duration_sec: float
) -> list[tuple[float, float]]:
    cuts = [0.0, *markers, duration_sec]
    return [
        (start, end)
        for start, end in zip(cuts, cuts[1:])
        if end - start > 1e-6
    ]


def _partition_in_section(
    section_bars: Sequence[float],
    sec_start: float,
    sec_end: float,
    rng: random.Random,
) -> list[tuple[float, float]]:
    if sec_end - sec_start < 1e-6:
        return []
    if not section_bars:
        return [(sec_start, sec_end)]
    raw = _partition_on_bars(section_bars, sec_end, rng)
    if not raw:
        return [(sec_start, sec_end)]
    adjusted: list[tuple[float, float]] = []
    for i, (ps, pe) in enumerate(raw):
        start = sec_start if i == 0 else ps
        end = sec_end if i == len(raw) - 1 else pe
        if end - start > 1e-6:
            adjusted.append((start, end))
    return adjusted if adjusted else [(sec_start, sec_end)]


def _partition_on_bars(
    bars: Sequence[float],
    duration_sec: float,
    rng: random.Random,
) -> list[tuple[float, float]]:
    sections: list[tuple[float, float]] = []
    i = 0
    n = len(bars)
    while i < n:
        remaining = n - i
        if remaining <= SECTION_BARS_MAX:
            target = remaining
        else:
            target = rng.randint(SECTION_BARS_MIN, SECTION_BARS_MAX)
            leftover = remaining - target
            if 0 < leftover < SECTION_BARS_MIN:
                target = remaining
        start = bars[i]
        end_i = i + target
        end = bars[end_i] if end_i < n else duration_sec
        while end - start < SECTION_SEC_MIN - 1e-9 and end_i < n:
            end_i += 1
            end = bars[end_i] if end_i < n else duration_sec
        if end - start < 1e-6:
            break
        sections.append((start, end))
        i = end_i
        if end >= duration_sec - 1e-6:
            break
    return sections


def _beat_period(
    bar_times: Sequence[float], beat_times: Sequence[float]
) -> float:
    gap = _median_gap(beat_times)
    if gap is not None and gap > 1e-9:
        return gap
    bar_gap = _median_gap(bar_times)
    if bar_gap is not None and bar_gap > 1e-9:
        return bar_gap / 4.0
    return 0.5


def _median_gap(times: Sequence[float]) -> float | None:
    vals = [float(t) for t in times]
    if len(vals) < 2:
        return None
    gaps = [vals[i + 1] - vals[i] for i in range(len(vals) - 1) if vals[i + 1] > vals[i]]
    if not gaps:
        return None
    return float(statistics.median(gaps))


def _offset_time(
    t: float,
    n_beats: int,
    direction: int,
    beat_times: Sequence[float],
    beat_period: float,
    t_min: float,
    t_max: float,
) -> float:
    cand: float | None = None
    beats = [float(b) for b in beat_times]
    if len(beats) >= 2:
        idx = min(range(len(beats)), key=lambda i: (abs(beats[i] - t), beats[i]))
        target_idx = idx + direction * n_beats
        if 0 <= target_idx < len(beats):
            cand = beats[target_idx]
    if cand is None:
        cand = t + direction * n_beats * beat_period
    if t_max <= t_min:
        return t
    return max(t_min, min(t_max, cand))


_T = TypeVar("_T")


def _weighted_choice(rng: random.Random, items: Sequence[tuple[_T, float]]) -> _T:
    filtered = [(item, w) for item, w in items if w > 0.0]
    if not filtered:
        return items[0][0]
    values, weights = zip(*filtered)
    return rng.choices(list(values), weights=list(weights), k=1)[0]


def _pick_target_count(
    rng: random.Random,
    n_slots: int,
    *,
    density_bias: int,
    near_crescendo: bool,
    near_diminuendo: bool,
    allow_five: bool,
    budget_gain: float,
    near_silent: bool,
) -> int:
    if n_slots <= 1:
        return 1
    w2, w3, w4, w5 = 0.45, 0.35, 0.15, 0.05
    if density_bias > 0:
        shift = 0.06 * density_bias
        w2 = max(0.05, w2 - shift)
        w4 += shift * 0.6
        w5 += shift * 0.4
    elif density_bias < 0:
        shift = 0.06 * (-density_bias)
        w2 += shift
        w4 = max(0.0, w4 - shift * 0.6)
        w5 = max(0.0, w5 - shift * 0.4)
    if not allow_five:
        w4 += w5
        w5 = 0.0
    if near_crescendo:
        w2 *= 0.15
        w3 *= 0.4
        w4 *= 2.2
        if n_slots >= 5:
            w5 = max(w5, 0.2) * 2.5
    if near_diminuendo:
        w2, w3, w4, w5 = 0.75, 0.25, 0.0, 0.0
    if near_silent:
        w2, w3, w4, w5 = 0.85, 0.15, 0.0, 0.0
    folded: dict[int, float] = {}
    for count, weight in ((2, w2), (3, w3), (4, w4), (5, w5)):
        if weight <= 0.0:
            continue
        clamped = min(max(count, 2), n_slots)
        folded[clamped] = folded.get(clamped, 0.0) + weight
    if not folded:
        return min(2, n_slots)
    picked = _weighted_choice(rng, tuple(folded.items()))
    if budget_gain >= 1.2 and not near_diminuendo:
        picked = min(n_slots, picked + 1)
        if picked >= 5 and not allow_five:
            picked = min(4, n_slots)
    elif budget_gain <= 0.8:
        picked = max(2, picked - 1)
    return max(2, min(n_slots, picked))


def _pick_action(
    rng: random.Random,
    current_n: int,
    target_n: int,
    n_slots: int,
) -> _Action:
    add_one, remove_one, add_two, hold = 0.50, 0.30, 0.10, 0.10
    can_add_one = current_n < n_slots
    can_add_two = current_n + 2 <= n_slots
    can_remove = current_n > 2
    if current_n >= target_n:
        remove_one *= 2.5
        add_one *= 0.35
        add_two *= 0.2
        if current_n > target_n:
            hold *= 0.4
    else:
        add_one *= 2.0
        add_two *= 1.8
        remove_one *= 0.25
        hold *= 0.5
    if not can_add_one:
        add_one = 0.0
        add_two = 0.0
    elif not can_add_two:
        add_two = 0.0
    if not can_remove:
        remove_one = 0.0
    if current_n < 2 and can_add_one:
        return "add_one"
    return _weighted_choice(
        rng,
        (
            ("add_one", add_one),
            ("remove_one", remove_one),
            ("add_two", add_two),
            ("hold", hold),
        ),
    )


def _resolve_mutation(
    rng: random.Random,
    current: frozenset[str],
    action: _Action,
    target: int,
    order: Sequence[str],
    weights: PhraseWeights | None,
    airtime: Mapping[str, float],
    *,
    allow_five: bool,
) -> tuple[frozenset[str], frozenset[str]]:
    current_n = len(current)
    n_slots = len(order)
    inactive = [slot for slot in order if slot not in current]
    active = [slot for slot in order if slot in current]

    def _add(k: int) -> frozenset[str]:
        return frozenset(
            _pick_slots(rng, inactive, k, weights, airtime, prefer_busy=True)
        )

    def _remove(k: int) -> frozenset[str]:
        cap = max(0, current_n - 2)
        return frozenset(
            _pick_slots(
                rng, active, min(k, cap), weights, airtime, prefer_busy=False
            )
        )

    if action == "hold":
        return frozenset(), frozenset()

    if action == "add_two":
        grow_to = current_n + 2
        if grow_to >= 5 and not allow_five:
            action = "add_one"
        elif len(inactive) >= 2 and grow_to <= n_slots:
            return _add(2), frozenset()
        elif inactive:
            action = "add_one"
        else:
            return frozenset(), frozenset()

    if action == "add_one":
        if inactive and current_n < target:
            return _add(1), frozenset()
        if inactive and current_n >= 2:
            return _add(1), _remove(1)
        if current_n > 2:
            return frozenset(), _remove(1)
        return frozenset(), frozenset()

    if current_n > max(2, target):
        return frozenset(), _remove(1)
    if current_n > 2 and current_n >= target:
        return frozenset(), _remove(1)
    if inactive and current_n >= 2:
        return _add(1), _remove(1)
    return frozenset(), frozenset()


def _pick_slots(
    rng: random.Random,
    pool: Sequence[str],
    k: int,
    weights: PhraseWeights | None,
    airtime: Mapping[str, float],
    *,
    prefer_busy: bool,
) -> list[str]:
    remaining = list(pool)
    picked: list[str] = []
    n = max(len(airtime), 1)
    if weights is not None and remaining and k > 0:
        if prefer_busy:
            seeded = max(
                remaining,
                key=lambda slot: (
                    float(weights.slot_activity.get(slot, 0.0)),
                    -float(airtime.get(slot, 0.0)),
                ),
            )
        else:
            seeded = min(
                remaining,
                key=lambda slot: (
                    float(weights.slot_activity.get(slot, 0.0)),
                    -float(airtime.get(slot, 0.0)),
                ),
            )
        picked.append(seeded)
        remaining.remove(seeded)
    while remaining and len(picked) < k:
        slot_weights = [
            _slot_weight(
                slot, weights, airtime, n, prefer_busy=prefer_busy
            )
            for slot in remaining
        ]
        choice = rng.choices(remaining, weights=slot_weights, k=1)[0]
        picked.append(choice)
        remaining.remove(choice)
    return picked


def _slot_weight(
    slot: str,
    weights: PhraseWeights | None,
    airtime: Mapping[str, float],
    n: int,
    *,
    prefer_busy: bool,
) -> float:
    even = 1.0 / max(n, 1)
    total = sum(max(0.0, float(v)) for v in airtime.values())
    share = (max(0.0, float(airtime.get(slot, 0.0))) / total) if total > 0.0 else even
    activity = CONDUCTOR_ACTIVITY_MIDPOINT
    if weights is not None:
        activity = float(weights.slot_activity.get(slot, CONDUCTOR_ACTIVITY_MIDPOINT))
    if prefer_busy:
        score = (activity * activity) * 3.0 - AIRTIME_PENALTY * (share - even)
    else:
        quiet = 1.0 - activity
        score = (quiet * quiet) * 3.0 + AIRTIME_PENALTY * (share - even)
    return max(0.05, score + 1.0)


def _accumulate_airtime(
    airtime: dict[str, float], active: frozenset[str], duration: float
) -> None:
    if duration <= 0.0:
        return
    for slot in active:
        airtime[slot] = airtime.get(slot, 0.0) + duration


def _cast_for_slots(
    slots: Sequence[str] | frozenset[str], rng: random.Random
) -> dict[str, tuple[CueRole, BlendMode]]:
    roles, weights = zip(*_ROLE_WEIGHTS)
    cast: dict[str, tuple[CueRole, BlendMode]] = {}
    for slot in slots:
        role: CueRole = rng.choices(list(roles), weights=list(weights), k=1)[0]
        cast[slot] = (role, CUE_ROLE_BLEND[role])
    return cast


def _overlap_states(
    start: float,
    end: float,
    last_t: float,
    current: frozenset[str],
    added: frozenset[str],
    removed: frozenset[str],
    settled: frozenset[str],
    rng: random.Random,
    beat_times: Sequence[float],
    beat_period: float,
) -> list[tuple[float, frozenset[str], frozenset[str]]]:
    """Return (t, active, newly_on) states for a section-boundary mutation."""
    if not added and not removed:
        return []
    t_lo = last_t + _MIN_STATE_GAP
    t_hi = end - _MIN_STATE_GAP
    if added and removed:
        t_add = _offset_time(
            start,
            rng.choice((1, 2)),
            -1,
            beat_times,
            beat_period,
            t_lo,
            t_hi,
        )
        t_remove = _offset_time(
            start,
            rng.choice((1, 2)),
            1,
            beat_times,
            beat_period,
            t_lo,
            t_hi,
        )
        if t_add < t_remove - _MIN_STATE_GAP:
            return [
                (t_add, current | added, added),
                (t_remove, settled, frozenset()),
            ]
        t_add = max(t_lo, start - beat_period)
        t_remove = min(t_hi, start + beat_period)
        if t_add < t_remove - _MIN_STATE_GAP:
            return [
                (t_add, current | added, added),
                (t_remove, settled, frozenset()),
            ]
        return [(max(start, t_lo), settled, added)]
    if added:
        t_add = _offset_time(
            start,
            rng.choice((1, 2)),
            -1,
            beat_times,
            beat_period,
            t_lo,
            t_hi,
        )
        return [(t_add, settled, added)]
    t_remove = _offset_time(
        start,
        rng.choice((1, 2)),
        1,
        beat_times,
        beat_period,
        t_lo,
        t_hi,
    )
    return [(t_remove, settled, frozenset())]
