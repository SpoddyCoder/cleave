"""Plan a pattern mask timeline: layers come and go through the mask's wipes.

Under the pattern mask each layer gets a region of the frame, and every change
of which layers are on is an animated wipe. The wipes are the point, so:

- Two or more layers are on, except in calm and very calm sections, which
  can drop to one (an intro opening, a breakdown, an outro's end),
  and only an intense section shows all of them, so there is nearly always
  a layer to bring in.
- Every song marker changes the set, and the wipe starts on the marker.
- Between markers the set changes as often as the section's intensity asks,
  scaled by the layer changes option (``mask_options.MaskChangesPace``).
- The marker's type sets how the layers move: an intro opens out, a build
  adds layers ever faster up to a full last bar, a chorus or drop opens with
  a big change and keeps changing, a breakdown holds the fewest, a bridge
  brings in layers that were not on before, and an outro thins out.

Layer counts and timing are this mode's own; layers mode's opacity shapes do
not apply, since a hard-edged mask shows every layer at full.

Compose/compositor contract
---------------------------
This module emits ``SlotCue`` on/off (slot-set changes) and optional
``SlotCue.recast`` (preset switch on a continuing slot). Recast is not a
wipe and is not a slot-set change. Changes are at least ``transition_duration``
plus one beat apart, so each wipe plays out before the next starts.

``LayerFramePipeline.composite`` turns a slot-set change into an explicit
``MaskTransition`` (``hard_layout`` for strips/bars/radial, ``weight_field`` for
checker/plasma, or ``clear`` when duration is 0). The masked compositor
applies that command; it does not infer wipes from slot diffs.
"""

from __future__ import annotations

import bisect
import math
import random
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, TypeVar

from cleave.blend_modes import BlendMode
from cleave.cue_roles import CueRole
from cleave.signals import Signals
from cleave.song_markers import SongIntensity, SongMarker, SongSection, resolve_sections
from cleave.stems import StemSource
from cleave.timeline import (
    LEVEL_EPS,
    SlotCue,
    TimelineLane,
    canonicalize,
    lane_level_at,
)
from cleave.timeline_presets.conductor import (
    AIRTIME_PENALTY,
    CONDUCTOR_ACTIVITY_MIDPOINT,
    CONDUCTOR_GAIN_MAX,
    CONDUCTOR_GAIN_MIN,
    PhraseWeights,
    StemConductor,
)
from cleave.timeline_presets.emit import cues_from_states, levels_from_active
from cleave.timeline_presets.grid import thin_bar_times_for_arrange
from cleave.timeline_presets.mask_options import (
    DEFAULT_TIMELINE_PRESET_MASK_CHANGES,
    MaskChangesPace,
    TimelinePresetMaskChanges,
    mask_changes_pace,
)
from cleave.timeline_presets.shapes import SHAPES, Part, part_at, section_parts

FALLBACK_BAR_SEC = 2.0
_MIN_STATE_GAP = 1e-3

# Bars between layer changes inside a section, with weights, by intensity.
CHANGE_BARS: dict[SongIntensity, tuple[tuple[float, float], ...]] = {
    "very calm": ((4.0, 0.5), (8.0, 0.5)),
    "calm": ((2.0, 0.3), (4.0, 0.5), (8.0, 0.2)),
    "normal": ((1.0, 0.3), (2.0, 0.5), (4.0, 0.2)),
    "intense": ((1.0, 0.6), (2.0, 0.4)),
    "very intense": ((0.5, 0.35), (1.0, 0.65)),
}

# Layers on, fewest and most, by intensity, for up to five layers.
MASK_LAYERS: dict[SongIntensity, tuple[int, int]] = {
    "very calm": (1, 2),
    "calm": (1, 3),
    "normal": (2, 3),
    "intense": (3, 4),
    "very intense": (3, 4),
}
# With this many layers, normal and up can show one more, very intense two.
_WIDE_STACK = 6
# Intensities that may show a single layer on its own.
_SOLO_LAYER: frozenset[SongIntensity] = frozenset({"very calm", "calm"})
# Intensities that may show every layer at once.
_ALL_LAYERS: frozenset[SongIntensity] = frozenset({"intense", "very intense"})

