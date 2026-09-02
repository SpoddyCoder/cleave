"""Procedural timeline preset cue generation."""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence

from cleave.stems import StemSource
from cleave.signals import Signals
from cleave.timeline import TimelineLane
from cleave.timeline_presets.arrange import PHRASE_SEC_MIN, compose_timeline
from cleave.timeline_presets.pattern_mask_arrange import (
    SECTION_BARS_MAX,
    SECTION_BARS_MIN,
    SECTION_BARS_WEIGHTS,
    SECTION_LONG_BARS_MAX,
    SECTION_LONG_BARS_MIN,
    SECTION_LONG_WEIGHT,
    SECTION_SEC_MIN,
    compose_pattern_mask_timeline,
    partition_pattern_mask_sections,
)
from cleave.timeline_presets.characters import (
    ARC,
    BREATHING,
    CHARACTER_HELP_ENTRIES,
    DIALOGUE,
    PULSE,
)
from cleave.timeline_presets.motifs import (
    MIN_SWITCH_GAP_BARS,
    MIN_SWITCH_GAP_SEC,
    SOFT_LATCH_PROXIMITY_SEC,
)

_RESET_HELP_ENTRIES: tuple[tuple[str, str], ...] = (
    ("All Off", "clear cues; every layer off for the whole track."),
    ("All On", "clear cues; every layer on for the whole track."),
)

TIMELINE_PRESET_HELP_ENTRIES: tuple[tuple[str, str], ...] = CHARACTER_HELP_ENTRIES

TIMELINE_RESET_HELP_ENTRIES: tuple[tuple[str, str], ...] = _RESET_HELP_ENTRIES

__all__ = (
    "ALL_BUILDERS",
    "MIN_SWITCH_GAP_BARS",
    "MIN_SWITCH_GAP_SEC",
    "PHRASE_SEC_MIN",
    "SECTION_BARS_MAX",
    "SECTION_BARS_MIN",
    "SECTION_BARS_WEIGHTS",
    "SECTION_LONG_BARS_MAX",
    "SECTION_LONG_BARS_MIN",
    "SECTION_LONG_WEIGHT",
    "SECTION_SEC_MIN",
    "SOFT_LATCH_PROXIMITY_SEC",
    "TIMELINE_PRESET_HELP_ENTRIES",
    "TIMELINE_RESET_HELP_ENTRIES",
    "build_arc_cues",
    "build_breathing_cues",
    "build_dialogue_cues",
    "build_pulse_cues",
    "compose_pattern_mask_timeline",
    "partition_pattern_mask_sections",
)


def _rng(rng: random.Random | None) -> random.Random:
    return rng if rng is not None else random.Random()


def build_breathing_cues(
    slots: Sequence[str],
    duration_sec: float,
    rng: random.Random | None = None,
    bar_times: Sequence[float] = (),
    song_marker_times: Sequence[float] = (),
    density_bias: int = 0,
    signals: Signals | None = None,
    slot_stems: Mapping[str, StemSource] | None = None,
) -> dict[str, TimelineLane]:
    return compose_timeline(
        slots,
        duration_sec,
        BREATHING,
        _rng(rng),
        bar_times,
        song_marker_times=song_marker_times,
        density_bias=density_bias,
        signals=signals,
        slot_stems=slot_stems,
    )


def build_dialogue_cues(
    slots: Sequence[str],
    duration_sec: float,
    rng: random.Random | None = None,
    bar_times: Sequence[float] = (),
    song_marker_times: Sequence[float] = (),
    density_bias: int = 0,
    signals: Signals | None = None,
    slot_stems: Mapping[str, StemSource] | None = None,
) -> dict[str, TimelineLane]:
    return compose_timeline(
        slots,
        duration_sec,
        DIALOGUE,
        _rng(rng),
        bar_times,
        song_marker_times=song_marker_times,
        density_bias=density_bias,
        signals=signals,
        slot_stems=slot_stems,
    )


def build_arc_cues(
    slots: Sequence[str],
    duration_sec: float,
    rng: random.Random | None = None,
    bar_times: Sequence[float] = (),
    song_marker_times: Sequence[float] = (),
    density_bias: int = 0,
    signals: Signals | None = None,
    slot_stems: Mapping[str, StemSource] | None = None,
) -> dict[str, TimelineLane]:
    return compose_timeline(
        slots,
        duration_sec,
        ARC,
        _rng(rng),
        bar_times,
        song_marker_times=song_marker_times,
        density_bias=density_bias,
        signals=signals,
        slot_stems=slot_stems,
    )


def build_pulse_cues(
    slots: Sequence[str],
    duration_sec: float,
    rng: random.Random | None = None,
    bar_times: Sequence[float] = (),
    song_marker_times: Sequence[float] = (),
    density_bias: int = 0,
    signals: Signals | None = None,
    slot_stems: Mapping[str, StemSource] | None = None,
) -> dict[str, TimelineLane]:
    return compose_timeline(
        slots,
        duration_sec,
        PULSE,
        _rng(rng),
        bar_times,
        song_marker_times=song_marker_times,
        density_bias=density_bias,
        signals=signals,
        slot_stems=slot_stems,
    )


ALL_BUILDERS = (
    build_breathing_cues,
    build_dialogue_cues,
    build_arc_cues,
    build_pulse_cues,
)
