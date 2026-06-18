"""Tests for the per-stem cleave effects registry."""

from __future__ import annotations

import pytest

from cleave.effects.registry import (
    DRIVER_SLUGS,
    EFFECT_IDS,
    effect_roster,
    effect_row_count,
    validate_effect_entry,
)
from cleave.effects.handlers import EFFECT_HANDLERS
from cleave.extract import STEM_NAMES


def test_effect_ids_and_driver_slugs() -> None:
    assert EFFECT_IDS == frozenset({"pulse", "flare", "flash", "hue", "grit"})
    assert DRIVER_SLUGS == frozenset(
        {"onset", "sub_bass", "mid_bass", "rms", "pitch", "centroid"}
    )


@pytest.mark.parametrize(
    ("stem", "expected_count", "expected_rows"),
    [
        (
            "drums",
            4,
            [
                ("pulse", "onset"),
                ("flare", "onset"),
                ("flash", "onset"),
                ("grit", "onset"),
            ],
        ),
        (
            "bass",
            4,
            [
                ("pulse", "sub_bass"),
                ("pulse", "mid_bass"),
                ("flash", "sub_bass"),
                ("grit", "sub_bass"),
            ],
        ),
        (
            "vocals",
            4,
            [
                ("pulse", "rms"),
                ("hue", "pitch"),
                ("flash", "rms"),
                ("grit", "rms"),
            ],
        ),
        (
            "other",
            3,
            [
                ("pulse", "centroid"),
                ("flash", "centroid"),
                ("grit", "centroid"),
            ],
        ),
    ],
)
def test_effect_roster_per_stem(
    stem: str,
    expected_count: int,
    expected_rows: list[tuple[str, str]],
) -> None:
    roster = effect_roster(stem)
    assert effect_row_count(stem) == expected_count
    assert len(roster) == expected_count
    rows = [(row.effect_id, row.driver_slug) for row in roster]
    assert rows == expected_rows


def test_validate_effect_entry_rejects_unknown_effect() -> None:
    with pytest.raises(ValueError, match="unknown effect"):
        validate_effect_entry("drums", "ripple", "onset")


def test_validate_effect_entry_rejects_roster_mismatch() -> None:
    with pytest.raises(ValueError, match="not in roster"):
        validate_effect_entry("drums", "hue", "pitch")


def test_all_stems_have_rosters() -> None:
    for stem in STEM_NAMES:
        assert effect_row_count(stem) >= 3


def test_every_effect_id_has_handler() -> None:
    assert EFFECT_HANDLERS.keys() == set(EFFECT_IDS)
    for effect_id in EFFECT_IDS:
        assert effect_id in EFFECT_HANDLERS
        handler = EFFECT_HANDLERS[effect_id]
        assert handler.effect_id == effect_id
