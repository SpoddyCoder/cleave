"""Phrase-based timeline arranger with motif scoring and voice leading."""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence

from cleave.stems import StemSource
from cleave.signals import Signals
from cleave.song_markers import SongMarker, SongSection, resolve_sections, section_at
from cleave.timeline import TimelineLane
from cleave.timeline_presets.characters import CharacterProfile, in_climax_window
from cleave.timeline_presets.chords import (
    ChordVocab,
    budget_scale_for,
    build_vocab,
    density_score_bonus,
)
from cleave.timeline_presets.conductor import PhraseWeights, StemConductor
from cleave.timeline_presets.emit import cues_from_states, levels_from_active
from cleave.timeline_presets.grid import thin_bar_times_for_arrange
from cleave.timeline_presets.motifs import (
    MIN_SWITCH_GAP_BARS,
    MIN_SWITCH_GAP_SEC,
    SOFT_LATCH_PROXIMITY_SEC,
    MotifDef,
    expand_motif,
    hamming_distance,
    motif_max_cost_resolved,
    motifs_for_profile,
    switch_gap_ok,
)
from cleave.timeline_presets.sections import (
    any_typed,
    climax_section,
    fit_layers,
    layer_range,
    section_profile,
)

# Phrase length bounds for the arranger (bar counts and wall-clock seconds).
PHRASE_BARS_MIN = 4
PHRASE_BARS_MAX = 8
PHRASE_SEC_MIN = 8.0

# Motif-pick score weight: favors fuller peaks when density_bias > 0.
_DENSITY_PICK_WEIGHT = 1.0
# Soft bias toward chords whose stems are active in the current phrase.
_CONDUCTOR_PICK_WEIGHT = 2.0
# Shortest time between switches in a fast section.
FAST_SWITCH_GAP_SEC = 3.0


