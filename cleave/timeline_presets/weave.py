"""Spread a plan's changes out in time, one layer at a time.

Between markers, layers come in, go out, brighten, and dim one after another,
a bar or two apart, so the screen never jumps as a whole. A marker may land
a few changes together. Preset changes are then placed on layers that stay
on, at markers and at a steady pace between them, offset from layer to layer.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from cleave.cue_roles import CueRole
from cleave.timeline_presets.plan import ACCENT_SEC, Plan, Target, accent_slot
from cleave.timeline_presets.shapes import INTENSITY_STEP

_EPS = 1e-6
# Opacity changes smaller than this are left alone.
_LEVEL_EPS = 0.025
_FULL = 0.999


@dataclass
class SlotEvents:
    """One layer's changes: opacity, role, and where a preset starts."""

    levels: list[tuple[float, float]] = field(default_factory=list)
    roles: list[tuple[float, CueRole | None]] = field(default_factory=list)
    recasts: list[float] = field(default_factory=list)

    def level_at(self, t: float) -> float:
        level = 0.0
        for at, value in sorted(self.levels, key=lambda item: item[0]):
            if at > t + _EPS:
                break
            level = value
        return level

    def level_before(self, t: float) -> float:
        """The opacity just before *t*, ignoring a change at *t* itself."""
        level = 0.0
        for at, value in sorted(self.levels, key=lambda item: item[0]):
            if at >= t - _EPS:
                break
            level = value
        return level

    def times(self) -> list[float]:
        """Every time this layer changes anything."""
        return sorted(
            {t for t, _ in self.levels} | {t for t, _ in self.roles} | set(self.recasts)
        )


@dataclass(frozen=True)
class _Move:
    slot: str
    level: float
    kind: int  # 0 enter, 1 leave, 2 brighten, 3 dim


def _gap_bars(target: Target) -> int:
    return 2 if target.shape.pace == "slow" else 1


def _grid_after(t: float, bars: Sequence[float], bar_sec: float, count: int) -> float:
    """The bar *count* bars after *t* (or as many bar lengths without a grid).

    A bar *t* would snap to does not count, so snapping to bars never lands
    two changes on one layer at the same time.
    """
    later = [b for b in bars if b > t + 0.55 * bar_sec]
    if len(later) >= count:
        return later[count - 1]
    return t + count * bar_sec


def weave(
    slots: Sequence[str], plan: Plan, duration_sec: float
) -> dict[str, SlotEvents]:
    """Every layer's changes over the whole song."""
    events = {slot: SlotEvents() for slot in slots}
    targets = _merged(plan.targets)
    current: dict[str, float] = {}
    for index, target in enumerate(targets):
        until = targets[index + 1].t if index + 1 < len(targets) else duration_sec
        groups = _moves(current, target)
        # Layers over what the target allows leave at once.
        surplus = max(0, len(current) - len(target.levels))
        times = _move_times(target, len(groups), until, plan, surplus)
        for group, t in zip(groups, times):
            for move in group:
                events[move.slot].levels.append((t, move.level))
                if move.level > 0.0:
                    current[move.slot] = move.level
                else:
                    current.pop(move.slot, None)
        for slot, role in target.roles.items():
            events[slot].roles.append((target.t, role))
    _place_accents(events, targets, duration_sec)
    _place_preset_changes(events, targets, plan, duration_sec)
    return events


def _merged(targets: Sequence[Target]) -> list[Target]:
    """Targets in time order; of two at one time, the later wins."""
    by_time: dict[float, Target] = {}
    for target in targets:
        by_time[round(target.t, 6)] = target
    return [by_time[t] for t in sorted(by_time)]


def _moves(current: dict[str, float], target: Target) -> list[list[_Move]]:
    """Changes from *current* to *target*, in groups that land together.

    A layer reaching full lands with one dropping from full, so the lead is
    handed over in one crossfade and the number at full never jumps. The lead
    goes first; then new layers, leavers (first when there are too many),
    rises, and dims.
    """
    moves: list[_Move] = []
    for slot, level in target.levels.items():
        before = current.get(slot, 0.0)
        if before <= 0.0:
            moves.append(_Move(slot, level, 0))
        elif level - before > _LEVEL_EPS:
            moves.append(_Move(slot, level, 2))
        elif before - level > _LEVEL_EPS:
            moves.append(_Move(slot, level, 3))
    for slot in current:
        if slot not in target.levels:
            moves.append(_Move(slot, 0.0, 1))
    surplus = len(current) > len(target.levels)
    order = {0: 1, 1: 0, 2: 2, 3: 3} if surplus else {0: 0, 1: 1, 2: 2, 3: 3}
    moves.sort(key=lambda m: (m.slot != target.lead, order[m.kind], m.slot))
    # Layers at full now that will not be: each can hand over to one reaching full.
    handing = [
        m for m in moves if m.kind in (1, 3) and current.get(m.slot, 0.0) >= _FULL
    ]
    groups: list[list[_Move]] = []
    for move in moves:
        if any(move in group for group in groups):
            continue
        group = [move]
        if move.kind in (0, 2) and move.level >= _FULL and handing:
            partner = handing.pop(0)
            group.append(partner)
        elif move in handing:
            handing.remove(move)
        groups.append(group)
    return groups


