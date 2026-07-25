"""Emit timeline lanes from per-slot level state sequences."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cleave.timeline import SlotCue, TimelineLane, canonicalize, empty_lane, levels_equal


def levels_from_active(
    active: frozenset[str] | set[str],
    level: float = 1.0,
) -> dict[str, float]:
    """Map an active-slot set to a level mapping (absent slots mean 0.0)."""
    return {slot: float(level) for slot in active}


def cues_from_states(
    slots: Sequence[str],
    states: Sequence[tuple[float, Mapping[str, float]]],
) -> dict[str, TimelineLane]:
    """Build per-slot lanes: baseline from the first state, then level transitions.

    Absent slots in a state mapping are treated as level ``0.0``.
    """
    slot_list = list(slots)
    if not states:
        return {slot: empty_lane() for slot in slot_list}

    _t0, first_levels = states[0]
    baselines = {
        slot: float(first_levels.get(slot, 0.0)) for slot in slot_list
    }
    cues_by_slot: dict[str, list[SlotCue]] = {slot: [] for slot in slot_list}
    prev = {slot: baselines[slot] for slot in slot_list}
    for t, levels in states[1:]:
        for slot in slot_list:
            now = float(levels.get(slot, 0.0))
            if not levels_equal(now, prev[slot]):
                cues_by_slot[slot].append(SlotCue(t=float(t), level=now))
            prev[slot] = now
    return {
        slot: TimelineLane(
            baseline=baselines[slot],
            cues=canonicalize(baselines[slot], cues_by_slot[slot]),
        )
        for slot in slot_list
    }