def compose_timeline(
    slots: Sequence[str],
    duration_sec: float,
    profile: CharacterProfile,
    rng: random.Random,
    bar_times: Sequence[float],
    song_markers: Sequence[SongMarker] = (),
    density_bias: int = 0,
    signals: Signals | None = None,
    slot_stems: Mapping[str, StemSource] | None = None,
) -> dict[str, TimelineLane]:
    slot_list = list(slots)
    if not slot_list or duration_sec <= 0.0:
        return {}
    sections = resolve_sections(song_markers, duration_sec)
    typed = any_typed(sections)
    markers = [section.start for section in sections[1:]]
    if len(slot_list) == 1:
        return cues_from_states(
            slot_list,
            [(0.0, levels_from_active({slot_list[0]}))],
        )

    order = list(slot_list)
    rng.shuffle(order)
    vocab = build_vocab(order, density_bias=density_bias)
    motifs = motifs_for_profile(profile.motif_ids)

    bars = thin_bar_times_for_arrange(bar_times, duration_sec)
    if len(bars) < PHRASE_BARS_MIN and not markers and not typed:
        opening = frozenset({order[0]})
        return cues_from_states(
            slot_list,
            [(0.0, levels_from_active(opening))],
        )

    phrases = _partition_phrases(bars, duration_sec, rng, markers)
    if not phrases and typed:
        phrases = [(section.start, section.end) for section in sections]
    if not phrases:
        opening = frozenset({order[0]})
        return cues_from_states(
            slot_list,
            [(0.0, levels_from_active(opening))],
        )

    conductor = StemConductor.build(
        signals, slot_stems, phrases, density_bias=density_bias
    )

    states: list[tuple[float, frozenset[str]]] = []
    prev_active: frozenset[str] | None = None
    prev_motif_id: str | None = None
    motif_streak = 0
    climax_used = False
    solo_rotation = 0
    layer_airtime = {slot: 0.0 for slot in order}
    claimed_markers: set[float] = set()
    section_starts: set[float] = set()
    prev_section: SongSection | None = None
    avoid: frozenset[str] = frozenset()

    climax_phrase_index = _climax_phrase_index(phrases, duration_sec)
    climax_section_start: float | None = None
    if typed:
        climax = climax_section(sections)
        if climax is not None:
            climax_section_start = climax.start
            climax_phrase_index = next(
                (
                    i
                    for i, (start, end) in enumerate(phrases)
                    if climax.contains((start + end) * 0.5)
                ),
                None,
            )
    budget_scale = budget_scale_for(density_bias)

    for phrase_i, (phrase_start, phrase_end) in enumerate(phrases):
        midpoint = (phrase_start + phrase_end) * 0.5
        progress = midpoint / duration_sec
        weights = None if conductor is None else conductor.phrase_at(midpoint)
        budget_gain = 1.0 if weights is None else weights.budget_gain
        section = section_at(sections, midpoint)
        shape = section_profile(section)
        energy = profile.envelope(progress) if shape is None else shape.budget
        budget = max(1.0, energy * budget_scale * budget_gain)
        if climax_section_start is not None:
            climax_window = phrase_i == climax_phrase_index
        else:
            climax_window = shape is None and in_climax_window(progress)
        force_climax = (
            profile.climax_motif_id is not None
            and phrase_i == climax_phrase_index
            and not climax_used
            and (shape is None or climax_section_start is not None)
        )

        rotation = solo_rotation
        if conductor is not None and weights is not None:
            # vocab.slots is index-aligned with vocab.singles, so the returned
            # index feeds the motif rotation directly.
            rotation = conductor.rotation_for(vocab.slots, weights, layer_airtime)

        motif = _pick_motif(
            motifs=motifs,
            profile=profile,
            vocab=vocab,
            rng=rng,
            budget=budget,
            climax_window=climax_window,
            climax_used=climax_used,
            prev_active=prev_active,
            prev_motif_id=prev_motif_id,
            motif_streak=motif_streak,
            solo_rotation=rotation,
            layer_airtime=layer_airtime,
            duration_sec=duration_sec,
            force_climax=force_climax,
            conductor=conductor,
            phrase_weights=weights,
        )

        if motif.id == profile.climax_motif_id and climax_window:
            climax_used = True

        if motif.id == prev_motif_id:
            motif_streak += 1
        else:
            motif_streak = 1
        prev_motif_id = motif.id

        phrase_states = expand_motif(
            motif,
            vocab,
            rng,
            rotation,
            phrase_start,
            phrase_end,
            bars,
            duration_sec=duration_sec,
            prev_time=states[-1][0] if states else None,
            min_gap_bars=MIN_SWITCH_GAP_BARS,
            min_gap_sec=MIN_SWITCH_GAP_SEC,
            song_marker_times=markers,
            claimed_markers=claimed_markers,
            soft_latch_proximity=SOFT_LATCH_PROXIMITY_SEC,
        )
        solo_rotation += len(phrase_states)

        gap_sec = MIN_SWITCH_GAP_SEC
        if typed and section is not None:
            entering = section != prev_section
            boundary = entering and (
                section.typed or (prev_section is not None and prev_section.typed)
            )
            if entering:
                avoid = frozenset()
                if section.section_type == "bridge" and states:
                    avoid = _lead_of(states[-1], order, conductor, layer_airtime)
            activity = {} if weights is None else weights.slot_activity
            if shape is not None and shape.pace == "fast":
                gap_sec = FAST_SWITCH_GAP_SEC
            phrase_states = _section_phrase_states(
                phrase_states,
                section,
                phrase_start=phrase_start,
                phrase_end=phrase_end,
                bars=bars,
                order=order,
                density_bias=density_bias,
                activity=activity,
                airtime=layer_airtime,
                avoid=avoid,
                peak=force_climax,
            )
            if boundary and phrase_states:
                start = section.start
                first = phrase_states[0][1]
                while (
                    len(states) > 1
                    and states[-1][0] > start - MIN_SWITCH_GAP_SEC
                    and states[-1][0] not in section_starts
                ):
                    states.pop()
                prev_active = states[-1][1] if states else None
                section_starts.add(start)
                if first != prev_active:
                    states.append((start, first))
                    prev_active = first
                phrase_states = phrase_states[1:]
                for slot in first:
                    layer_airtime[slot] += max(phrase_end - start, 1e-6) / len(first)
            prev_section = section

        for t, active in phrase_states:
            if prev_active is not None and active == prev_active:
                continue
            winding_down = (
                shape is not None
                and shape.winds_down
                and section is not None
                and t >= (section.start + section.end) * 0.5 - 1e-9
            )
            if states and not winding_down:
                t = _enforce_min_bar_gap(
                    bars,
                    states[-1][0],
                    t,
                    MIN_SWITCH_GAP_BARS,
                    gap_sec,
                )
                if t is None:
                    continue
            if typed and section is not None and not section.contains(t):
                continue
            if t >= duration_sec:
                break
            states.append((t, active))
            prev_active = active
            phrase_dur = max(phrase_end - phrase_start, 1e-6)
            for slot in active:
                layer_airtime[slot] = layer_airtime.get(slot, 0.0) + phrase_dur / len(active)

    if not states:
        opening = frozenset({order[0]})
        states = [(0.0, opening)]
    elif states[0][0] != 0.0:
        states.insert(0, (0.0, states[0][1]))

    if not sections[-1].typed:
        _apply_resolve(profile, vocab, states, duration_sec, bars, rng)
    states.sort(key=lambda item: item[0])

    level_states = (
        [(t, levels_from_active(active)) for t, active in states]
        if conductor is None
        else conductor.level_states(
            states,
            duration_sec,
            keep_stack_at=lambda t: (
                section_profile(section_at(sections, t)) is not None
            ),
        )
    )
    casts = None
    if conductor is not None:
        casts = [
            conductor.cast_for_state(active, conductor.phrase_at(t))
            for t, active in states
        ]
    return cues_from_states(
        slot_list,
        level_states,
        casts,
    )


