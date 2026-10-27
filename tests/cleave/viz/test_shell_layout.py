"""Shell column geometry for the live editor."""

from __future__ import annotations

from cleave.config_schema.editor import DEFAULT_HELP_WIDTH
from cleave.gl_compositor import _present_dest_rect
from cleave.viz.shell_layout import (
    INSPECTOR_WIDTH,
    MIN_COLUMN_WIDTH,
    NAVIGATOR_WIDTH,
    ShellLayout,
    splitter_hit,
    splitter_request_width,
)


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


def test_omitted_width_overrides_use_nominal_columns() -> None:
    layout = ShellLayout.compute(
        1280, 720, 0, 0, 0, nav_width=None, insp_width=None
    )
    assert layout.navigator[2] == NAVIGATOR_WIDTH == 230
    assert layout.inspector[2] == INSPECTOR_WIDTH == 495
    assert layout.visualiser[2] == 1280 - 230 - 495


def test_width_overrides_set_column_rects() -> None:
    menu_h = 23
    transport_h = 23
    nav_w = 300
    insp_w = 180
    layout = ShellLayout.compute(
        1280,
        720,
        menu_h,
        transport_h,
        0,
        nav_width=nav_w,
        insp_width=insp_w,
    )
    columns_y = menu_h + transport_h
    columns_h = 720 - columns_y
    assert layout.navigator == (0, columns_y, nav_w, columns_h)
    assert layout.visualiser == (
        nav_w,
        columns_y,
        1280 - nav_w - insp_w,
        columns_h,
    )
    assert layout.inspector == (
        1280 - insp_w,
        columns_y,
        insp_w,
        columns_h,
    )
    assert layout.menu == (0, 0, 1280, menu_h)
    assert layout.timeline == (0, 720, 1280, 0)


def test_one_width_override_leaves_the_other_nominal() -> None:
    layout = ShellLayout.compute(1280, 720, 0, 0, 0, nav_width=300)
    assert layout.navigator[2] == 300
    assert layout.inspector[2] == INSPECTOR_WIDTH
    assert layout.visualiser == (300, 0, 1280 - 300 - INSPECTOR_WIDTH, 720)


def test_narrow_override_lifts_to_the_column_minimum() -> None:
    layout = ShellLayout.compute(
        1280, 720, 0, 0, 0, nav_width=10, insp_width=INSPECTOR_WIDTH
    )
    assert layout.navigator == (0, 0, MIN_COLUMN_WIDTH, 720)
    assert layout.inspector[2] == INSPECTOR_WIDTH
    assert layout.visualiser == (
        MIN_COLUMN_WIDTH,
        0,
        1280 - MIN_COLUMN_WIDTH - INSPECTOR_WIDTH,
        720,
    )


def test_present_rect_none_stretches_to_the_display() -> None:
    assert _present_dest_rect(None, 1920, 1080, 1280, 720) == (
        0.0,
        0.0,
        1920.0,
        1080.0,
    )


def test_docked_places_navigator_inspector_then_visualiser() -> None:
    menu_h = 23
    transport_h = 23
    layout = ShellLayout.compute(
        1280, 720, menu_h, transport_h, 0, docked=True
    )
    columns_y = menu_h + transport_h
    columns_h = 720 - columns_y
    nav_w = NAVIGATOR_WIDTH
    insp_w = INSPECTOR_WIDTH
    viz_w = 1280 - nav_w - insp_w

    assert layout.docked is True
    assert layout.navigator == (0, columns_y, nav_w, columns_h)
    assert layout.inspector == (nav_w, columns_y, insp_w, columns_h)
    assert layout.visualiser == (nav_w + insp_w, columns_y, viz_w, columns_h)
    assert nav_w + insp_w + viz_w == 1280


