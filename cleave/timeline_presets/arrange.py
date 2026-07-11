"""Phrase-based timeline arranger with motif scoring and voice leading."""

from __future__ import annotations

import random
from collections.abc import Sequence

from cleave.timeline import TimelineLane
from cleave.timeline_presets.busyness import (
    MIN_SWITCH_GAP_SEC,
    CharacterProfile,
    in_climax_window,
)
from cleave.timeline_presets.chords import ChordVocab, build_vocab
from cleave.timeline_presets.emit import cues_from_states
from cleave.timeline_presets.motifs import (
    MotifDef,
    expand_motif,
    hamming_distance,
    motif_max_cost_resolved,
    motifs_for_profile,
)


def compose_timeline(
    slots: Sequence[str],
    duration_sec: float,
    profile: CharacterProfile,
    rng: random.Random,
) -> dict[str, TimelineLane]:
    slot_list = list(slots)
    if not slot_list or duration_sec <= 0.0:
        return {}
    if len(slot_list) == 1:
        return cues_from_states(slot_list, [(0.0, frozenset({slot_list[0]}))])

    order = list(slot_list)
    rng.shuffle(order)
    vocab = build_vocab(order)
    motifs = motifs_for_profile(profile.motif_ids)

    if duration_sec <= MIN_SWITCH_GAP_SEC:
        opening = frozenset({order[0]})
        return cues_from_states(slot_list, [(0.0, opening)])

    phrases = _partition_phrases(duration_sec, rng)
    if not phrases:
        opening = frozenset({order[0]})
        return cues_from_states(slot_list, [(0.0, opening)])

    states: list[tuple[float, frozenset[str]]] = []
    prev_active: frozenset[str] | None = None
    prev_motif_id: str | None = None
    motif_streak = 0
    climax_used = False
    solo_rotation = 0
    layer_airtime = {slot: 0.0 for slot in order}

    climax_phrase_index = _climax_phrase_index(phrases, duration_sec)

    for phrase_i, (phrase_start, phrase_end) in enumerate(phrases):
        progress = (phrase_start + phrase_end) * 0.5 / duration_sec
        budget = profile.envelope(progress)
        climax_window = in_climax_window(progress)
        force_climax = (
            profile.climax_motif_id is not None
            and phrase_i == climax_phrase_index
            and not climax_used
        )

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
            solo_rotation=solo_rotation,
            layer_airtime=layer_airtime,
            duration_sec=duration_sec,
            force_climax=force_climax,
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
            solo_rotation,
            phrase_start,
            phrase_end,
            MIN_SWITCH_GAP_SEC,
            duration_sec=duration_sec,
            prev_time=states[-1][0] if states else None,
        )
        solo_rotation += len(phrase_states)

        for t, active in phrase_states:
            if prev_active is not None and active == prev_active:
                continue
            if states and t - states[-1][0] < MIN_SWITCH_GAP_SEC:
                t = states[-1][0] + MIN_SWITCH_GAP_SEC
            if t >= duration_sec:
                break
            states.append((t, active))
            prev_active = active
            phrase_dur = max(phrase_end - phrase_start, MIN_SWITCH_GAP_SEC * 0.5)
            for slot in active:
                layer_airtime[slot] = layer_airtime.get(slot, 0.0) + phrase_dur / len(active)

    if not states or states[0][0] != 0.0:
        opening = states[0][1] if states else frozenset({order[0]})
        if states and states[0][0] != 0.0:
            states.insert(0, (0.0, opening))
        elif not states:
            states = [(0.0, opening)]

    _apply_resolve(profile, vocab, states, duration_sec, rng)
    states.sort(key=lambda item: item[0])

    return cues_from_states(slot_list, states)


def _partition_phrases(duration_sec: float, rng: random.Random) -> list[tuple[float, float]]:
    phrases: list[tuple[float, float]] = []
    t = 0.0
    while t < duration_sec - 1e-6:
        remaining = duration_sec - t
        if remaining <= MIN_SWITCH_GAP_SEC:
            break
        target = rng.uniform(8.0, min(16.0, remaining))
        if remaining - target < MIN_SWITCH_GAP_SEC * 0.5 and len(phrases) > 0:
            target = remaining
        phrase_end = min(t + target, duration_sec)
        if phrase_end - t < MIN_SWITCH_GAP_SEC * 0.75 and phrases:
            phrase_end = duration_sec
        if phrase_end - t < 1e-6:
            break
        phrases.append((t, phrase_end))
        t = phrase_end
        if t >= duration_sec - 1e-6:
            break
    return phrases


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
    rng: random.Random,
) -> None:
    """End-state shaping: Arc resolves to sparse; never tutti at song end."""
    if profile.name != "arc" or not states:
        return
    if duration_sec < MIN_SWITCH_GAP_SEC * 3:
        return

    last_t, last_active = states[-1]
    tutti = vocab.chords.get(vocab.tutti_id or "", frozenset())
    if last_active == tutti:
        solo_id = vocab.singles[0]
        states[-1] = (last_t, vocab.active_for(solo_id))
        last_active = states[-1][1]
    elif len(last_active) > 2:
        duo_id = vocab.duos[0] if vocab.duos else vocab.singles[0]
        states[-1] = (last_t, vocab.active_for(duo_id))
        last_active = states[-1][1]

    if len(vocab.slots) <= 1:
        return

    final_t = states[-1][0] + MIN_SWITCH_GAP_SEC
    if final_t >= duration_sec:
        return
    solo = vocab.active_for(vocab.singles[rng.randint(0, len(vocab.singles) - 1)])
    if last_active != solo:
        states.append((final_t, solo))
