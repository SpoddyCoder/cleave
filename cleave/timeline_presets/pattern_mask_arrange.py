"""Short-section pattern-mask timeline arranger.

Self-contained parallel to the layers arranger. Frequent add/remove is the
point: the masked compositor sees a slot-set change and runs its spatial
transition. Add-then-remove overlap is kept only when it spans at least
transition_duration plus one beat; otherwise the section swaps in one step.
Mid-section ``SlotCue.recast`` may switch the Milkdrop preset on a
continuing slot (already on; not an add/remove). Character profiles are
not used.
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
from cleave.song_markers import SongMarker, SongMarkerType
from cleave.timeline import (
    LEVEL_EPS,
    SlotCue,
    TimelineLane,
    canonicalize,
    lane_level_at,
)
from cleave.timeline_presets.conductor import (
    AIRTIME_PENALTY,
    CONDUCTOR_ACTIVITY_MIDPOINT,
    PhraseWeights,
    StemConductor,
)
from cleave.timeline_presets.emit import cues_from_states, levels_from_active
from cleave.timeline_presets.grid import thin_bar_times_for_arrange

SECTION_BARS_MIN = 1
SECTION_BARS_MAX = 4
SECTION_LONG_BARS_MIN = 6
SECTION_LONG_BARS_MAX = 8
SECTION_SEC_MIN = 2.0
SECTION_BARS_WEIGHTS: tuple[tuple[int, float], ...] = (
    (1, 0.50),
    (2, 0.32),
    (3, 0.12),
    (4, 0.06),
)
SECTION_LONG_WEIGHT = 0.08

_MIN_STATE_GAP = 1e-3
_HIGH_ENERGY_GAIN = 1.15

_Action = Literal["add_one", "remove_one", "add_two", "hold"]

_ROLE_WEIGHTS: tuple[tuple[CueRole, float], ...] = (
    ("lead", 0.52),
    ("pulse", 0.28),
    ("accent", 0.15),
    ("bed", 0.05),
)
_RECAST_P = 0.45
_RECAST_LONG_P = 0.80
_RECAST_KEEP_ROLE_P = 0.40


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
    transition_duration: float = 0.0,
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
        opening = frozenset(slot_list[:1])
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
    recast_rng = random.Random(rng.getrandbits(64))

    airtime = {slot: 0.0 for slot in order}
    current: frozenset[str] = frozenset()
    current_roles: dict[str, CueRole] = {}
    levels: list[tuple[float, dict[str, float]]] = []
    casts: list[dict[str, tuple[CueRole, BlendMode]]] = []
    recasts: list[tuple[str, float, CueRole]] = []
    last_t = -1.0

    def _emit(
        t: float,
        active: frozenset[str],
        *,
        new_slots: frozenset[str],
        force_t: bool = False,
    ) -> None:
        nonlocal last_t
        cue_t = 0.0 if not levels else float(t)
        if (
            not force_t
            and levels
            and cue_t <= last_t + _MIN_STATE_GAP * 0.5
        ):
            cue_t = last_t + _MIN_STATE_GAP
        if cue_t >= duration_sec:
            return
        levels.append((cue_t, levels_from_active(active, 1.0)))
        cast = _cast_for_slots(new_slots, rng)
        casts.append(cast)
        for slot, (role, _blend) in cast.items():
            current_roles[slot] = role
        for slot in [s for s in current_roles if s not in active]:
            del current_roles[slot]
        last_t = cue_t

    for index, (start, end) in enumerate(sections):
        midpoint = (start + end) * 0.5
        weights = None if conductor is None else conductor.phrase_at(midpoint)
        budget_gain = 1.0 if weights is None else weights.budget_gain
        high_energy = budget_gain >= _HIGH_ENERGY_GAIN
        marker_type = _marker_type_at(start, markers)
        next_start = sections[index + 1][0] if index + 1 < len(sections) else None
        next_marker = (
            _marker_type_at(next_start, markers) if next_start is not None else None
        )
        at_begin = marker_type == "begin"
        at_crescendo = marker_type == "crescendo"
        next_crescendo = next_marker == "crescendo"
        near_diminuendo = (
            marker_type == "diminuendo" or next_marker == "diminuendo"
        )
        at_marker = marker_type is not None
        allow_five = (
            next_crescendo or at_crescendo or high_energy or density_bias >= 2
        )
        target = _pick_target_count(
            rng,
            n_slots,
            density_bias=density_bias,
            at_begin=at_begin,
            at_crescendo=at_crescendo,
            next_crescendo=next_crescendo,
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
            _schedule_section_recasts(
                recast_rng,
                start,
                end,
                last_t,
                current,
                current_roles,
                recasts,
                bars,
                beat_times,
                beat_period,
            )
            _accumulate_airtime(airtime, current, end - start)
            continue

        action = _pick_action(
            rng,
            len(current),
            target,
            n_slots,
            at_marker=at_marker,
            next_crescendo=next_crescendo,
        )
        added, removed = _resolve_mutation(
            rng,
            current,
            action,
            target,
            order,
            weights,
            airtime,
            allow_five=allow_five,
            at_marker=at_marker,
            drop_to_one=at_begin or at_crescendo,
        )
        if at_marker and not added and not removed:
            added, removed = _swap_one(rng, current, order, weights, airtime)
        settled = (current | added) - removed

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
            transition_duration=transition_duration,
            at_marker=at_marker,
        ):
            _emit(t, active, new_slots=new_slots, force_t=at_marker)

        current = settled
        _schedule_section_recasts(
            recast_rng,
            start,
            end,
            last_t,
            settled - added,
            current_roles,
            recasts,
            bars,
            beat_times,
            beat_period,
        )
        _accumulate_airtime(airtime, current, max(0.0, end - start))

    if not levels:
        opening = frozenset(order[:1])
        return cues_from_states(
            slot_list,
            [(0.0, levels_from_active(opening))],
            [_cast_for_slots(opening, rng)],
        )
    return _apply_recasts(cues_from_states(slot_list, levels, casts), recasts)


def partition_pattern_mask_sections(
    bars: Sequence[float],
    duration_sec: float,
    rng: random.Random,
    song_marker_times: Sequence[float] = (),
) -> list[tuple[float, float]]:
    """Split the song into short sections; song markers always cut.

    Common lengths are 1-2 bars, with occasional 3-4. At most one section
    per song may be 6-8 bars.
    """
    markers = [
        float(t) for t in song_marker_times if 0.0 < float(t) < duration_sec
    ]
    long_used = False
    if not markers:
        sections, _long_used = _partition_on_bars(
            bars, duration_sec, rng, long_used
        )
        return sections

    sections: list[tuple[float, float]] = []
    for sec_start, sec_end in _section_bounds(markers, duration_sec):
        section_bars = [t for t in bars if sec_start <= t < sec_end]
        chunk, long_used = _partition_in_section(
            section_bars, sec_start, sec_end, rng, long_used
        )
        sections.extend(chunk)
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


def _marker_type_at(
    t: float | None, markers: Sequence[SongMarker]
) -> SongMarkerType | None:
    if t is None:
        return None
    for marker in markers:
        if abs(marker.time - t) <= 1e-6:
            return marker.marker_type
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
    long_used: bool,
) -> tuple[list[tuple[float, float]], bool]:
    if sec_end - sec_start < 1e-6:
        return [], long_used
    if not section_bars:
        return [(sec_start, sec_end)], long_used
    raw, long_used = _partition_on_bars(
        section_bars, sec_end, rng, long_used
    )
    if not raw:
        return [(sec_start, sec_end)], long_used
    adjusted: list[tuple[float, float]] = []
    for i, (ps, pe) in enumerate(raw):
        start = sec_start if i == 0 else ps
        end = sec_end if i == len(raw) - 1 else pe
        if end - start > 1e-6:
            adjusted.append((start, end))
    if not adjusted:
        return [(sec_start, sec_end)], long_used
    return adjusted, long_used


def _pick_section_bars(
    rng: random.Random,
    remaining: int,
    *,
    long_used: bool,
) -> tuple[int, bool]:
    if remaining <= SECTION_BARS_MAX:
        return remaining, long_used
    can_long = (
        not long_used and remaining >= SECTION_LONG_BARS_MIN
    )
    if can_long and rng.random() < SECTION_LONG_WEIGHT:
        hi = min(SECTION_LONG_BARS_MAX, remaining)
        return rng.randint(SECTION_LONG_BARS_MIN, hi), True
    target = _weighted_choice(rng, SECTION_BARS_WEIGHTS)
    return max(SECTION_BARS_MIN, min(target, remaining)), long_used


def _partition_on_bars(
    bars: Sequence[float],
    duration_sec: float,
    rng: random.Random,
    long_used: bool,
) -> tuple[list[tuple[float, float]], bool]:
    sections: list[tuple[float, float]] = []
    i = 0
    n = len(bars)
    while i < n:
        remaining = n - i
        target, long_used = _pick_section_bars(
            rng, remaining, long_used=long_used
        )
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
    return sections, long_used


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
    at_begin: bool,
    at_crescendo: bool,
    next_crescendo: bool,
    near_diminuendo: bool,
    allow_five: bool,
    budget_gain: float,
    near_silent: bool,
) -> int:
    if n_slots <= 1:
        return 1
    if at_begin or at_crescendo:
        return 1
    w1, w2, w3, w4, w5 = 0.08, 0.45, 0.35, 0.15, 0.05
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
    if next_crescendo:
        w1 = 0.0
        w2 *= 0.15
        w3 *= 0.4
        w4 *= 2.2
        if n_slots >= 5:
            w5 = max(w5, 0.2) * 2.5
    if near_diminuendo:
        w1, w2, w3, w4, w5 = 0.20, 0.60, 0.20, 0.0, 0.0
    if near_silent:
        w1, w2, w3, w4, w5 = 0.30, 0.60, 0.10, 0.0, 0.0
    folded: dict[int, float] = {}
    for count, weight in ((1, w1), (2, w2), (3, w3), (4, w4), (5, w5)):
        if weight <= 0.0:
            continue
        clamped = min(max(count, 1), n_slots)
        folded[clamped] = folded.get(clamped, 0.0) + weight
    if not folded:
        return 1
    picked = _weighted_choice(rng, tuple(folded.items()))
    if budget_gain >= 1.2 and not near_diminuendo:
        picked = min(n_slots, picked + 1)
        if picked >= 5 and not allow_five:
            picked = min(4, n_slots)
    elif budget_gain <= 0.8:
        picked = max(2 if next_crescendo else 1, picked - 1)
    floor = 2 if next_crescendo else 1
    return max(floor, min(n_slots, picked))


def _pick_action(
    rng: random.Random,
    current_n: int,
    target_n: int,
    n_slots: int,
    *,
    at_marker: bool = False,
    next_crescendo: bool = False,
) -> _Action:
    add_one, remove_one, add_two, hold = 0.50, 0.30, 0.10, 0.10
    can_add_one = current_n < n_slots
    can_add_two = current_n + 2 <= n_slots
    can_remove = current_n > 1
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
    if at_marker:
        hold = 0.0
    if next_crescendo and current_n < 2:
        hold = 0.0
        remove_one = 0.0
    return _weighted_choice(
        rng,
        (
            ("add_one", add_one),
            ("remove_one", remove_one),
            ("add_two", add_two),
            ("hold", hold),
        ),
    )


def _swap_one(
    rng: random.Random,
    current: frozenset[str],
    order: Sequence[str],
    weights: PhraseWeights | None,
    airtime: Mapping[str, float],
) -> tuple[frozenset[str], frozenset[str]]:
    inactive = [slot for slot in order if slot not in current]
    active = [slot for slot in order if slot in current]
    if inactive and active:
        added = frozenset(
            _pick_slots(rng, inactive, 1, weights, airtime, prefer_busy=True)
        )
        removed = frozenset(
            _pick_slots(rng, active, 1, weights, airtime, prefer_busy=False)
        )
        return added, removed
    if len(active) > 1:
        removed = frozenset(
            _pick_slots(rng, active, 1, weights, airtime, prefer_busy=False)
        )
        return frozenset(), removed
    if inactive:
        added = frozenset(
            _pick_slots(rng, inactive, 1, weights, airtime, prefer_busy=True)
        )
        return added, frozenset()
    return frozenset(), frozenset()


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
    at_marker: bool = False,
    drop_to_one: bool = False,
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
        cap = max(0, current_n - 1)
        return frozenset(
            _pick_slots(
                rng, active, min(k, cap), weights, airtime, prefer_busy=False
            )
        )

    if drop_to_one:
        if current_n <= 1:
            return _swap_one(rng, current, order, weights, airtime)
        keep = frozenset(
            _pick_slots(rng, active, 1, weights, airtime, prefer_busy=True)
        )
        return frozenset(), current - keep

    if at_marker and current_n == target:
        return _swap_one(rng, current, order, weights, airtime)

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
        if inactive and current_n >= 1:
            return _add(1), _remove(1)
        if current_n > 1:
            return frozenset(), _remove(1)
        return frozenset(), frozenset()

    if current_n > max(1, target):
        return frozenset(), _remove(1)
    if current_n > 1 and current_n >= target:
        return frozenset(), _remove(1)
    if inactive and current_n >= 1:
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


def _pick_role(rng: random.Random, *, exclude: CueRole | None = None) -> CueRole:
    pool = tuple((role, w) for role, w in _ROLE_WEIGHTS if role != exclude)
    return _weighted_choice(rng, pool)


def _recast_role(rng: random.Random, current: CueRole) -> CueRole:
    if rng.random() < _RECAST_KEEP_ROLE_P:
        return current
    return _pick_role(rng, exclude=current)


def _cast_for_slots(
    slots: Sequence[str] | frozenset[str], rng: random.Random
) -> dict[str, tuple[CueRole, BlendMode]]:
    cast: dict[str, tuple[CueRole, BlendMode]] = {}
    for slot in slots:
        role = _pick_role(rng)
        cast[slot] = (role, CUE_ROLE_BLEND[role])
    return cast


def _section_is_long(start: float, end: float, bars: Sequence[float]) -> bool:
    n_bars = sum(1 for b in bars if start <= b < end)
    return SECTION_LONG_BARS_MIN <= n_bars <= SECTION_LONG_BARS_MAX


def _pick_recast_time(
    rng: random.Random,
    ref_t: float,
    section_end: float,
    beat_times: Sequence[float],
    beat_period: float,
    *,
    after: float | None = None,
) -> float | None:
    t_lo = ref_t + beat_period
    if after is not None:
        t_lo = max(t_lo, after + beat_period)
    t_hi = section_end - beat_period
    if t_hi <= t_lo:
        return None
    n_max = max(1, int((t_hi - ref_t) / beat_period) + 2)
    choices: list[float] = []
    seen: set[float] = set()
    for n in range(1, n_max + 1):
        cand = _offset_time(ref_t, n, 1, beat_times, beat_period, t_lo, t_hi)
        if cand < t_lo - 1e-9 or cand > t_hi + 1e-9:
            continue
        key = round(cand, 9)
        if key in seen:
            continue
        seen.add(key)
        choices.append(cand)
    if not choices:
        return None
    return rng.choice(choices)


def _schedule_section_recasts(
    rng: random.Random,
    start: float,
    end: float,
    last_t: float,
    continuing: frozenset[str],
    current_roles: dict[str, CueRole],
    recasts: list[tuple[str, float, CueRole]],
    bars: Sequence[float],
    beat_times: Sequence[float],
    beat_period: float,
) -> None:
    pool = [slot for slot in continuing if slot in current_roles]
    if not pool:
        return
    ref_t = max(last_t, start)
    long_section = _section_is_long(start, end, bars)
    p = _RECAST_LONG_P if long_section else _RECAST_P
    t = _pick_recast_time(rng, ref_t, end, beat_times, beat_period)
    if t is None:
        return
    if rng.random() >= p:
        return
    slot = rng.choice(pool)
    role = _recast_role(rng, current_roles[slot])
    recasts.append((slot, t, role))
    current_roles[slot] = role
    if not long_section:
        return
    pool2 = [s for s in pool if s != slot]
    if not pool2:
        return
    t2 = _pick_recast_time(rng, ref_t, end, beat_times, beat_period, after=t)
    if t2 is None:
        return
    slot2 = rng.choice(pool2)
    role2 = _recast_role(rng, current_roles[slot2])
    recasts.append((slot2, t2, role2))
    current_roles[slot2] = role2


def _apply_recasts(
    lanes: dict[str, TimelineLane],
    recasts: Sequence[tuple[str, float, CueRole]],
) -> dict[str, TimelineLane]:
    if not recasts:
        return lanes
    out = dict(lanes)
    for slot, t, role in recasts:
        lane = out.get(slot)
        if lane is None:
            continue
        if any(abs(cue.t - t) <= _MIN_STATE_GAP for cue in lane.cues):
            continue
        if lane_level_at(lane, t - _MIN_STATE_GAP, inherit=0.0) <= LEVEL_EPS:
            continue
        cue = SlotCue(
            t=t,
            level=1.0,
            blend=CUE_ROLE_BLEND[role],
            role=role,
            cut="none",
            recast=True,
            anchor=True,
        )
        out[slot] = TimelineLane(
            baseline=lane.baseline,
            cues=canonicalize(lane.baseline, [*lane.cues, cue]),
        )
    return out


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
    transition_duration: float = 0.0,
    at_marker: bool = False,
) -> list[tuple[float, frozenset[str], frozenset[str]]]:
    """Return (t, active, newly_on) states for a section-boundary mutation."""
    if not added and not removed:
        return []
    t_lo = last_t + _MIN_STATE_GAP
    t_hi = end - _MIN_STATE_GAP
    if at_marker:
        return [(start, settled, added)]
    if added and removed:
        min_span = max(0.0, float(transition_duration)) + beat_period
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
        if t_add < t_remove - _MIN_STATE_GAP and (t_remove - t_add) >= min_span:
            return [
                (t_add, current | added, added),
                (t_remove, settled, frozenset()),
            ]
        t_add = max(t_lo, start - beat_period)
        t_remove = min(t_hi, start + beat_period)
        if t_add < t_remove - _MIN_STATE_GAP and (t_remove - t_add) >= min_span:
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
