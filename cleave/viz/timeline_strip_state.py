"""Timeline strip view state and the per-row data drawn from it."""

from __future__ import annotations

import bisect
from collections.abc import Sequence
from dataclasses import dataclass, field

from cleave.stems import StemSource
from cleave.timeline import (
    ClipEdge,
    SlotCue,
    TimelineClip,
    TimelineFadeGroup,
    TimelineLane,
    empty_lane,
    lane_clips,
    lane_level_breakpoints,
    lane_tick_times,
    levels_equal,
    opening_cue,
)


@dataclass
class TimelineViewState:
    layer_z_order: list[str]
    lanes: dict[str, TimelineLane]
    defaults: dict[str, float]
    position_sec: float
    duration_sec: float
    focus_row: int  # 0..N-1, index into layer_z_order (0 = bottom stem)
    monitor_visible: dict[str, bool]
    slot_stems: dict[str, StemSource] = field(default_factory=dict)
    override_slots: set[str] = field(default_factory=set)
    solo_slot: str | None = None
    armed_slots: set[str] = field(default_factory=set)
    recording: bool = False
    paused: bool = True
    locked: bool = False
    # Pointer hover: a row's label or header button as (target, row), drawn
    # in static chrome, or a corner button (live).
    hover_row_target: tuple[str, int] | None = None
    hover_button: str | None = None
    record_start_sec: float | None = None
    record_slot_start_sec: dict[str, float] = field(default_factory=dict)
    record_baseline: dict[str, float] = field(default_factory=dict)
    record_buffer: dict[str, list[SlotCue]] = field(default_factory=dict)
    record_high_water_mark: float | None = None
    enabled: bool = False
    submenu_focused: bool = False
    arm_flash_start_ms: dict[str, int] = field(default_factory=dict)
    show_bar_grid: bool = False
    bar_grid_times: tuple[float, ...] = ()
    song_marker_times: tuple[float, ...] = ()
    selected_song_marker_index: int | None = None
    song_marker_flash_start_ms: int | None = None
    hard_cut_fades: TimelineFadeGroup = field(default_factory=TimelineFadeGroup)
    soft_cut_fades: TimelineFadeGroup = field(default_factory=TimelineFadeGroup)
    selected_clip_t: dict[str, float] = field(default_factory=dict)
    selected_clip_flash_start_ms: int | None = None
    # Clip under the pointer: (row, clip start, edge or None for the body).
    hover_clip: tuple[int, float, ClipEdge | None] | None = None
    # Visible time window mapped onto the bar. An end of None is the song end.
    view_start_sec: float = 0.0
    view_end_sec: float | None = None


def view_window(state: TimelineViewState) -> tuple[float, float]:
    """Visible ``(start, end)`` in song seconds."""
    if state.view_end_sec is None:
        return (0.0, state.duration_sec)
    return (state.view_start_sec, state.view_end_sec)


def cue_times_for_stem(
    lane: TimelineLane,
    duration_sec: float,
) -> list[float]:
    """Cue times within ``[0, duration_sec]`` (every stored cue is a real transition)."""
    return lane_tick_times(lane, duration_sec)


def lane_for_view(state: TimelineViewState, slot: str) -> TimelineLane:
    return state.lanes.get(slot) or empty_lane()


def inherit_for_view(state: TimelineViewState, slot: str) -> float:
    return float(state.defaults.get(slot, 1.0))


def recording_view_lane(state: TimelineViewState, slot: str) -> TimelineLane:
    return TimelineLane(
        baseline=state.record_baseline[slot],
        cues=list(state.record_buffer.get(slot, [])),
    )


def level_at_breakpoints(
    breakpoints: list[tuple[float, float]],
    t: float,
) -> float:
    """Linear level along a breakpoint polyline (strip geometry, not smoothstep)."""
    if not breakpoints:
        return 0.0
    if t <= breakpoints[0][0]:
        return float(breakpoints[0][1])
    if t >= breakpoints[-1][0]:
        return float(breakpoints[-1][1])
    for index in range(len(breakpoints) - 1):
        t0, v0 = breakpoints[index]
        t1, v1 = breakpoints[index + 1]
        # Half-open [t0, t1) so a hard step at t1 wins over the prior segment end.
        if t >= t1:
            continue
        if t1 <= t0:
            last = index + 1
            while (
                last + 1 < len(breakpoints)
                and breakpoints[last + 1][0] <= t0
            ):
                last += 1
            return float(breakpoints[last][1])
        u = (t - t0) / (t1 - t0)
        return float(v0 + (v1 - v0) * u)
    return float(breakpoints[-1][1])


def clip_breakpoints(
    breakpoints: list[tuple[float, float]],
    start: float,
    end: float,
) -> list[tuple[float, float]]:
    """Clip a breakpoint polyline to ``[start, end]``, interpolating at the edges.

    A step exactly at ``start`` or ``end`` is kept as its own vertical pair,
    so the segment next to it stays flat instead of ramping across the clip.
    """
    if end <= start or not breakpoints:
        return []
    clipped: list[tuple[float, float]] = [
        (float(t), float(level))
        for t, level in breakpoints
        if start <= t <= end
    ]
    if not clipped or clipped[0][0] > start:
        clipped.insert(0, (start, level_at_breakpoints(breakpoints, start)))
    if clipped[-1][0] < end:
        clipped.append((end, level_at_breakpoints(breakpoints, end)))
    return clipped