# How a change that keeps the count is made: a swap trades one layer for
# another; otherwise one layer comes in or goes out, and the next change
# brings the count back.
_STAGGER_SWAP_P = 0.5
_MARKER_RECAST_P = 0.5
_BIG_ENTRY_RECAST_P = 0.8
_PLAIN_PRESET_BARS = 8


@dataclass(frozen=True)
class MaskMotion:
    """How a kind of section moves its layers under the mask.

    ``span`` is where the count sits in the intensity's range at the start and
    end of the run: 0 is the fewest, 1 the most. ``pace`` multiplies the bars
    between changes; with ``end_pace`` it moves from one to the other through
    the run. ``swap`` is the chance a change that keeps the count trades
    one layer for another rather than bringing one in or out.
    """

    span: tuple[float, float]
    pace: float
    swap: float
    # The count only rises (1) or only falls (-1) through the run.
    direction: int = 0
    # Changes come faster as the run goes, from ``pace`` to this, and its last
    # bar has every layer.
    end_pace: float | None = None
    # The marker swaps out most of the layers that were on.
    big_entry: bool = False
    # The marker brings in layers that were not on before.
    fresh_entry: bool = False

    @property
    def accelerate(self) -> bool:
        return self.end_pace is not None

    def pace_at(self, progress: float) -> float:
        """The pace *progress* (0 to 1) of the way through the run."""
        if self.end_pace is None:
            return self.pace
        return self.pace + (self.end_pace - self.pace) * progress


PLAIN_MOTION = MaskMotion((0.5, 0.5), 1.0, 0.5)

MOTIONS: dict[str, MaskMotion] = {
    "intro": MaskMotion((0.0, 1.0), 1.5, 0.3, direction=1),
    "verse": MaskMotion((0.5, 0.5), 1.0, 0.7),
    # A build starts sparser than a plain section and ends four times as busy.
    "build": MaskMotion((0.0, 1.0), 1.5, 0.2, direction=1, end_pace=0.25),
    "chorus": MaskMotion((0.75, 0.75), 1.0, 0.5, big_entry=True),
    "drop": MaskMotion((1.0, 1.0), 0.75, 0.8, big_entry=True),
    # A quarter up the range, so a calm breakdown is often one layer, not always.
    "breakdown": MaskMotion((0.25, 0.25), 1.5, 0.8),
    "bridge": MaskMotion((0.5, 0.5), 1.0, 0.6, fresh_entry=True),
    "outro": MaskMotion((1.0, 0.0), 1.5, 0.3, direction=-1),
}

_ChangeKind = Literal["opening", "marker", "inner", "finish"]


@dataclass(frozen=True)
class _Change:
    t: float
    kind: _ChangeKind
    part: Part
    # The run's first section starts here: count direction starts afresh.
    new_run: bool = False


@dataclass(frozen=True)
class _Grid:
    bars: tuple[float, ...]
    bar_sec: float
    beats: tuple[float, ...]
    beat_sec: float

    def position(self, t: float) -> float:
        """*t* in bars from the first bar line."""
        bars = self.bars
        i = bisect.bisect_right(bars, t) - 1
        if i < 0:
            return (t - bars[0]) / self.bar_sec
        if i >= len(bars) - 1:
            return (len(bars) - 1) + (t - bars[-1]) / self.bar_sec
        return i + (t - bars[i]) / (bars[i + 1] - bars[i])

    def time(self, position: float) -> float:
        bars = self.bars
        i = math.floor(position)
        if i < 0:
            return bars[0] + position * self.bar_sec
        if i >= len(bars) - 1:
            return bars[-1] + (position - (len(bars) - 1)) * self.bar_sec
        return bars[i] + (position - i) * (bars[i + 1] - bars[i])

    def on_beat(self, t: float) -> float:
        if not self.beats:
            return t
        i = bisect.bisect_left(self.beats, t)
        near = [b for b in self.beats[max(0, i - 1) : i + 1]]
        return min(near, key=lambda b: abs(b - t)) if near else t

    def next_beat_after(self, t: float) -> float:
        i = bisect.bisect_left(self.beats, t - 1e-9)
        return self.beats[i] if i < len(self.beats) else t


