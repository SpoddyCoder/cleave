"""Per-lane timeline evaluation and editing for layer visibility."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from cleave.extract import STEM_SOURCES, StemSource

RECORD_DEBOUNCE_SEC = 0.08

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


def lane_tick_times(lane: TimelineLane, duration_sec: float) -> list[float]:
    """Cue times within ``[0, duration_sec]`` (every stored cue is a real transition)."""
    return sorted(
        cue.t for cue in lane.cues if 0.0 <= cue.t <= duration_sec
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