def _span_breakpoints_for_lane(
    state: TimelineViewState,
    lane: TimelineLane,
    *,
    inherit: float,
    duration_sec: float,
) -> list[tuple[float, float]]:
    """Breakpoints covering ``[0, duration_sec]`` for strip drawing."""
    if duration_sec <= 0.0:
        return []
    breakpoints = lane_level_breakpoints(
        lane,
        inherit=inherit,
        hard_cut_fades=state.hard_cut_fades,
        soft_cut_fades=state.soft_cut_fades,
        duration_sec=duration_sec,
    )
    if not breakpoints:
        level = inherit if lane.baseline is None else float(lane.baseline)
        return [(0.0, level), (duration_sec, level)]
    spanned = list(breakpoints)
    if spanned[0][0] > 0.0:
        spanned.insert(0, (0.0, spanned[0][1]))
    if spanned[-1][0] < duration_sec:
        spanned.append((duration_sec, spanned[-1][1]))
    return spanned


def _extend_breakpoints(
    dest: list[tuple[float, float]],
    more: list[tuple[float, float]],
) -> None:
    for t, level in more:
        if (
            dest
            and dest[-1][0] == t
            and levels_equal(dest[-1][1], level)
        ):
            continue
        dest.append((t, level))


def bar_level_breakpoints_for_row(
    state: TimelineViewState,
    slot: str,
) -> list[tuple[float, float]]:
    """Level breakpoints for one timeline row, including live record preview."""
    duration = state.duration_sec
    if duration <= 0:
        return []
    inherit = inherit_for_view(state, slot)
    lane = lane_for_view(state, slot)
    if not (state.recording and slot in state.record_baseline):
        return _span_breakpoints_for_lane(
            state, lane, inherit=inherit, duration_sec=duration
        )

    record_start = state.record_slot_start_sec.get(slot, state.record_start_sec)
    if record_start is None:
        record_start = state.position_sec
    record_start = max(0.0, min(record_start, duration))
    playhead = max(0.0, min(state.position_sec, duration))

    committed = _span_breakpoints_for_lane(
        state, lane, inherit=inherit, duration_sec=duration
    )
    result: list[tuple[float, float]] = []

    if record_start > 0.0:
        _extend_breakpoints(result, clip_breakpoints(committed, 0.0, record_start))

    effective_end = max(playhead, state.record_high_water_mark or 0.0)
    if effective_end > record_start:
        live = _span_breakpoints_for_lane(
            state,
            recording_view_lane(state, slot),
            inherit=1.0,
            duration_sec=effective_end,
        )
        _extend_breakpoints(
            result, clip_breakpoints(live, record_start, effective_end)
        )

    if effective_end < duration:
        _extend_breakpoints(
            result, clip_breakpoints(committed, effective_end, duration)
        )
    return result


def row_clips_for_view(state: TimelineViewState, slot: str) -> list[TimelineClip]:
    """The committed clips of one timeline row."""
    return lane_clips(
        lane_for_view(state, slot),
        inherit=inherit_for_view(state, slot),
        duration_sec=state.duration_sec,
    )


def bar_cues_for_row(state: TimelineViewState, slot: str) -> list[SlotCue]:
    """Cues whose ticks are drawn for one timeline row.

    Includes a synthetic ``t=0`` cue when the opening period is on via baseline
    only, so the first section can be selected for cast/blend.
    """
    duration = state.duration_sec
    lane = lane_for_view(state, slot)
    if not (state.recording and slot in state.record_baseline):
        cues = [cue for cue in lane.cues if 0.0 <= cue.t <= duration]
        synthetic = opening_cue(lane)
        if synthetic is not None and duration >= 0.0:
            cues = [synthetic, *cues]
        return cues

    record_start = state.record_slot_start_sec.get(slot, state.record_start_sec)
    if record_start is None:
        record_start = state.position_sec
    playhead = state.position_sec
    effective_end = max(playhead, state.record_high_water_mark or 0.0)
    committed = [
        cue
        for cue in lane.cues
        if 0.0 <= cue.t <= duration
        and (cue.t < record_start or cue.t > effective_end)
    ]
    live = [
        cue
        for cue in recording_view_lane(state, slot).cues
        if record_start <= cue.t <= effective_end and cue.t <= duration
    ]
    by_t = {cue.t: cue for cue in committed}
    for cue in live:
        by_t[cue.t] = cue
    synthetic = opening_cue(lane)
    if synthetic is not None and 0.0 not in by_t and duration >= 0.0:
        by_t[0.0] = synthetic
    return [by_t[t] for t in sorted(by_t)]


def bar_tick_times_for_row(state: TimelineViewState, slot: str) -> list[float]:
    """Cue tick times for one timeline row."""
    return [cue.t for cue in bar_cues_for_row(state, slot)]


def glyph_lane_for_cue(
    state: TimelineViewState,
    slot: str,
    cue_t: float,
) -> tuple[TimelineLane, float]:
    """Lane and inherit used for stepped previous-level at a drawn cue."""
    inherit = inherit_for_view(state, slot)
    if state.recording and slot in state.record_baseline:
        record_start = state.record_slot_start_sec.get(slot, state.record_start_sec)
        if record_start is None:
            record_start = state.position_sec
        effective_end = max(state.position_sec, state.record_high_water_mark or 0.0)
        if record_start <= cue_t <= effective_end:
            return recording_view_lane(state, slot), 1.0
    return lane_for_view(state, slot), inherit


def playback_bar_text(position_sec: float, downbeat_times: Sequence[float]) -> str:
    """1-based bar at the playhead. Empty grids show an em dash."""
    if not downbeat_times:
        return "—"
    count = bisect.bisect_right(downbeat_times, position_sec)
    return str(max(1, count))