def mask_layer_range(
    intensity: SongIntensity, n_slots: int, density_bias: int = 0
) -> tuple[int, int]:
    """Fewest and most layers on under the mask in a section of *intensity*.

    Never fewer than two, except in a calm or very calm section or when there
    are only two layers, which can drop to one. Only an intense or very intense
    section shows every layer; otherwise one is always left out for the next
    wipe to bring in.
    """
    if n_slots <= 1:
        return (n_slots, n_slots)
    if n_slots == 2:
        return (1, 2)
    lo, hi = MASK_LAYERS[intensity]
    if n_slots >= _WIDE_STACK and intensity in ("normal", "intense", "very intense"):
        hi += 1
        if intensity == "very intense":
            lo += 1
            hi += 1
    hi += max(-1, min(1, density_bias))
    lo += -1 if density_bias <= -2 else (1 if density_bias >= 2 else 0)
    cap = n_slots if intensity in _ALL_LAYERS else n_slots - 1
    lo = max(1 if intensity in _SOLO_LAYER else 2, min(cap, lo))
    hi = max(lo, min(cap, hi))
    return lo, hi


def motion_for(section: SongSection) -> MaskMotion:
    return MOTIONS.get(section.section_type, PLAIN_MOTION)


def compose_pattern_mask_timeline(
    slots: Sequence[str],
    duration_sec: float,
    rng: random.Random,
    bar_times: Sequence[float],
    song_markers: Sequence[SongMarker] = (),
    density_bias: int = 0,
    signals: Signals | None = None,
    slot_stems: Mapping[str, StemSource] | None = None,
    beat_times: Sequence[float] = (),
    transition_duration: float = 0.0,
    changes: TimelinePresetMaskChanges = DEFAULT_TIMELINE_PRESET_MASK_CHANGES,
) -> dict[str, TimelineLane]:
    slot_list = list(slots)
    if not slot_list or duration_sec <= 0.0:
        return {}
    if len(slot_list) == 1:
        return cues_from_states(slot_list, [(0.0, levels_from_active(set(slot_list)))])

    grid = _grid(bar_times, beat_times, duration_sec)
    min_gap = max(float(transition_duration), 0.0) + grid.beat_sec
    parts = section_parts(resolve_sections(song_markers, duration_sec))
    schedule = _schedule(
        parts, grid, rng, min_gap, duration_sec, mask_changes_pace(changes)
    )
    spans = [
        (change.t, nxt.t)
        for change, nxt in zip(schedule, [*schedule[1:], None])
        if nxt is not None
    ] + [(schedule[-1].t, duration_sec)]
    conductor = StemConductor.build(signals, slot_stems, spans)

    planner = _Planner(
        slot_list, rng, density_bias, conductor, grid, min_gap, duration_sec
    )
    for index, change in enumerate(schedule):
        next_t = schedule[index + 1].t if index + 1 < len(schedule) else duration_sec
        planner.change(change, next_t)
    lanes = cues_from_states(slot_list, planner.states, planner.casts)
    return _apply_recasts(lanes, planner.recasts(schedule))