def _move_times(
    target: Target, count: int, until: float, plan: Plan, surplus: int = 0
) -> list[float]:
    """When each of *count* groups of moves lands: up to ``together`` at the
    target, then one per gap.

    At a marker, *surplus* leavers also land at the target.
    """
    if count == 0:
        return []
    at_marker = target.t == target.part.section.start
    together = target.together + (surplus if at_marker else 0)
    times = [target.t] * min(count, together)
    gap = _gap_bars(target)
    t = target.t
    while len(times) < count:
        t = _grid_after(t, plan.bars, plan.bar_sec, gap)
        if t >= until - 0.25 * plan.bar_sec:
            break
        times.append(t)
    # Out of room: what is left waits for the next target, which starts
    # again from what is on by then.
    return times


def _place_accents(
    events: dict[str, SlotEvents], targets: Sequence[Target], duration_sec: float
) -> None:
    for index, target in enumerate(targets):
        held = [
            slot
            for slot, slot_events in events.items()
            if slot_events.level_before(target.t) > 0.0
            and slot_events.level_at(target.t) > 0.0
        ]
        slot = accent_slot(target, held)
        if slot is None:
            continue
        until = targets[index + 1].t if index + 1 < len(targets) else duration_sec
        end = min(target.t + ACCENT_SEC, until, target.part.section.end)
        if end - target.t < 1.0:
            continue
        events[slot].roles.append((target.t, "accent"))
        events[slot].roles.append((end, target.roles.get(slot, "bed")))


def _preset_bars(target: Target, density_bias: int = 0) -> float:
    bars = float(target.shape.preset_bars)
    step = INTENSITY_STEP[target.part.section.intensity]
    bars *= 0.85**step
    return max(2.0, bars * 0.85 ** max(-2, min(2, density_bias)))


def _place_preset_changes(
    events: dict[str, SlotEvents],
    targets: Sequence[Target],
    plan: Plan,
    duration_sec: float,
) -> None:
    """New presets on held layers: at markers, and at each section's pace.

    At a section change about half the held layers change, those that have
    shown one preset longest; at a marker inside a run, one does. Between
    markers each layer keeps its own clock, offset from the others so they
    rarely change together.
    """
    slots = list(events)
    bar_sec = plan.bar_sec
    taken: set[float] = set()

    def on_through(slot: str, t: float) -> bool:
        slot_events = events[slot]
        return slot_events.level_before(t) > 0.0 and slot_events.level_at(t) > 0.0

    def entries(slot: str) -> list[float]:
        return [
            t
            for t, level in sorted(events[slot].levels)
            if level > 0.0 and events[slot].level_before(t) <= 0.0
        ]

    def last_start(slot: str, t: float) -> float:
        starts = [x for x in entries(slot) + events[slot].recasts if x <= t + _EPS]
        return max(starts, default=0.0)

    for target in targets:
        if target.t != target.part.section.start:
            continue
        held = [slot for slot in slots if on_through(slot, target.t)]
        held.sort(key=lambda slot: last_start(slot, target.t))
        want = math.ceil(len(held) / 2) if target.part.first else min(1, len(held))
        for slot in held[:want]:
            events[slot].recasts.append(target.t)
            taken.add(round(target.t, 6))

    def target_at(t: float) -> Target:
        current = targets[0]
        for target in targets:
            if target.t > t + _EPS:
                break
            current = target
        return current

    def clear(slot: str, t: float) -> bool:
        return round(t, 6) not in taken and all(
            abs(t - other) >= 0.5 * bar_sec for other in events[slot].times()
        )

    for position, slot in enumerate(slots):
        resets = sorted(set(entries(slot) + events[slot].recasts))
        if not resets:
            continue
        # A layer's first change comes early or late in its pace, by its place.
        share = 0.5 + 0.5 * position / max(1, len(slots))
        t = resets[0]
        due = t + _preset_bars(target_at(t)) * bar_sec * share
        while due < duration_sec - bar_sec:
            later = [x for x in resets if t + _EPS < x <= due + _EPS]
            if later:
                t = later[0]
                due = t + _preset_bars(target_at(t)) * bar_sec
                continue
            when = _grid_after(due - 0.25 * bar_sec, plan.bars, bar_sec, 1)
            for _try in range(4):
                if clear(slot, when):
                    break
                when = _grid_after(when, plan.bars, bar_sec, 1)
            if when >= duration_sec - 0.5 * bar_sec:
                break
            if not on_through(slot, when):
                # Off here: the clock waits for the layer's next entry.
                following = [x for x in resets if x > when + _EPS]
                if not following:
                    break
                t = following[0]
            elif clear(slot, when):
                events[slot].recasts.append(when)
                taken.add(round(when, 6))
                t = when
            else:
                # Busy for a while: try again a bar later.
                due = when + bar_sec
                continue
            due = t + _preset_bars(target_at(t)) * bar_sec
