"""Per-lane timeline evaluation and editing for layer levels."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np

from cleave.blend_modes import BlendMode
from cleave.cue_roles import CueRole
from cleave.cut_types import CutType
from cleave.easing import smoothstep
from cleave.stems import STEM_SOURCES, StemSource

RECORD_DEBOUNCE_SEC = 0.08
# Epsilon for apply-cut scoping against song marker times (not fade selection).
SONG_MARKER_CUT_MATCH_EPS = 1e-3
LEVEL_QUANTUM = 0.25
# Manual strip nudges (percent of full); generative Apply still uses LEVEL_QUANTUM.
LEVEL_STEP_SMALL = 0.01
LEVEL_STEP_LARGE = 0.10
LEVEL_EDIT_MIN = 0.10
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
    cut: CutType | None = None
    anchor: bool = False
    recast: bool = False


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
    """True when ``cue`` may carry blend/role (on cues only).

    Off cues (``level <= LEVEL_EPS``) are level transitions; cast and blend are
    authored on the next on / visible period. Cut may still be set on offs.
    """
    return float(cue.level) > LEVEL_EPS


def opening_baseline_editable(lane: TimelineLane) -> bool:
    """True when the opening period is on via ``baseline`` with no cue at ``t=0``.

    Generative Apply stores the first on-level in ``baseline``, so there is no
    stored cue to select for cast/blend until one is materialized at ``0.0``.
    """
    return (
        lane.baseline is not None
        and float(lane.baseline) > LEVEL_EPS
        and not any(cue.t == 0.0 for cue in lane.cues)
    )


def opening_cue(lane: TimelineLane) -> SlotCue | None:
    """Synthetic on-cue at ``t=0`` for an editable opening baseline, else None."""
    if not opening_baseline_editable(lane):
        return None
    return SlotCue(t=0.0, level=float(lane.baseline))


def canonicalize(
    baseline: float | None,
    cues: Sequence[SlotCue],
) -> list[SlotCue]:
    """Drop redundant/no-op transitions; last-wins at equal ``t``.

    Returns strictly increasing ``t`` cues where each changes level and/or
    blend from the previous state (``baseline`` with blend inherit ``None``,
    or the prior cue when baseline is None). Role and cut are not part of the
    comparison. Same-level ``anchor`` and ``recast`` cues are kept. Off cues
    (``level <= LEVEL_EPS``) always have ``blend`` and ``role`` cleared before
    compare and emit; ``cut`` is preserved.
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
            and not cue.anchor
            and not cue.recast
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
    """Per-edge fade settings for hard-cut or soft-cut cue boundaries."""

    enabled: bool = False
    fade_in: float = 2.0
    fade_out: float = 2.0
    crossfade: bool = False


def matches_song_marker(
    t: float,
    markers: Sequence[float],
    *,
    eps: float = SONG_MARKER_CUT_MATCH_EPS,
) -> bool:
    """True when ``t`` is within ``eps`` of any song marker time."""
    return any(abs(marker - t) <= eps for marker in markers)


