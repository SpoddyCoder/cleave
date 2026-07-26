"""Per-lane timeline evaluation and editing for layer levels."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np

from cleave.blend_modes import BlendMode
from cleave.cue_roles import CueRole
from cleave.easing import smoothstep
from cleave.extract import STEM_SOURCES, StemSource

RECORD_DEBOUNCE_SEC = 0.08
SONG_MARKER_FADE_MATCH_EPS = 1e-3
LEVEL_QUANTUM = 0.25
LEVEL_EPS = 1e-6

_STEM_SOURCE_ABBREVIATIONS = {
    "drums": "D",
    "bass": "B",
    "vocals": "V",
    "other": "O",
    "full_mix": "M",
}


@dataclass(frozen=True)
class SlotCue:
    t: float
    level: float
    blend: BlendMode | None = None
    role: CueRole | None = None


@dataclass
class TimelineLane:
    baseline: float | None  # None = inherit session.layers[slot].enabled as 1.0/0.0
    cues: list[SlotCue]  # canonical: strictly increasing t, no redundant transitions


def empty_lane() -> TimelineLane:
    return TimelineLane(baseline=None, cues=[])


def copy_lane(lane: TimelineLane) -> TimelineLane:
    return TimelineLane(baseline=lane.baseline, cues=list(lane.cues))


def stem_abbreviation(stem: StemSource) -> str:
    if stem not in _STEM_SOURCE_ABBREVIATIONS:
        allowed = ", ".join(STEM_SOURCES)
        raise ValueError(f"unknown stem: {stem!r} (expected one of: {allowed})")
    return _STEM_SOURCE_ABBREVIATIONS[stem]


def clamp_level(level: float) -> float:
    return max(0.0, min(1.0, float(level)))


def quantize_level(level: float) -> float:
    clamped = clamp_level(level)
    steps = round(clamped / LEVEL_QUANTUM)
    return clamp_level(steps * LEVEL_QUANTUM)


def levels_equal(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= LEVEL_EPS


def cue_editable_for_blend_role(cue: SlotCue) -> bool:
    """True when ``cue`` may carry blend/role and is in the strip nav set.

    Off cues (``level <= LEVEL_EPS``) are level transitions only; cast and blend
    are authored on the next on / visible period.
    """
    return float(cue.level) > LEVEL_EPS


def navigable_cue_times(lane: TimelineLane) -> list[float]:
    """Cue times eligible for ``,`` / ``.`` selection (level above off)."""
    return [cue.t for cue in lane.cues if cue_editable_for_blend_role(cue)]


def canonicalize(
    baseline: float | None,
    cues: Sequence[SlotCue],
) -> list[SlotCue]:
    """Drop redundant/no-op transitions; last-wins at equal ``t``.

    Returns strictly increasing ``t`` cues where each changes level and/or
    blend from the previous state (``baseline`` with blend inherit ``None``,
    or the prior cue when baseline is None). Role is not part of the
    comparison. Off cues (``level <= LEVEL_EPS``) always have ``blend`` and
    ``role`` cleared before compare and emit.
    """
    if not cues:
        return []
    ordered = sorted(cues, key=lambda cue: cue.t)
    collapsed: list[SlotCue] = []
    for cue in ordered:
        if collapsed and collapsed[-1].t == cue.t:
            collapsed[-1] = cue
        else:
            collapsed.append(cue)
    result: list[SlotCue] = []
    current_level = baseline
    current_blend: BlendMode | None = None
    for cue in collapsed:
        if not cue_editable_for_blend_role(cue):
            cue = replace(cue, blend=None, role=None)
        if (
            current_level is not None
            and levels_equal(cue.level, current_level)
            and cue.blend == current_blend
        ):
            continue
        result.append(cue)
        current_level = cue.level
        current_blend = cue.blend
    return result


def lane_level_at(
    lane: TimelineLane,
    t_sec: float,
    *,
    inherit: float,
) -> float:
    """Stepped level at ``t_sec``. If ``baseline`` is None, use ``inherit`` until the first cue."""
    level = inherit if lane.baseline is None else lane.baseline
    for cue in lane.cues:
        if cue.t > t_sec:
            break
        level = cue.level
    return level


def lane_blend_at(lane: TimelineLane, t_sec: float) -> BlendMode | None:
    """Held blend at ``t_sec``: last cue's ``blend`` at or before ``t``.

    ``None`` means inherit the layer's static ``blend_mode``. A later cue may
    set ``blend`` back to ``None`` to revert.
    """
    blend: BlendMode | None = None
    for cue in lane.cues:
        if cue.t > t_sec:
            break
        blend = cue.blend
    return blend


def lane_role_at(lane: TimelineLane, t_sec: float) -> CueRole | None:
    """Held role at ``t_sec``: last cue's ``role`` at or before ``t``.

    ``None`` means no cast (limiter treats unset as ``pulse``). A later cue may
    set ``role`` back to ``None`` to clear.
    """
    role: CueRole | None = None
    for cue in lane.cues:
        if cue.t > t_sec:
            break
        role = cue.role
    return role


def lane_level_segments(
    lane: TimelineLane,
    duration_sec: float,
    *,
    inherit: float,
) -> list[tuple[float, float, float]]:
    """Return ``(start_t, end_t, level)`` segments over ``[0, duration_sec]``."""
    if duration_sec <= 0:
        return []
    boundaries = sorted({0.0, duration_sec} | {cue.t for cue in lane.cues})
    segments: list[tuple[float, float, float]] = []
    for index in range(len(boundaries) - 1):
        start_t = boundaries[index]
        end_t = boundaries[index + 1]
        if end_t <= start_t:
            continue
        if end_t <= 0.0 or start_t >= duration_sec:
            continue
        clip_start = max(start_t, 0.0)
        clip_end = min(end_t, duration_sec)
        if clip_end <= clip_start:
            continue
        level = lane_level_at(lane, clip_start, inherit=inherit)
        segments.append((clip_start, clip_end, level))
    return segments


@dataclass(frozen=True)
class TimelineFadeGroup:
    """Per-edge fade settings for song-marker or standard cue boundaries."""

    enabled: bool = False
    fade_in: float = 2.0
    fade_out: float = 2.0


def _matches_song_marker(t: float, markers: Sequence[float]) -> bool:
    return any(abs(marker - t) <= SONG_MARKER_FADE_MATCH_EPS for marker in markers)


def _fade_group_for_edge(
    t: float,
    *,
    song_marker_times: Sequence[float],
    song_marker_fades: TimelineFadeGroup,
    standard_fades: TimelineFadeGroup,
) -> TimelineFadeGroup:
    if _matches_song_marker(t, song_marker_times):
        return song_marker_fades
    return standard_fades


def _append_breakpoint(
    breakpoints: list[tuple[float, float]],
    t: float,
    level: float,
) -> None:
    if breakpoints and t < breakpoints[-1][0]:
        t = breakpoints[-1][0]
    if (
        breakpoints
        and breakpoints[-1][0] == t
        and levels_equal(breakpoints[-1][1], level)
    ):
        return
    breakpoints.append((float(t), float(level)))


def lane_level_breakpoints(
    lane: TimelineLane,
    *,
    inherit: float,
    song_marker_fades: TimelineFadeGroup,
    standard_fades: TimelineFadeGroup,
    duration_sec: float,
    song_marker_times: Sequence[float] = (),
) -> list[tuple[float, float]]:
    """Build a monotone ``(t, level)`` polyline for the lane envelope.

    For a transition at ``t`` from level ``a`` to ``b``, fade durations act as
    slopes: a full-scale move takes the configured duration. Rise completes at
    the cue time; fall starts at the cue time. Disabled groups or zero duration
    collapse to a hard step. Overlapping rise starts clamp forward.
    """
    if duration_sec <= 0.0:
        return []
    level = inherit if lane.baseline is None else float(lane.baseline)
    if not lane.cues:
        return [(0.0, float(level))]

    breakpoints: list[tuple[float, float]] = []
    previous = float(level)
    for cue in lane.cues:
        a = previous
        b = float(cue.level)
        t = float(cue.t)
        previous = b
        if levels_equal(a, b):
            continue
        group = _fade_group_for_edge(
            t,
            song_marker_times=song_marker_times,
            song_marker_fades=song_marker_fades,
            standard_fades=standard_fades,
        )
        if b > a:
            delta = b - a
            fade_in = max(0.0, float(group.fade_in)) if group.enabled else 0.0
            ramp = fade_in * delta
            if ramp <= 0.0:
                _append_breakpoint(breakpoints, t, a)
                _append_breakpoint(breakpoints, t, b)
                continue
            t_start = t - ramp
            if breakpoints and t_start < breakpoints[-1][0]:
                t_start = breakpoints[-1][0]
            if t_start >= t:
                _append_breakpoint(breakpoints, t, a)
                _append_breakpoint(breakpoints, t, b)
            else:
                _append_breakpoint(breakpoints, t_start, a)
                _append_breakpoint(breakpoints, t, b)
        else:
            delta = a - b
            fade_out = max(0.0, float(group.fade_out)) if group.enabled else 0.0
            ramp = fade_out * delta
            if ramp <= 0.0:
                _append_breakpoint(breakpoints, t, a)
                _append_breakpoint(breakpoints, t, b)
                continue
            _append_breakpoint(breakpoints, t, a)
            _append_breakpoint(breakpoints, t + ramp, b)

    if not breakpoints:
        return [(0.0, float(level))]
    return breakpoints


def lane_level_envelope(
    t_sec: float,
    breakpoints: Sequence[tuple[float, float]],
) -> float:
    """Interpolate level at ``t_sec`` along breakpoints with smoothstep easing."""
    if not breakpoints:
        return 0.0
    if t_sec < breakpoints[0][0]:
        return float(breakpoints[0][1])
    if t_sec > breakpoints[-1][0]:
        return float(breakpoints[-1][1])
    for index in range(len(breakpoints) - 1):
        t0, v0 = breakpoints[index]
        t1, v1 = breakpoints[index + 1]
        # Half-open [t0, t1) so a hard step at t1 wins over the prior segment end.
        if t_sec >= t1:
            continue
        if t1 <= t0:
            # Hard step: settle to the last value at this instant.
            last = index + 1
            while (
                last + 1 < len(breakpoints)
                and breakpoints[last + 1][0] <= t0
            ):
                last += 1
            return float(breakpoints[last][1])
        u = (t_sec - t0) / (t1 - t0)
        return float(v0 + (v1 - v0) * smoothstep(u))
    return float(breakpoints[-1][1])


def lane_tick_times(lane: TimelineLane, duration_sec: float) -> list[float]:
    """Cue times within ``[0, duration_sec]`` (every stored cue is a real transition)."""
    return sorted(
        cue.t for cue in lane.cues if 0.0 <= cue.t <= duration_sec
    )


def lane_on_transition_cues(
    lane: TimelineLane,
    *,
    song_marker_times: Sequence[float] = (),
    song_marker_fades: TimelineFadeGroup,
    standard_fades: TimelineFadeGroup,
) -> list[tuple[float, SlotCue]]:
    """Preset-switch ``(trigger_t, cue)`` pairs for each rise from zero.

    Fires when ``previous <= LEVEL_EPS < cue.level``, with ``previous`` from
    ``baseline`` or ``0.0`` when baseline is None. Trigger is
    ``cue.t - fade_in * cue.level`` using the song-marker vs standard fade
    group for that edge. When the matching group is disabled or ``fade_in`` is
    0, the trigger is ``cue.t``.
    """
    results: list[tuple[float, SlotCue]] = []
    previous = 0.0 if lane.baseline is None else float(lane.baseline)
    for cue in lane.cues:
        if previous <= LEVEL_EPS < cue.level:
            group = _fade_group_for_edge(
                cue.t,
                song_marker_times=song_marker_times,
                song_marker_fades=song_marker_fades,
                standard_fades=standard_fades,
            )
            if not group.enabled or group.fade_in <= 0.0:
                ramp = 0.0
            else:
                ramp = max(0.0, float(group.fade_in)) * float(cue.level)
            results.append((cue.t - ramp, cue))
        previous = float(cue.level)
    return results


def lane_on_transition_trigger_times(
    lane: TimelineLane,
    *,
    song_marker_times: Sequence[float] = (),
    song_marker_fades: TimelineFadeGroup,
    standard_fades: TimelineFadeGroup,
) -> list[float]:
    """Preset-switch trigger times for each rise from zero."""
    return [
        trigger
        for trigger, _cue in lane_on_transition_cues(
            lane,
            song_marker_times=song_marker_times,
            song_marker_fades=song_marker_fades,
            standard_fades=standard_fades,
        )
    ]


def lane_on_transition_count(
    lane: TimelineLane,
    t_sec: float,
    *,
    song_marker_times: Sequence[float] = (),
    song_marker_fades: TimelineFadeGroup,
    standard_fades: TimelineFadeGroup,
) -> int:
    """Number of on-transition triggers at or before ``t_sec`` (seek-stable)."""
    return sum(
        1
        for trigger in lane_on_transition_trigger_times(
            lane,
            song_marker_times=song_marker_times,
            song_marker_fades=song_marker_fades,
            standard_fades=standard_fades,
        )
        if trigger <= t_sec
    )


def punch_lane(
    lane: TimelineLane,
    start_sec: float,
    stop_sec: float,
    new_cues: Sequence[SlotCue],
) -> TimelineLane:
    """Overwrite cues in ``[start_sec, stop_sec]`` with ``new_cues``; canonicalize."""
    kept = [
        cue for cue in lane.cues if not (start_sec <= cue.t <= stop_sec)
    ]
    return TimelineLane(
        baseline=lane.baseline,
        cues=canonicalize(lane.baseline, kept + list(new_cues)),
    )


def strip_lane_range(
    lane: TimelineLane,
    start_sec: float,
    stop_sec: float,
) -> TimelineLane:
    """Remove cues with ``t`` in ``[start_sec, stop_sec]``; canonicalize."""
    kept = [
        cue for cue in lane.cues if not (start_sec <= cue.t <= stop_sec)
    ]
    return TimelineLane(
        baseline=lane.baseline,
        cues=canonicalize(lane.baseline, kept),
    )


def set_lane_cue(
    lane: TimelineLane,
    t: float,
    level: float,
) -> TimelineLane:
    """Set or replace the transition at ``t``; canonicalize.

    Replacing an existing cue keeps its ``blend`` and ``role``.
    """
    others = [cue for cue in lane.cues if cue.t != t]
    existing = next((cue for cue in lane.cues if cue.t == t), None)
    if existing is not None:
        new_cue = replace(existing, level=level)
    else:
        new_cue = SlotCue(t=t, level=level)
    return TimelineLane(
        baseline=lane.baseline,
        cues=canonicalize(lane.baseline, others + [new_cue]),
    )


def update_lane_cue(
    lane: TimelineLane,
    cue_t: float,
    *,
    blend: BlendMode | None,
    role: CueRole | None,
) -> TimelineLane:
    """Update ``blend`` / ``role`` on the cue at ``cue_t`` without changing level."""
    updated = [
        replace(cue, blend=blend, role=role) if cue.t == cue_t else cue
        for cue in lane.cues
    ]
    return TimelineLane(
        baseline=lane.baseline,
        cues=canonicalize(lane.baseline, updated),
    )


def should_accept_toggle(last_toggle_t: float | None, t_sec: float) -> bool:
    if last_toggle_t is None:
        return True
    return t_sec - last_toggle_t >= RECORD_DEBOUNCE_SEC


def _nearest_with_earlier_tie(t: float, candidates: Sequence[float]) -> float:
    return min(candidates, key=lambda c: (abs(c - t), c))


def _nearest_beat_index(t: float, beats: np.ndarray) -> int:
    last = len(beats) - 1
    idx = int(np.searchsorted(beats, float(t)))
    candidates: list[int] = []
    if idx > 0:
        candidates.append(idx - 1)
    if idx <= last:
        candidates.append(idx)
    return min(
        candidates,
        key=lambda i: (abs(float(beats[i]) - float(t)), float(beats[i])),
    )


def snap_time_to_grid(t: float, grid: Sequence[float]) -> float:
    """Nearest grid time (earlier on a tie). Empty grid returns ``t`` unchanged."""
    if not grid:
        return float(t)
    beats = np.asarray(grid, dtype=np.float64)
    return float(beats[_nearest_beat_index(float(t), beats)])


def snap_placement_time(
    t: float,
    mode: str,
    *,
    beat_times: Sequence[float] = (),
    bar_times: Sequence[float] = (),
) -> float:
    """Snap authoring time for ``timeline.placement_snap`` mode."""
    if mode == "beat":
        return snap_time_to_grid(t, beat_times)
    if mode == "bar":
        return snap_time_to_grid(t, bar_times)
    return float(t)


def shift_bars_by_beats(
    downbeat_times: Sequence[float],
    beat_times: Sequence[float],
    offset: int,
) -> tuple[float, ...]:
    """Map each downbeat to the beat ``offset`` positions away (clamped).

    Each downbeat is matched to the nearest beat (earlier on a tie), then the
    beat index is shifted by ``offset`` and clamped to the beat grid.
    """
    if not downbeat_times or not beat_times:
        return ()
    beats = np.asarray(beat_times, dtype=np.float64)
    last = len(beats) - 1
    result: list[float] = []
    for t in downbeat_times:
        nearest = _nearest_beat_index(float(t), beats)
        shifted = max(0, min(last, nearest + offset))
        result.append(float(beats[shifted]))
    return tuple(result)


def shift_lane_cues_by_beats(
    lane: TimelineLane,
    beat_times: Sequence[float],
    delta: int,
) -> TimelineLane:
    """Map each cue to the nearest beat, move by ``delta`` indices, canonicalize."""
    if not lane.cues or not beat_times or delta == 0:
        return TimelineLane(baseline=lane.baseline, cues=list(lane.cues))

    beats = np.asarray(beat_times, dtype=np.float64)
    last = len(beats) - 1
    shifted = [
        replace(
            cue,
            t=float(
                beats[max(0, min(last, _nearest_beat_index(cue.t, beats) + delta))]
            ),
        )
        for cue in lane.cues
    ]
    return TimelineLane(
        baseline=lane.baseline,
        cues=canonicalize(lane.baseline, shifted),
    )


def snap_lane_to_beats(
    lane: TimelineLane,
    beat_times: Sequence[float],
) -> TimelineLane:
    """Rewrite cue times to the nearest beat; canonicalize collisions."""
    if not lane.cues or not beat_times:
        return TimelineLane(baseline=lane.baseline, cues=list(lane.cues))

    beats = np.asarray(beat_times, dtype=np.float64)
    if beats.size == 1:
        sole = float(beats[0])
        snapped = [replace(cue, t=sole) for cue in lane.cues]
        return TimelineLane(
            baseline=lane.baseline,
            cues=canonicalize(lane.baseline, snapped),
        )

    first = float(beats[0])
    last = float(beats[-1])
    interval = float(np.median(np.diff(beats)))

    def snap_t(t: float) -> float:
        if first <= t <= last:
            idx = int(np.searchsorted(beats, t))
            candidates: list[float] = []
            if idx > 0:
                candidates.append(float(beats[idx - 1]))
            if idx < len(beats):
                candidates.append(float(beats[idx]))
            return _nearest_with_earlier_tie(t, candidates)
        raw = (t - first) / interval
        lo = int(np.floor(raw))
        return _nearest_with_earlier_tie(
            t,
            (first + lo * interval, first + (lo + 1) * interval),
        )

    snapped = [replace(cue, t=snap_t(cue.t)) for cue in lane.cues]
    return TimelineLane(
        baseline=lane.baseline,
        cues=canonicalize(lane.baseline, snapped),
    )


SongMarkerSnapMode = Literal["each_layer", "closest_wins"]


def snap_lanes_to_song_markers(
    lanes: Mapping[str, TimelineLane],
    song_marker_times: Sequence[float],
    *,
    proximity: float,
    layer_z_order: Sequence[str],
    slots: Sequence[str],
    mode: SongMarkerSnapMode = "each_layer",
) -> tuple[dict[str, TimelineLane], int]:
    """Move closest cues within ``proximity`` onto song markers; exclusive claims.

    Markers are processed in ascending time. Each cue moves at most once.
    ``each_layer`` claims per lane; ``closest_wins`` shares one claim set across
    ``slots`` (tie: earlier cue time, then earlier ``layer_z_order`` index).

    Returns updated lanes for ``slots`` (other keys unchanged) and move count.
    """
    result = {slot: copy_lane(lane) for slot, lane in lanes.items()}
    if proximity <= 0 or not song_marker_times or not slots:
        return result, 0

    markers = sorted(float(t) for t in song_marker_times)
    target_slots = [slot for slot in slots if slot]
    if not target_slots:
        return result, 0

    for slot in target_slots:
        if slot not in result:
            result[slot] = empty_lane()

    working: dict[str, list[SlotCue]] = {
        slot: list(result[slot].cues) for slot in target_slots
    }
    moved = 0

    if mode == "each_layer":
        for slot in target_slots:
            claimed: set[int] = set()
            cues = working[slot]
            for marker in markers:
                best_i: int | None = None
                best_key: tuple[float, float] | None = None
                for i, cue in enumerate(cues):
                    if i in claimed:
                        continue
                    dist = abs(cue.t - marker)
                    if dist > proximity:
                        continue
                    key = (dist, cue.t)
                    if best_key is None or key < best_key:
                        best_i = i
                        best_key = key
                if best_i is None:
                    continue
                old = cues[best_i]
                cues[best_i] = replace(old, t=marker)
                claimed.add(best_i)
                moved += 1
    else:
        z_index = {slot: i for i, slot in enumerate(layer_z_order)}
        claimed_pairs: set[tuple[str, int]] = set()
        for marker in markers:
            best: tuple[float, float, int, str, int] | None = None
            for slot in target_slots:
                cues = working[slot]
                for i, cue in enumerate(cues):
                    if (slot, i) in claimed_pairs:
                        continue
                    dist = abs(cue.t - marker)
                    if dist > proximity:
                        continue
                    key = (dist, cue.t, z_index.get(slot, len(layer_z_order)), slot, i)
                    if best is None or key < best:
                        best = key
            if best is None:
                continue
            _dist, _t, _z, slot, cue_i = best
            old = working[slot][cue_i]
            working[slot][cue_i] = replace(old, t=marker)
            claimed_pairs.add((slot, cue_i))
            moved += 1

    for slot in target_slots:
        baseline = result[slot].baseline
        result[slot] = TimelineLane(
            baseline=baseline,
            cues=canonicalize(baseline, working[slot]),
        )
    return result, moved
