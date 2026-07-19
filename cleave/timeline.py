"""Per-lane timeline evaluation and editing for layer visibility."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from cleave.easing import smoothstep
from cleave.extract import STEM_SOURCES, StemSource

RECORD_DEBOUNCE_SEC = 0.08
SONG_MARKER_FADE_MATCH_EPS = 1e-3
_CUE_BOUNDARY_EPS = 1e-9

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
    visible: bool


@dataclass
class TimelineLane:
    baseline: bool | None  # None = inherit session.layers[slot].enabled
    cues: list[SlotCue]  # canonical: strictly increasing t, no redundant transitions


@dataclass
class Timeline:
    enabled: bool = True
    lanes: dict[str, TimelineLane] = field(default_factory=dict)

    def visible_at(self, slot: str, t_sec: float, *, inherit: bool) -> bool:
        lane = self.lanes.get(slot)
        if lane is None:
            return inherit
        return lane_visible_at(lane, t_sec, inherit=inherit)

    def visible_state_at(
        self,
        slots: Sequence[str],
        t_sec: float,
        inherits: Mapping[str, bool],
    ) -> dict[str, bool]:
        return {
            slot: self.visible_at(slot, t_sec, inherit=inherits[slot])
            for slot in slots
        }


def empty_lane() -> TimelineLane:
    return TimelineLane(baseline=None, cues=[])


def copy_lane(lane: TimelineLane) -> TimelineLane:
    return TimelineLane(baseline=lane.baseline, cues=list(lane.cues))


def stem_abbreviation(stem: StemSource) -> str:
    if stem not in _STEM_SOURCE_ABBREVIATIONS:
        allowed = ", ".join(STEM_SOURCES)
        raise ValueError(f"unknown stem: {stem!r} (expected one of: {allowed})")
    return _STEM_SOURCE_ABBREVIATIONS[stem]


def canonicalize(
    baseline: bool | None,
    cues: Sequence[SlotCue],
) -> list[SlotCue]:
    """Drop redundant/no-op transitions; last-wins at equal ``t``.

    Returns strictly increasing ``t`` cues where each changes visibility from
    the previous state (``baseline``, or the prior cue when baseline is None).
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
    current = baseline
    for cue in collapsed:
        if current is not None and cue.visible == current:
            continue
        result.append(cue)
        current = cue.visible
    return result


def lane_visible_at(
    lane: TimelineLane,
    t_sec: float,
    *,
    inherit: bool,
) -> bool:
    """Visibility at ``t_sec``. If ``baseline`` is None, use ``inherit`` until the first cue."""
    visible = inherit if lane.baseline is None else lane.baseline
    for cue in lane.cues:
        if cue.t > t_sec:
            break
        visible = cue.visible
    return visible


def lane_segments(
    lane: TimelineLane,
    duration_sec: float,
    *,
    inherit: bool,
) -> list[tuple[float, float, bool]]:
    """Return ``(start_t, end_t, visible)`` segments over ``[0, duration_sec]``."""
    if duration_sec <= 0:
        return []
    boundaries = sorted({0.0, duration_sec} | {cue.t for cue in lane.cues})
    segments: list[tuple[float, float, bool]] = []
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
        visible = lane_visible_at(lane, clip_start, inherit=inherit)
        segments.append((clip_start, clip_end, visible))
    return segments


def _boundary_has_cue(lane: TimelineLane, t: float) -> bool:
    return any(abs(cue.t - t) <= _CUE_BOUNDARY_EPS for cue in lane.cues)


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


def _edge_fade_duration(
    lane: TimelineLane,
    t: float,
    *,
    is_fade_in: bool,
    duration_sec: float,
    song_marker_times: Sequence[float],
    song_marker_fades: TimelineFadeGroup,
    standard_fades: TimelineFadeGroup,
) -> float:
    if is_fade_in:
        if t <= 0.0 and not _boundary_has_cue(lane, t):
            return 0.0
    elif t >= duration_sec and not _boundary_has_cue(lane, t):
        return 0.0
    group = _fade_group_for_edge(
        t,
        song_marker_times=song_marker_times,
        song_marker_fades=song_marker_fades,
        standard_fades=standard_fades,
    )
    if not group.enabled:
        return 0.0
    duration = group.fade_in if is_fade_in else group.fade_out
    return max(0.0, float(duration))


def _segment_fade_durations(
    lane: TimelineLane,
    start: float,
    end: float,
    *,
    duration_sec: float,
    song_marker_times: Sequence[float],
    song_marker_fades: TimelineFadeGroup,
    standard_fades: TimelineFadeGroup,
) -> tuple[float, float]:
    fade_in = _edge_fade_duration(
        lane,
        start,
        is_fade_in=True,
        duration_sec=duration_sec,
        song_marker_times=song_marker_times,
        song_marker_fades=song_marker_fades,
        standard_fades=standard_fades,
    )
    fade_out = _edge_fade_duration(
        lane,
        end,
        is_fade_in=False,
        duration_sec=duration_sec,
        song_marker_times=song_marker_times,
        song_marker_fades=song_marker_fades,
        standard_fades=standard_fades,
    )
    return fade_in, fade_out


def _segment_fade_envelope(
    t_sec: float,
    start: float,
    end: float,
    *,
    fade_in: float,
    fade_out: float,
) -> float:
    if start <= t_sec < end:
        return 1.0
    if fade_in > 0.0 and start - fade_in <= t_sec < start:
        return smoothstep((t_sec - (start - fade_in)) / fade_in)
    if fade_out > 0.0 and end <= t_sec < end + fade_out:
        return smoothstep((end + fade_out - t_sec) / fade_out)
    return 0.0