def test_docked_width_overrides_set_column_rects() -> None:
    nav_w = 300
    insp_w = 180
    layout = ShellLayout.compute(
        1280, 720, 0, 0, 0, nav_width=nav_w, insp_width=insp_w, docked=True
    )
    assert layout.navigator == (0, 0, nav_w, 720)
    assert layout.inspector == (nav_w, 0, insp_w, 720)
    assert layout.visualiser == (
        nav_w + insp_w,
        0,
        1280 - nav_w - insp_w,
        720,
    )


def test_splitter_hit_and_request_width_split_vs_docked() -> None:
    menu_h = 23
    transport_h = 23
    split = ShellLayout.compute(1280, 720, menu_h, transport_h, 0, docked=False)
    docked = ShellLayout.compute(1280, 720, menu_h, transport_h, 0, docked=True)

    nav_edge = split.navigator[0] + split.navigator[2]
    split_insp_edge = split.inspector[0]
    docked_insp_edge = docked.inspector[0] + docked.inspector[2]

    y = menu_h + transport_h + 10
    assert splitter_hit(split, nav_edge, y) == "nav"
    assert splitter_hit(split, split_insp_edge, y) == "insp"
    assert splitter_hit(docked, nav_edge, y) == "nav"
    assert splitter_hit(docked, docked_insp_edge, y) == "insp"

    assert splitter_request_width(split, "nav", 400.0) == 400
    assert splitter_request_width(docked, "nav", 400.0) == 400

    # Split inspector grows leftward; docked grows rightward from its left edge.
    assert splitter_request_width(split, "insp", 700.0) == 1280 - 700
    assert splitter_request_width(docked, "insp", 500.0) == (
        500 - NAVIGATOR_WIDTH
    )


def test_open_help_column_sits_beside_the_inspector() -> None:
    menu_h = 23
    transport_h = 23
    help_w = DEFAULT_HELP_WIDTH
    display_w = 1280
    columns_y = menu_h + transport_h
    columns_h = 720 - columns_y
    nav_w = NAVIGATOR_WIDTH
    insp_w = INSPECTOR_WIDTH
    viz_w = display_w - nav_w - insp_w - help_w

    split = ShellLayout.compute(
        display_w,
        720,
        menu_h,
        transport_h,
        0,
        help_width=help_w,
        docked=False,
    )
    assert split.navigator == (0, columns_y, nav_w, columns_h)
    assert split.visualiser == (nav_w, columns_y, viz_w, columns_h)
    assert split.inspector == (nav_w + viz_w, columns_y, insp_w, columns_h)
    assert split.help == (nav_w + viz_w + insp_w, columns_y, help_w, columns_h)
    assert nav_w + viz_w + insp_w + help_w == display_w

    docked = ShellLayout.compute(
        display_w,
        720,
        menu_h,
        transport_h,
        0,
        help_width=help_w,
        docked=True,
    )
    assert docked.navigator == (0, columns_y, nav_w, columns_h)
    assert docked.inspector == (nav_w, columns_y, insp_w, columns_h)
    assert docked.help == (nav_w + insp_w, columns_y, help_w, columns_h)
    assert docked.visualiser == (
        nav_w + insp_w + help_w,
        columns_y,
        viz_w,
        columns_h,
    )
    assert nav_w + insp_w + help_w + viz_w == display_w


def test_narrow_display_keeps_open_help_in_the_column_row() -> None:
    display_w = 100
    split = ShellLayout.compute(
        display_w, 200, 0, 0, 0, help_width=DEFAULT_HELP_WIDTH, docked=False
    )
    docked = ShellLayout.compute(
        display_w, 200, 0, 0, 0, help_width=DEFAULT_HELP_WIDTH, docked=True
    )
    for layout in (split, docked):
        nav_w = layout.navigator[2]
        viz_w = layout.visualiser[2]
        insp_w = layout.inspector[2]
        help_w = layout.help[2]
        assert nav_w >= 0 and viz_w >= 0 and insp_w >= 0 and help_w >= 0
        assert nav_w + viz_w + insp_w + help_w == display_w
        assert viz_w == display_w - nav_w - insp_w - help_w

    assert split.navigator[2] == 21
    assert split.visualiser == (21, 0, 1, 200)
    assert split.inspector == (22, 0, 46, 200)
    assert split.help == (68, 0, 32, 200)

    assert docked.navigator == (0, 0, 21, 200)
    assert docked.inspector == (21, 0, 46, 200)
    assert docked.help == (67, 0, 32, 200)
    assert docked.visualiser == (99, 0, 1, 200)