def _fade_group_for_edge(
    cue: SlotCue,
    *,
    hard_cut_fades: TimelineFadeGroup,
    soft_cut_fades: TimelineFadeGroup,
) -> TimelineFadeGroup | None:
    """Select fade group from ``cue.cut``; ``none`` / unset means a hard step."""
    if cue.cut == "hard":
        return hard_cut_fades
    if cue.cut == "soft":
        return soft_cut_fades
    return None


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
    hard_cut_fades: TimelineFadeGroup,
    soft_cut_fades: TimelineFadeGroup,
    duration_sec: float,
) -> list[tuple[float, float]]:
    """Build a monotone ``(t, level)`` polyline for the lane envelope.

    For a transition at ``t`` from level ``a`` to ``b``, fade durations act as
    slopes: a full-scale move takes the configured duration. By default, rise
    completes at the cue time and fall starts at the cue time. With
    ``crossfade`` enabled on the fade group, rise and fall ramps are centered on
    the cue time (``t - ramp/2`` through ``t + ramp/2``). Cut type ``none`` /
    unset, disabled groups, or zero duration collapse to a hard step. Each cue's
    cut controls its own edge (rise or fall). Overlapping rise starts clamp
    forward.
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
        if levels_equal(a, b):
            previous = b
            continue
        group = _fade_group_for_edge(
            cue,
            hard_cut_fades=hard_cut_fades,
            soft_cut_fades=soft_cut_fades,
        )
        if b > a:
            delta = b - a
            fade_in = (
                max(0.0, float(group.fade_in))
                if group is not None and group.enabled
                else 0.0
            )
            ramp = fade_in * delta
            if ramp <= 0.0:
                _append_breakpoint(breakpoints, t, a)
                _append_breakpoint(breakpoints, t, b)
            elif group is not None and group.crossfade:
                half = ramp / 2.0
                t_start = t - half
                t_end = t + half
                if breakpoints and t_start < breakpoints[-1][0]:
                    t_start = breakpoints[-1][0]
                if t_start >= t_end:
                    _append_breakpoint(breakpoints, t, a)
                    _append_breakpoint(breakpoints, t, b)
                else:
                    _append_breakpoint(breakpoints, t_start, a)
                    _append_breakpoint(breakpoints, t_end, b)
            else:
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
            fade_out = (
                max(0.0, float(group.fade_out))
                if group is not None and group.enabled
                else 0.0
            )
            ramp = fade_out * delta
            if ramp <= 0.0:
                _append_breakpoint(breakpoints, t, a)
                _append_breakpoint(breakpoints, t, b)
            elif group is not None and group.crossfade:
                half = ramp / 2.0
                t_start = t - half
                t_end = t + half
                if breakpoints and t_start < breakpoints[-1][0]:
                    t_start = breakpoints[-1][0]
                if t_start >= t_end:
                    _append_breakpoint(breakpoints, t, a)
                    _append_breakpoint(breakpoints, t, b)
                else:
                    _append_breakpoint(breakpoints, t_start, a)
                    _append_breakpoint(breakpoints, t_end, b)
            else:
                _append_breakpoint(breakpoints, t, a)
                _append_breakpoint(breakpoints, t + ramp, b)
        previous = b

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
    hard_cut_fades: TimelineFadeGroup,
    soft_cut_fades: TimelineFadeGroup,
) -> list[tuple[float, SlotCue]]:
    """Preset-switch ``(trigger_t, cue)`` pairs for rises and recasts.

    Fires when ``previous <= LEVEL_EPS < cue.level``, with ``previous`` from
    ``baseline`` or ``0.0`` when baseline is None. Also fires when
    ``cue.recast`` and the slot is already on (``previous > LEVEL_EPS`` and
    ``cue.level > LEVEL_EPS``). A same-level ``anchor`` hold does not fire.
    Trigger is ``cue.t - ramp`` using the on-cue's cut type to select the fade
    group, where ``ramp`` is ``fade_in * cue.level``. With ``crossfade``
    enabled, trigger is ``cue.t - ramp/2`` (visual onset). When cut is
    ``none`` / unset, the group is disabled, or ``fade_in`` is 0, the trigger
    is ``cue.t``.
    """
    results: list[tuple[float, SlotCue]] = []
    previous = 0.0 if lane.baseline is None else float(lane.baseline)
    for cue in lane.cues:
        rise = previous <= LEVEL_EPS < cue.level
        recast_on = (
            cue.recast and previous > LEVEL_EPS and cue.level > LEVEL_EPS
        )
        if rise or recast_on:
            group = _fade_group_for_edge(
                cue,
                hard_cut_fades=hard_cut_fades,
                soft_cut_fades=soft_cut_fades,
            )
            if group is None or not group.enabled or group.fade_in <= 0.0:
                ramp = 0.0
            else:
                ramp = max(0.0, float(group.fade_in)) * float(cue.level)
                if group.crossfade:
                    ramp /= 2.0
            results.append((cue.t - ramp, cue))
        previous = float(cue.level)
    return results


def lane_on_transition_trigger_times(
    lane: TimelineLane,
    *,
    hard_cut_fades: TimelineFadeGroup,
    soft_cut_fades: TimelineFadeGroup,
) -> list[float]:
    """Preset-switch trigger times for each rise from zero or on-recast."""
    return [
        trigger
        for trigger, _cue in lane_on_transition_cues(
            lane,
            hard_cut_fades=hard_cut_fades,
            soft_cut_fades=soft_cut_fades,
        )
    ]


def lane_on_transition_count(
    lane: TimelineLane,
    t_sec: float,
    *,
    hard_cut_fades: TimelineFadeGroup,
    soft_cut_fades: TimelineFadeGroup,
) -> int:
    """Number of on-transition triggers at or before ``t_sec`` (seek-stable)."""
    return sum(
        1
        for trigger in lane_on_transition_trigger_times(
            lane,
            hard_cut_fades=hard_cut_fades,
            soft_cut_fades=soft_cut_fades,
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


def update_lane_cue(
    lane: TimelineLane,
    cue_t: float,
    *,
    blend: BlendMode | None,
    role: CueRole | None,
    level: float | None = None,
    cut: CutType | None = None,
) -> TimelineLane:
    """Update ``blend`` / ``role`` / ``cut`` / optional ``level`` on the cue at ``cue_t``.

    When ``cue_t`` is ``0.0`` and the opening period is only a baseline on-level:
    level-only edits (``blend`` and ``role`` both ``None``, and ``cut`` unset or
    ``none``) update ``baseline`` in place; otherwise materialize a real cue at
    ``0.0`` (baseline becomes ``0.0``) so cast/blend/cut persist and
    preset-switch rises can read the role.
    """
    cut_needs_cue = cut is not None and cut != "none"
    if cue_t == 0.0 and opening_baseline_editable(lane):
        new_level = (
            float(lane.baseline) if level is None else clamp_level(level)
        )
        if blend is None and role is None and not cut_needs_cue:
            if level is None:
                return copy_lane(lane)
            baseline = 0.0 if new_level <= LEVEL_EPS else new_level
            return TimelineLane(
                baseline=baseline,
                cues=canonicalize(baseline, list(lane.cues)),
            )
        return TimelineLane(
            baseline=0.0,
            cues=canonicalize(
                0.0,
                [
                    SlotCue(
                        t=0.0,
                        level=new_level,
                        blend=blend,
                        role=role,
                        cut=cut,
                    ),
                    *lane.cues,
                ],
            ),
        )
    updated: list[SlotCue] = []
    for cue in lane.cues:
        if cue.t != cue_t:
            updated.append(cue)
            continue
        new_level = cue.level if level is None else clamp_level(level)
        updated.append(
            replace(cue, level=new_level, blend=blend, role=role, cut=cut)
        )
    return TimelineLane(
        baseline=lane.baseline,
        cues=canonicalize(lane.baseline, updated),
    )


def lane_last_on_level(lane: TimelineLane, t_sec: float) -> float:
    """The on level a new on cue at ``t_sec`` should take.

    The latest on cue at or before ``t_sec``, else an on ``baseline``, else
    the first on cue after it, else full.
    """
    level: float | None = (
        float(lane.baseline)
        if lane.baseline is not None and float(lane.baseline) > LEVEL_EPS
        else None
    )
    for cue in lane.cues:
        if cue.t > t_sec:
            break
        if float(cue.level) > LEVEL_EPS:
            level = float(cue.level)
    if level is not None:
        return level
    later = next(
        (float(cue.level) for cue in lane.cues if float(cue.level) > LEVEL_EPS),
        None,
    )
    return later if later is not None else 1.0


MIN_CLIP_SEC = 0.1
ClipEdge = Literal["start", "end"]
# What a pointer press on a clip edge grabs. ``"start"`` and ``"end"`` trim
# that edge of the named clip, leaving a gap at a boundary it shared with a
# butted neighbour. ``"roll"`` moves a shared boundary (named by the earlier
# clip), so both clips change.
ClipGrip = Literal["start", "end", "roll"]


@dataclass(frozen=True)
class TimelineClip:
    """One visible span of a lane: an on cue up to the next cue or the song end.

    ``cut_in`` is the start cue's cut. ``cut_out`` is the cut of the off cue
    that ends the clip, and stays ``None`` without one (``has_end_cue``
    False): the clip butts the next one (``butts_next``) or runs to the song
    end. ``recast`` and ``anchor`` are the start cue's flags.
    """

    start: float
    end: float
    level: float
    blend: BlendMode | None = None
    role: CueRole | None = None
    cut_in: CutType | None = None
    cut_out: CutType | None = None
    butts_next: bool = False
    has_end_cue: bool = False
    recast: bool = False
    anchor: bool = False


def fold_lane_baseline(lane: TimelineLane, inherit: float) -> TimelineLane:
    """Freeze ``inherit`` into an explicit baseline when the lane has none."""
    if lane.baseline is not None:
        return copy_lane(lane)
    return TimelineLane(baseline=inherit, cues=canonicalize(inherit, lane.cues))


def lane_clips(
    lane: TimelineLane,
    *,
    inherit: float,
    duration_sec: float,
) -> list[TimelineClip]:
    """The lane's clips in time order; every span outside them is off.

    An opening period that is on (by ``baseline``, or ``inherit`` when the
    baseline is None) is a clip from ``0.0``. The last clip ends at
    ``duration_sec``. An on cue right after another on cue starts a new clip
    that butts the one before.
    """
    if duration_sec <= 0.0:
        return []
    opening = float(inherit if lane.baseline is None else lane.baseline)
    points = [cue for cue in lane.cues if cue.t < duration_sec]
    if opening > LEVEL_EPS and not (points and points[0].t <= 0.0):
        points.insert(0, SlotCue(t=0.0, level=opening))
    clips: list[TimelineClip] = []
    for index, cue in enumerate(points):
        if float(cue.level) <= LEVEL_EPS:
            continue
        following = points[index + 1] if index + 1 < len(points) else None
        butts_next = following is not None and float(following.level) > LEVEL_EPS
        has_end_cue = following is not None and not butts_next
        clips.append(
            TimelineClip(
                start=cue.t,
                end=duration_sec if following is None else following.t,
                level=float(cue.level),
                blend=cue.blend,
                role=cue.role,
                cut_in=cue.cut,
                cut_out=following.cut if has_end_cue else None,
                butts_next=butts_next,
                has_end_cue=has_end_cue,
                recast=cue.recast,
                anchor=cue.anchor,
            )
        )
    return clips


def clip_at(clips: Sequence[TimelineClip], t_sec: float) -> TimelineClip | None:
    """The clip covering ``t_sec`` (start inclusive, end exclusive)."""
    return next((clip for clip in clips if clip.start <= t_sec < clip.end), None)


def clip_starting_at(
    clips: Sequence[TimelineClip], start: float
) -> TimelineClip | None:
    return next((clip for clip in clips if clip.start == start), None)


def _clip_neighbours(
    clips: Sequence[TimelineClip], clip: TimelineClip
) -> tuple[TimelineClip | None, TimelineClip | None]:
    previous = next(
        (other for other in reversed(clips) if other.start < clip.start), None
    )
    following = next((other for other in clips if other.start > clip.start), None)
    return previous, following


def clip_move_bounds(
    clips: Sequence[TimelineClip],
    clip: TimelineClip,
    duration_sec: float,
) -> tuple[float, float]:
    """Earliest and latest start for ``clip`` moved at its length between its neighbours."""
    previous, following = _clip_neighbours(clips, clip)
    low = 0.0 if previous is None else previous.end
    limit = duration_sec if following is None else following.start
    high = limit - (clip.end - clip.start)
    return (low, max(low, high))


def clip_trim_bounds(
    clips: Sequence[TimelineClip],
    clip: TimelineClip,
    edge: ClipEdge,
    min_len: float,
    duration_sec: float,
    *,
    roll: bool = True,
) -> tuple[float, float]:
    """Range one edge of ``clip`` may move in, leaving each clip ``min_len``.

    An edge shared with a butted neighbour rolls, so the neighbour keeps
    ``min_len`` too; with ``roll`` False it trims away from the neighbour
    and may only move into ``clip``. A free edge stops at the neighbour or
    the song bounds. A clip already shorter than ``min_len`` keeps its edge
    where it is.
    """
    previous, following = _clip_neighbours(clips, clip)
    if edge == "start":
        current = clip.start
        if previous is None:
            low = 0.0
        elif previous.end == clip.start:
            low = previous.start + min_len if roll else clip.start
        else:
            low = previous.end
        high = clip.end - min_len
    else:
        current = clip.end
        low = clip.start + min_len
        if following is None:
            high = duration_sec
        elif clip.butts_next:
            high = following.end - min_len if roll else clip.end
        else:
            high = following.start
    low = min(low, current)
    high = max(high, current)
    return (low, high)


def _explicit_cues(lane: TimelineLane, inherit: float) -> list[SlotCue]:
    """The lane's cues over an off baseline, with an on opening as a cue at ``0.0``."""
    folded = fold_lane_baseline(lane, inherit)
    cues = list(folded.cues)
    opening = float(folded.baseline or 0.0)
    if opening > LEVEL_EPS and not any(cue.t == 0.0 for cue in cues):
        cues.insert(0, SlotCue(t=0.0, level=opening))
    return cues


