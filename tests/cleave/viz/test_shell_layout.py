"""Shell column geometry for the live editor."""

from __future__ import annotations

from cleave.config_schema.editor import DEFAULT_HELP_WIDTH, DEFAULT_INSPECTOR_WIDTH
from cleave.gl_compositor import _present_dest_rect
from cleave.viz.shell_layout import (
    INSPECTOR_WIDTH,
    MIN_COLUMN_WIDTH,
    ShellLayout,
    navigator_row_px,
    splitter_hit,
    splitter_request_height,
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
    spans = [
        (rect[0], rect[0] + rect[2])
        for rect in (nav, viz, help_rect)
        if rect[2] > 0
    ]
    spans.sort()
    assert spans[0][0] == 0
    assert spans[-1][1] == display_w
    for index in range(1, len(spans)):
        assert spans[index][0] == spans[index - 1][1]


def test_default_places_the_navigator_on_the_left() -> None:
    menu_h = 23
    transport_h = 23
    row = navigator_row_px()
    layout = ShellLayout.compute(1280, 720, menu_h, transport_h, 0)
    columns_y = menu_h + transport_h
    columns_h = 720 - columns_y

    assert layout.navigator_side == "left"
    assert layout.help_side == "right"
    assert layout.menu == (0, 0, 1280, menu_h)
    assert layout.transport == (0, menu_h, 1280, transport_h)
    assert layout.timeline == (0, 720, 1280, 0)
    _assert_stack(layout, 1280, columns_y, columns_h)
    assert layout.navigator[2] == INSPECTOR_WIDTH == 495
    assert layout.inspector[2] == INSPECTOR_WIDTH
    assert layout.navigator[3] == row
    assert layout.inspector[3] == columns_h - row
    assert layout.navigator[0] == 0
    assert layout.visualiser == (
        INSPECTOR_WIDTH,
        columns_y,
        1280 - INSPECTOR_WIDTH,
        columns_h,
    )
    assert layout.help[2] == 0


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
    assert layout.navigator[0] == 0
    assert layout.visualiser[0] == stack_w


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
    assert layout.navigator[0] == 0
    assert layout.visualiser[0] == INSPECTOR_WIDTH


def test_narrow_override_lifts_to_the_column_minimum() -> None:
    layout = ShellLayout.compute(1280, 720, 0, 0, 0, insp_width=10)
    assert layout.navigator[2] == MIN_COLUMN_WIDTH
    assert layout.inspector[2] == MIN_COLUMN_WIDTH
    assert layout.navigator[0] == 0
    assert layout.visualiser == (
        MIN_COLUMN_WIDTH,
        0,
        1280 - MIN_COLUMN_WIDTH,
        720,
    )


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


def test_width_override_sets_the_stack_rects() -> None:
    stack_w = 180
    row = navigator_row_px()
    layout = ShellLayout.compute(
        1280, 720, 0, 0, 0, insp_width=stack_w
    )
    assert layout.navigator == (0, 0, stack_w, row)
    assert layout.inspector == (0, row, stack_w, 720 - row)
    assert layout.visualiser == (stack_w, 0, 1280 - stack_w, 720)


def test_splitter_resizes_the_stack_not_a_navigator_column() -> None:
    menu_h = 23
    transport_h = 23
    content = 80
    left = ShellLayout.compute(
        1280,
        720,
        menu_h,
        transport_h,
        0,
        nav_content_h=content,
        navigator_side="left",
    )
    right = ShellLayout.compute(
        1280,
        720,
        menu_h,
        transport_h,
        0,
        nav_content_h=content,
        navigator_side="right",
    )
    y_nav = left.navigator[1] + 2
    y_insp = left.inspector[1] + 4
    left_edge = left.navigator[0] + left.navigator[2]
    right_edge = right.navigator[0]

    assert splitter_hit(left, left_edge, y_nav) == "insp"
    assert splitter_hit(left, left_edge, y_insp) == "insp"
    assert splitter_hit(right, right_edge, y_nav) == "insp"
    assert splitter_hit(right, right_edge, y_insp) == "insp"
    assert splitter_request_width(left, "nav", 400.0) == 0
    assert splitter_request_width(right, "nav", 400.0) == 0

    boundary_x = left.navigator[0] + left.navigator[2] // 2
    boundary_y = left.navigator[1] + left.navigator[3]
    assert splitter_hit(left, boundary_x, boundary_y - 1) == "nav"
    assert splitter_hit(left, boundary_x, boundary_y) == "nav"
    assert splitter_hit(left, boundary_x, boundary_y + 10) is None
    viz_x = left.visualiser[0] + 20
    assert splitter_hit(left, viz_x, boundary_y) is None

    assert splitter_request_width(left, "insp", left_edge + 40) == (
        left.inspector[2] + 40
    )
    assert splitter_request_width(right, "insp", right_edge - 40) == (
        right.inspector[2] + 40
    )


def test_column_sides_keep_the_navigator_against_the_visualiser() -> None:
    menu_h = 23
    transport_h = 23
    help_w = DEFAULT_HELP_WIDTH
    display_w = 1280
    columns_y = menu_h + transport_h
    columns_h = 720 - columns_y
    stack_w = INSPECTOR_WIDTH
    row = navigator_row_px()
    viz_w = display_w - stack_w - help_w

    def placed(navigator_side: str, help_side: str) -> ShellLayout:
        return ShellLayout.compute(
            display_w,
            720,
            menu_h,
            transport_h,
            0,
            help_width=help_w,
            navigator_side=navigator_side,
            help_side=help_side,
        )

    default = placed("left", "right")
    _assert_stack(default, display_w, columns_y, columns_h)
    assert default.navigator == (0, columns_y, stack_w, row)
    assert default.inspector == (0, columns_y + row, stack_w, columns_h - row)
    assert default.visualiser == (stack_w, columns_y, viz_w, columns_h)
    assert default.help == (stack_w + viz_w, columns_y, help_w, columns_h)

    mirrored = placed("right", "left")
    _assert_stack(mirrored, display_w, columns_y, columns_h)
    assert mirrored.help == (0, columns_y, help_w, columns_h)
    assert mirrored.visualiser == (help_w, columns_y, viz_w, columns_h)
    assert mirrored.navigator == (help_w + viz_w, columns_y, stack_w, row)

    both_left = placed("left", "left")
    _assert_stack(both_left, display_w, columns_y, columns_h)
    assert both_left.help == (0, columns_y, help_w, columns_h)
    assert both_left.navigator == (help_w, columns_y, stack_w, row)
    assert both_left.visualiser == (help_w + stack_w, columns_y, viz_w, columns_h)

    both_right = placed("right", "right")
    _assert_stack(both_right, display_w, columns_y, columns_h)
    assert both_right.visualiser == (0, columns_y, viz_w, columns_h)
    assert both_right.navigator == (viz_w, columns_y, stack_w, row)
    assert both_right.help == (viz_w + stack_w, columns_y, help_w, columns_h)


def test_narrow_display_keeps_open_help_in_the_column_row() -> None:
    display_w = 100
    default = ShellLayout.compute(
        display_w,
        200,
        0,
        0,
        0,
        help_width=DEFAULT_HELP_WIDTH,
        navigator_side="left",
        help_side="right",
    )
    both_right = ShellLayout.compute(
        display_w,
        200,
        0,
        0,
        0,
        help_width=DEFAULT_HELP_WIDTH,
        navigator_side="right",
        help_side="right",
    )
    for layout in (default, both_right):
        stack_w = layout.navigator[2]
        viz_w = layout.visualiser[2]
        help_w = layout.help[2]
        assert stack_w == layout.inspector[2]
        assert stack_w >= 0 and viz_w >= 0 and help_w >= 0
        assert stack_w + viz_w + help_w == display_w
        assert layout.navigator[3] + layout.inspector[3] == 200
        assert layout.help[3] == 200

    assert default.navigator[0] == 0
    assert default.navigator[2] == 60
    assert default.inspector[0] == 0
    assert default.inspector[2] == 60
    assert default.visualiser == (60, 0, 1, 200)
    assert default.help == (61, 0, 39, 200)

    assert both_right.visualiser == (0, 0, 1, 200)
    assert both_right.navigator[2] == 60
    assert both_right.navigator[0] == 1
    assert both_right.inspector == (
        1,
        both_right.navigator[3],
        60,
        200 - both_right.navigator[3],
    )
    assert both_right.help == (61, 0, 39, 200)


def test_closed_help_matches_open_column_geometry() -> None:
    for navigator_side, help_side in (
        ("left", "right"),
        ("right", "left"),
        ("left", "left"),
        ("right", "right"),
    ):
        current = ShellLayout.compute(
            1280,
            720,
            23,
            23,
            0,
            navigator_side=navigator_side,
            help_side=help_side,
        )
        for help_width in (None, 0):
            closed = ShellLayout.compute(
                1280,
                720,
                23,
                23,
                0,
                help_width=help_width,
                navigator_side=navigator_side,
                help_side=help_side,
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
    assert closed.navigator[0] == 0
    assert closed.visualiser[0] == closed.navigator[2]

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
    help_right = ShellLayout.compute(
        1280,
        720,
        menu_h,
        transport_h,
        0,
        help_width=help_w,
        navigator_side="left",
        help_side="right",
    )
    help_left = ShellLayout.compute(
        1280,
        720,
        menu_h,
        transport_h,
        0,
        help_width=help_w,
        navigator_side="right",
        help_side="left",
    )
    closed = ShellLayout.compute(
        1280, 720, menu_h, transport_h, 0, help_width=0
    )

    right_edge = help_right.help[0]
    left_edge = help_left.help[0] + help_left.help[2]
    assert splitter_hit(help_right, right_edge, y) == "help"
    assert splitter_hit(help_left, left_edge, y) == "help"
    assert splitter_hit(
        help_right, help_right.navigator[0] + help_right.navigator[2], y
    ) == "insp"
    assert splitter_hit(closed, right_edge, y) != "help"
    assert splitter_hit(closed, closed.help[0], y) != "help"
    assert splitter_hit(
        closed,
        closed.navigator[0] + closed.navigator[2],
        y,
    ) == "insp"

    assert splitter_request_width(help_right, "help", right_edge - 40) == (
        help_w + 40
    )
    assert splitter_request_width(help_left, "help", left_edge + 40) == (
        help_w + 40
    )


def test_present_rect_aspect_fits_inside_the_rect() -> None:
    pillar = _present_dest_rect((10, 20, 200, 100), 800, 600, 100, 100)
    assert pillar == (60.0, 20.0, 100.0, 100.0)
    letter = _present_dest_rect((10, 20, 100, 200), 800, 600, 200, 100)
    assert letter == (10.0, 95.0, 100.0, 50.0)


def test_navigator_height_overrides_the_row_fit() -> None:
    row = navigator_row_px()
    columns_h = 600
    layout = ShellLayout.compute(
        1280, columns_h, 0, 0, 0, nav_content_h=row * 2, navigator_height=450
    )
    assert layout.navigator[3] == 450
    assert layout.inspector[1] == 450
    assert layout.inspector[3] == columns_h - 450


def test_navigator_height_leaves_each_side_one_row() -> None:
    row = navigator_row_px()
    columns_h = 600
    tall = ShellLayout.compute(1280, columns_h, 0, 0, 0, navigator_height=10_000)
    assert tall.navigator[3] == columns_h - row
    assert tall.inspector[3] == row
    short = ShellLayout.compute(1280, columns_h, 0, 0, 0, navigator_height=1)
    assert short.navigator[3] == row


def test_zero_navigator_height_fits_rows() -> None:
    content = navigator_row_px() * 3
    layout = ShellLayout.compute(
        1280, 600, 0, 0, 0, nav_content_h=content, navigator_height=0
    )
    assert layout.navigator[3] == content


def test_nav_splitter_request_height_is_from_the_navigator_top() -> None:
    layout = ShellLayout.compute(1280, 720, 23, 23, 0)
    top = layout.navigator[1]
    assert splitter_request_height(layout, top + 300.0) == 300
    assert splitter_request_height(layout, top - 50.0) == 0


def test_shell_row_heights_grow_with_ui_scale() -> None:
    from cleave.config_schema.editor import DEFAULT_UI_SCALE
    from cleave.viz.shell_host import menu_bar_height_px
    from cleave.viz.theme import set_ui_scale_percent

    row, bar = navigator_row_px(), menu_bar_height_px()
    try:
        set_ui_scale_percent(200)
        assert navigator_row_px() == row * 2
        assert menu_bar_height_px() == bar * 2
    finally:
        set_ui_scale_percent(DEFAULT_UI_SCALE)
    assert navigator_row_px() == row


def test_minimum_window_keeps_every_column_and_both_stack_panes() -> None:
    from cleave.config_schema.window import window_minimum_size
    from cleave.viz.shell_host import menu_bar_height_px
    from cleave.viz.theme import set_ui_scale_percent
    from cleave.viz.timeline_overlay import timeline_band_height_px

    try:
        for percent in (100, 200):
            set_ui_scale_percent(percent)
            width, height = window_minimum_size(percent / 100.0, None)
            bar_h = menu_bar_height_px()
            layout = ShellLayout.compute(
                width,
                height,
                bar_h,
                bar_h,
                timeline_band_height_px(4),
                insp_width=DEFAULT_INSPECTOR_WIDTH,
                help_width=DEFAULT_HELP_WIDTH,
            )
            row = navigator_row_px()
            assert layout.navigator[2] >= MIN_COLUMN_WIDTH
            assert layout.help[2] >= MIN_COLUMN_WIDTH
            assert layout.visualiser[2] >= MIN_COLUMN_WIDTH
            assert layout.navigator[3] >= row
            assert layout.inspector[3] >= row
    finally:
        set_ui_scale_percent(100)