def _grid(
    bar_times: Sequence[float], beat_times: Sequence[float], duration_sec: float
) -> _Grid:
    bars = tuple(thin_bar_times_for_arrange(sorted(bar_times), duration_sec))
    gaps = [b - a for a, b in zip(bars, bars[1:]) if b > a]
    bar_sec = statistics.median(gaps) if gaps else FALLBACK_BAR_SEC
    if not bars:
        bars = (0.0,)
    beats = tuple(sorted(float(b) for b in beat_times if 0.0 <= b < duration_sec))
    beat_gaps = [b - a for a, b in zip(beats, beats[1:]) if b > a]
    beat_sec = statistics.median(beat_gaps) if beat_gaps else bar_sec / 4.0
    return _Grid(bars, bar_sec, beats, beat_sec)


def _schedule(
    parts: Sequence[Part],
    grid: _Grid,
    rng: random.Random,
    min_gap: float,
    duration_sec: float,
    pace: MaskChangesPace,
) -> list[_Change]:
    """Every time the layers change: each marker, then through each section."""
    out: list[_Change] = []
    for part in parts:
        section = part.section
        motion = motion_for(section)
        kind: _ChangeKind = "opening" if not out else "marker"
        out.append(_Change(section.start, kind, part, new_run=part.first))
        end = section.end
        finish: float | None = None
        last_of_run = abs(section.end - part.run_end) < 1e-6
        if motion.accelerate and last_of_run:
            t_finish = grid.time(grid.position(end) - 1.0)
            if section.start + min_gap <= t_finish <= end - min_gap:
                finish = t_finish
                end = t_finish
        t = section.start
        while True:
            bars = _weighted_choice(rng, CHANGE_BARS[section.intensity])
            bars *= motion.pace_at(part.progress(t)) * pace.scale
            bars = max(pace.grid_bars, bars)
            position = grid.position(t) + bars
            position = pace.grid_bars * math.ceil(position / pace.grid_bars - 1e-6)
            nxt = grid.on_beat(grid.time(position))
            if nxt < t + min_gap:
                nxt = grid.next_beat_after(t + min_gap)
                if nxt < t + min_gap:
                    nxt = t + min_gap
            if nxt > end - min_gap or nxt >= duration_sec:
                break
            out.append(_Change(nxt, "inner", part))
            t = nxt
        if finish is not None:
            out.append(_Change(finish, "finish", part))
    return out


