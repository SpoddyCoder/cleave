"""Shell column geometry for the live editor."""

from __future__ import annotations

from cleave.gl_compositor import _present_dest_rect
from cleave.viz.shell_layout import INSPECTOR_WIDTH, NAVIGATOR_WIDTH, ShellLayout


def test_columns_use_navigator_and_inspector_widths() -> None:
    menu_h = 23
    transport_h = 23
    layout = ShellLayout.compute(1280, 720, menu_h, transport_h, 0)
    columns_y = menu_h + transport_h
    columns_h = 720 - columns_y

    assert layout.menu == (0, 0, 1280, menu_h)
    assert layout.transport == (0, menu_h, 1280, transport_h)
    assert layout.navigator == (0, columns_y, NAVIGATOR_WIDTH, columns_h)
    assert layout.inspector == (
        1280 - INSPECTOR_WIDTH,
        columns_y,
        INSPECTOR_WIDTH,
        columns_h,
    )
    assert layout.visualiser == (
        NAVIGATOR_WIDTH,
        columns_y,
        1280 - NAVIGATOR_WIDTH - INSPECTOR_WIDTH,
        columns_h,
    )
    assert layout.navigator[2] == 230
    assert layout.inspector[2] == 495
    assert layout.timeline == (0, 720, 1280, 0)


def test_timeline_band_shrinks_columns_and_spans_full_width() -> None:
    timeline_h = 100
    layout = ShellLayout.compute(1280, 720, 20, 20, timeline_h)
    columns_h = 720 - 40 - timeline_h

    assert layout.visualiser[3] == columns_h
    assert layout.navigator[3] == columns_h
    assert layout.inspector[3] == columns_h
    assert layout.timeline == (0, 720 - timeline_h, 1280, timeline_h)
    assert layout.visualiser[1] + layout.visualiser[3] == layout.timeline[1]


def test_narrow_display_keeps_widths_non_negative() -> None:
    layout = ShellLayout.compute(400, 300, 10, 10, 20)
    nav_w = layout.navigator[2]
    viz_w = layout.visualiser[2]
    insp_w = layout.inspector[2]

    assert nav_w >= 0
    assert insp_w >= 0
    assert viz_w >= 1
    assert nav_w + viz_w + insp_w == 400
    assert nav_w < NAVIGATOR_WIDTH
    assert insp_w < INSPECTOR_WIDTH
    assert nav_w == 126
    assert insp_w == 273
    assert viz_w == 1
    assert layout.visualiser[3] == 300 - 20 - 20
    assert layout.timeline[2] == 400


def test_side_columns_shrink_when_they_would_leave_no_visualiser() -> None:
    layout = ShellLayout.compute(NAVIGATOR_WIDTH + INSPECTOR_WIDTH, 200, 0, 0, 0)
    assert layout.visualiser[2] == 1
    assert (
        layout.navigator[2] + layout.visualiser[2] + layout.inspector[2]
        == NAVIGATOR_WIDTH + INSPECTOR_WIDTH
    )
    assert layout.navigator[2] >= 0
    assert layout.inspector[2] >= 0


def test_present_rect_none_stretches_to_the_display() -> None:
    assert _present_dest_rect(None, 1920, 1080, 1280, 720) == (
        0.0,
        0.0,
        1920.0,
        1080.0,
    )


def test_present_rect_aspect_fits_inside_the_rect() -> None:
    pillar = _present_dest_rect((10, 20, 200, 100), 800, 600, 100, 100)
    assert pillar == (60.0, 20.0, 100.0, 100.0)
    letter = _present_dest_rect((10, 20, 100, 200), 800, 600, 200, 100)
    assert letter == (10.0, 95.0, 100.0, 50.0)
