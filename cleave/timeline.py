"""Timeline cue evaluation and editing for per-stem layer visibility."""

from __future__ import annotations

from dataclasses import dataclass

from cleave.extract import STEM_NAMES

RECORD_DEBOUNCE_SEC = 0.08

_STEM_ABBREVIATIONS = {
    "drums": "D",
    "bass": "B",
    "vocals": "V",
    "other": "O",
}


@dataclass(frozen=True)
class TimelineCue:
    t: float
    layers: dict[str, bool]


def stem_abbreviation(stem: str) -> str:
    if stem not in _STEM_ABBREVIATIONS:
        raise ValueError(f"unknown stem: {stem!r} (expected one of {', '.join(STEM_NAMES)})")
    return _STEM_ABBREVIATIONS[stem]


def layer_visible_at(
    cues: list[TimelineCue],
    defaults: dict[str, bool],
    stem: str,
    t_sec: float,
) -> bool:
    if stem not in defaults:
        raise ValueError(f"unknown stem: {stem!r} (expected one of {', '.join(STEM_NAMES)})")
    visible = defaults[stem]
    for cue in sorted(cues, key=lambda c: c.t):
        if cue.t > t_sec:
            break
        if stem in cue.layers:
            visible = cue.layers[stem]
    return visible


def visible_state_at(
    cues: list[TimelineCue],
    defaults: dict[str, bool],
    t_sec: float,
) -> dict[str, bool]:
    return {stem: layer_visible_at(cues, defaults, stem, t_sec) for stem in STEM_NAMES}


def _cue_modifies_armed_stem(cue: TimelineCue, armed_stems: set[str]) -> bool:
    return bool(set(cue.layers) & armed_stems)


def _merge_cues_at_same_t(cues: list[TimelineCue]) -> list[TimelineCue]:
    if not cues:
        return []
    merged: list[TimelineCue] = []
    current_t: float | None = None
    current_layers: dict[str, bool] = {}
    for cue in sorted(cues, key=lambda c: c.t):
        if current_t is None:
            current_t = cue.t
        elif cue.t != current_t:
            merged.append(TimelineCue(t=current_t, layers=dict(current_layers)))
            current_t = cue.t
            current_layers = {}
        current_layers.update(cue.layers)
    if current_t is not None:
        merged.append(TimelineCue(t=current_t, layers=dict(current_layers)))
    return merged


def punch_replace(
    cues: list[TimelineCue],
    armed_stems: set[str],
    start_sec: float,
    stop_sec: float,
    new_cues: list[TimelineCue],
) -> list[TimelineCue]:
    kept = [
        cue
        for cue in cues
        if not (
            start_sec <= cue.t <= stop_sec
            and _cue_modifies_armed_stem(cue, armed_stems)
        )
    ]
    combined = kept + list(new_cues)
    return _merge_cues_at_same_t(combined)


def should_accept_toggle(last_toggle_t: float | None, t_sec: float) -> bool:
    if last_toggle_t is None:
        return True
    return t_sec - last_toggle_t >= RECORD_DEBOUNCE_SEC