def _lead_of(
    state: tuple[float, frozenset[str]],
    order: Sequence[str],
    conductor: StemConductor | None,
    airtime: Mapping[str, float],
) -> frozenset[str]:
    """The layer leading *state*: its cast lead, else the one seen most."""
    t, active = state
    if conductor is not None:
        cast = conductor.cast_for_state(active, conductor.phrase_at(t))
        leads = frozenset(slot for slot, (role, _blend) in cast.items() if role == "lead")
        if leads:
            return leads
    present = [slot for slot in order if slot in active]
    if not present:
        return frozenset()
    return frozenset({max(present, key=lambda slot: airtime.get(slot, 0.0))})


def _section_phrase_states(
    states: Sequence[tuple[float, frozenset[str]]],
    section: SongSection,
    *,
    phrase_start: float,
    phrase_end: float,
    bars: Sequence[float],
    order: Sequence[str],
    density_bias: int,
    activity: Mapping[str, float],
    airtime: Mapping[str, float],
    avoid: frozenset[str],
    peak: bool,
) -> list[tuple[float, frozenset[str]]]:
    """A phrase's states fitted to its section's pace and layer range.

    Plain sections only lose states that fall outside them. *peak* asks for the
    most layers the section allows.
    """
    inside = [
        (max(t, section.start), active) for t, active in states if t < section.end - 1e-9
    ]
    shape = section_profile(section)
    if shape is None:
        return inside
    if not inside:
        inside = [(phrase_start, states[0][1] if states else frozenset())]
    if shape.pace == "slow":
        inside = inside[:1]
    start = section.start if phrase_start <= section.start + 1e-9 else inside[0][0]
    inside[0] = (start, inside[0][1])
    if shape.winds_down:
        half = (section.start + section.end) * 0.5
        turn = next((t for t in bars if half - 1e-9 <= t < section.end - 1e-9), half)
        if phrase_start < turn < phrase_end:
            inside.append((turn, inside[-1][1]))
    if shape.pace == "fast":
        # Keep the stack and trade one layer at a time.
        previous = start
        for t in bars:
            if previous + FAST_SWITCH_GAP_SEC - 1e-9 <= t < phrase_end - 1e-9:
                inside.append((t, frozenset()))
                previous = t
        inside = [inside[0]] + [entry for entry in inside[1:] if not entry[1]]

    fitted: list[tuple[float, frozenset[str]]] = []
    for index, (t, active) in enumerate(inside):
        lo, hi = layer_range(section, t, len(order), density_bias)
        if shape.pace == "fast" and fitted:
            active = _trade_one(fitted[-1][1], order, fitted)
        fitted.append(
            (
                t,
                fit_layers(
                    active,
                    hi if peak and index == 0 else lo,
                    hi,
                    order,
                    activity,
                    airtime,
                    avoid=avoid,
                ),
            )
        )
    return fitted


def _trade_one(
    active: frozenset[str],
    order: Sequence[str],
    fitted: Sequence[tuple[float, frozenset[str]]],
) -> frozenset[str]:
    """*active* with its longest-standing layer swapped for the longest-absent one."""

    def run(slot: str, on: bool) -> int:
        count = 0
        for _t, layers in reversed(fitted):
            if (slot in layers) != on:
                break
            count += 1
        return count

    absent = [slot for slot in order if slot not in active]
    present = [slot for slot in order if slot in active]
    if not absent or not present:
        return active
    leaving = max(present, key=lambda slot: run(slot, True))
    joining = max(absent, key=lambda slot: run(slot, False))
    return (active - {leaving}) | {joining}


