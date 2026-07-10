"""Procedural timeline preset cue generation."""

from __future__ import annotations

import random
from collections.abc import Sequence

from cleave.timeline import TimelineCue
from cleave.timeline_presets.arrange import compose_timeline
from cleave.timeline_presets.busyness import (
    ARC,
    BREATHING,
    DIALOGUE,
    MIN_SWITCH_GAP_SEC,
    PHI,
    PULSE,
    TIMELINE_PRESET_HELP_ENTRIES,
)

__all__ = (
    "ALL_BUILDERS",
    "MIN_SWITCH_GAP_SEC",
    "PHI",
    "TIMELINE_PRESET_HELP_ENTRIES",
    "build_arc_cues",
    "build_breathing_cues",
    "build_dialogue_cues",
    "build_pulse_cues",
)


def _rng(rng: random.Random | None) -> random.Random:
    return rng if rng is not None else random.Random()


def build_breathing_cues(
    slots: Sequence[str],
    duration_sec: float,
    rng: random.Random | None = None,
) -> list[TimelineCue]:
    return compose_timeline(slots, duration_sec, BREATHING, _rng(rng))


def build_dialogue_cues(
    slots: Sequence[str],
    duration_sec: float,
    rng: random.Random | None = None,
) -> list[TimelineCue]:
    return compose_timeline(slots, duration_sec, DIALOGUE, _rng(rng))


def build_arc_cues(
    slots: Sequence[str],
    duration_sec: float,
    rng: random.Random | None = None,
) -> list[TimelineCue]:
    return compose_timeline(slots, duration_sec, ARC, _rng(rng))


def build_pulse_cues(
    slots: Sequence[str],
    duration_sec: float,
    rng: random.Random | None = None,
) -> list[TimelineCue]:
    return compose_timeline(slots, duration_sec, PULSE, _rng(rng))


ALL_BUILDERS = (
    build_breathing_cues,
    build_dialogue_cues,
    build_arc_cues,
    build_pulse_cues,
)
