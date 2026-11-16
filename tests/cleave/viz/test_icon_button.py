"""Shared icon-button geometry. No GL window."""

from __future__ import annotations

from cleave.viz.icon_button import (
    band_side,
    box_index_at,
    glyph_x,
    icon_box,
    icon_columns,
    icon_row,
    ink_origin,
    text_box,
)


def test_icon_box_is_a_square_as_tall_as_the_band() -> None:
    band = (10.0, 34.0)
    assert band_side(band) == 24.0
    assert icon_box(100.4, band) == (100.0, 10.0, 24.0, 24.0)


def test_text_box_is_the_text_plus_a_space_and_the_band_tall() -> None:
    assert text_box(50.0, 8.0, 6.0, (4.0, 26.0)) == (50.0, 4.0, 14.0, 22.0)


def test_glyph_centres_in_its_box_on_a_whole_pixel() -> None:
    assert glyph_x((100.0, 0.0, 24.0, 24.0), 16.0) == 104.0
    assert glyph_x((100.0, 0.0, 24.0, 24.0), 15.0) == 104.0


def test_columns_end_flush_right_with_the_gap_between() -> None:
    assert icon_columns(100.0, 3, 20.0, 2.0) == (36.0, 58.0, 80.0)
    assert icon_columns(100.0, 0, 20.0, 2.0) == ()


def test_row_runs_left_to_right_with_the_gap_between() -> None:
    assert icon_row(10.0, 3, 20.0, 2.0) == (10.0, 32.0, 54.0)


def test_box_index_at_finds_the_box_and_skips_the_gap() -> None:
    band = (0.0, 20.0)
    boxes = tuple(icon_box(x, band) for x in icon_row(10.0, 2, 20.0, 2.0))
    assert box_index_at(boxes, 10.0, 5.0) == 0
    assert box_index_at(boxes, 30.0, 5.0) is None
    assert box_index_at(boxes, 32.0, 19.0) == 1
    assert box_index_at(boxes, 32.0, 20.0) is None


def test_ink_origin_centres_the_painted_bounds_not_the_glyph_cell() -> None:
    # Ink 10x12 starting 3px right and 1px down from the draw origin.
    assert ink_origin((100.0, 20.0, 18.0, 18.0), (3.0, 1.0, 10.0, 12.0)) == (101.0, 22.0)
    # An odd spare pixel goes to the right and bottom margins.
    assert ink_origin((0.0, 0.0, 17.0, 17.0), (0.0, 0.0, 10.0, 12.0)) == (3.0, 2.0)
