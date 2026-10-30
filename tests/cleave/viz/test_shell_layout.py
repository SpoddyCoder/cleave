"""Shell column geometry for the live editor."""

from __future__ import annotations

from cleave.config_schema.editor import DEFAULT_HELP_WIDTH
from cleave.gl_compositor import _present_dest_rect
from cleave.viz.shell_layout import (
    INSPECTOR_WIDTH,
    MIN_COLUMN_WIDTH,
    ShellLayout,
    navigator_row_px,
    splitter_hit,
    splitter_request_width,
)


def _assert_stack(layout: ShellLayout, display_w: int, columns_y: int, columns_h: int) -> None:
    nav = layout.navigator
    insp = layout.inspector
    viz = layout.visualiser
    help_rect = layout.help
    assert nav[2] == insp[2]
    assert nav[0] == insp[0]
    assert nav[1] == columns_y
    assert insp[1] == nav[1] + nav[3]
    assert nav[3] + insp[3] == columns_h
    assert viz[1] == columns_y and viz[3] == columns_h
    assert help_rect[1] == columns_y and help_rect[3] == columns_h
    assert nav[2] + viz[2] + help_rect[2] == display_w
    assert nav[1] + nav[3] <= insp[1] or nav[3] == 0
    if layout.docked:
        assert nav[0] == 0
        assert help_rect[0] == nav[2]
        assert viz[0] == nav[2] + help_rect[2]
    else:
        assert viz[0] == 0
        assert nav[0] == viz[2]
        assert help_rect[0] == viz[2] + nav[2]


def test_split_stacks_navigator_on_the_inspector() -> None:
    menu_h = 23
    transport_h = 23
    row = navigator_row_px()
    layout = ShellLayout.compute(1280, 720, menu_h, transport_h, 0)
    columns_y = menu_h + transport_h
    columns_h = 720 - columns_y

    assert layout.docked is False
    assert layout.menu == (0, 0, 1280, menu_h)
    assert layout.transport == (0, menu_h, 1280, transport_h)
    assert layout.timeline == (0, 720, 1280, 0)
    _assert_stack(layout, 1280, columns_y, columns_h)
    assert layout.navigator[2] == INSPECTOR_WIDTH == 495
    assert layout.inspector[2] == INSPECTOR_WIDTH
    assert layout.navigator[3] == row
    assert layout.inspector[3] == columns_h - row
    assert layout.visualiser == (
        0,
        columns_y,
        1280 - INSPECTOR_WIDTH,
        columns_h,
    )
    assert layout.help[2] == 0


def test_docked_places_the_stack_then_the_visualiser() -> None:
    menu_h = 23
    transport_h = 23
    row = navigator_row_px()
    layout = ShellLayout.compute(
        1280, 720, menu_h, transport_h, 0, docked=True
    )
    columns_y = menu_h + transport_h
    columns_h = 720 - columns_y

    assert layout.docked is True
    _assert_stack(layout, 1280, columns_y, columns_h)
    assert layout.navigator == (0, columns_y, INSPECTOR_WIDTH, row)
    assert layout.inspector == (
        0,
        columns_y + row,
        INSPECTOR_WIDTH,
        columns_h - row,
    )
    assert layout.visualiser == (
        INSPECTOR_WIDTH,
        columns_y,
        1280 - INSPECTOR_WIDTH,
        columns_h,
    )


def test_timeline_band_shrinks_the_column_band() -> None:
    timeline_h = 100
    layout = ShellLayout.compute(1280, 720, 20, 20, timeline_h)
    columns_h = 720 - 40 - timeline_h

    assert layout.visualiser[3] == columns_h
    assert layout.navigator[3] + layout.inspector[3] == columns_h
    assert layout.help[3] == columns_h
    assert layout.timeline == (0, 720 - timeline_h, 1280, timeline_h)
    assert layout.visualiser[1] + layout.visualiser[3] == layout.timeline[1]