def _lane_from_cues(cues: Sequence[SlotCue], duration_sec: float) -> TimelineLane:
    """Canonical lane over an off baseline that keeps butted clips apart.

    An on cue that matches the on state before it would merge into it, so it
    becomes an ``anchor`` (the same preset carries on). Cues at or past the
    song end are dropped.
    """
    ordered = sorted(
        (cue for cue in cues if cue.t < duration_sec), key=lambda cue: cue.t
    )
    kept: list[SlotCue] = []
    level = 0.0
    blend: BlendMode | None = None
    for cue in ordered:
        if (
            float(cue.level) > LEVEL_EPS
            and level > LEVEL_EPS
            and levels_equal(cue.level, level)
            and cue.blend == blend
            and not cue.recast
        ):
            cue = replace(cue, anchor=True)
        kept.append(cue)
        level = float(cue.level)
        blend = cue.blend if level > LEVEL_EPS else None
    return TimelineLane(baseline=0.0, cues=canonicalize(0.0, kept))


def _without(cues: Sequence[SlotCue], *times: float) -> list[SlotCue]:
    return [cue for cue in cues if cue.t not in times]


def _level_before(cues: Sequence[SlotCue], t_sec: float) -> float:
    level = 0.0
    for cue in cues:
        if cue.t >= t_sec:
            break
        level = float(cue.level)
    return level