def test_closed_help_matches_split_and_docked_geometry() -> None:
    for docked in (False, True):
        current = ShellLayout.compute(1280, 720, 23, 23, 0, docked=docked)
        for help_width in (None, 0):
            closed = ShellLayout.compute(
                1280, 720, 23, 23, 0, help_width=help_width, docked=docked
            )
            assert closed.help[2] == 0
            assert closed.help[3] == current.navigator[3]
            assert closed.navigator == current.navigator
            assert closed.visualiser == current.visualiser
            assert closed.inspector == current.inspector
            assert (
                closed.navigator[2]
                + closed.visualiser[2]
                + closed.inspector[2]
                + closed.help[2]
                == 1280
            )


def test_closed_help_does_not_take_a_minimum_slot() -> None:
    closed = ShellLayout.compute(
        121, 100, 0, 0, 0, nav_width=60, insp_width=60, help_width=0
    )
    assert (closed.navigator[2], closed.visualiser[2], closed.inspector[2]) == (
        60,
        1,
        60,
    )
    assert closed.help[2] == 0

    opened = ShellLayout.compute(
        121, 100, 0, 0, 0, nav_width=60, insp_width=60, help_width=1
    )
    assert opened.help[2] > 0
    assert opened.visualiser[2] >= 0
    assert (
        opened.navigator[2]
        + opened.visualiser[2]
        + opened.inspector[2]
        + opened.help[2]
        == 121
    )


def test_help_splitter_hit_and_request_width() -> None:
    menu_h = 23
    transport_h = 23
    y = menu_h + transport_h + 10
    help_w = DEFAULT_HELP_WIDTH
    split = ShellLayout.compute(
        1280, 720, menu_h, transport_h, 0, help_width=help_w, docked=False
    )
    docked = ShellLayout.compute(
        1280, 720, menu_h, transport_h, 0, help_width=help_w, docked=True
    )
    closed = ShellLayout.compute(
        1280, 720, menu_h, transport_h, 0, help_width=0, docked=False
    )
    closed_docked = ShellLayout.compute(
        1280, 720, menu_h, transport_h, 0, help_width=None, docked=True
    )

    split_edge = split.help[0]
    docked_edge = docked.help[0] + docked.help[2]
    assert splitter_hit(split, split_edge, y) == "help"
    assert splitter_hit(docked, docked_edge, y) == "help"
    assert splitter_hit(split, split.navigator[2], y) == "nav"
    assert splitter_hit(split, split.inspector[0], y) == "insp"
    assert splitter_hit(closed, split_edge, y) != "help"
    assert splitter_hit(closed, closed.help[0], y) != "help"
    assert splitter_hit(
        closed_docked,
        closed_docked.inspector[0] + closed_docked.inspector[2],
        y,
    ) == "insp"

    assert splitter_request_width(split, "help", split_edge - 40) == help_w + 40
    assert splitter_request_width(
        docked, "help", docked.help[0] + help_w + 40
    ) == (help_w + 40)


def test_present_rect_aspect_fits_inside_the_rect() -> None:
    pillar = _present_dest_rect((10, 20, 200, 100), 800, 600, 100, 100)
    assert pillar == (60.0, 20.0, 100.0, 100.0)
    letter = _present_dest_rect((10, 20, 100, 200), 800, 600, 200, 100)
    assert letter == (10.0, 95.0, 100.0, 50.0)