def test_narrow_display_keeps_widths_non_negative() -> None:
    layout = ShellLayout.compute(400, 300, 10, 10, 20)
    stack_w = layout.navigator[2]
    viz_w = layout.visualiser[2]

    assert stack_w == layout.inspector[2]
    assert stack_w >= 0
    assert viz_w >= 1
    assert stack_w + viz_w + layout.help[2] == 400
    assert stack_w < INSPECTOR_WIDTH
    assert stack_w == 399
    assert viz_w == 1
    assert layout.visualiser[3] == 300 - 20 - 20
    assert layout.timeline[2] == 400
    assert layout.visualiser[0] == 0
    assert layout.navigator[0] == viz_w


def test_stack_shrinks_when_it_would_leave_no_visualiser() -> None:
    layout = ShellLayout.compute(INSPECTOR_WIDTH, 200, 0, 0, 0)
    assert layout.visualiser[2] == 1
    assert layout.navigator[2] + layout.visualiser[2] == INSPECTOR_WIDTH
    assert layout.navigator[2] == layout.inspector[2]
    assert layout.navigator[2] >= 0


def test_omitted_width_uses_the_nominal_stack() -> None:
    layout = ShellLayout.compute(1280, 720, 0, 0, 0, insp_width=None)
    assert layout.navigator[2] == INSPECTOR_WIDTH == 495
    assert layout.inspector[2] == INSPECTOR_WIDTH
    assert layout.visualiser[2] == 1280 - 495
    assert layout.visualiser[0] == 0


def test_width_override_sets_the_stack_rects() -> None:
    menu_h = 23
    transport_h = 23
    stack_w = 180
    row = navigator_row_px()
    layout = ShellLayout.compute(
        1280,
        720,
        menu_h,
        transport_h,
        0,
        insp_width=stack_w,
    )
    columns_y = menu_h + transport_h
    columns_h = 720 - columns_y
    assert layout.visualiser == (0, columns_y, 1280 - stack_w, columns_h)
    assert layout.navigator == (1280 - stack_w, columns_y, stack_w, row)
    assert layout.inspector == (
        1280 - stack_w,
        columns_y + row,
        stack_w,
        columns_h - row,
    )
    assert layout.menu == (0, 0, 1280, menu_h)
    assert layout.timeline == (0, 720, 1280, 0)


def test_narrow_override_lifts_to_the_column_minimum() -> None:
    layout = ShellLayout.compute(1280, 720, 0, 0, 0, insp_width=10)
    assert layout.navigator[2] == MIN_COLUMN_WIDTH
    assert layout.inspector[2] == MIN_COLUMN_WIDTH
    assert layout.visualiser == (
        0,
        0,
        1280 - MIN_COLUMN_WIDTH,
        720,
    )
    assert layout.navigator[0] == layout.visualiser[2]


def test_content_height_clamps_so_the_inspector_keeps_half() -> None:
    columns_h = 200
    layout = ShellLayout.compute(
        1280, columns_h, 0, 0, 0, nav_content_h=10_000
    )
    assert layout.navigator[3] == columns_h // 2
    assert layout.inspector[3] == columns_h - columns_h // 2
    assert layout.inspector[3] >= columns_h / 2

    odd = ShellLayout.compute(1280, 201, 0, 0, 0, nav_content_h=10_000)
    assert odd.navigator[3] == 100
    assert odd.inspector[3] == 101


def test_short_content_leaves_the_rest_of_the_stack_to_the_inspector() -> None:
    row = navigator_row_px()
    content = row * 3
    columns_h = 400
    assert content < columns_h // 2
    layout = ShellLayout.compute(
        1280, columns_h, 0, 0, 0, nav_content_h=content
    )
    assert layout.navigator[3] == content
    assert layout.inspector[3] == columns_h - content
    assert layout.navigator[2] == layout.inspector[2]


