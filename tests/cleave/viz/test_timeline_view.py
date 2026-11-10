"""Strip view window: zoom, pan, and playhead follow."""

from __future__ import annotations

import pytest

from cleave.viz.timeline_view import MIN_VIEW_SPAN_SEC, StripView


def test_default_window_is_the_whole_song() -> None:
    view = StripView()
    assert view.window(100.0) == (0.0, 100.0)
    assert view.window(0.0) == (0.0, 0.0)
    assert not view.zoomed


def test_zoom_keeps_the_anchor_in_place() -> None:
    view = StripView()
    view.zoom_at(25.0, 2.0, 100.0)
    start, end = view.window(100.0)
    assert end - start == pytest.approx(50.0)
    # 25s was a quarter of the way across and still is.
    assert (25.0 - start) / (end - start) == pytest.approx(0.25)
    view.zoom_at(30.0, 2.0, 100.0)
    start2, end2 = view.window(100.0)
    assert (30.0 - start2) / (end2 - start2) == pytest.approx((30.0 - start) / 50.0)


def test_zoom_clamps_at_the_shortest_window_and_the_whole_song() -> None:
    view = StripView()
    view.zoom_at(50.0, 1e6, 100.0)
    assert view.span_sec == MIN_VIEW_SPAN_SEC
    view.zoom_at(50.0, 1e-6, 100.0)
    assert view.span_sec is None and view.start_sec == 0.0
    short = StripView()
    short.zoom_at(0.2, 4.0, 0.5)
    assert short.window(0.5) == (0.0, 0.5)


def test_zoom_out_near_a_song_end_stays_inside_the_song() -> None:
    view = StripView(start_sec=90.0, span_sec=10.0)
    view.zoom_at(99.0, 0.5, 100.0)
    assert view.window(100.0) == pytest.approx((80.0, 100.0))


def test_pan_clamps_to_the_song() -> None:
    view = StripView(start_sec=40.0, span_sec=20.0)
    view.pan_by(-100.0, 100.0)
    assert view.window(100.0) == (0.0, 20.0)
    view.pan_by(500.0, 100.0)
    assert view.window(100.0) == (80.0, 100.0)
    view.centre_on(50.0, 100.0)
    assert view.window(100.0) == (40.0, 60.0)
    whole = StripView()
    whole.pan_by(10.0, 100.0)
    assert whole.window(100.0) == (0.0, 100.0)


def test_window_reclamps_when_the_song_is_shorter() -> None:
    view = StripView(start_sec=80.0, span_sec=20.0)
    assert view.window(50.0) == (30.0, 50.0)
    assert view.window(10.0) == (0.0, 10.0)


def test_follow_pages_forward_when_playback_runs_off_the_window() -> None:
    view = StripView(start_sec=40.0, span_sec=20.0)
    view.follow_playhead(59.9, 100.0, paused=False)
    assert view.start_sec == 40.0
    view.follow_playhead(60.1, 100.0, paused=False)
    assert view.window(100.0) == pytest.approx((58.1, 78.1))


def test_follow_recentres_on_a_paused_seek_outside_the_window() -> None:
    view = StripView(start_sec=40.0, span_sec=20.0)
    view.follow_playhead(5.0, 100.0, paused=True)
    assert view.start_sec == 40.0
    view.follow_playhead(5.0, 100.0, paused=True)
    assert view.start_sec == 40.0
    view.follow_playhead(80.0, 100.0, paused=True)
    assert view.window(100.0) == (70.0, 90.0)


def test_follow_leaves_a_window_panned_away_from_playback() -> None:
    view = StripView(start_sec=40.0, span_sec=20.0)
    view.follow_playhead(10.0, 100.0, paused=False)
    view.follow_playhead(10.1, 100.0, paused=False)
    view.follow_playhead(10.2, 100.0, paused=False)
    assert view.start_sec == 40.0


def test_follow_waits_while_a_gesture_is_held() -> None:
    view = StripView(start_sec=40.0, span_sec=20.0, held=True)
    view.follow_playhead(59.9, 100.0, paused=False)
    view.follow_playhead(60.1, 100.0, paused=False)
    assert view.start_sec == 40.0
    view.held = False
    # The playhead is already outside, so the window stays where it was put.
    view.follow_playhead(60.2, 100.0, paused=False)
    assert view.start_sec == 40.0


def test_follow_does_nothing_at_full_zoom() -> None:
    view = StripView()
    view.follow_playhead(10.0, 100.0, paused=False)
    view.follow_playhead(99.0, 100.0, paused=False)
    assert view.span_sec is None and view.start_sec == 0.0
