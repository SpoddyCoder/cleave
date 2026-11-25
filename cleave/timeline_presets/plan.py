"""Plan a layers timeline: which layers play each phrase, which one leads, how bright.

The plan is data, phrase by phrase. ``weave.py`` spreads its changes out in
time and ``lanes.py`` writes them as clips.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from statistics import median

from cleave.cue_roles import CueRole
from cleave.signals import Signals
from cleave.song_markers import SongSection
from cleave.stems import StemSource
from cleave.timeline_presets.conductor import PhraseWeights, StemConductor
from cleave.timeline_presets.shapes import (
    INTENSITY_STEP,
    SHAPES,
    Part,
    SectionShape,
    layer_bounds,
    level_ranges,
    plain_shape,
    quantize,
)

# Seconds a bar is taken to last when the song has no bar grid.
FALLBACK_BAR_SEC = 2.0
# A bar line this share of a bar after a marker is the marker's own bar.
_OWN_BAR_SHARE = 0.5
# A build brightens from this share of its opacity to all of it.
_BUILD_START_SHARE = 0.6
# The accent a chorus or drop opens with lasts at most this long.
ACCENT_SEC = 8.0


@dataclass(frozen=True)
class Target:
    """What should be on from *t*: each visible layer's opacity and role."""

    t: float
    levels: dict[str, float]
    lead: str
    part: Part
    shape: SectionShape
    # Changes that may land together at *t*: everything at a section change,
    # two at a marker inside a run, one elsewhere.
    together: int
    roles: dict[str, CueRole] = field(default_factory=dict)


@dataclass(frozen=True)
class Plan:
    targets: list[Target]
    bar_sec: float
    bars: list[float]


@dataclass
class _Memory:
    active: list[str] = field(default_factory=list)
    lead: str | None = None
    lead_phrases: int = 0
    levels: dict[str, float] = field(default_factory=dict)
    airtime: dict[str, float] = field(default_factory=dict)
    lead_time: dict[str, float] = field(default_factory=dict)
    on_since: dict[str, float] = field(default_factory=dict)


def bar_length(bars: Sequence[float]) -> float:
    gaps = [b - a for a, b in zip(bars, bars[1:]) if b > a]
    return median(gaps) if gaps else FALLBACK_BAR_SEC


def phrase_starts(
    part: Part, shape: SectionShape, bars: Sequence[float], bar_sec: float
) -> list[float]:
    """Where *part*'s phrases start: its marker, then every phrase on the bars."""
    start, end = part.section.start, part.section.end
    slack = _OWN_BAR_SHARE * bar_sec
    inside = [b for b in bars if start + slack < b < end - slack]
    if not inside:
        step = shape.phrase_bars * bar_sec
        count = max(1, int(round((end - start) / step)))
        return [start + i * (end - start) / count for i in range(count)]
    # Count phrases from the run's start, so a run keeps its phrasing.
    before = sum(1 for b in bars if part.run_start + slack < b <= start + slack)
    starts = [start]
    for index, b in enumerate(inside, start=before + 1):
        if index % shape.phrase_bars == 0 and end - b > slack * 2:
            starts.append(b)
    return starts


def _loudness(signals: Signals | None, t0: float, t1: float) -> float:
    if signals is None:
        return 0.0
    try:
        rms = signals.window_mean("full_mix", "rms", t0, t1)
        onset = signals.window_mean("full_mix", "onset_strength", t0, t1)
    except KeyError:
        return 0.0
    value = 0.65 * rms + 0.35 * onset
    return 0.0 if math.isnan(value) else float(value)


def _ranks(values: Sequence[float]) -> list[float]:
    """Each value's place among *values*, 0 (lowest) to 1; all equal is 0.5."""
    if len(values) < 2 or max(values) - min(values) < 1e-9:
        return [0.5] * len(values)
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    for place, index in enumerate(order):
        ranks[index] = place / (len(values) - 1)
    return ranks


