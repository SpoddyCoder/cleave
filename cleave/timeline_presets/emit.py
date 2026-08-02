"""Emit timeline lanes from per-slot level state sequences."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cleave.blend_modes import BlendMode
from cleave.cue_roles import CueRole
from cleave.cut_types import CutType
from cleave.timeline import (
    LEVEL_EPS,
    SlotCue,
    TimelineLane,
    canonicalize,
    empty_lane,
    levels_equal,
    matches_song_marker,
)


def levels_from_active(
    active: frozenset[str] | set[str],
    level: float = 1.0,
) -> dict[str, float]:
    """Map an active-slot set to a level mapping (absent slots mean 0.0)."""
    return {slot: float(level) for slot in active}


def cues_from_states(
    slots: Sequence[str],
    states: Sequence[tuple[float, Mapping[str, float]]],
    casts: Sequence[Mapping[str, tuple[CueRole, BlendMode]]] | None = None,
    *,
    song_marker_times: Sequence[float] = (),
) -> dict[str, TimelineLane]:
    """Build per-slot lanes from level states.

    Baseline is always ``0.0``. The first state's levels are emitted as cues at
    ``t=0`` (so an opening on-section is selectable for cast/blend). Later
    states use their own times. Absent slots in a state mapping are ``0.0``.

    When ``casts`` is provided (parallel to ``states``), on-transitions and
    other non-zero level cues write ``blend`` and ``role`` from the cast entry.
    Off-cues remain stripped by ``canonicalize``.

    On-cues (level above ``LEVEL_EPS``) get cut ``hard`` when ``cue_t`` matches
    a song marker, otherwise ``soft``. Off-cues inherit cut from the preceding
    on-cue for that slot (default ``soft`` when none).
    """
    slot_list = list(slots)
    if not states:
        return {slot: empty_lane() for slot in slot_list}

    markers = tuple(float(t) for t in song_marker_times)
    baselines = {slot: 0.0 for slot in slot_list}
    cues_by_slot: dict[str, list[SlotCue]] = {slot: [] for slot in slot_list}
    prev = {slot: 0.0 for slot in slot_list}
    last_cut: dict[str, CutType] = {slot: "soft" for slot in slot_list}
    for index, (t, levels) in enumerate(states):
        cue_t = 0.0 if index == 0 else float(t)
        cast_map = casts[index] if casts is not None and index < len(casts) else None
        for slot in slot_list:
            now = float(levels.get(slot, 0.0))
            if not levels_equal(now, prev[slot]):
                blend: BlendMode | None = None
                role: CueRole | None = None
                if cast_map is not None and now > LEVEL_EPS:
                    entry = cast_map.get(slot)
                    if entry is not None:
                        role, blend = entry
                if now > LEVEL_EPS:
                    cut: CutType = (
                        "hard" if matches_song_marker(cue_t, markers) else "soft"
                    )
                    last_cut[slot] = cut
                else:
                    cut = last_cut[slot]
                cues_by_slot[slot].append(
                    SlotCue(
                        t=cue_t,
                        level=now,
                        blend=blend,
                        role=role,
                        cut=cut,
                    )
                )
            prev[slot] = now
    return {
        slot: TimelineLane(
            baseline=baselines[slot],
            cues=canonicalize(baselines[slot], cues_by_slot[slot]),
        )
        for slot in slot_list
    }
