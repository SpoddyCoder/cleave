"""Build overlay for timeline presets.

Each ``build`` section ramps from one dim layer to the full stack and holds it
for the last bar. Only cues inside the section are rewritten, so whatever the
arrangement does next lands on the section's end.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median

from cleave.blend_modes import BlendMode
from cleave.cue_roles import CUE_ROLE_BLEND, CueRole
from cleave.song_markers import SongMarker, resolve_sections
from cleave.timeline import (
    LEVEL_EPS,
    LEVEL_QUANTUM,
    SlotCue,
    TimelineLane,
    canonicalize,
    clamp_level,
    empty_lane,
    lane_blend_at,
    lane_level_at,
    lane_role_at,
    levels_equal,
    quantize_level,
)
from cleave.timeline_presets.sections import max_layers

# An entrant appears at the dimmest visible level and climbs to full by t_full.
BUILD_ENTRY_LEVEL = LEVEL_QUANTUM
# Enough steps for a lane to climb through every quantised level on the way up.
BUILD_RAMP_STEPS = int(round(1.0 / LEVEL_QUANTUM))
# The ramp takes at least this share of the section, so a short build still rises.
_MIN_RAMP_FRACTION = 0.75


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * float(t)


@dataclass(frozen=True)
class BuildWindow:
    """Times the ramp starts, the stack is full, and the section ends."""

    t_start: float
    t_full: float
    t_end: float


def resolve_build_windows(
    song_markers: Sequence[SongMarker],
    duration_sec: float,
    bar_times: Sequence[float] = (),
) -> list[BuildWindow]:
    """One window per ``build`` section, full from the start of its last bar."""
    return [
        BuildWindow(
            section.start,
            _full_time(section.start, section.end, bar_times),
            section.end,
        )
        for section in resolve_sections(song_markers, duration_sec)
        if section.section_type == "build"
    ]


def _full_time(t_start: float, t_end: float, bar_times: Sequence[float]) -> float:
    earliest = t_start + _MIN_RAMP_FRACTION * (t_end - t_start)
    gaps = [b - a for a, b in zip(bar_times, bar_times[1:]) if b > a]
    # A bar line just before the marker is the marker's own bar, not a last bar.
    slack = 0.5 * median(gaps) if gaps else 0.0
    bars = [float(t) for t in bar_times if t_start < float(t) < t_end - slack]
    return max(earliest, bars[-1]) if bars else earliest


def apply_build(
    lanes: dict[str, TimelineLane],
    slots: Sequence[str],
    *,
    duration_sec: float,
    bar_times: Sequence[float],
    song_markers: Sequence[SongMarker],
    rng: random.Random,
) -> dict[str, TimelineLane]:
    """Rewrite ``lanes`` inside each ``build`` section; return ``lanes`` if none.

    When the lanes carry roles, the ramp casts its first layer as lead and the
    rest as bed.
    """
    slot_list = list(slots)
    windows = resolve_build_windows(song_markers, duration_sec, bar_times)
    if not slot_list or not windows:
        return lanes
    with_roles = any(
        cue.role is not None for lane in lanes.values() for cue in lane.cues
    )
    result = {slot: lanes.get(slot) or empty_lane() for slot in slot_list}
    for window in windows:
        states = _build_states(slot_list, window, bar_times=bar_times, rng=rng)
        result = {
            slot: _splice_lane(
                result[slot], slot, window, states, duration_sec, with_roles
            )
            for slot in slot_list
        }
    return result


def _splice_lane(
    lane: TimelineLane,
    slot: str,
    window: BuildWindow,
    states: Sequence[tuple[float, Mapping[str, float]]],
    duration_sec: float,
    with_roles: bool,
) -> TimelineLane:
    cues = [cue for cue in lane.cues if cue.t < window.t_start - 1e-9]
    previous: float | None = None
    for t, levels in states:
        level = float(levels.get(slot, 0.0))
        if previous is not None and levels_equal(level, previous):
            continue
        previous = level
        role: CueRole | None = None
        blend: BlendMode | None = None
        if with_roles and level > LEVEL_EPS:
            role = "lead" if slot == next(iter(levels)) else "bed"
            blend = CUE_ROLE_BLEND[role]
        cues.append(
            SlotCue(
                t=t,
                level=level,
                blend=blend,
                role=role,
                cut="none",
                # Same level and blend as before still has to take the new role.
                anchor=role is not None and not cues_hold_role(cues, role),
            )
        )
    if window.t_end < duration_sec - 1e-9:
        after = [cue for cue in lane.cues if cue.t >= window.t_end - 1e-9]
        if not after or after[0].t > window.t_end + 1e-9:
            level = lane_level_at(lane, window.t_end, inherit=0.0)
            role = lane_role_at(lane, window.t_end)
            cues.append(
                SlotCue(
                    t=window.t_end,
                    level=level,
                    blend=lane_blend_at(lane, window.t_end),
                    role=role,
                    cut="none",
                    anchor=role is not None and not cues_hold_role(cues, role),
                )
            )
        cues.extend(after)
    return TimelineLane(baseline=lane.baseline, cues=canonicalize(lane.baseline, cues))


def cues_hold_role(cues: Sequence[SlotCue], role: CueRole | None) -> bool:
    """True when the last of *cues* is off or already holds *role*."""
    return not cues or cues[-1].level <= LEVEL_EPS or cues[-1].role == role


def _build_states(
    slots: Sequence[str],
    window: BuildWindow,
    *,
    bar_times: Sequence[float],
    rng: random.Random,
) -> list[tuple[float, dict[str, float]]]:
    order = list(slots)
    rng.shuffle(order)
    max_n = max_layers(len(order))
    stack = order[:max_n]
    # One more step than entrants so the last layer also fades in rather than
    # appearing at full level on the final step.
    step_count = max(max_n + 1, BUILD_RAMP_STEPS)
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
                    clamp_level(_lerp(BUILD_ENTRY_LEVEL, 1.0, progress))
                )
        states.append((float(t), levels))
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
