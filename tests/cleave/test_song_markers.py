"""Tests for cleave.song_markers domain helpers."""

from __future__ import annotations

import pytest

from cleave.song_markers import (
    SongMarker,
    cycle_song_marker_type,
    format_marker_time,
    nearest_index,
    place_marker,
    song_marker_gesture_warning,
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
    assert cycle_song_marker_type("standard", forward=True) == "begin"
    assert cycle_song_marker_type("begin", forward=True) == "sustain"
    assert cycle_song_marker_type("sustain", forward=True) == "crescendo"
    assert cycle_song_marker_type("crescendo", forward=True) == "diminuendo"
    assert cycle_song_marker_type("diminuendo", forward=True) == "standard"
    assert cycle_song_marker_type("standard", forward=False) == "diminuendo"
    assert cycle_song_marker_type("begin", forward=False) == "standard"
    assert cycle_song_marker_type("crescendo", forward=False) == "sustain"


def test_song_marker_gesture_warning_orphan_begin() -> None:
    markers = [SongMarker(10.0, "begin"), SongMarker(20.0)]
    assert (
        song_marker_gesture_warning(markers, 0)
        == "begin has no crescendo/diminuendo after it"
    )


def test_song_marker_gesture_warning_orphan_sustain() -> None:
    markers = [
        SongMarker(10.0, "crescendo"),
        SongMarker(20.0, "sustain"),
        SongMarker(30.0),
    ]
    assert (
        song_marker_gesture_warning(markers, 1)
        == "sustain has no crescendo/diminuendo after it"
    )


def test_song_marker_gesture_warning_sustain_before_begin() -> None:
    markers = [
        SongMarker(10.0, "sustain"),
        SongMarker(20.0, "begin"),
        SongMarker(30.0, "crescendo"),
    ]
    assert (
        song_marker_gesture_warning(markers, 0)
        == "sustain has no crescendo/diminuendo after it"
    )
    assert song_marker_gesture_warning(markers, 1) is None


def test_song_marker_gesture_warning_peak_first() -> None:
    markers = [SongMarker(10.0, "crescendo"), SongMarker(20.0)]
    assert (
        song_marker_gesture_warning(markers, 0)
        == "crescendo has no marker before it to rise from"
    )
    markers[0] = SongMarker(10.0, "diminuendo")
    assert (
        song_marker_gesture_warning(markers, 0)
        == "diminuendo has no marker before it to rise from"
    )


def test_song_marker_gesture_warning_valid_gesture() -> None:
    markers = [
        SongMarker(10.0, "begin"),
        SongMarker(20.0, "sustain"),
        SongMarker(30.0, "crescendo"),
    ]
    assert song_marker_gesture_warning(markers, 0) is None
    assert song_marker_gesture_warning(markers, 1) is None
    assert song_marker_gesture_warning(markers, 2) is None


def test_song_marker_gesture_warning_diminuendo_info() -> None:
    markers = [SongMarker(10.0), SongMarker(20.0, "diminuendo")]
    assert (
        song_marker_gesture_warning(markers, 1)
        == "diminuendo is not generated yet"
    )
