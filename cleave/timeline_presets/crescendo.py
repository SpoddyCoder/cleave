"""Optional song-marker crescendo overlay for timeline presets."""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from cleave.timeline import TimelineLane, lane_visible_at
from cleave.timeline_presets.chords import MAX_CONCURRENT_LAYERS
from cleave.timeline_presets.emit import cues_from_states

CrescendoTarget = Literal["last", "penultimate"]

CRESCENDO_MIN_MARKERS = 3
_FALLBACK_START_FRACTION = 0.20

TIMELINE_PRESET_CRESCENDO_OPTIONS: tuple[CrescendoTarget | None, ...] = (
    None,
    "last",
    "penultimate",
)

_CRESCENDO_DISPLAY: dict[CrescendoTarget | None, str] = {
    None: "no",
    "last": "last song marker",
    "penultimate": "penultimate song marker",
}


def timeline_preset_crescendo_display(target: CrescendoTarget | None) -> str:
    return _CRESCENDO_DISPLAY.get(target, _CRESCENDO_DISPLAY[None])


def cycle_timeline_preset_crescendo(
    value: CrescendoTarget | None, *, forward: bool
) -> CrescendoTarget | None:
    options = TIMELINE_PRESET_CRESCENDO_OPTIONS
    try:
        index = options.index(value)
    except ValueError:
        index = 0
    delta = 1 if forward else -1
    return options[(index + delta) % len(options)]


@dataclass(frozen=True)
class CrescendoWindow:
    """Times for ramp start, full stack, and drop-to-solo."""

    t_start: float
    t_full: float
    t_peak_end: float


def normalize_crescendo_markers(
    song_marker_times: Sequence[float],
    duration_sec: float,
) -> list[float]:
    """Sorted unique markers strictly inside ``(0, duration_sec)``."""
    return sorted(
        {
            float(t)
            for t in song_marker_times
            if 0.0 < float(t) < duration_sec
        }
    )


def resolve_crescendo_window(
    song_marker_times: Sequence[float],
    duration_sec: float,
    target: CrescendoTarget,
) -> CrescendoWindow | None:
    """Resolve crescendo times for ``last`` / ``penultimate`` marker targets."""
    markers = normalize_crescendo_markers(song_marker_times, duration_sec)
    if len(markers) < CRESCENDO_MIN_MARKERS or duration_sec <= 0.0:
        return None
    selected_idx = len(markers) - 1 if target == "last" else len(markers) - 2
    if selected_idx < 1:
        return None
    t_peak_end = markers[selected_idx]
    t_full = markers[selected_idx - 1]
    if selected_idx >= 2:
        t_start = markers[selected_idx - 2]
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
    song_marker_times: Sequence[float],
    target: CrescendoTarget,
    rng: random.Random,
) -> dict[str, TimelineLane]:
    """Rewrite ``lanes`` from the crescendo window through song end."""
    slot_list = list(slots)
    if not slot_list or duration_sec <= 0.0:
        return lanes
    window = resolve_crescendo_window(song_marker_times, duration_sec, target)
    if window is None:
        return lanes

    prefix = _states_before(lanes, slot_list, window.t_start)
    crescendo = _crescendo_states(
        slot_list,
        window,
        duration_sec=duration_sec,
        bar_times=bar_times,
        rng=rng,
    )
    merged = _merge_states(prefix, crescendo)
    if not merged:
        return lanes
    return cues_from_states(slot_list, merged)


def _states_before(
    lanes: dict[str, TimelineLane],
    slots: Sequence[str],
    t_start: float,
) -> list[tuple[float, frozenset[str]]]:
    times = {0.0}
    for slot in slots:
        lane = lanes.get(slot)
        if lane is None:
            continue
        for cue in lane.cues:
            if cue.t < t_start - 1e-9:
                times.add(float(cue.t))
    states: list[tuple[float, frozenset[str]]] = []
    for t in sorted(times):
        active = _active_at(lanes, slots, t)
        if not states or states[-1][1] != active:
            states.append((t, active))
    return states


def _active_at(
    lanes: dict[str, TimelineLane],
    slots: Sequence[str],
    t: float,
) -> frozenset[str]:
    active = frozenset(
        slot
        for slot in slots
        if lane_visible_at(
            lanes.get(slot) or TimelineLane(baseline=False, cues=[]),
            t,
            inherit=False,
        )
    )
    if active:
        return active
    return frozenset({slots[0]})


def _crescendo_states(
    slots: Sequence[str],
    window: CrescendoWindow,
    *,
    duration_sec: float,
    bar_times: Sequence[float],
    rng: random.Random,
) -> list[tuple[float, frozenset[str]]]:
    order = list(slots)
    rng.shuffle(order)
    max_n = min(len(order), MAX_CONCURRENT_LAYERS)
    stack = order[:max_n]
    times = _spread_times(window.t_start, window.t_full, max_n, bar_times)
    states: list[tuple[float, frozenset[str]]] = []
    for i, t in enumerate(times):
        n_active = min(i + 1, max_n)
        states.append((float(t), frozenset(stack[:n_active])))
    # Drop to a single layer at the selected marker; hold through song end.
    solo = frozenset({stack[0]})
    peak_end = float(window.t_peak_end)
    if peak_end < duration_sec - 1e-9:
        if not states or abs(states[-1][0] - peak_end) > 1e-9 or states[-1][1] != solo:
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
    """``count`` times from ``t_start`` to ``t_full`` inclusive, preferring bars."""
    if count <= 1:
        return [float(t_start)]
    if t_full <= t_start + 1e-9:
        return [float(t_start)] * count

    if count == 2:
        return [float(t_start), float(t_full)]

    interior_need = count - 2
    bars = [float(t) for t in bar_times if t_start + 1e-9 < float(t) < t_full - 1e-9]
    if len(bars) >= interior_need:
        interior = [
            bars[_even_index(i, interior_need, len(bars))]
            for i in range(interior_need)
        ]
    else:
        span = t_full - t_start
        interior = [
            t_start + span * (i + 1) / (count - 1)
            for i in range(interior_need)
        ]
    return [float(t_start), *[float(t) for t in interior], float(t_full)]


def _even_index(i: int, need: int, n: int) -> int:
    if need <= 1:
        return n // 2
    return int(round(i * (n - 1) / (need - 1)))


def _merge_states(
    prefix: Sequence[tuple[float, frozenset[str]]],
    crescendo: Sequence[tuple[float, frozenset[str]]],
) -> list[tuple[float, frozenset[str]]]:
    if not crescendo:
        return list(prefix)
    merged = list(prefix)
    first_t = crescendo[0][0]
    while merged and merged[-1][0] >= first_t - 1e-9:
        merged.pop()
    for t, active in crescendo:
        if merged and merged[-1][1] == active:
            continue
        if merged and abs(merged[-1][0] - t) < 1e-9:
            merged[-1] = (t, active)
            continue
        merged.append((t, active))
    return merged
