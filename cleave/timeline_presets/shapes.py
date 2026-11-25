"""What each kind of section and each intensity asks of a generated timeline.

Counts are for four layers at normal intensity and density; the tables here
are the one place to tune how busy and how bright a section looks.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import groupby
from typing import Literal

from cleave.song_markers import DEFAULT_SONG_MARKER_TYPE, SongIntensity, SongSection

ShapePace = Literal["slow", "normal", "fast"]

# Most layers on at once, and with six or more layers when very intense.
MAX_LAYERS = 4
MAX_LAYERS_VERY_INTENSE = 5
LEVEL_STEP = 0.05


@dataclass(frozen=True)
class SectionShape:
    """How a kind of section behaves across its whole run of markers.

    ``count`` is the layers on at the start and the end of the run, at normal
    intensity; a fraction alternates between its neighbours. ``phrase_bars``
    is how often the layers are reconsidered, ``lead_phrases`` how many
    phrases one layer leads, ``preset_bars`` how often a held layer changes
    preset, and ``swaps`` the chance a phrase trades one layer for another.
    """

    count: tuple[float, float]
    pace: ShapePace
    phrase_bars: int
    lead_phrases: int
    preset_bars: int
    swaps: float
    # A bridge is led by a layer that did not lead before it.
    new_lead: bool = False
    # A build's layers brighten as it goes, and its last bar is full.
    rising: bool = False


SHAPES: dict[str, SectionShape] = {
    "intro": SectionShape((1.0, 2.0), "slow", 8, 2, 16, 0.3),
    "verse": SectionShape((2.5, 2.5), "slow", 8, 2, 16, 0.6),
    "bridge": SectionShape((2.5, 2.5), "normal", 8, 2, 8, 0.6, new_lead=True),
    "build": SectionShape((1.0, 4.0), "normal", 4, 2, 8, 0.2, rising=True),
    "chorus": SectionShape((3.0, 3.0), "normal", 8, 2, 8, 0.7),
    "drop": SectionShape((3.5, 3.5), "fast", 4, 1, 4, 1.0),
    "breakdown": SectionShape((1.5, 1.5), "slow", 8, 2, 16, 0.3),
    "outro": SectionShape((2.0, 1.0), "slow", 8, 2, 16, 0.3),
}


def plain_shape(loudness: float) -> SectionShape:
    """A plain section's shape from how loud it is against the rest of the song.

    *loudness* runs from 0 (the quietest phrase) to 1 (the loudest); 0.5 is a
    verse, which is also what a song without audio analysis gets.
    """
    count = 1.5 + 2.0 * max(0.0, min(1.0, loudness))
    pace: ShapePace = "slow" if loudness < 0.5 else "normal"
    return SectionShape((count, count), pace, 8, 2, 16 if pace == "slow" else 8, 0.5)


# Layers on, by intensity, before the layer count caps it.
INTENSITY_LAYERS: dict[SongIntensity, tuple[int, int]] = {
    "very calm": (1, 1),
    "calm": (1, 2),
    "normal": (1, 4),
    "intense": (2, 4),
    "very intense": (3, 4),
}

INTENSITY_STEP: dict[SongIntensity, int] = {
    "very calm": -2,
    "calm": -1,
    "normal": 0,
    "intense": 1,
    "very intense": 2,
}

LevelRange = tuple[float, float]

# Clip opacity by rank, strongest first, for each number of layers on.
LEVELS: dict[SongIntensity, dict[int, tuple[LevelRange, ...]]] = {
    "very calm": {1: ((0.70, 0.85),)},
    "calm": {
        1: ((0.80, 0.95),),
        2: ((0.80, 0.95), (0.60, 0.75)),
    },
    "normal": {
        1: ((1.0, 1.0),),
        2: ((1.0, 1.0), (0.60, 0.90)),
        3: ((1.0, 1.0), (0.50, 0.85), (0.50, 0.75)),
        4: ((1.0, 1.0), (0.50, 0.80), (0.50, 0.70), (0.50, 0.60)),
    },
    "intense": {
        2: ((1.0, 1.0), (1.0, 1.0)),
        3: ((1.0, 1.0), (0.75, 0.90), (0.60, 0.80)),
        4: ((1.0, 1.0), (1.0, 1.0), (0.75, 0.85), (0.70, 0.80)),
    },
    "very intense": {
        3: ((1.0, 1.0), (0.95, 0.95), (0.90, 0.90)),
        4: ((1.0, 1.0), (1.0, 1.0), (1.0, 1.0), (0.80, 0.90)),
        5: ((1.0, 1.0), (1.0, 1.0), (1.0, 1.0), (0.70, 0.80), (0.60, 0.70)),
    },
}


def layer_bounds(intensity: SongIntensity, n_slots: int) -> tuple[int, int]:
    """Fewest and most layers on in a section of *intensity*."""
    cap = MAX_LAYERS
    if intensity == "very intense" and n_slots >= 6:
        cap = MAX_LAYERS_VERY_INTENSE
    cap = max(1, min(n_slots, cap))
    lo, hi = INTENSITY_LAYERS[intensity]
    hi = MAX_LAYERS_VERY_INTENSE if cap == MAX_LAYERS_VERY_INTENSE else hi
    return (min(lo, cap), min(hi, cap))


def level_ranges(intensity: SongIntensity, count: int) -> tuple[LevelRange, ...]:
    """Opacity range for each rank when *count* layers are on.

    A count the intensity's table does not list (one layer when intense, say,
    because only one exists) takes the nearest it does, and ranks past the
    table's end sit below its last.
    """
    table = LEVELS[intensity]
    nearest = min(table, key=lambda key: (abs(key - count), -key))
    ranges = list(table[nearest][:count])
    while len(ranges) < count:
        lo, hi = ranges[-1]
        ranges.append((max(0.4, lo - 0.1), max(0.45, hi - 0.1)))
    return tuple(ranges)


def quantize(level: float) -> float:
    """*level* on the generated opacity step, within ``LEVEL_STEP..1``."""
    steps = round(max(0.0, min(1.0, level)) / LEVEL_STEP)
    return max(LEVEL_STEP, min(1.0, steps * LEVEL_STEP))


@dataclass(frozen=True)
class Part:
    """One section, and where it sits in its run of same-type sections."""

    section: SongSection
    run_start: float
    run_end: float
    first: bool

    def progress(self, t: float) -> float:
        """How far through the run *t* is, 0 to 1."""
        span = self.run_end - self.run_start
        return 0.0 if span <= 0.0 else max(0.0, min(1.0, (t - self.run_start) / span))


def part_at(parts: Sequence[Part], t: float) -> Part | None:
    """The part holding *t*, or None outside the song."""
    return next((part for part in parts if part.section.contains(t)), None)


def section_parts(sections: Sequence[SongSection]) -> list[Part]:
    """Every section as a part of its run.

    Back-to-back sections of one type make one run, so a build or an outro
    spreads over all of its markers. Each plain section is a run of its own.
    """
    parts: list[Part] = []
    for section_type, group in groupby(sections, key=lambda s: s.section_type):
        run = list(group)
        runs = [[s] for s in run] if section_type == DEFAULT_SONG_MARKER_TYPE else [run]
        for members in runs:
            for position, section in enumerate(members):
                parts.append(
                    Part(section, members[0].start, members[-1].end, position == 0)
                )
    return parts