class _Planner:
    """Walks the changes and decides which layers each one leaves on."""

    def __init__(
        self,
        slots: Sequence[str],
        rng: random.Random,
        density_bias: int,
        conductor: StemConductor | None,
        grid: _Grid,
        min_gap: float,
        duration_sec: float,
    ) -> None:
        self.order = list(slots)
        rng.shuffle(self.order)
        self.rng = rng
        self.density_bias = density_bias
        self.conductor = conductor
        self.grid = grid
        self.min_gap = min_gap
        self.duration_sec = duration_sec
        self.current: frozenset[str] = frozenset()
        self.airtime = {slot: 0.0 for slot in self.order}
        self.states: list[tuple[float, dict[str, float]]] = []
        self.casts: list[dict[str, tuple[CueRole, BlendMode]]] = []
        self._last_t = 0.0

    # -- decisions ------------------------------------------------------

    def change(self, change: _Change, next_t: float) -> None:
        section = change.part.section
        motion = motion_for(section)
        weights = None if self.conductor is None else self.conductor.phrase_at(change.t)
        n = len(self.order)
        lo, hi = mask_layer_range(section.intensity, n, self.density_bias)
        if motion.direction > 0 and n >= 3:
            # A rise keeps one layer back for its last bar to bring in.
            hi = min(hi, n - 1)
        # A staggered swap shows one extra layer for a moment.
        stagger = not motion.direction and len(self.current) + 1 <= max(
            hi, n - 1 if section.intensity not in _ALL_LAYERS else n
        )
        target = self._target(change, motion, weights, lo, hi)
        current = self.current
        if change.kind == "opening":
            self._emit(change.t, frozenset(self._pick(self.order, target, weights, busy=True)), weights)
            return
        if change.kind == "finish":
            # A build's last bar: every layer, for the next marker to break open.
            self._emit(change.t, frozenset(self.order), weights)
            return
        if change.kind == "marker":
            self._emit(
                change.t, self._enter(current, target, lo, motion, weights), weights
            )
            return
        count = len(current)
        rising_ok = motion.direction >= 0
        falling_ok = motion.direction <= 0
        if count < target and rising_ok:
            self._emit(change.t, self._resize(current, count + 1, weights), weights)
        elif count > target and falling_ok:
            self._emit(change.t, self._resize(current, count - 1, weights), weights)
        elif self.rng.random() < motion.swap or not (lo < hi):
            self._swap(change.t, next_t, weights, stagger=stagger)
        else:
            # Breathe: one in or out, and the next change brings the count back.
            grow = count < hi and (count <= lo or self.rng.random() < 0.5)
            if grow and rising_ok:
                self._emit(change.t, self._resize(current, count + 1, weights), weights)
            elif not grow and count > lo and falling_ok:
                self._emit(change.t, self._resize(current, count - 1, weights), weights)
            else:
                self._swap(change.t, next_t, weights, stagger=stagger)

    def _target(
        self,
        change: _Change,
        motion: MaskMotion,
        weights: PhraseWeights | None,
        lo: int,
        hi: int,
    ) -> int:
        part = change.part
        first, last = motion.span
        share = first + (last - first) * part.progress(change.t)
        if motion is PLAIN_MOTION and weights is not None:
            share = (weights.budget_gain - CONDUCTOR_GAIN_MIN) / (
                CONDUCTOR_GAIN_MAX - CONDUCTOR_GAIN_MIN
            )
            if weights.near_silent:
                share = 0.0
        raw = lo + max(0.0, min(1.0, share)) * (hi - lo)
        if motion.direction:
            target = int(math.floor(raw + 0.5))
        else:
            whole = math.floor(raw)
            target = whole + (1 if self.rng.random() < raw - whole else 0)
        target = max(lo, min(hi, target))
        if not change.new_run and self.current:
            # A rising run never loses a layer, a falling one never gains one.
            if motion.direction > 0:
                target = max(target, min(hi, len(self.current)))
            elif motion.direction < 0:
                target = min(target, max(lo, len(self.current)))
        return target

    def _enter(
        self,
        current: frozenset[str],
        target: int,
        lo: int,
        motion: MaskMotion,
        weights: PhraseWeights | None,
    ) -> frozenset[str]:
        """The set a marker opens with: always a change, bigger for some types."""
        inactive = [s for s in self.order if s not in current]
        if motion.big_entry and not inactive:
            # Out of a full stack, a big change opens up two regions.
            return self._resize(current, max(lo, len(current) - 2), weights)
        if motion.fresh_entry or motion.big_entry:
            want_new = target if motion.fresh_entry else max(2, (target + 1) // 2)
            n_new = min(len(inactive), want_new, target)
            n_keep = min(len(current), target - n_new)
            n_new = min(len(inactive), target - n_keep)
            kept = self._pick(sorted(current, key=self.order.index), n_keep, weights, busy=True)
            new = self._pick(inactive, n_new, weights, busy=True)
            out = frozenset(kept) | frozenset(new)
            if out != current:
                return out
        out = self._resize(current, target, weights)
        if out == current:
            out = self._swapped(current, weights)
        if out == current and len(current) > 1:
            # Everything is on: the marker takes one out.
            out = self._resize(current, len(current) - 1, weights)
        return out

    def _resize(
        self, current: frozenset[str], target: int, weights: PhraseWeights | None
    ) -> frozenset[str]:
        active = [s for s in self.order if s in current]
        if len(active) > target:
            gone = self._pick(active, len(active) - target, weights, busy=False)
            return current - frozenset(gone)
        inactive = [s for s in self.order if s not in current]
        new = self._pick(inactive, target - len(active), weights, busy=True)
        return current | frozenset(new)

    def _swapped(
        self, current: frozenset[str], weights: PhraseWeights | None
    ) -> frozenset[str]:
        active = [s for s in self.order if s in current]
        inactive = [s for s in self.order if s not in current]
        if not active or not inactive:
            return current
        gone = self._pick(active, 1, weights, busy=False)
        new = self._pick(inactive, 1, weights, busy=True)
        return (current - frozenset(gone)) | frozenset(new)

    def _swap(
        self,
        t: float,
        next_t: float,
        weights: PhraseWeights | None,
        *,
        stagger: bool,
    ) -> None:
        """Trade one layer for another: in one wipe, or in, then the other out."""
        current = self.current
        swapped = self._swapped(current, weights)
        if swapped == current:
            return
        joining = swapped - current
        later = self.grid.next_beat_after(t + self.min_gap)
        if later < t + self.min_gap:
            later = t + self.min_gap
        if (
            stagger
            and later <= next_t - self.min_gap
            and later < self.duration_sec
            and self.rng.random() < _STAGGER_SWAP_P
        ):
            self._emit(t, current | joining, weights)
            self._emit(later, swapped, weights)
            return
        self._emit(t, swapped, weights)

    def _pick(
        self,
        pool: Sequence[str],
        k: int,
        weights: PhraseWeights | None,
        *,
        busy: bool,
    ) -> list[str]:
        return _pick_slots(self.rng, pool, k, weights, self.airtime, prefer_busy=busy)

    # -- output ---------------------------------------------------------

    def _emit(
        self, t: float, active: frozenset[str], weights: PhraseWeights | None
    ) -> None:
        if self.states and t <= self._last_t + _MIN_STATE_GAP:
            t = self._last_t + _MIN_STATE_GAP
        if t >= self.duration_sec:
            return
        for slot in self.current:
            self.airtime[slot] += max(0.0, t - self._last_t)
        cast: dict[str, tuple[CueRole, BlendMode]] = {}
        if self.conductor is not None and weights is not None:
            cast = self.conductor.cast_for_state(active, weights)
        self.states.append((t, levels_from_active(active)))
        self.casts.append(cast)
        self.current = active
        self._last_t = t

    def recasts(self, schedule: Sequence[_Change]) -> list[tuple[str, float]]:
        """Preset changes on layers that stay on: at markers, and in long holds."""
        if not self.states:
            return []
        markers = {
            round(change.t, 6): change
            for change in schedule
            if change.kind == "marker"
        }
        out: list[tuple[str, float]] = []
        preset_start: dict[str, float] = {}
        previous: frozenset[str] = frozenset()
        times = [t for t, _levels in self.states]
        for index, (t, levels) in enumerate(self.states):
            active = frozenset(levels)
            for slot in active - previous:
                preset_start[slot] = t
            marker = markers.get(round(t, 6))
            if marker is not None:
                p = _BIG_ENTRY_RECAST_P if motion_for(marker.part.section).big_entry else _MARKER_RECAST_P
                for slot in sorted(active & previous, key=self.order.index):
                    if self.rng.random() < p:
                        out.append((slot, t))
                        preset_start[slot] = t
            end = times[index + 1] if index + 1 < len(times) else self.duration_sec
            section = _section_at(schedule, t)
            shape = None if section is None else SHAPES.get(section.section_type)
            preset_bars = _PLAIN_PRESET_BARS if shape is None else shape.preset_bars
            hold = preset_bars * self.grid.bar_sec
            room = self.grid.beat_sec
            if end - t < 2.0 * room:
                previous = active
                continue
            mid = self.grid.on_beat(self.grid.time(round(self.grid.position(0.5 * (t + end)))))
            if not t + room <= mid <= end - room:
                mid = self.grid.on_beat(0.5 * (t + end))
            if not t + room <= mid <= end - room:
                previous = active
                continue
            for slot in sorted(active, key=self.order.index):
                if mid - preset_start.get(slot, t) >= hold:
                    out.append((slot, mid))
                    preset_start[slot] = mid
            previous = active
        return out


def _section_at(schedule: Sequence[_Change], t: float) -> SongSection | None:
    for change in reversed(schedule):
        if change.t <= t + 1e-9:
            return change.part.section
    return None


_T = TypeVar("_T")


def _weighted_choice(rng: random.Random, items: Sequence[tuple[_T, float]]) -> _T:
    values = [item for item, weight in items if weight > 0.0]
    weights = [weight for _item, weight in items if weight > 0.0]
    if not values:
        return items[0][0]
    return rng.choices(values, weights=weights, k=1)[0]


def _pick_slots(
    rng: random.Random,
    pool: Sequence[str],
    k: int,
    weights: PhraseWeights | None,
    airtime: Mapping[str, float],
    *,
    prefer_busy: bool,
) -> list[str]:
    """*k* layers from *pool*: busy stems in (quiet ones out), fair on airtime."""
    remaining = list(pool)
    picked: list[str] = []
    if k <= 0:
        return picked
    n = max(len(airtime), 1)
    if weights is not None and remaining:

        def activity(slot: str) -> float:
            return float(weights.slot_activity.get(slot, 0.0))

        key = lambda slot: (activity(slot), -float(airtime.get(slot, 0.0)))  # noqa: E731
        seeded = max(remaining, key=key) if prefer_busy else min(remaining, key=key)
        picked.append(seeded)
        remaining.remove(seeded)
    while remaining and len(picked) < k:
        slot_weights = [
            _slot_weight(slot, weights, airtime, n, prefer_busy=prefer_busy)
            for slot in remaining
        ]
        choice = rng.choices(remaining, weights=slot_weights, k=1)[0]
        picked.append(choice)
        remaining.remove(choice)
    return picked


def _slot_weight(
    slot: str,
    weights: PhraseWeights | None,
    airtime: Mapping[str, float],
    n: int,
    *,
    prefer_busy: bool,
) -> float:
    even = 1.0 / max(n, 1)
    total = sum(max(0.0, float(v)) for v in airtime.values())
    share = (max(0.0, float(airtime.get(slot, 0.0))) / total) if total > 0.0 else even
    activity = CONDUCTOR_ACTIVITY_MIDPOINT
    if weights is not None:
        activity = float(weights.slot_activity.get(slot, CONDUCTOR_ACTIVITY_MIDPOINT))
    # Airtime counts double here: rotation through every layer is the show.
    penalty = 2.0 * AIRTIME_PENALTY * (share - even) * n
    if prefer_busy:
        score = (activity * activity) * 3.0 - penalty
    else:
        quiet = 1.0 - activity
        score = (quiet * quiet) * 3.0 + penalty
    return max(0.05, score + 1.0)


def _apply_recasts(
    lanes: dict[str, TimelineLane],
    recasts: Sequence[tuple[str, float]],
) -> dict[str, TimelineLane]:
    """A new preset on each layer at each time; the clip keeps its blend and role."""
    if not recasts:
        return lanes
    out = dict(lanes)
    for slot, t in recasts:
        lane = out.get(slot)
        if lane is None:
            continue
        if any(abs(cue.t - t) <= _MIN_STATE_GAP for cue in lane.cues):
            continue
        if lane_level_at(lane, t - _MIN_STATE_GAP, inherit=0.0) <= LEVEL_EPS:
            continue
        prior = next((cue for cue in reversed(lane.cues) if cue.t < t), None)
        cue = SlotCue(
            t=t,
            level=1.0,
            blend=None if prior is None else prior.blend,
            role=None if prior is None else prior.role,
            cut="none",
            recast=True,
            anchor=True,
        )
        out[slot] = TimelineLane(
            baseline=lane.baseline,
            cues=canonicalize(lane.baseline, [*lane.cues, cue]),
        )
    return out
