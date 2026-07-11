"""Emit timeline lanes from active-set state sequences."""

from __future__ import annotations

from collections.abc import Sequence

from cleave.timeline import SlotCue, TimelineLane, canonicalize, empty_lane


def cues_from_states(
    slots: Sequence[str],
    states: Sequence[tuple[float, frozenset[str]]],
) -> dict[str, TimelineLane]:
    """Build per-slot lanes: baseline from the first state, then transitions."""
    slot_list = list(slots)
    if not states:
        return {slot: empty_lane() for slot in slot_list}

    _t0, first_active = states[0]
    baselines = {slot: (slot in first_active) for slot in slot_list}
    cues_by_slot: dict[str, list[SlotCue]] = {slot: [] for slot in slot_list}
    prev = first_active
    for t, active in states[1:]:
        for slot in slot_list:
            now = slot in active
            if now != (slot in prev):
                cues_by_slot[slot].append(SlotCue(t=float(t), visible=now))
        prev = active
    return {
        slot: TimelineLane(
            baseline=baselines[slot],
            cues=canonicalize(baselines[slot], cues_by_slot[slot]),
        )
        for slot in slot_list
    }
