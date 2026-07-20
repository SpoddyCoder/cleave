"""Timeline preset characters: energy envelopes, profiles, and help copy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


def _arc_envelope(progress: float) -> float:
    if progress < 0.15:
        return 1.0
    if progress < 0.45:
        return 2.2
    if progress < 0.70:
        return 4.0
    if progress < 0.78:
        return 7.5
    if progress < 0.88:
        return 1.5
    return 2.2


def _breathing_envelope(progress: float) -> float:
    if progress < 0.20:
        return 1.0
    if progress < 0.75:
        return 2.2
    if progress < 0.90:
        return 1.0
    return 1.5


def _dialogue_envelope(progress: float) -> float:
    if progress < 0.15:
        return 1.0
    if progress < 0.85:
        return 2.2
    return 1.5


def _pulse_envelope(progress: float) -> float:
    if progress < 0.10:
        return 1.0
    if progress < 0.80:
        return 2.2
    if progress < 0.92:
        return 4.0
    return 1.5


def in_climax_window(progress: float) -> bool:
    return 0.70 <= progress < 0.78


@dataclass(frozen=True)
class CharacterProfile:
    name: str
    envelope: Callable[[float], float]
    allow_tutti: bool
    motif_ids: tuple[str, ...]
    motif_weights: dict[str, float]
    climax_motif_id: str | None = None


BREATHING = CharacterProfile(
    name="breathing",
    envelope=_breathing_envelope,
    allow_tutti=False,
    motif_ids=("solo_hold", "duo_breathe", "shed"),
    motif_weights={
        "solo_hold": 4.0,
        "duo_breathe": 2.0,
        "shed": 1.0,
    },
)

DIALOGUE = CharacterProfile(
    name="dialogue",
    envelope=_dialogue_envelope,
    allow_tutti=False,
    motif_ids=("solo_hold", "call_response", "antiphony", "duo_breathe"),
    motif_weights={
        "call_response": 4.0,
        "antiphony": 3.0,
        "solo_hold": 2.0,
        "duo_breathe": 1.5,
    },
)

ARC = CharacterProfile(
    name="arc",
    envelope=_arc_envelope,
    allow_tutti=True,
    motif_ids=(
        "solo_hold",
        "duo_breathe",
        "call_response",
        "stack_up",
        "shed",
        "flash_tutti",
    ),
    motif_weights={
        "solo_hold": 2.5,
        "duo_breathe": 2.0,
        "call_response": 1.5,
        "stack_up": 2.0,
        "shed": 1.5,
        "flash_tutti": 0.5,
    },
    climax_motif_id="flash_tutti",
)

PULSE = CharacterProfile(
    name="pulse",
    envelope=_pulse_envelope,
    allow_tutti=False,
    motif_ids=("rotate_solo", "duo_breathe", "solo_hold"),
    motif_weights={
        "rotate_solo": 5.0,
        "duo_breathe": 1.5,
        "solo_hold": 1.0,
    },
)

CHARACTERS: dict[str, CharacterProfile] = {
    "breathing": BREATHING,
    "dialogue": DIALOGUE,
    "arc": ARC,
    "pulse": PULSE,
}

TIMELINE_PRESET_KIND_OPTIONS: tuple[str, ...] = tuple(CHARACTERS)
DEFAULT_TIMELINE_PRESET_KIND = "breathing"

_CHARACTER_DISPLAY: dict[str, str] = {
    "breathing": "breathing",
    "dialogue": "dialogue",
    "arc": "arc",
    "pulse": "pulse",
}

CHARACTER_HELP_ENTRIES: tuple[tuple[str, str], ...] = (
    ("Breathing", "sparse singles and rare duos; no tutti stacks."),
    ("Dialogue", "call/response and antiphony between layers."),
    ("Arc", "builds to one short climax flash, then breathes and resolves."),
    ("Pulse", "rotates solo layers with sparse duo accents."),
)


def timeline_preset_kind_display(kind: str) -> str:
    return _CHARACTER_DISPLAY.get(kind, _CHARACTER_DISPLAY[DEFAULT_TIMELINE_PRESET_KIND])


def cycle_timeline_preset_kind(value: str, *, forward: bool) -> str:
    options = TIMELINE_PRESET_KIND_OPTIONS
    try:
        index = options.index(value)
    except ValueError:
        index = options.index(DEFAULT_TIMELINE_PRESET_KIND)
    delta = 1 if forward else -1
    return options[(index + delta) % len(options)]