def _stored_clip(
    lane: TimelineLane,
    clip: TimelineClip,
    inherit: float,
    duration_sec: float,
) -> TimelineClip | None:
    """The lane's current clip at ``clip.start``, or None when it is gone."""
    return clip_starting_at(
        lane_clips(lane, inherit=inherit, duration_sec=duration_sec), clip.start
    )


def add_clip(
    lane: TimelineLane,
    start: float,
    end: float,
    level: float,
    *,
    inherit: float,
    duration_sec: float,
    blend: BlendMode | None = None,
    role: CueRole | None = None,
    cut_in: CutType | None = None,
    cut_out: CutType | None = None,
    recast: bool = False,
    anchor: bool = False,
) -> TimelineLane:
    """Add a clip over the off span ``[start, end)``.

    Writes an on cue at ``start`` and, unless the span runs into the next
    clip or the song end, an off cue at ``end`` carrying ``cut_out``.
    """
    cues = _explicit_cues(lane, inherit)
    on_cue = SlotCue(
        t=start,
        level=clamp_level(level),
        blend=blend,
        role=role,
        cut=cut_in,
        anchor=anchor,
        recast=recast,
    )
    at_end = next((cue for cue in cues if cue.t == end), None)
    kept = [cue for cue in cues if not (start <= cue.t < end)]
    if at_end is None or float(at_end.level) <= LEVEL_EPS:
        kept = _without(kept, end)
        kept.append(SlotCue(t=end, level=0.0, cut=cut_out))
    return _lane_from_cues([*kept, on_cue], duration_sec)


