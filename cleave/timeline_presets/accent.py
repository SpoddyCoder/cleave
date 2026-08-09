"""Song-marker accent overlay for timeline presets.

Fires accents at in-range song markers typed ``standard`` when the conductor
supplies stem signals. Other marker types are ignored for triggering but still
cut sections (any marker ends the prior section).

Each accent spans from its ``standard`` marker to the next song marker (or song
end), capped at ``ACCENT_MAX_SEC``. Long sections get one accent window from the
marker then restore; there is no second accent in the leftover. While the accent
slot is up, one other active supporting layer is dimmed by one ``LEVEL_QUANTUM``
step (floored at ``LEVEL_QUANTUM``) and restored when the accent ends.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from cleave.blend_modes import BlendMode
from cleave.cue_roles import CUE_ROLE_BLEND, CueRole
from cleave.extract import StemSource
from cleave.signals import Signals
from cleave.song_markers import SongMarker
from cleave.timeline import (
    LEVEL_EPS,
    LEVEL_QUANTUM,
    SlotCue,
    TimelineLane,
    canonicalize,
    copy_lane,
    empty_lane,
    lane_blend_at,
    lane_level_at,
    lane_role_at,
    quantize_level,
)
from cleave.timeline_presets.emit import cues_from_states
from cleave.timeline_presets.motifs import MIN_SWITCH_GAP_SEC

# Longest single accent hold from a standard marker; leftover of a longer
# section stays at restored prior levels (no second accent in that section).
ACCENT_MAX_SEC = 20.0
# Dim supporting layers by one strip quantum so the duck reads on the bar.
ACCENT_DIM_STEP = LEVEL_QUANTUM
# Instantaneous presence window around the marker (percentile-normalized).
_PRESENCE_WINDOW_SEC = 0.05

# Prefer dimming lead, then pulse, then bed (never the accent slot itself).
_DIM_ROLE_RANK: dict[CueRole, int] = {
    "lead": 0,
    "pulse": 1,
    "bed": 2,
    "accent": 3,
}

_STEM_PRESENCE: dict[StemSource, str] = {
    "drums": "onset_strength",
    "bass": "rms",
    "vocals": "rms",
    "other": "rms",
    "full_mix": "rms",
}


@dataclass(frozen=True)
class AccentBurst:
    """One accent window: accent slot, optional dimmed support, start, restore."""

    slot: str
    t_start: float
    t_end: float
    dim_slot: str | None = None


def resolve_accent_times(
    song_markers: Sequence[SongMarker],
    duration_sec: float,
) -> list[float]:
    """Sorted unique ``standard`` marker times strictly inside ``(0, duration_sec)``."""
    times: list[float] = []
    seen: set[float] = set()
    for marker in song_markers:
        if marker.marker_type != "standard":
            continue
        t = float(marker.time)
        if not (0.0 < t < duration_sec) or t in seen:
            continue
        seen.add(t)
        times.append(t)
    times.sort()
    return times


def marker_cut_times(
    song_markers: Sequence[SongMarker],
    duration_sec: float,
) -> list[float]:
    """Sorted unique marker times that cut the song into sections."""
    return sorted(
        {
            float(marker.time)
            for marker in song_markers
            if 0.0 < float(marker.time) < duration_sec
        }
    )


def accent_window(
    t: float,
    song_markers: Sequence[SongMarker],
    duration_sec: float,
) -> tuple[float, float] | None:
    """Return ``(t_start, t_end)`` for an accent beginning at ``t``.

    End is the next song marker after ``t`` (any type), or ``duration_sec``,
    capped so the hold is at most ``ACCENT_MAX_SEC``. Returns ``None`` when the
    window is empty.
    """
    t_start = float(t)
    if duration_sec <= 0.0 or t_start >= duration_sec - 1e-9:
        return None
    section_end = float(duration_sec)
    for cut in marker_cut_times(song_markers, duration_sec):
        if cut > t_start + 1e-9:
            section_end = cut
            break
    t_end = min(section_end, t_start + ACCENT_MAX_SEC, float(duration_sec))
    if t_end <= t_start + 1e-9:
        return None
    return (t_start, t_end)


def dimmed_support_level(level: float) -> float:
    """One ``LEVEL_QUANTUM`` step down, floored at ``LEVEL_QUANTUM``."""
    prior = float(level)
    if prior <= LEVEL_QUANTUM + 1e-9:
        return quantize_level(prior)
    return max(LEVEL_QUANTUM, quantize_level(prior - ACCENT_DIM_STEP))


def apply_accent(
    lanes: dict[str, TimelineLane],
    slots: Sequence[str],
    *,
    duration_sec: float,
    song_markers: Sequence[SongMarker],
    signals: Signals,
    slot_stems: Mapping[str, StemSource],
    density_bias: int,
    rng: random.Random,
    bar_times: Sequence[float] = (),
) -> dict[str, TimelineLane]:
    """Insert section accents at ``standard`` markers; return ``lanes`` if none.

    ``density_bias`` is accepted for pipeline symmetry with the conductor; accents
    do not scale by density. ``bar_times`` is unused (section bounds use markers).
    """
    del density_bias  # reserved for future density-aware accent staging
    del bar_times  # section span uses song markers only
    slot_list = list(slots)
    if not slot_list or duration_sec <= 0.0:
        return lanes
    times = resolve_accent_times(song_markers, duration_sec)
    if not times:
        return lanes
    if not _signals_ready(signals, slot_stems, slot_list):
        return lanes

    bursts = _plan_bursts(
        times,
        slot_list,
        duration_sec=duration_sec,
        song_markers=song_markers,
        signals=signals,
        slot_stems=slot_stems,
        lanes=lanes,
        rng=rng,
    )
    if not bursts:
        return lanes

    result = {slot: copy_lane(lanes.get(slot) or empty_lane()) for slot in slot_list}
    for burst in bursts:
        result[burst.slot] = _inject_accent_cues(
            result[burst.slot],
            burst.slot,
            t_start=burst.t_start,
            t_end=burst.t_end,
        )
        if burst.dim_slot is not None:
            result[burst.dim_slot] = _inject_dim_cues(
                result[burst.dim_slot],
                burst.dim_slot,
                t_start=burst.t_start,
                t_end=burst.t_end,
            )
    return result


def _signals_ready(
    signals: Signals,
    slot_stems: Mapping[str, StemSource],
    slots: Sequence[str],
) -> bool:
    try:
        for slot in slots:
            stem = slot_stems[slot]
            signals.array(stem, _STEM_PRESENCE[stem])
    except KeyError:
        return False
    return True


def _plan_bursts(
    times: Sequence[float],
    slots: Sequence[str],
    *,
    duration_sec: float,
    song_markers: Sequence[SongMarker],
    signals: Signals,
    slot_stems: Mapping[str, StemSource],
    lanes: Mapping[str, TimelineLane],
    rng: random.Random,
) -> list[AccentBurst]:
    airtime = _layer_airtime(lanes, slots, duration_sec)
    bursts: list[AccentBurst] = []
    last_start: float | None = None
    recent_slots: list[str] = []
    for t in times:
        if last_start is not None and t - last_start < MIN_SWITCH_GAP_SEC - 1e-9:
            continue
        window = accent_window(t, song_markers, duration_sec)
        if window is None:
            continue
        t_start, t_end = window
        slot = _pick_accent_slot(
            signals,
            slot_stems,
            slots,
            t_start,
            airtime=airtime,
            recent_slots=recent_slots,
            rng=rng,
        )
        dim_slot = _pick_dim_slot(lanes, slots, accent_slot=slot, t=t_start)
        bursts.append(
            AccentBurst(
                slot=slot,
                t_start=t_start,
                t_end=t_end,
                dim_slot=dim_slot,
            )
        )
        last_start = t_start
        recent_slots.append(slot)
        airtime[slot] = airtime.get(slot, 0.0) + (t_end - t_start)
    return bursts


def _pick_accent_slot(
    signals: Signals,
    slot_stems: Mapping[str, StemSource],
    slots: Sequence[str],
    t: float,
    *,
    airtime: Mapping[str, float],
    recent_slots: Sequence[str],
    rng: random.Random,
) -> str:
    presence = {
        slot: _presence_at(signals, slot_stems[slot], t) for slot in slots
    }
    peak = max(presence.values())
    candidates = [slot for slot in slots if presence[slot] >= peak - 1e-9]
    if len(candidates) == 1:
        return candidates[0]

    last = recent_slots[-1] if recent_slots else None
    if last is not None and len(candidates) > 1:
        rotated = [slot for slot in candidates if slot != last]
        if rotated:
            candidates = rotated

    min_air = min(airtime.get(slot, 0.0) for slot in candidates)
    least = [
        slot
        for slot in candidates
        if airtime.get(slot, 0.0) <= min_air + 1e-9
    ]
    if len(least) == 1:
        return least[0]
    return rng.choice(least)


def _pick_dim_slot(
    lanes: Mapping[str, TimelineLane],
    slots: Sequence[str],
    *,
    accent_slot: str,
    t: float,
) -> str | None:
    """Pick an active non-accent layer to duck; ``None`` if none suitable."""
    ranked: list[tuple[int, float, int, str]] = []
    for index, slot in enumerate(slots):
        if slot == accent_slot:
            continue
        lane = lanes.get(slot) or empty_lane()
        level = lane_level_at(lane, t, inherit=0.0)
        if level <= LEVEL_EPS:
            continue
        dimmed = dimmed_support_level(level)
        if dimmed >= level - 1e-9:
            continue
        role = lane_role_at(lane, t)
        role_rank = _DIM_ROLE_RANK.get(role, 1) if role is not None else 1
        # Prefer lead/pulse/bed, then higher level, then earlier slot order.
        ranked.append((role_rank, -level, index, slot))
    if not ranked:
        return None
    ranked.sort()
    return ranked[0][3]


def _presence_at(signals: Signals, stem: StemSource, t: float) -> float:
    key = _STEM_PRESENCE[stem]
    t0 = float(t)
    t1 = t0 + _PRESENCE_WINDOW_SEC
    return float(signals.window_mean(stem, key, t0, t1))


def _layer_airtime(
    lanes: Mapping[str, TimelineLane],
    slots: Sequence[str],
    duration_sec: float,
) -> dict[str, float]:
    """Approximate on-time per slot from stepped levels (for tie-breaks)."""
    airtime = {slot: 0.0 for slot in slots}
    if duration_sec <= 0.0:
        return airtime
    times = {0.0, float(duration_sec)}
    for slot in slots:
        lane = lanes.get(slot) or empty_lane()
        for cue in lane.cues:
            if 0.0 < cue.t < duration_sec:
                times.add(float(cue.t))
    ordered = sorted(times)
    for i, t0 in enumerate(ordered[:-1]):
        t1 = ordered[i + 1]
        dt = t1 - t0
        if dt <= 0.0:
            continue
        for slot in slots:
            level = lane_level_at(
                lanes.get(slot) or empty_lane(),
                t0,
                inherit=0.0,
            )
            if level > LEVEL_EPS:
                airtime[slot] += dt
    return airtime


def _inject_accent_cues(
    lane: TimelineLane,
    slot: str,
    *,
    t_start: float,
    t_end: float,
) -> TimelineLane:
    """Rewrite ``slot`` through the burst via ``cues_from_states``.

    When the slot is already at full level with an add blend, ``cues_from_states``
    would drop a role-only transition; fall back to anchored cue upsert.
    """
    prior_level = lane_level_at(lane, t_start, inherit=0.0)
    prior_role = lane_role_at(lane, t_start)
    prior_blend = lane_blend_at(lane, t_start)

    times = {0.0, float(t_start), float(t_end)}
    for cue in lane.cues:
        ct = float(cue.t)
        if ct < t_start - 1e-9 or ct > t_end + 1e-9:
            times.add(ct)

    states: list[tuple[float, dict[str, float]]] = []
    casts: list[dict[str, tuple[CueRole, BlendMode]]] = []
    for t in sorted(times):
        if t_start - 1e-9 <= t < t_end - 1e-9:
            states.append((t, {slot: 1.0}))
            casts.append({slot: ("accent", CUE_ROLE_BLEND["accent"])})
            continue
        level = lane_level_at(lane, t, inherit=0.0)
        states.append((t, {slot: level}))
        role = lane_role_at(lane, t)
        if level > LEVEL_EPS and role is not None:
            blend = lane_blend_at(lane, t)
            if blend is None:
                blend = CUE_ROLE_BLEND[role]
            casts.append({slot: (role, blend)})
        else:
            casts.append({})

    rebuilt = cues_from_states([slot], states, casts)[slot]
    if lane_role_at(rebuilt, t_start) == "accent":
        return rebuilt
    return _anchored_accent_lane(
        lane,
        t_start=t_start,
        t_end=t_end,
        prior_level=prior_level,
        prior_role=prior_role,
        prior_blend=prior_blend,
    )


def _inject_dim_cues(
    lane: TimelineLane,
    slot: str,
    *,
    t_start: float,
    t_end: float,
) -> TimelineLane:
    """Hold a dimmed level through the accent window; restore after."""
    prior_level = lane_level_at(lane, t_start, inherit=0.0)
    dimmed = dimmed_support_level(prior_level)
    if dimmed >= prior_level - 1e-9:
        return lane

    prior_role = lane_role_at(lane, t_start)
    prior_blend = lane_blend_at(lane, t_start)
    if prior_blend is None and prior_role is not None:
        prior_blend = CUE_ROLE_BLEND[prior_role]

    times = {0.0, float(t_start), float(t_end)}
    for cue in lane.cues:
        ct = float(cue.t)
        if ct < t_start - 1e-9 or ct > t_end + 1e-9:
            times.add(ct)

    states: list[tuple[float, dict[str, float]]] = []
    casts: list[dict[str, tuple[CueRole, BlendMode]]] = []
    for t in sorted(times):
        if t_start - 1e-9 <= t < t_end - 1e-9:
            states.append((t, {slot: dimmed}))
            if prior_role is not None and prior_blend is not None:
                casts.append({slot: (prior_role, prior_blend)})
            else:
                casts.append({})
            continue
        level = lane_level_at(lane, t, inherit=0.0)
        states.append((t, {slot: level}))
        role = lane_role_at(lane, t)
        if level > LEVEL_EPS and role is not None:
            blend = lane_blend_at(lane, t)
            if blend is None:
                blend = CUE_ROLE_BLEND[role]
            casts.append({slot: (role, blend)})
        else:
            casts.append({})

    return cues_from_states([slot], states, casts)[slot]


def _anchored_accent_lane(
    lane: TimelineLane,
    *,
    t_start: float,
    t_end: float,
    prior_level: float,
    prior_role: CueRole | None,
    prior_blend: BlendMode | None,
) -> TimelineLane:
    """Upsert anchored accent/restore cues when emit would drop a role-only change."""
    cues = [
        cue
        for cue in lane.cues
        if not (t_start - 1e-9 <= float(cue.t) <= t_end + 1e-9)
    ]
    cues.append(
        SlotCue(
            t=t_start,
            level=1.0,
            blend=CUE_ROLE_BLEND["accent"],
            role="accent",
            cut="none",
            anchor=True,
        )
    )
    cues.append(
        _restore_cue(
            t_end,
            prior_level=prior_level,
            prior_role=prior_role,
            prior_blend=prior_blend,
        )
    )
    cues.sort(key=lambda cue: cue.t)
    baseline = 0.0 if lane.baseline is None else float(lane.baseline)
    return TimelineLane(baseline=baseline, cues=canonicalize(baseline, cues))


def _restore_cue(
    t_end: float,
    *,
    prior_level: float,
    prior_role: CueRole | None,
    prior_blend: BlendMode | None,
) -> SlotCue:
    if prior_level <= LEVEL_EPS:
        return SlotCue(t=t_end, level=0.0, cut="none", anchor=True)
    blend = prior_blend
    if blend is None and prior_role is not None:
        blend = CUE_ROLE_BLEND[prior_role]
    return SlotCue(
        t=t_end,
        level=float(prior_level),
        blend=blend,
        role=prior_role,
        cut="none",
        anchor=True,
    )