def _section_bounds(
    markers: Sequence[float],
    duration_sec: float,
) -> list[tuple[float, float]]:
    cuts = [0.0, *markers, duration_sec]
    sections: list[tuple[float, float]] = []
    for start, end in zip(cuts, cuts[1:]):
        if end - start > 1e-6:
            sections.append((start, end))
    return sections


def _partition_phrases(
    bars: Sequence[float],
    duration_sec: float,
    rng: random.Random,
    song_marker_times: Sequence[float] = (),
) -> list[tuple[float, float]]:
    markers = list(song_marker_times)
    if not markers:
        return _partition_phrases_on_bars(bars, duration_sec, rng)

    phrases: list[tuple[float, float]] = []
    for sec_start, sec_end in _section_bounds(markers, duration_sec):
        section_bars = [t for t in bars if sec_start <= t < sec_end]
        section_phrases = _partition_phrases_in_section(
            section_bars, sec_start, sec_end, rng
        )
        phrases.extend(section_phrases)
    return phrases


def _partition_phrases_in_section(
    section_bars: Sequence[float],
    sec_start: float,
    sec_end: float,
    rng: random.Random,
) -> list[tuple[float, float]]:
    if sec_end - sec_start < 1e-6:
        return []
    if not section_bars:
        return [(sec_start, sec_end)]

    raw = _partition_phrases_on_bars(section_bars, sec_end, rng)
    if not raw:
        return [(sec_start, sec_end)]

    adjusted: list[tuple[float, float]] = []
    for i, (ps, pe) in enumerate(raw):
        start = sec_start if i == 0 else ps
        end = sec_end if i == len(raw) - 1 else pe
        if end - start > 1e-6:
            adjusted.append((start, end))
    return adjusted if adjusted else [(sec_start, sec_end)]


def _partition_phrases_on_bars(
    bars: Sequence[float],
    duration_sec: float,
    rng: random.Random,
) -> list[tuple[float, float]]:
    phrases: list[tuple[float, float]] = []
    i = 0
    n = len(bars)
    while i < n:
        remaining = n - i
        if remaining <= PHRASE_BARS_MAX:
            target = remaining
        else:
            target = rng.randint(PHRASE_BARS_MIN, PHRASE_BARS_MAX)
            leftover = remaining - target
            if 0 < leftover < PHRASE_BARS_MIN:
                target = remaining

        start = bars[i]
        end_i = i + target
        end = bars[end_i] if end_i < n else duration_sec

        # Extend on the thinned grid until wall-clock meets PHRASE_SEC_MIN.
        # Gaps in the bar grid may yield longer phrases; do not invent bars.
        while end - start < PHRASE_SEC_MIN - 1e-9 and end_i < n:
            end_i += 1
            end = bars[end_i] if end_i < n else duration_sec

        if end - start < 1e-6:
            break
        phrases.append((start, end))
        i = end_i
        if end >= duration_sec - 1e-6:
            break
    return phrases


def _nearest_bar_index(t: float, bars: Sequence[float]) -> int:
    return min(range(len(bars)), key=lambda i: (abs(bars[i] - t), bars[i]))


def _enforce_min_bar_gap(
    bars: Sequence[float],
    prev_t: float,
    t: float,
    min_gap_bars: int,
    min_gap_sec: float = MIN_SWITCH_GAP_SEC,
) -> float | None:
    """Keep ``t`` when gaps are already met (incl. soft-latched markers).

    Otherwise snap forward onto the bar grid.
    """
    if switch_gap_ok(prev_t, t, bars, min_gap_bars, min_gap_sec):
        return t
    if not bars:
        return None
    prev_idx = _nearest_bar_index(prev_t, bars)
    t_idx = _nearest_bar_index(t, bars)
    need_idx = prev_idx + min_gap_bars
    idx = max(t_idx, need_idx)
    while idx < len(bars):
        if (
            idx - prev_idx >= min_gap_bars
            and bars[idx] - prev_t >= min_gap_sec - 1e-9
        ):
            return bars[idx]
        idx += 1
    return None


def _bar_after_gap(
    bars: Sequence[float],
    from_t: float,
    gap_bars: int,
    min_gap_sec: float = MIN_SWITCH_GAP_SEC,
) -> float | None:
    if not bars:
        return None
    idx = _nearest_bar_index(from_t, bars)
    target = idx + gap_bars
    while target < len(bars):
        if bars[target] - from_t >= min_gap_sec - 1e-9:
            return bars[target]
        target += 1
    return None


