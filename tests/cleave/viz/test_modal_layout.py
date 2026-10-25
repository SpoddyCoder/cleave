"""Pure modal geometry, measured without pygame."""

from __future__ import annotations

from cleave.viz.modal import ModalKind, ModalLabeledLine, ModalViewState, TextFocusRegion
from cleave.viz.modal_layout import (
    CARET_WIDTH,
    MESSAGE_MAX_SCREEN_FRACTION,
    caret_index_at_point,
    measure_labeled_lines,
    measure_panel,
    measure_text_panel,
    message_lines,
    message_max_width,
    panel_min_width,
    single_line_scroll_x,
    text_max_field_lines,
    visible_field_lines,
)


class _FixedMeasure:
    def __init__(self, char_w: int = 10, line_h: int = 16) -> None:
        self._char_w = char_w
        self._line_h = line_h

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * self._char_w, self._line_h)

    def get_linesize(self) -> int:
        return self._line_h


def _option_view(
    message: str = "Hi", options: tuple[str, ...] = ("Yes", "No")
) -> ModalViewState:
    return ModalViewState(
        kind=ModalKind.YES_NO,
        message=message,
        options=options,
        focus_index=0,
    )


def test_panel_min_width_is_twenty_percent_of_screen() -> None:
    measure = _FixedMeasure()
    screen_w = 1000
    assert panel_min_width(screen_w) == int(screen_w * 0.2)
    panel_w, _ = measure_panel(
        measure, _option_view(), line_gap=4, screen_w=screen_w
    )
    assert panel_w == panel_min_width(screen_w)

    text = ModalViewState(
        kind=ModalKind.TEXT,
        message=None,
        options=(),
        focus_index=0,
        cta="Name",
        draft="a",
        single_line=True,
        editing=False,
        caret_index=1,
        focus_region=TextFocusRegion.FIELD,
    )
    wide = 2000
    text_w, _ = measure_text_panel(
        measure, text, line_gap=4, screen_w=wide, screen_h=800
    )
    assert panel_min_width(wide) == int(wide * 0.2)
    assert text_w == panel_min_width(wide)


def test_message_wrap_width_is_half_the_screen() -> None:
    measure = _FixedMeasure()
    screen_w = 200
    wrap_w = message_max_width(screen_w)
    assert wrap_w == int(screen_w * MESSAGE_MAX_SCREEN_FRACTION)
    assert wrap_w == screen_w // 2

    message = "abcdefghijKLMNOPQRST"
    lines = message_lines(measure, message, screen_w=screen_w)
    assert len(lines) > 1
    assert all(measure.size(line)[0] <= wrap_w for line in lines)
    assert "".join(lines) == message

    panel_w, _ = measure_panel(
        measure,
        _option_view(message=message, options=("Ok",)),
        line_gap=4,
        screen_w=screen_w,
    )
    assert panel_w >= panel_min_width(screen_w)


def test_labeled_line_block_height() -> None:
    measure = _FixedMeasure()
    line_gap = 4
    line_h = measure.get_linesize()
    labeled = (
        ModalLabeledLine("character", "breathing"),
        ModalLabeledLine("density", "normal"),
    )
    _width, height = measure_labeled_lines(measure, labeled, line_gap=line_gap)
    assert height == 2 * line_h + line_gap

    with_lines = ModalViewState(
        kind=ModalKind.YES_NO,
        message="Apply?",
        options=("Yes", "Cancel"),
        focus_index=0,
        labeled_lines=labeled,
    )
    without = ModalViewState(
        kind=ModalKind.YES_NO,
        message="Apply?",
        options=("Yes", "Cancel"),
        focus_index=0,
    )
    _, height_with = measure_panel(
        measure, with_lines, line_gap=line_gap, screen_w=1000
    )
    _, height_without = measure_panel(
        measure, without, line_gap=line_gap, screen_w=1000
    )
    section_gap = line_h + line_gap
    assert height_with - height_without == section_gap + height


def test_visible_field_window_keeps_caret_line_visible() -> None:
    lines = [f"L{index}" for index in range(20)]
    max_lines = text_max_field_lines(
        line_h=16,
        line_gap=4,
        screen_h=200,
        cta_line_count=2,
    )
    assert max_lines is not None
    assert max_lines < len(lines)
    for caret in (0, 5, len(lines) - 1):
        visible, relative = visible_field_lines(lines, caret, max_lines)
        assert visible[relative] == lines[caret]
        assert len(visible) <= max_lines

    visible, relative = visible_field_lines(lines, caret_line=19, max_lines=3)
    assert visible == lines[17:20]
    assert relative == 2


def test_single_line_scroll_keeps_caret_inside_clip() -> None:
    measure = _FixedMeasure()
    line = "a" * 30
    content_w = 100
    column = 25
    scroll_x = single_line_scroll_x(measure, line, column, content_w)
    caret_x = measure.size(line[:column])[0]
    assert 0 <= caret_x - scroll_x <= content_w - CARET_WIDTH
    assert scroll_x == max(0, caret_x - (content_w - CARET_WIDTH))

    assert single_line_scroll_x(measure, "hi", 2, content_w) == 0
    assert single_line_scroll_x(measure, "", 0, content_w) == 0
    assert single_line_scroll_x(measure, line, 0, content_w) == 0


def test_caret_index_at_point_round_trips_column_and_line() -> None:
    measure = _FixedMeasure()
    line_gap = 4
    draft = "hello\nworld"
    lines = ["hello", "world"]

    column = 2
    local_x = measure.size(lines[0][:column])[0]
    assert (
        caret_index_at_point(
            draft, lines, 0, local_x, 0, measure, line_gap, 0
        )
        == column
    )

    later_column = 3
    later_x = measure.size(lines[1][:later_column])[0]
    later_y = measure.get_linesize() + line_gap
    assert (
        caret_index_at_point(
            draft, lines, 0, later_x, later_y, measure, line_gap, 0
        )
        == len("hello\n") + later_column
    )

    assert (
        caret_index_at_point(
            draft, lines, 1, later_x, 0, measure, line_gap, 0
        )
        == len("hello\n") + later_column
    )

    scrolled = "hello"
    scroll_x = measure.size("he")[0]
    click_x = measure.size("l")[0]
    assert (
        caret_index_at_point(
            scrolled, [scrolled], 0, click_x, 0, measure, line_gap, scroll_x
        )
        == 3
    )