def remove_clip(
    lane: TimelineLane,
    clip: TimelineClip,
    *,
    inherit: float,
    duration_sec: float,
) -> TimelineLane:
    """Turn the clip's span off.

    Its start cue becomes an off cue, or goes when the span before it is
    already off. A butted next clip keeps its start cue.
    """
    cues = _explicit_cues(lane, inherit)
    kept = _without(cues, clip.start)
    if _level_before(cues, clip.start) > LEVEL_EPS:
        kept.append(SlotCue(t=clip.start, level=0.0))
    return _lane_from_cues(kept, duration_sec)


def move_clip(
    lane: TimelineLane,
    clip: TimelineClip,
    new_start: float,
    *,
    inherit: float,
    duration_sec: float,
) -> TimelineLane:
    """Move the clip to ``new_start`` at its length, keeping every property.

    The start is clamped between the neighbours (``clip_move_bounds``). The
    span it leaves turns off.
    """
    clips = lane_clips(lane, inherit=inherit, duration_sec=duration_sec)
    stored = clip_starting_at(clips, clip.start)
    if stored is None:
        return copy_lane(lane)
    low, high = clip_move_bounds(clips, stored, duration_sec)
    start = max(low, min(high, new_start))
    removed = remove_clip(lane, stored, inherit=inherit, duration_sec=duration_sec)
    return add_clip(
        removed,
        start,
        start + (stored.end - stored.start),
        stored.level,
        inherit=0.0,
        duration_sec=duration_sec,
        blend=stored.blend,
        role=stored.role,
        cut_in=stored.cut_in,
        cut_out=stored.cut_out,
        recast=stored.recast,
        anchor=stored.anchor,
    )