def plan_timeline(
    slots: Sequence[str],
    parts: Sequence[Part],
    *,
    bars: Sequence[float],
    density_bias: int,
    rng: random.Random,
    signals: Signals | None = None,
    slot_stems: Mapping[str, StemSource] | None = None,
) -> Plan:
    """Targets for every phrase of every part, in time order."""
    slots = list(slots)
    bars = sorted(float(b) for b in bars)
    bar_sec = bar_length(bars)
    phrases: list[tuple[Part, SectionShape, float, float]] = []
    plain_loudness: list[float] = []
    plain_index: list[int] = []
    for part in parts:
        shape = SHAPES.get(part.section.section_type)
        provisional = shape or plain_shape(0.5)
        starts = phrase_starts(part, provisional, bars, bar_sec)
        for start, end in zip(starts, [*starts[1:], part.section.end]):
            if shape is None:
                plain_index.append(len(phrases))
                plain_loudness.append(_loudness(signals, start, end))
            phrases.append((part, provisional, start, end))
    for index, rank in zip(plain_index, _ranks(plain_loudness)):
        part, _shape, start, end = phrases[index]
        phrases[index] = (part, plain_shape(rank), start, end)

    conductor = StemConductor.build(
        signals, slot_stems, [(start, end) for _p, _s, start, end in phrases]
    )
    memory = _Memory(
        airtime={slot: 0.0 for slot in slots},
        lead_time={slot: 0.0 for slot in slots},
    )
    order = list(slots)
    rng.shuffle(order)
    targets: list[Target] = []
    previous_part: Part | None = None
    for part, shape, start, end in phrases:
        weights = None if conductor is None else conductor.phrase_at(0.5 * (start + end))
        entering = part is not previous_part
        new_run = entering and part.first
        target = _plan_phrase(
            order,
            part,
            shape,
            start,
            end,
            density_bias=density_bias,
            rng=rng,
            memory=memory,
            weights=weights,
            new_run=new_run,
        )
        together = len(slots) if new_run else (2 if entering else 1)
        roles = _roles(target, conductor, weights, slot_stems)
        targets.append(
            Target(start, target[0], target[1], part, shape, together, roles)
        )
        if shape.rising and _last_bar(part, end, bars, bar_sec) is not None:
            targets.append(_full_stack(targets[-1], order, part, bars, bar_sec, memory))
        previous_part = part
    return Plan(targets, bar_sec, bars)


def _last_bar(
    part: Part, end: float, bars: Sequence[float], bar_sec: float
) -> float | None:
    """Start of the run's last bar, when it falls in this phrase."""
    if abs(end - part.run_end) > 1e-6:
        return None
    t = part.run_end - bar_sec
    candidates = [b for b in bars if part.section.start < b < part.run_end - 0.5 * bar_sec]
    if candidates:
        t = candidates[-1]
    return t if part.section.start + 0.5 * bar_sec < t < part.run_end else None


def _full_stack(
    phrase: Target,
    order: Sequence[str],
    part: Part,
    bars: Sequence[float],
    bar_sec: float,
    memory: _Memory,
) -> Target:
    """The build's last bar: the most layers its intensity allows, at full opacity."""
    t = _last_bar(part, part.run_end, bars, bar_sec)
    assert t is not None
    _lo, hi = layer_bounds(part.section.intensity, len(order))
    active = list(phrase.levels)
    for slot in sorted(order, key=lambda s: memory.airtime.get(s, 0.0)):
        if len(active) >= hi:
            break
        if slot not in active:
            active.append(slot)
    ranked = [phrase.lead] + [s for s in active if s != phrase.lead]
    levels = {
        slot: quantize(high)
        for slot, (_low, high) in zip(
            ranked, level_ranges(part.section.intensity, len(ranked))
        )
    }
    memory.active = ranked
    memory.levels = dict(levels)
    roles = {slot: phrase.roles.get(slot, "bed") for slot in levels} if phrase.roles else {}
    return Target(t, levels, phrase.lead, part, phrase.shape, 1, roles)


