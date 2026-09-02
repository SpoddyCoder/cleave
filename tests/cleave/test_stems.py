"""Tests for stem types, labels, and project wav paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from cleave.stems import (
    STEM_NAMES,
    STEM_SOURCES,
    parse_beat_detection_stem,
    stem_control_label,
    stem_overlay_header,
    stem_paths,
    stems_dir,
)


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


def test_parse_beat_detection_stem() -> None:
    assert parse_beat_detection_stem("drums") == "drums"
    assert parse_beat_detection_stem("full-mix") == "full_mix"
    with pytest.raises(ValueError, match="invalid beat detection stem"):
        parse_beat_detection_stem("full_mix")


def test_stems_dir_and_stem_paths(tmp_path: Path) -> None:
    assert stems_dir(tmp_path) == tmp_path / "stems"
    paths = stem_paths(tmp_path)
    assert tuple(paths) == STEM_NAMES
    for name, path in paths.items():
        assert path == tmp_path / "stems" / f"{name}.wav"