def trim_clip(
    lane: TimelineLane,
    clip: TimelineClip,
    edge: ClipEdge,
    t_sec: float,
    *,
    inherit: float,
    duration_sec: float,
    min_len: float = MIN_CLIP_SEC,
    roll: bool = True,
) -> TimelineLane:
    """Move one edge of the clip to ``t_sec``, clamped by ``clip_trim_bounds``.

    An edge shared with a butted neighbour moves the shared cue, so both
    clips change (a roll). With ``roll`` False that edge trims only this
    clip and opens a gap: the neighbour keeps its edge, through a new off
    cue. An end trimmed out to the song end drops its off cue; a clip that
    ran to the song end gains one when trimmed back.
    """
    clips = lane_clips(lane, inherit=inherit, duration_sec=duration_sec)
    stored = clip_starting_at(clips, clip.start)
    if stored is None:
        return copy_lane(lane)
    low, high = clip_trim_bounds(
        clips, stored, edge, min_len, duration_sec, roll=roll
    )
    target = max(low, min(high, t_sec))
    cues = _explicit_cues(lane, inherit)
    old_t = stored.start if edge == "start" else stored.end
    if not roll and target != old_t:
        previous, _ = _clip_neighbours(clips, stored)
        if edge == "end" and stored.butts_next:
            # The next clip keeps its start cue; this clip ends early.
            return _lane_from_cues(
                [*cues, SlotCue(t=target, level=0.0)], duration_sec
            )
        if edge == "start" and previous is not None and previous.end == old_t:
            # The earlier clip keeps its end through an off cue at the old start.
            moving = next(cue for cue in cues if cue.t == old_t)
            kept = _without(cues, old_t)
            kept += [SlotCue(t=old_t, level=0.0), replace(moving, t=target)]
            return _lane_from_cues(kept, duration_sec)
    moving = next((cue for cue in cues if cue.t == old_t), None)
    if moving is None:
        # The clip ran to the song end, so its end has no cue yet.
        moving = SlotCue(t=old_t, level=0.0)
    landing = next((cue for cue in cues if cue.t == target), None)
    kept = _without(cues, old_t, target)
    if (
        float(moving.level) <= LEVEL_EPS
        and landing is not None
        and float(landing.level) > LEVEL_EPS
    ):
        # The off cue reached the next clip's start: the clips now butt.
        kept.append(landing)
    else:
        kept.append(replace(moving, t=target))
    return _lane_from_cues(kept, duration_sec)


def split_clip(
    lane: TimelineLane,
    clip: TimelineClip,
    t_sec: float,
    *,
    inherit: float,
    duration_sec: float,
    min_len: float = MIN_CLIP_SEC,
) -> TimelineLane:
    """Split the clip in two at ``t_sec`` with the same look and no preset switch.

    Unchanged when either part would be shorter than ``min_len``.
    """
    stored = _stored_clip(lane, clip, inherit, duration_sec)
    if (
        stored is None
        or t_sec < stored.start + min_len
        or t_sec > stored.end - min_len
    ):
        return copy_lane(lane)
    cues = _explicit_cues(lane, inherit)
    cues.append(
        SlotCue(
            t=t_sec,
            level=stored.level,
            blend=stored.blend,
            role=stored.role,
            anchor=True,
        )
    )
    return _lane_from_cues(cues, duration_sec)


