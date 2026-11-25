"""Tests for the timeline strip's zoom-adaptive bar and beat lines."""

from __future__ import annotations

from cleave.viz.timeline_strip_grid import GridLines, grid_lines

_BARS = tuple(i * 2.0 for i in range(100))
_BEATS = tuple(i * 0.5 for i in range(400))


def _lines(start: float, end: float, *, bars=_BARS, beats=_BEATS) -> GridLines:
    return grid_lines(
        bars,
        beats,
        view_start_sec=start,
        view_end_sec=end,
        bar_width=400,
        min_label_px=40,
    )


def test_zoomed_out_draws_every_few_bars_without_beats() -> None:
    lines = _lines(0.0, 200.0)
    assert lines.bars[:3] == (0.0, 8.0, 16.0)
    assert lines.beats == ()
    assert lines.labels[:2] == ((0.0, 1), (32.0, 17))


def test_lines_stay_on_the_same_bars_while_scrolling() -> None:
    whole = set(_lines(0.0, 200.0).bars)
    scrolled = grid_lines(
        _BARS,
        _BEATS,
        view_start_sec=3.0,
        view_end_sec=197.0,
        bar_width=388,
        min_label_px=40,
    )
    assert set(scrolled.bars) <= whole


def test_zoomed_in_adds_beats_between_bars() -> None:
    lines = _lines(10.0, 20.0)
    assert lines.bars == (10.0, 12.0, 14.0, 16.0, 18.0, 20.0)
    assert lines.beats[:4] == (10.5, 11.0, 11.5, 12.5)
    assert lines.labels[0] == (10.0, 6)


def test_beats_almost_on_a_bar_are_not_doubled() -> None:
    beats = tuple(t + 0.01 for t in _BEATS)
    assert 12.01 not in _lines(10.0, 20.0, beats=beats).beats


def test_beatless_gap_does_not_change_the_step() -> None:
    gapped = tuple(t for t in _BARS if not 40.0 < t < 160.0)
    assert _lines(0.0, 20.0, bars=gapped).bars == _lines(0.0, 20.0).bars


def test_empty_grid_or_window_draws_nothing() -> None:
    assert _lines(0.0, 200.0, bars=()) == GridLines()
    assert _lines(5.0, 5.0) == GridLines()