def test_missing_content_height_is_one_row() -> None:
    row = navigator_row_px()
    for content in (None, 0, -5):
        layout = ShellLayout.compute(
            1280, 720, 0, 0, 0, nav_content_h=content
        )
        assert layout.navigator[3] == row
        assert layout.inspector[3] == 720 - row
        assert layout.navigator[3] > 0


def test_short_band_gives_the_navigator_one_row() -> None:
    row = navigator_row_px()
    band = row * 2 - 1
    layout = ShellLayout.compute(
        1280, band, 0, 0, 0, nav_content_h=10_000
    )
    assert layout.navigator[3] == row
    assert layout.inspector[3] == band - row
    assert layout.inspector[3] < layout.navigator[3]

    tiny = max(1, row // 2)
    squeezed = ShellLayout.compute(
        1280, tiny, 0, 0, 0, nav_content_h=10_000
    )
    assert squeezed.navigator[3] == tiny
    assert squeezed.inspector[3] == 0


def test_present_rect_none_stretches_to_the_display() -> None:
    assert _present_dest_rect(None, 1920, 1080, 1280, 720) == (
        0.0,
        0.0,
        1920.0,
        1080.0,
    )


def test_docked_width_override_sets_the_stack_rects() -> None:
    stack_w = 180
    row = navigator_row_px()
    layout = ShellLayout.compute(
        1280, 720, 0, 0, 0, insp_width=stack_w, docked=True
    )
    assert layout.navigator == (0, 0, stack_w, row)
    assert layout.inspector == (0, row, stack_w, 720 - row)
    assert layout.visualiser == (stack_w, 0, 1280 - stack_w, 720)


def test_splitter_resizes_the_stack_not_a_navigator_column() -> None:
    menu_h = 23
    transport_h = 23
    content = 80
    split = ShellLayout.compute(
        1280, 720, menu_h, transport_h, 0, nav_content_h=content, docked=False
    )
    docked = ShellLayout.compute(
        1280, 720, menu_h, transport_h, 0, nav_content_h=content, docked=True
    )
    y_nav = split.navigator[1] + 2
    y_insp = split.inspector[1] + 4
    split_edge = split.navigator[0]
    docked_edge = docked.navigator[0] + docked.navigator[2]

    assert splitter_hit(split, split_edge, y_nav) == "insp"
    assert splitter_hit(split, split_edge, y_insp) == "insp"
    assert splitter_hit(docked, docked_edge, y_nav) == "insp"
    assert splitter_hit(docked, docked_edge, y_insp) == "insp"
    assert splitter_hit(split, split_edge, y_nav) != "nav"
    assert splitter_request_width(split, "nav", 400.0) == 0
    assert splitter_request_width(docked, "nav", 400.0) == 0

    boundary_x = split.navigator[0] + split.navigator[2] // 2
    boundary_y = split.navigator[1] + split.navigator[3]
    assert splitter_hit(split, boundary_x, boundary_y - 1) is None
    assert splitter_hit(split, boundary_x, boundary_y) is None

    assert splitter_request_width(split, "insp", split_edge - 40) == (
        split.inspector[2] + 40
    )
    assert splitter_request_width(docked, "insp", docked_edge + 40) == (
        docked.inspector[2] + 40
    )


def test_open_help_column_sits_beside_the_stack() -> None:
    menu_h = 23
    transport_h = 23
    help_w = DEFAULT_HELP_WIDTH
    display_w = 1280
    columns_y = menu_h + transport_h
    columns_h = 720 - columns_y
    stack_w = INSPECTOR_WIDTH
    row = navigator_row_px()
    viz_w = display_w - stack_w - help_w

    split = ShellLayout.compute(
        display_w,
        720,
        menu_h,
        transport_h,
        0,
        help_width=help_w,
        docked=False,
    )
    _assert_stack(split, display_w, columns_y, columns_h)
    assert split.visualiser == (0, columns_y, viz_w, columns_h)
    assert split.navigator == (viz_w, columns_y, stack_w, row)
    assert split.inspector == (viz_w, columns_y + row, stack_w, columns_h - row)
    assert split.help == (viz_w + stack_w, columns_y, help_w, columns_h)

    docked = ShellLayout.compute(
        display_w,
        720,
        menu_h,
        transport_h,
        0,
        help_width=help_w,
        docked=True,
    )
    _assert_stack(docked, display_w, columns_y, columns_h)
    assert docked.navigator == (0, columns_y, stack_w, row)
    assert docked.inspector == (0, columns_y + row, stack_w, columns_h - row)
    assert docked.help == (stack_w, columns_y, help_w, columns_h)
    assert docked.visualiser == (
        stack_w + help_w,
        columns_y,
        viz_w,
        columns_h,
    )


def test_narrow_display_keeps_open_help_in_the_column_row() -> None:
    display_w = 100
    split = ShellLayout.compute(
        display_w, 200, 0, 0, 0, help_width=DEFAULT_HELP_WIDTH, docked=False
    )
    docked = ShellLayout.compute(
        display_w, 200, 0, 0, 0, help_width=DEFAULT_HELP_WIDTH, docked=True
    )
    for layout in (split, docked):
        stack_w = layout.navigator[2]
        viz_w = layout.visualiser[2]
        help_w = layout.help[2]
        assert stack_w == layout.inspector[2]
        assert stack_w >= 0 and viz_w >= 0 and help_w >= 0
        assert stack_w + viz_w + help_w == display_w
        assert layout.navigator[3] + layout.inspector[3] == 200
        assert layout.help[3] == 200

    assert split.visualiser == (0, 0, 1, 200)
    assert split.navigator[2] == 60
    assert split.navigator[0] == 1
    assert split.inspector == (1, split.navigator[3], 60, 200 - split.navigator[3])
    assert split.help == (61, 0, 39, 200)

    assert docked.navigator[0] == 0
    assert docked.navigator[2] == 60
    assert docked.inspector[0] == 0
    assert docked.inspector[2] == 60
    assert docked.help == (60, 0, 39, 200)
    assert docked.visualiser == (99, 0, 1, 200)


def test_closed_help_matches_split_and_docked_geometry() -> None:
    for docked in (False, True):
        current = ShellLayout.compute(1280, 720, 23, 23, 0, docked=docked)
        for help_width in (None, 0):
            closed = ShellLayout.compute(
                1280, 720, 23, 23, 0, help_width=help_width, docked=docked
            )
            assert closed.help[2] == 0
            assert closed.help[3] == current.visualiser[3]
            assert closed.navigator == current.navigator
            assert closed.visualiser == current.visualiser
            assert closed.inspector == current.inspector
            assert (
                closed.navigator[2]
                + closed.visualiser[2]
                + closed.help[2]
                == 1280
            )


def test_closed_help_does_not_take_a_minimum_slot() -> None:
    closed = ShellLayout.compute(
        121, 100, 0, 0, 0, insp_width=60, help_width=0
    )
    assert (closed.navigator[2], closed.visualiser[2], closed.inspector[2]) == (
        60,
        61,
        60,
    )
    assert closed.help[2] == 0
    assert closed.visualiser[0] == 0

    opened = ShellLayout.compute(
        121, 100, 0, 0, 0, insp_width=60, help_width=1
    )
    assert opened.help[2] > 0
    assert opened.visualiser[2] >= 0
    assert (
        opened.navigator[2]
        + opened.visualiser[2]
        + opened.help[2]
        == 121
    )
    assert opened.navigator[2] == opened.inspector[2]


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
    assert splitter_hit(split, split.navigator[0], y) == "insp"
    assert splitter_hit(closed, split_edge, y) != "help"
    assert splitter_hit(closed, closed.help[0], y) != "help"
    assert splitter_hit(
        closed_docked,
        closed_docked.navigator[0] + closed_docked.navigator[2],
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
