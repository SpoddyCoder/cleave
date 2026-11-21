"""Tests for stem types, labels, and project wav paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from cleave.project import write_manifest
from cleave.stems import (
    FOUR_STEM_NAMES,
    SIX_STEM_NAMES,
    STEM_SOURCES,
    parse_beat_detection_stem,
    parse_stem_count,
    project_stem_count,
    stem_control_label,
    stem_names,
    stem_overlay_header,
    stem_paths,
    stem_sources,
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
    assert tuple(paths) == FOUR_STEM_NAMES
    for name, path in paths.items():
        assert path == tmp_path / "stems" / f"{name}.wav"


def test_stem_names_and_sources_per_count() -> None:
    assert stem_names(4) == FOUR_STEM_NAMES
    assert stem_names(6) == SIX_STEM_NAMES
    assert stem_sources(4) == (*FOUR_STEM_NAMES, "full_mix")
    assert stem_sources(6) == (*SIX_STEM_NAMES, "full_mix")
    assert set(stem_sources(6)) == set(STEM_SOURCES)
    with pytest.raises(ValueError, match="unsupported stem count"):
        stem_names(5)  # type: ignore[arg-type]


def test_parse_stem_count() -> None:
    assert parse_stem_count(4) == 4
    assert parse_stem_count("6") == 6
    for bad in (5, True, "six", None):
        with pytest.raises(ValueError, match="invalid stem count"):
            parse_stem_count(bad)


def test_parse_beat_detection_stem_six_stem_values() -> None:
    assert parse_beat_detection_stem("guitar") == "guitar"
    assert parse_beat_detection_stem("piano") == "piano"


def test_project_stem_count_reads_the_manifest_model(tmp_path: Path) -> None:
    assert project_stem_count(tmp_path) == 4
    write_manifest(
        tmp_path,
        slug="song",
        mix_filename="song.wav",
        original_path=tmp_path / "song.wav",
        demucs_model="htdemucs_6s",
    )
    assert project_stem_count(tmp_path) == 6
    assert tuple(stem_paths(tmp_path)) == SIX_STEM_NAMES
    assert tuple(stem_paths(tmp_path, 4)) == FOUR_STEM_NAMES
