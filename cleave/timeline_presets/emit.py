"""Emit timeline cues from active-set state sequences."""

from __future__ import annotations

from collections.abc import Sequence

from cleave.timeline import TimelineCue


def cues_from_states(
    slots: Sequence[str],
    states: Sequence[tuple[float, frozenset[str]]],
) -> list[TimelineCue]:
    cues: list[TimelineCue] = []
    prev: frozenset[str] | None = None
    for t, active in states:
        if prev is None:
            layers = {slot: (slot in active) for slot in slots}
        else:
            layers = {
                slot: (slot in active)
                for slot in slots
                if (slot in active) != (slot in prev)
            }
            if not layers:
                continue
        cues.append(TimelineCue(t=float(t), layers=layers))
        prev = active
    return cues