def _climax_phrase_index(
    phrases: list[tuple[float, float]],
    duration_sec: float,
) -> int | None:
    window_start = 0.70 * duration_sec
    window_end = 0.78 * duration_sec
    best_index: int | None = None
    best_overlap = 0.0
    for i, (start, end) in enumerate(phrases):
        overlap = min(end, window_end) - max(start, window_start)
        if overlap > best_overlap:
            best_overlap = overlap
            best_index = i
    return best_index if best_overlap > 0.0 else None


def _pick_motif(
    *,
    motifs: list[MotifDef],
    profile: CharacterProfile,
    vocab: ChordVocab,
    rng: random.Random,
    budget: float,
    climax_window: bool,
    climax_used: bool,
    prev_active: frozenset[str] | None,
    prev_motif_id: str | None,
    motif_streak: int,
    solo_rotation: int,
    layer_airtime: dict[str, float],
    duration_sec: float,
    force_climax: bool = False,
    conductor: StemConductor | None = None,
    phrase_weights: PhraseWeights | None = None,
) -> MotifDef:
    if force_climax and profile.climax_motif_id is not None:
        forced = next((m for m in motifs if m.id == profile.climax_motif_id), None)
        if forced is not None:
            return forced

    candidates: list[tuple[float, MotifDef]] = []

    for motif in motifs:
        if motif.climax_only:
            if not profile.allow_tutti or not climax_window or climax_used:
                continue
        elif motif.id == profile.climax_motif_id and climax_window and not climax_used:
            pass
        else:
            resolved_cost = motif_max_cost_resolved(motif, vocab, rng, solo_rotation)
            if resolved_cost > budget + 1e-6:
                continue

        score = profile.motif_weights.get(motif.id, 1.0)
        steps = motif.resolve_steps(vocab, rng, solo_rotation)
        first_active = vocab.active_for(steps[0])
        peak_card = max(len(vocab.active_for(step)) for step in steps)
        score += density_score_bonus(
            len(vocab.slots), peak_card, vocab.density_bias
        )
        score += _DENSITY_PICK_WEIGHT * vocab.density_bias * (peak_card - 1)

        if conductor is not None and phrase_weights is not None:
            score += _CONDUCTOR_PICK_WEIGHT * conductor.chord_score(
                first_active, phrase_weights
            )

        if prev_active is not None:
            dist = hamming_distance(prev_active, first_active)
            if dist == 1:
                score += 3.0
            elif dist == 2:
                score += 1.5
            elif dist == 0:
                score += 0.5
            elif not motif.allows_boundary_jump:
                score -= 4.0

        if motif.id == prev_motif_id and motif_streak >= 2:
            score -= 2.5

        if motif.id == profile.climax_motif_id and climax_window and not climax_used:
            score += 8.0

        underrepresented = min(layer_airtime.values()) if layer_airtime else 0.0
        for slot in first_active:
            if layer_airtime.get(slot, 0.0) <= underrepresented + 1e-6:
                score += 0.4

        score += rng.random() * 0.75
        candidates.append((score, motif))

    if not candidates:
        fallback = motifs[0]
        return fallback

    candidates.sort(key=lambda item: item[0], reverse=True)
    top_score = candidates[0][0]
    top = [m for s, m in candidates if s >= top_score - 0.5]
    return rng.choice(top)


def _apply_resolve(
    profile: CharacterProfile,
    vocab: ChordVocab,
    states: list[tuple[float, frozenset[str]]],
    duration_sec: float,
    bars: Sequence[float],
    rng: random.Random,
) -> None:
    """End-state shaping: Arc resolves to sparse; never tutti at song end."""
    if profile.name != "arc" or not states:
        return
    if len(bars) < PHRASE_BARS_MIN * 2:
        return

    last_t, last_active = states[-1]
    tutti = vocab.chords.get(vocab.tutti_id or "", frozenset())
    if last_active == tutti:
        solo_id = vocab.singles[0]
        states[-1] = (last_t, vocab.active_for(solo_id))
        last_active = states[-1][1]
    elif len(last_active) > 2:
        # Resolve dense end-states toward a duo (or solo when no duos).
        resolve_id = vocab.duos[0] if vocab.duos else vocab.singles[0]
        states[-1] = (last_t, vocab.active_for(resolve_id))
        last_active = states[-1][1]

    if len(vocab.slots) <= 1:
        return

    final_t = _bar_after_gap(bars, states[-1][0], MIN_SWITCH_GAP_BARS)
    if final_t is None or final_t >= duration_sec:
        return
    solo = vocab.active_for(vocab.singles[rng.randint(0, len(vocab.singles) - 1)])
    if last_active != solo:
        states.append((final_t, solo))
