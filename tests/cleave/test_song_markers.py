"""Tests for cleave.song_markers domain helpers."""

from __future__ import annotations

import pytest

from cleave.song_markers import (
    SongMarker,
    cycle_song_marker_type,
    format_marker_time,
    nearest_index,
    place_marker,
)


def test_place_marker_insert_sorted() -> None:
    markers, replaced_index, replaced_time = place_marker(
        (SongMarker(10.0), SongMarker(30.0)), 20.0
    )
    assert markers == (SongMarker(10.0), SongMarker(20.0), SongMarker(30.0))
    assert replaced_index is None
    assert replaced_time is None


def test_place_marker_insert_empty() -> None:
    markers, replaced_index, replaced_time = place_marker((), 12.5)
    assert markers == (SongMarker(12.5),)
    assert replaced_index is None
    assert replaced_time is None


def test_place_marker_replace_within_2s() -> None:
    markers, replaced_index, replaced_time = place_marker(
        (SongMarker(10.0, "crescendo"), SongMarker(30.0)), 11.5
    )
    assert markers == (SongMarker(11.5, "crescendo"), SongMarker(30.0))
    assert replaced_index == 0
    assert replaced_time == 10.0


def test_place_marker_replace_nearest_of_two() -> None:
    markers, replaced_index, replaced_time = place_marker(
        (SongMarker(10.0), SongMarker(12.0)), 10.5
    )
    assert markers == (SongMarker(10.5), SongMarker(12.0))
    assert replaced_index == 0
    assert replaced_time == 10.0

    markers, replaced_index, replaced_time = place_marker(
        (SongMarker(10.0), SongMarker(12.0, "diminuendo")), 11.5
    )
    assert markers == (SongMarker(10.0), SongMarker(11.5, "diminuendo"))
    assert replaced_index == 1
    assert replaced_time == 12.0


def test_place_marker_outside_window_inserts() -> None:
    markers, replaced_index, replaced_time = place_marker(
        (SongMarker(10.0), SongMarker(20.0)), 13.0
    )
    assert markers == (SongMarker(10.0), SongMarker(13.0), SongMarker(20.0))
    assert replaced_index is None
    assert replaced_time is None


def test_place_marker_window_boundary_replaces() -> None:
    markers, replaced_index, replaced_time = place_marker(
        (SongMarker(10.0),), 12.0
    )
    assert markers == (SongMarker(12.0),)
    assert replaced_index == 0
    assert replaced_time == 10.0


def test_nearest_index() -> None:
    assert nearest_index((10.0, 20.0, 30.0), 21.0) == 1
    assert nearest_index((10.0, 20.0), 15.0) == 0  # earlier on tie


def test_nearest_index_empty_raises() -> None:
    with pytest.raises(ValueError, match="at least one song marker"):
        nearest_index((), 1.0)


def test_format_marker_time() -> None:
    assert format_marker_time(0.0) == "00:00.00"
    assert format_marker_time(65.0) == "01:05.00"
    assert format_marker_time(65.123) == "01:05.12"
    assert format_marker_time(65.129) == "01:05.13"
    assert format_marker_time(125.456) == "02:05.46"
    assert format_marker_time(-1.0) == "00:00.00"


def test_cycle_song_marker_type() -> None:
    assert cycle_song_marker_type("standard", forward=True) == "crescendo"
    assert cycle_song_marker_type("crescendo", forward=True) == "diminuendo"
    assert cycle_song_marker_type("diminuendo", forward=True) == "standard"
    assert cycle_song_marker_type("standard", forward=False) == "diminuendo"
    assert cycle_song_marker_type("crescendo", forward=False) == "standard"
