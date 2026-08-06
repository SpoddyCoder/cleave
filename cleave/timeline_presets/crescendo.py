"""Song-marker crescendo overlay for timeline presets.

Builds crescendos to each in-range song marker typed ``crescendo``.
``diminuendo`` markers are ignored.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from cleave.blend_modes import BlendMode
from cleave.cue_roles import CUE_ROLE_BLEND, CueRole
from cleave.song_markers import SongMarker
from cleave.timeline import (
    LEVEL_EPS,
    LEVEL_QUANTUM,
    TimelineLane,
    clamp_level,
    lane_blend_at,
    lane_level_at,
    lane_role_at,
    levels_equal,
    quantize_level,
)
from cleave.timeline_presets.chords import MAX_CONCURRENT_LAYERS
from cleave.timeline_presets.emit import cues_from_states

_FALLBACK_START_FRACTION = 0.20
# An entrant appears at the dimmest visible level and climbs to full by t_full.
CRESCENDO_ENTRY_LEVEL = LEVEL_QUANTUM
# Enough steps for a lane to climb through every quantised level on the way up.
CRESCENDO_RAMP_STEPS = int(round(1.0 / LEVEL_QUANTUM))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * float(t)


@dataclass(frozen=True)
class CrescendoWindow:
    """Times for ramp start, full stack, and drop-to-solo."""

    t_start: float
    t_full: float
    t_peak_end: float


def normalize_crescendo_markers(
    song_markers: Sequence[SongMarker],
    duration_sec: float,
) -> list[SongMarker]:
    """Sorted unique markers strictly inside ``(0, duration_sec)``.

    On duplicate times, the first occurrence wins.
    """
    by_time: dict[float, SongMarker] = {}
    for marker in song_markers:
        t = float(marker.time)
        if 0.0 < t < duration_sec and t not in by_time:
            by_time[t] = SongMarker(t, marker.marker_type)
    return [by_time[t] for t in sorted(by_time)]


def resolve_crescendo_windows(
    song_markers: Sequence[SongMarker],
    duration_sec: float,
) -> list[CrescendoWindow]:
    """Resolve one window per crescendo-typed marker that has a prior marker."""
    markers = normalize_crescendo_markers(song_markers, duration_sec)
    if duration_sec <= 0.0 or not markers:
        return []
    windows: list[CrescendoWindow] = []
    for selected_idx, marker in enumerate(markers):
        if marker.marker_type != "crescendo":
            continue
        window = _window_at_index(markers, selected_idx, duration_sec)
        if window is not None:
            windows.append(window)
    return windows


def resolve_crescendo_window(
    song_markers: Sequence[SongMarker],
    duration_sec: float,
    *,
    peak_time: float | None = None,
) -> CrescendoWindow | None:
    """Resolve a single crescendo window.

    When ``peak_time`` is set, resolve the window for that crescendo marker.
    Otherwise return the earliest resolved crescendo window, or ``None``.
    """
    if peak_time is not None:
        markers = normalize_crescendo_markers(song_markers, duration_sec)
        peak = float(peak_time)
        for selected_idx, marker in enumerate(markers):
            if marker.marker_type != "crescendo":
                continue
            if abs(marker.time - peak) < 1e-9:
                return _window_at_index(markers, selected_idx, duration_sec)
        return None
    windows = resolve_crescendo_windows(song_markers, duration_sec)
    return windows[0] if windows else None


def _window_at_index(
    markers: Sequence[SongMarker],
    selected_idx: int,
    duration_sec: float,
) -> CrescendoWindow | None:
    if selected_idx < 1 or duration_sec <= 0.0:
        return None
    t_peak_end = float(markers[selected_idx].time)
    t_full = float(markers[selected_idx - 1].time)
    if selected_idx >= 2:
        t_start = float(markers[selected_idx - 2].time)
    else:
        t_start = max(0.0, t_peak_end - _FALLBACK_START_FRACTION * duration_sec)
    if t_start > t_full:
        t_start = max(0.0, t_full - _FALLBACK_START_FRACTION * duration_sec)
    if t_full > t_peak_end:
        return None
    return CrescendoWindow(t_start=t_start, t_full=t_full, t_peak_end=t_peak_end)


def apply_crescendo(
    lanes: dict[str, TimelineLane],
    slots: Sequence[str],
    *,
    duration_sec: float,
    bar_times: Sequence[float],
    song_markers: Sequence[SongMarker],
    rng: random.Random,
) -> dict[str, TimelineLane]:
    """Rewrite ``lanes`` for each crescendo-typed song marker through song end.

    Windows are applied earliest-first so a later crescendo overwrites from its
    ramp start. When the source lanes carry cast roles (e.g. conductor Apply),
    the prefix keeps those held role/blend values and each crescendo ramp
    assigns a simple lead/bed cast so ``cues_from_states`` does not strip them.
    """
    slot_list = list(slots)
    if not slot_list or duration_sec <= 0.0:
        return lanes
    windows = resolve_crescendo_windows(song_markers, duration_sec)
    if not windows:
        return lanes

    result = lanes
    for window in windows:
        result = _apply_crescendo_window(
            result,
            slot_list,
            window,
            duration_sec=duration_sec,
            bar_times=bar_times,
            rng=rng,
        )
    return result


def _apply_crescendo_window(
    lanes: dict[str, TimelineLane],
    slots: Sequence[str],
    window: CrescendoWindow,
    *,
    duration_sec: float,
    bar_times: Sequence[float],
    rng: random.Random,
) -> dict[str, TimelineLane]:
    prefix = _states_before(lanes, slots, window.t_start)
    crescendo = _crescendo_states(
        slots,
        window,
        duration_sec=duration_sec,
        bar_times=bar_times,
        rng=rng,
    )
    merged = _merge_states(prefix, crescendo)
    if not merged:
        return lanes
    casts = None
    if _lanes_have_roles(lanes):
        casts = _casts_for_merged(
            lanes, slots, merged, t_start=window.t_start
        )
    return cues_from_states(
        list(slots),
        merged,
        casts,
    )


def _levels_equal_maps(
    a: Mapping[str, float],
    b: Mapping[str, float],
    slots: Sequence[str] | None = None,
) -> bool:
    keys = slots if slots is not None else sorted(set(a) | set(b))
    return all(
        levels_equal(float(a.get(slot, 0.0)), float(b.get(slot, 0.0)))
        for slot in keys
    )


def _lanes_have_roles(lanes: Mapping[str, TimelineLane]) -> bool:
    return any(
        cue.role is not None for lane in lanes.values() for cue in lane.cues
    )


def _cast_at_from_lanes(
    lanes: Mapping[str, TimelineLane],
    slots: Sequence[str],
    t: float,
    levels: Mapping[str, float],
) -> dict[str, tuple[CueRole, BlendMode]]:
    """Held role/blend at ``t`` for slots that are on in ``levels``."""
    cast: dict[str, tuple[CueRole, BlendMode]] = {}
    for slot in slots:
        if float(levels.get(slot, 0.0)) <= LEVEL_EPS:
            continue
        lane = lanes.get(slot) or TimelineLane(baseline=0.0, cues=[])
        role = lane_role_at(lane, t)
        if role is None:
            continue
        blend = lane_blend_at(lane, t)
        if blend is None:
            blend = CUE_ROLE_BLEND[role]
        cast[slot] = (role, blend)
    return cast


def _crescendo_cast_for_levels(
    levels: Mapping[str, float],
) -> dict[str, tuple[CueRole, BlendMode]]:
    """Simple ramp cast: first active slot (stack order) is lead; rest bed."""
    active = [
        slot for slot, level in levels.items() if float(level) > LEVEL_EPS
    ]
    if not active:
        return {}
    lead = active[0]
    cast: dict[str, tuple[CueRole, BlendMode]] = {}
    for slot in active:
        role: CueRole = "lead" if slot == lead else "bed"
        cast[slot] = (role, CUE_ROLE_BLEND[role])
    return cast


def _casts_for_merged(
    lanes: Mapping[str, TimelineLane],
    slots: Sequence[str],
    merged: Sequence[tuple[float, Mapping[str, float]]],
    *,
    t_start: float,
) -> list[dict[str, tuple[CueRole, BlendMode]]]:
    casts: list[dict[str, tuple[CueRole, BlendMode]]] = []
    for t, levels in merged:
        if t < t_start - 1e-9:
            casts.append(_cast_at_from_lanes(lanes, slots, t, levels))
        else:
            casts.append(_crescendo_cast_for_levels(levels))
    return casts


def _states_before(
    lanes: dict[str, TimelineLane],
    slots: Sequence[str],
    t_start: float,
) -> list[tuple[float, dict[str, float]]]:
    times = {0.0}
    for slot in slots:
        lane = lanes.get(slot)
        if lane is None:
            continue
        for cue in lane.cues:
            if cue.t < t_start - 1e-9:
                times.add(float(cue.t))
    states: list[tuple[float, dict[str, float]]] = []
    for t in sorted(times):
        levels = _active_at(lanes, slots, t)
        if not states or not _levels_equal_maps(states[-1][1], levels, slots):
            states.append((t, levels))
    return states


def _active_at(
    lanes: dict[str, TimelineLane],
    slots: Sequence[str],
    t: float,
) -> dict[str, float]:
    levels = {
        slot: lane_level_at(
            lanes.get(slot) or TimelineLane(baseline=0.0, cues=[]),
            t,
            inherit=0.0,
        )
        for slot in slots
    }
    if any(level > LEVEL_EPS for level in levels.values()):
        return levels
    return {slots[0]: 1.0}


def _crescendo_states(
    slots: Sequence[str],
    window: CrescendoWindow,
    *,
    duration_sec: float,
    bar_times: Sequence[float],
    rng: random.Random,
) -> list[tuple[float, dict[str, float]]]:
    order = list(slots)
    rng.shuffle(order)
    max_n = min(len(order), MAX_CONCURRENT_LAYERS)
    stack = order[:max_n]
    # One more step than entrants so the last layer also fades in rather than
    # appearing at full level on the final step.
    step_count = max(max_n + 1, CRESCENDO_RAMP_STEPS)
    entry_steps = [int(j * step_count / max_n) for j in range(max_n)]
    times = _spread_times(window.t_start, window.t_full, step_count, bar_times)
    states: list[tuple[float, dict[str, float]]] = []
    last_i = len(times) - 1
    for i, t in enumerate(times):
        if i == last_i:
            levels = {slot: 1.0 for slot in stack}
        else:
            levels = {}
            for j, slot in enumerate(stack):
                entry = entry_steps[j]
                if entry > i:
                    continue
                progress = (i - entry) / max(1, last_i - entry)
                levels[slot] = quantize_level(
                    clamp_level(_lerp(CRESCENDO_ENTRY_LEVEL, 1.0, progress))
                )
        states.append((float(t), levels))
    # Drop to a single layer at the selected marker; hold through song end.
    solo = {stack[0]: 1.0}
    peak_end = float(window.t_peak_end)
    if peak_end < duration_sec - 1e-9:
        if (
            not states
            or abs(states[-1][0] - peak_end) > 1e-9
            or not _levels_equal_maps(states[-1][1], solo)
        ):
            states.append((peak_end, solo))
    elif states:
        # Selected marker is at/after duration; force solo on the last step.
        states[-1] = (states[-1][0], solo)
    return states


def _spread_times(
    t_start: float,
    t_full: float,
    count: int,
    bar_times: Sequence[float],
) -> list[float]:
    """``count`` times evenly from ``t_start`` to ``t_full`` inclusive, snapped to bars."""
    if count <= 1:
        return [float(t_start)]
    if t_full <= t_start + 1e-9:
        return [float(t_start)] * count

    if count == 2:
        return [float(t_start), float(t_full)]

    bars = [float(t) for t in bar_times if t_start + 1e-9 < float(t) < t_full - 1e-9]
    span = t_full - t_start
    ideal_step = span / (count - 1)
    times = [float(t_start)]
    for i in range(1, count - 1):
        target = t_start + span * i / (count - 1)
        snapped = _nearest_bar_after(
            bars, target, times[-1], tolerance=0.5 * ideal_step
        )
        times.append(snapped if snapped is not None else max(target, times[-1]))
    times.append(float(t_full))
    return times


def _nearest_bar_after(
    bars: Sequence[float],
    target: float,
    previous: float,
    *,
    tolerance: float,
) -> float | None:
    """Bar nearest ``target`` within ``tolerance`` and later than ``previous``.

    A sparse grid should not distort the ramp, so a distant bar is refused and
    the caller falls back to the evenly spaced time.
    """
    candidates = [
        t
        for t in bars
        if t > previous + 1e-9 and abs(t - target) <= tolerance + 1e-9
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda t: (abs(t - target), t))


def _merge_states(
    prefix: Sequence[tuple[float, Mapping[str, float]]],
    crescendo: Sequence[tuple[float, Mapping[str, float]]],
) -> list[tuple[float, dict[str, float]]]:
    if not crescendo:
        return [(t, dict(levels)) for t, levels in prefix]
    merged: list[tuple[float, dict[str, float]]] = [
        (t, dict(levels)) for t, levels in prefix
    ]
    first_t = crescendo[0][0]
    while merged and merged[-1][0] >= first_t - 1e-9:
        merged.pop()
    for t, levels in crescendo:
        level_map = dict(levels)
        if merged and _levels_equal_maps(merged[-1][1], level_map):
            continue
        if merged and abs(merged[-1][0] - t) < 1e-9:
            merged[-1] = (t, level_map)
            continue
        merged.append((t, level_map))
    return merged
