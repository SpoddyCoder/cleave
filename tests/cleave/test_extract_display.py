"""Tests for stem source display helpers."""

from __future__ import annotations

from cleave.extract import STEM_SOURCES, stem_control_label, stem_overlay_header


def test_stem_overlay_header() -> None:
    assert stem_overlay_header("drums") == "DRUMS"
    assert stem_overlay_header("bass") == "BASS"
    assert stem_overlay_header("vocals") == "VOCALS"
    assert stem_overlay_header("other") == "OTHER"
    assert stem_overlay_header("full_mix") == "MIX"


def test_stem_control_label() -> None:
    assert stem_control_label("drums") == "drums"
    assert stem_control_label("bass") == "bass"
    assert stem_control_label("vocals") == "vocals"
    assert stem_control_label("other") == "other"
    assert stem_control_label("full_mix") == "full-mix"


def test_display_helpers_cover_all_stem_sources() -> None:
    for stem in STEM_SOURCES:
        assert stem_overlay_header(stem)
        assert stem_control_label(stem)
