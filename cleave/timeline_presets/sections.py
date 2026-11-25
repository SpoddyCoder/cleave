"""Song-section profiles: how busy each section type is and how fast it changes.

Shared by the layers and pattern mask arrangers. Plain sections have no
profile and keep each arranger's own behaviour.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from cleave.song_markers import SongMarkerType, SongSection
from cleave.timeline_presets.chords import MAX_CONCURRENT_LAYERS

SectionPace = Literal["slow", "normal", "fast"]


@dataclass(frozen=True)
class SectionProfile:
    """Layer range at normal density, stack budget, and pace of a section type."""

    layers: tuple[int, int]
    budget: float
    pace: SectionPace
    # Density leaves the layer range alone.
    fixed: bool = False
    # Down to one layer from halfway.
    winds_down: bool = False


SECTION_PROFILES: dict[SongMarkerType, SectionProfile] = {
    "intro": SectionProfile((1, 1), 1.0, "slow", fixed=True),
    "verse": SectionProfile((1, 2), 2.2, "slow"),
    "build": SectionProfile((1, MAX_CONCURRENT_LAYERS), 4.0, "normal", fixed=True),
    "chorus": SectionProfile((3, 4), 5.5, "normal"),
    "drop": SectionProfile((4, 4), 7.0, "fast"),
    "breakdown": SectionProfile((1, 1), 1.0, "slow", fixed=True),
    "bridge": SectionProfile((1, 2), 2.2, "normal"),
    "outro": SectionProfile((2, 2), 2.2, "slow", winds_down=True),
}

# Section types whose start is a climax, strongest first.
CLIMAX_SECTION_TYPES: tuple[SongMarkerType, ...] = ("drop", "chorus")
# Section types whose start gets an accent.
ACCENT_SECTION_TYPES: frozenset[SongMarkerType] = frozenset(
    ("standard", "chorus", "drop")
)


def section_profile(section: SongSection | None) -> SectionProfile | None:
    """Profile of *section*, or None for a plain one."""
    return None if section is None else SECTION_PROFILES.get(section.section_type)


def any_typed(sections: Sequence[SongSection]) -> bool:
    return any(section.typed for section in sections)


def max_layers(n_slots: int) -> int:
    return max(1, min(n_slots, MAX_CONCURRENT_LAYERS))


def layer_range(
    section: SongSection, t: float, n_slots: int, density_bias: int
) -> tuple[int, int]:
    """Fewest and most layers on at *t* in a typed *section*."""
    profile = SECTION_PROFILES[section.section_type]
    if profile.winds_down and t >= (section.start + section.end) * 0.5 - 1e-9:
        return (1, 1)
    bias = 0 if profile.fixed else density_bias
    top = max_layers(n_slots)
    lo, hi = profile.layers
    return (max(1, min(top, lo + bias)), max(1, min(top, hi + bias)))


def climax_section(sections: Sequence[SongSection]) -> SongSection | None:
    """The last drop, else the last chorus."""
    for section_type in CLIMAX_SECTION_TYPES:
        for section in reversed(sections):
            if section.section_type == section_type:
                return section
    return None


def fit_layers(
    active: frozenset[str],
    lo: int,
    hi: int,
    order: Sequence[str],
    activity: Mapping[str, float],
    airtime: Mapping[str, float],
    *,
    avoid: frozenset[str] = frozenset(),
) -> frozenset[str]:
    """*active* with layers added or removed to count between *lo* and *hi*.

    Busier stems are kept and added first, then the layers with least airtime.
    *avoid* stays out while enough other layers remain to reach *lo*.
    """
    pool = [slot for slot in order if slot not in avoid]
    if len(pool) < lo:
        pool = list(order)
    ranked = sorted(
        pool,
        key=lambda slot: (
            -float(activity.get(slot, 0.0)),
            float(airtime.get(slot, 0.0)),
        ),
    )
    kept = [slot for slot in ranked if slot in active][:hi]
    spare = [slot for slot in ranked if slot not in kept]
    return frozenset(kept + spare[: max(0, lo - len(kept))])
