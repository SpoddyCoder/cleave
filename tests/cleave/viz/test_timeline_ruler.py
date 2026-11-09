"""Tests for the timeline strip's time scale."""

from __future__ import annotations

import pygame

from cleave.viz.theme import MUTED
from cleave.viz.timeline_ruler import (
    RULER_BOTTOM_GAP_PX,
    format_ruler_time,
    render_time_ruler,
    ruler_ticks,
    view_time_to_x,
)


def test_format_ruler_time_minutes_hours_and_tenths() -> None:
    assert format_ruler_time(0.0, 10.0) == "0:00"
    assert format_ruler_time(75.0, 15.0) == "1:15"
    assert format_ruler_time(3725.0, 60.0) == "1:02:05"
    assert format_ruler_time(61.5, 0.5) == "1:01.5"


def test_ruler_ticks_picks_step_wide_enough_for_labels() -> None:
    ticks = ruler_ticks(
        view_start_sec=0.0, view_end_sec=240.0, bar_width=1200, min_label_px=60
    )
    assert ticks is not None
    # 5 px/s: 10s steps are 50px (too tight), 20s steps are 100px.
    assert ticks.major_step == 20.0
    assert ticks.major[0] == 0.0
    assert ticks.major[-1] == 240.0
    assert all(t % 10 == 0 for t in ticks.major)
    assert ticks.minor_step == 5.0
    assert 5.0 in ticks.minor
    assert not set(ticks.minor) & set(ticks.major)


def test_ruler_ticks_narrow_window_uses_fine_steps() -> None:
    # A zoomed window: 2 seconds across 1000px.
    ticks = ruler_ticks(
        view_start_sec=30.0, view_end_sec=32.0, bar_width=1000, min_label_px=60
    )
    assert ticks is not None
    assert ticks.major_step == 0.2
    assert ticks.major[0] == 30.0
    assert ticks.major[-1] == 32.0


def test_ruler_ticks_drops_minor_ticks_that_crowd() -> None:
    ticks = ruler_ticks(
        view_start_sec=0.0, view_end_sec=36000.0, bar_width=100, min_label_px=60
    )
    assert ticks is not None
    assert ticks.minor_step is None
    assert ticks.minor == ()


def test_ruler_ticks_empty_window() -> None:
    assert (
        ruler_ticks(view_start_sec=0.0, view_end_sec=0.0, bar_width=100, min_label_px=10)
        is None
    )


def test_view_time_to_x_maps_window_onto_bar() -> None:
    kw = dict(bar_left=100, bar_width=1000, view_start_sec=10.0, view_end_sec=20.0)
    assert view_time_to_x(10.0, **kw) == 100
    assert view_time_to_x(15.0, **kw) == 600
    assert view_time_to_x(20.0, **kw) == 1100


def test_render_time_ruler_draws_major_tick_at_bar_left() -> None:
    pygame.init()
    surface = render_time_ruler(
        width=800,
        height=24,
        bar_left=50,
        bar_width=700,
        view_start_sec=0.0,
        view_end_sec=180.0,
        strip_font_size=14,
    )
    assert surface is not None
    assert surface.get_size() == (800, 24)
    assert tuple(surface.get_at((50, 24 - 1 - RULER_BOTTOM_GAP_PX)))[:3] == MUTED
    # Nothing left of the bar.
    assert surface.get_at((10, 20)).a == 0
