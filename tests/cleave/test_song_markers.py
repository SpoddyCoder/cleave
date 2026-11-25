"""Tests for cleave.song_markers domain helpers."""

from __future__ import annotations

import pytest

from cleave.song_markers import (
    SongMarker,
    step_song_marker_type,
    format_marker_time,
    nearest_index,
    place_marker,
    snap_markers,
    resolve_sections,
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
    # The first marker also starts the song's first section.
    assert markers == (SongMarker(0.0), SongMarker(12.5))
    assert place_marker((), 0.0, marker_type="intro")[0] == (SongMarker(0.0, "intro"),)
    assert replaced_index is None
    assert replaced_time is None


def test_place_marker_replace_within_2s() -> None:
    markers, replaced_index, replaced_time = place_marker(
        (SongMarker(10.0, "chorus"), SongMarker(30.0)), 11.5
    )
    assert markers == (SongMarker(11.5, "chorus"), SongMarker(30.0))
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
        (SongMarker(10.0), SongMarker(12.0, "drop")), 11.5
    )
    assert markers == (SongMarker(10.0), SongMarker(11.5, "drop"))
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


def test_step_song_marker_type() -> None:
    assert step_song_marker_type("standard", forward=True) == "intro"
    assert step_song_marker_type("verse", forward=True) == "build"
    assert step_song_marker_type("outro", forward=True) == "outro"
    assert step_song_marker_type("standard", forward=False) == "standard"
    assert step_song_marker_type("intro", forward=False) == "standard"


def test_place_marker_type_wins_over_a_replaced_marker() -> None:
    markers, *_ = place_marker((SongMarker(10.0, "verse"),), 10.5, marker_type="drop")
    assert markers == (SongMarker(10.5, "drop"),)
    markers, *_ = place_marker((), 4.0, marker_type="intro")
    assert markers == (SongMarker(0.0), SongMarker(4.0, "intro"))
    markers, *_ = place_marker(markers, 30.0, marker_type="outro")
    assert markers[-1] == SongMarker(30.0, "outro")


def test_resolve_sections_cover_the_song() -> None:
    def spans(markers):
        return [
            (s.start, s.end, s.section_type) for s in resolve_sections(markers, 60.0)
        ]

    assert spans([]) == [(0.0, 60.0, "standard")]
    assert spans([SongMarker(0.0, "intro")]) == [(0.0, 60.0, "intro")]
    assert spans(
        [
            SongMarker(30.0),
            SongMarker(10.0, "chorus"),
            SongMarker(10.0, "verse"),
            SongMarker(60.0, "outro"),
            SongMarker(-1.0, "drop"),
        ]
    ) == [
        (0.0, 10.0, "standard"),
        (10.0, 30.0, "chorus"),
        (30.0, 60.0, "standard"),
    ]


def test_snap_markers_merges_and_maps_indices() -> None:
    markers, indices = snap_markers(
        (SongMarker(3.9), SongMarker(4.2, "chorus"), SongMarker(9.0, "verse")),
        lambda t: round(t / 4.0) * 4.0,
    )
    assert markers == (SongMarker(4.0, "chorus"), SongMarker(8.0, "verse"))
    assert indices == (0, 0, 1)


def test_intensity_survives_replace_and_retype() -> None:
    markers, *_ = place_marker((SongMarker(10.0, "verse", "calm"),), 10.5)
    assert markers == (SongMarker(10.5, "verse", "calm"),)
    markers, *_ = place_marker(markers, 10.5, marker_type="drop")
    assert markers == (SongMarker(10.5, "drop", "calm"),)


def test_snap_merges_type_and_intensity_separately() -> None:
    markers, _indices = snap_markers(
        (
            SongMarker(3.9, intensity="calm"),
            SongMarker(4.2, "chorus", "intense"),
            SongMarker(9.0, "verse", "intense"),
        ),
        lambda t: round(t / 4.0) * 4.0,
    )
    assert markers == (
        SongMarker(4.0, "chorus", "calm"),
        SongMarker(8.0, "verse", "intense"),
    )


def test_sections_carry_intensity() -> None:
    sections = resolve_sections([SongMarker(10.0, "drop", "calm")], 30.0)
    assert [section.intensity for section in sections] == ["normal", "calm"]