def _plan_phrase(
    order: Sequence[str],
    part: Part,
    shape: SectionShape,
    start: float,
    end: float,
    *,
    density_bias: int,
    rng: random.Random,
    memory: _Memory,
    weights: PhraseWeights | None,
    new_run: bool,
) -> tuple[dict[str, float], str]:
    section = part.section
    progress = part.progress(0.5 * (start + end))
    count = _count(shape, section, progress, len(order), density_bias, rng)

    def activity(slot: str) -> float:
        return 0.5 if weights is None else float(weights.slot_activity.get(slot, 0.0))

    total = sum(memory.airtime.values()) or 1.0

    def appeal(slot: str) -> float:
        return activity(slot) - memory.airtime.get(slot, 0.0) / total

    def held_for(slot: str) -> float:
        return start - memory.on_since.get(slot, start)

    previous_lead = memory.lead
    avoid = previous_lead if (shape.new_lead and new_run) else None
    active = [slot for slot in memory.active if slot in order]
    while len(active) > count:
        keep = memory.lead if memory.lead in active and len(active) > 1 else None
        leaving = max(
            (s for s in active if s != keep),
            key=lambda s: (held_for(s) - 4.0 * appeal(s), s),
        )
        active.remove(leaving)
    absent = [slot for slot in order if slot not in active]
    while len(active) < count and absent:
        joining = max(absent, key=lambda s: (appeal(s), -order.index(s)))
        absent.remove(joining)
        active.append(joining)
    if absent and active and (new_run or rng.random() < shape.swaps):
        keep = memory.lead if len(active) > 1 else None
        leaving = max(
            (s for s in active if s != keep),
            key=lambda s: (held_for(s) - 4.0 * appeal(s), s),
            default=None,
        )
        if leaving is not None:
            joining = max(absent, key=lambda s: (appeal(s), -order.index(s)))
            active[active.index(leaving)] = joining

    lead = _lead(active, memory, shape, avoid, activity, weights is not None)
    ranked = [lead] + sorted(
        (s for s in active if s != lead),
        key=lambda s: (-memory.levels.get(s, 0.0), -appeal(s), order.index(s)),
    )
    levels: dict[str, float] = {}
    for rank, (slot, (low, high)) in enumerate(
        zip(ranked, level_ranges(section.intensity, len(ranked)))
    ):
        previous = memory.levels.get(slot)
        if previous is not None and low - 1e-9 <= previous <= high + 1e-9:
            level = previous
        else:
            level = quantize(rng.uniform(low, high))
        if shape.rising and (rank or INTENSITY_STEP[section.intensity] < 0):
            # The lead of a build at normal or above stays at full.
            share = _BUILD_START_SHARE + (1.0 - _BUILD_START_SHARE) * progress
            level = quantize(level * share)
        levels[slot] = level

    span = max(0.0, end - start)
    for slot in ranked:
        memory.airtime[slot] = memory.airtime.get(slot, 0.0) + span
        if slot not in memory.active:
            memory.on_since[slot] = start
    memory.lead_time[lead] = memory.lead_time.get(lead, 0.0) + span
    memory.lead_phrases = memory.lead_phrases + 1 if lead == previous_lead else 1
    memory.lead = lead
    memory.active = ranked
    memory.levels = dict(levels)
    return levels, lead


def _count(
    shape: SectionShape,
    section: SongSection,
    progress: float,
    n_slots: int,
    density_bias: int,
    rng: random.Random,
) -> int:
    """Layers on for one phrase; a fraction picks its neighbours in turn."""
    first, last = shape.count
    raw = first + (last - first) * progress
    raw += INTENSITY_STEP[section.intensity] + 0.5 * density_bias
    lo, hi = layer_bounds(section.intensity, n_slots)
    raw = max(lo, min(hi, raw))
    whole = math.floor(raw)
    count = whole + (1 if rng.random() < raw - whole else 0)
    return max(lo, min(hi, count))


def _lead(
    active: Sequence[str],
    memory: _Memory,
    shape: SectionShape,
    avoid: str | None,
    activity,
    by_audio: bool,
) -> str:
    candidates = [s for s in active if s != avoid] or list(active)
    if by_audio:
        best = max(candidates, key=lambda s: (activity(s), s == memory.lead))
        return best
    keep = (
        memory.lead in candidates
        and memory.lead_phrases < shape.lead_phrases
    )
    if keep:
        assert memory.lead is not None
        return memory.lead
    others = [s for s in candidates if s != memory.lead] or candidates
    return min(others, key=lambda s: (memory.lead_time.get(s, 0.0), active.index(s)))


def _roles(
    target: tuple[dict[str, float], str],
    conductor: StemConductor | None,
    weights: PhraseWeights | None,
    slot_stems: Mapping[str, StemSource] | None,
) -> dict[str, CueRole]:
    """Roles when the conductor is on: the lead leads, drums pulse, the rest are bed."""
    if conductor is None or weights is None:
        return {}
    levels, lead = target
    stems = slot_stems or {}
    roles: dict[str, CueRole] = {}
    for slot in levels:
        if slot == lead:
            roles[slot] = "lead"
        elif stems.get(slot) == "drums" and weights.slot_activity.get(slot, 0.0) > 0.0:
            roles[slot] = "pulse"
        else:
            roles[slot] = "bed"
    return roles


def accent_slot(target: Target, held: Sequence[str]) -> str | None:
    """The layer a chorus or drop opens its accent on: a held one, not the lead."""
    if not target.roles or target.part.section.section_type not in ("chorus", "drop"):
        return None
    if not target.part.first or target.t != target.part.section.start:
        return None
    choices = [s for s in held if s in target.levels and s != target.lead]
    return choices[0] if choices else None