def update_clip(
    lane: TimelineLane,
    clip: TimelineClip,
    *,
    inherit: float,
) -> TimelineLane:
    """Write ``clip``'s level, blend, role, and cuts to the clip at ``clip.start``.

    Level, blend, role, and cut-in go on the start cue (``update_lane_cue``).
    Cut-out goes on the off cue at ``clip.end``; a clip without one
    (``has_end_cue`` False) ignores it.
    """
    updated = update_lane_cue(
        fold_lane_baseline(lane, inherit),
        clip.start,
        blend=clip.blend,
        role=clip.role,
        level=clip.level,
        cut=clip.cut_in,
    )
    if not clip.has_end_cue:
        return updated
    return TimelineLane(
        baseline=updated.baseline,
        cues=[
            replace(cue, cut=clip.cut_out)
            if cue.t == clip.end and float(cue.level) <= LEVEL_EPS
            else cue
            for cue in updated.cues
        ],
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


def _median_beat_interval(beats: np.ndarray) -> float:
    if beats.size < 2:
        return 0.0
    interval = float(np.median(np.diff(beats)))
    if not np.isfinite(interval) or interval <= 0.0:
        return 0.0
    return interval


def _beat_index_for_shift(t: float, beats: np.ndarray, interval: float) -> int:
    """Nearest beat index, extended backward before the first detected beat.

    Index 0 is ``beats[0]``. Negative indices are virtual beats at the median
    interval, so a cue at song start is not treated as the first detected beat.
    """
    first = float(beats[0])
    if float(t) < first and interval > 0.0:
        raw = (float(t) - first) / interval
        lo = int(np.floor(raw))
        earlier = first + lo * interval
        later = first + (lo + 1) * interval
        if (abs(earlier - t), earlier) <= (abs(later - t), later):
            return lo
        return lo + 1
    return _nearest_beat_index(t, beats)


def _beat_time_at_shift_index(
    index: int,
    beats: np.ndarray,
    interval: float,
) -> float:
    """Beat time for ``index``. Past the last beat clamps; before 0 stays >= 0."""
    last = len(beats) - 1
    if index >= len(beats):
        return float(beats[last])
    if index >= 0:
        return float(beats[index])
    if interval <= 0.0:
        return float(beats[0])
    return max(0.0, float(beats[0]) + index * interval)


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
    bar_phase: int = 0,
) -> float:
    """Snap authoring time for ``timeline.placement_snap`` mode.

    Bar snap uses ``bar_times`` shifted by ``bar_phase`` beats, the same grid
    the strip draws and timeline generation uses.

    Snap applies only within the detected grid, widened by half its median
    interval at each end. Intro and outro time outside it places freely.
    """
    if mode == "beat":
        return _snap_time_within_grid(t, beat_times)
    if mode == "bar":
        grid = (
            shift_bars_by_beats(bar_times, beat_times, bar_phase)
            if bar_phase
            else bar_times
        )
        return _snap_time_within_grid(t, grid)
    return float(t)


def _snap_time_within_grid(t: float, grid: Sequence[float]) -> float:
    if not grid:
        return float(t)
    points = np.asarray(grid, dtype=np.float64)
    margin = _median_beat_interval(points) / 2.0
    if t < float(points[0]) - margin or t > float(points[-1]) + margin:
        return float(t)
    return snap_time_to_grid(t, grid)


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
    """Map each cue to the nearest beat, move by ``delta`` indices, canonicalize.

    Cues before the first detected beat step along the median interval extended
    backward, then clamp at 0. Indices past the last beat stay on that beat.
    """
    if not lane.cues or not beat_times or delta == 0:
        return TimelineLane(baseline=lane.baseline, cues=list(lane.cues))

    beats = np.asarray(beat_times, dtype=np.float64)
    interval = _median_beat_interval(beats)
    shifted = [
        replace(
            cue,
            t=_beat_time_at_shift_index(
                _beat_index_for_shift(cue.t, beats, interval) + delta,
                beats,
                interval,
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
        sole = max(0.0, float(beats[0]))
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
            snapped_t = _nearest_with_earlier_tie(t, candidates)
        else:
            raw = (t - first) / interval
            lo = int(np.floor(raw))
            snapped_t = _nearest_with_earlier_tie(
                t,
                (first + lo * interval, first + (lo + 1) * interval),
            )
        # Extrapolation before the first beat can land on a virtual negative
        # grid point; persisted cues must stay non-negative.
        return max(0.0, snapped_t)

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