def lane_fade_spans(
    lane: TimelineLane,
    *,
    inherit: bool,
    song_marker_fades: TimelineFadeGroup,
    standard_fades: TimelineFadeGroup,
    duration_sec: float,
    song_marker_times: Sequence[float] = (),
) -> list[tuple[float, float, Literal["in", "out"]]]:
    """Return clipped ``(t0, t1, kind)`` fade wedges for visible lane segments."""
    if duration_sec <= 0.0:
        return []
    spans: list[tuple[float, float, Literal["in", "out"]]] = []
    for start, end, visible in lane_segments(lane, duration_sec, inherit=inherit):
        if not visible:
            continue
        fade_in, fade_out = _segment_fade_durations(
            lane,
            start,
            end,
            duration_sec=duration_sec,
            song_marker_times=song_marker_times,
            song_marker_fades=song_marker_fades,
            standard_fades=standard_fades,
        )
        if fade_in > 0.0:
            t0 = max(0.0, start - fade_in)
            t1 = start
            if t1 > t0:
                spans.append((t0, t1, "in"))
        if fade_out > 0.0:
            t0 = end
            t1 = min(duration_sec, end + fade_out)
            if t1 > t0:
                spans.append((t0, t1, "out"))
    return spans


def lane_fade_alpha(
    lane: TimelineLane,
    t_sec: float,
    *,
    inherit: bool,
    song_marker_fades: TimelineFadeGroup,
    standard_fades: TimelineFadeGroup,
    duration_sec: float,
    song_marker_times: Sequence[float] = (),
) -> float:
    """Continuous opacity for visible segments with optional edge fades.

    For each visible ``[A, B)`` from :func:`lane_segments`, fade-in starts
    before ``A`` and reaches full at ``A``; fade-out starts at ``B`` and
    reaches zero after ``B``. Durations come from the song-marker group when
    the edge matches a marker within :data:`SONG_MARKER_FADE_MATCH_EPS`, else
    the standard group. Disabled groups (or zero duration) stay abrupt.
    Overlapping envelopes use max. Song start/end without a cue at that edge
    do not fade.
    """
    if duration_sec <= 0.0:
        return 0.0
    alpha = 0.0
    for start, end, visible in lane_segments(lane, duration_sec, inherit=inherit):
        if not visible:
            continue
        fade_in, fade_out = _segment_fade_durations(
            lane,
            start,
            end,
            duration_sec=duration_sec,
            song_marker_times=song_marker_times,
            song_marker_fades=song_marker_fades,
            standard_fades=standard_fades,
        )
        contrib = _segment_fade_envelope(
            t_sec,
            start,
            end,
            fade_in=fade_in,
            fade_out=fade_out,
        )
        if contrib > alpha:
            alpha = contrib
    return alpha


def lane_tick_times(lane: TimelineLane, duration_sec: float) -> list[float]:
    """Cue times within ``[0, duration_sec]`` (every stored cue is a real transition)."""
    return sorted(
        cue.t for cue in lane.cues if 0.0 <= cue.t <= duration_sec
    )


def lane_on_transition_trigger_times(
    lane: TimelineLane,
    *,
    song_marker_times: Sequence[float] = (),
    song_marker_fades: TimelineFadeGroup,
    standard_fades: TimelineFadeGroup,
) -> list[float]:
    """Preset-switch trigger times for each rising edge (``visible=True`` cue).

    Canonical cues alternate, so every ``visible=True`` cue is an off->on edge.
    Trigger is ``cue.t - fade_in(edge)`` using the song-marker vs standard fade
    group for that edge (same selection as :func:`lane_fade_alpha`). When the
    matching group is disabled or ``fade_in`` is 0, the trigger is ``cue.t``.
    """
    triggers: list[float] = []
    for cue in lane.cues:
        if not cue.visible:
            continue
        fade_in = _edge_fade_duration(
            lane,
            cue.t,
            is_fade_in=True,
            duration_sec=0.0,
            song_marker_times=song_marker_times,
            song_marker_fades=song_marker_fades,
            standard_fades=standard_fades,
        )
        triggers.append(cue.t - fade_in)
    return triggers


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
    visible: bool,
) -> TimelineLane:
    """Set or replace the transition at ``t``; canonicalize."""
    others = [cue for cue in lane.cues if cue.t != t]
    return TimelineLane(
        baseline=lane.baseline,
        cues=canonicalize(lane.baseline, others + [SlotCue(t=t, visible=visible)]),
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
        SlotCue(
            t=float(
                beats[max(0, min(last, _nearest_beat_index(cue.t, beats) + delta))]
            ),
            visible=cue.visible,
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
        snapped = [SlotCue(t=sole, visible=cue.visible) for cue in lane.cues]
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

    snapped = [SlotCue(t=snap_t(cue.t), visible=cue.visible) for cue in lane.cues]
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
                cues[best_i] = SlotCue(t=marker, visible=old.visible)
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
            working[slot][cue_i] = SlotCue(t=marker, visible=old.visible)
            claimed_pairs.add((slot, cue_i))
            moved += 1

    for slot in target_slots:
        baseline = result[slot].baseline
        result[slot] = TimelineLane(
            baseline=baseline,
            cues=canonicalize(baseline, working[slot]),
        )
    return result, moved
