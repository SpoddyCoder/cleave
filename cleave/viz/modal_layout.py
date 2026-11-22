"""Modal panel geometry. No pygame or ImGui."""

from __future__ import annotations

from typing import Protocol

from cleave.viz.brand import logo_size
from cleave.viz.text_edit import caret_index_for_line_column, caret_line_column
from cleave.viz.modal import (
    FormRowView,
    ModalKind,
    ModalLabeledLine,
    ModalViewState,
)
from cleave.viz.choice_layout import choice_width, radio_width, stepper_width
from cleave.viz.progress_bar import progress_bar_height
from cleave.viz.text_fit import TextSizer, fit_text_to_width, wrap_text_to_width
from cleave.viz.theme import BORDER_WIDTH, row_half_pad_px, tuning_ui_metrics, ui_px

# Message wrap width and text-panel height cap, as a fraction of the viewport.
MESSAGE_MAX_SCREEN_FRACTION = 0.5
# Modal panel minimum width as a fraction of the viewport.
PANEL_MIN_SCREEN_FRACTION = 0.2
# Progress panel width as a fraction of the viewport, and its floor in base px.
PROGRESS_PANEL_SCREEN_FRACTION = 0.4
PROGRESS_PANEL_MIN_BASE = 420

TEXT_BUTTON_LABELS = ("Confirm", "Cancel")
EDITING_HINT = "Press Enter to confirm or ESC to cancel"
CARET_WIDTH = 2
# Banner logo height in text lines.
BANNER_HEIGHT_LINES = 6


# Spacing reads the live UI scale, so a scale change applies on the next frame.
def panel_pad_x() -> int:
    return tuning_ui_metrics().modal_panel_pad_x


def panel_pad_y() -> int:
    return tuning_ui_metrics().modal_panel_pad_y


def title_bar_pad_y() -> int:
    """Pad under a modal title inside its title bar.

    The bar runs from the panel's top border, so this matches the pad above
    the title.
    """
    return max(0, panel_pad_y() - BORDER_WIDTH)


def title_bar_bottom(text_top: int, text_h: int) -> int:
    """Bottom of the title bar over a title block *text_h* tall at *text_top*."""
    return text_top + text_h + title_bar_pad_y()


def text_cta_height(count: int, line_h: int) -> int:
    """The text modal's call to action: its title bar, then the editing hint."""
    if count <= 0:
        return 0
    return line_h + title_bar_pad_y() + (count - 1) * (panel_pad_y() + line_h)


def button_gap() -> int:
    return ui_px(8)


def button_pad_y() -> int:
    return ui_px(3)


def form_row_pad_y() -> int:
    """Space above and below a row's text: the same as an inspector row."""
    return row_half_pad_px()


def form_label_gap() -> int:
    return ui_px(24)


def form_section_indent() -> int:
    return ui_px(16)


def form_section_gap() -> int:
    """Space above every section heading but the first."""
    return ui_px(8)


def form_heading_height(line_h: int, *, first: bool) -> int:
    """Height of a section heading, with the gap above it after the first."""
    return form_row_height(line_h) + (0 if first else form_section_gap())


class TextMeasure(TextSizer, Protocol):
    """Text size plus line height. A pygame font satisfies this."""

    def get_linesize(self) -> int: ...


def message_max_width(screen_w: int) -> int:
    return max(1, int(screen_w * MESSAGE_MAX_SCREEN_FRACTION))


def panel_min_width(screen_w: int) -> int:
    return max(1, int(screen_w * PANEL_MIN_SCREEN_FRACTION))


def message_lines(measure: TextMeasure, message: str, *, screen_w: int) -> list[str]:
    return wrap_text_to_width(measure, message, message_max_width(screen_w))


def progress_panel_width(screen_w: int) -> int:
    """Fixed progress panel width: the bar's length, whatever the text says.

    Text never widens it, so a changing status line cannot resize the panel.
    """
    width = max(int(screen_w * PROGRESS_PANEL_SCREEN_FRACTION), ui_px(PROGRESS_PANEL_MIN_BASE))
    return max(1, min(width, screen_w))


def progress_content_width(screen_w: int) -> int:
    return max(1, progress_panel_width(screen_w) - panel_pad_x() * 2)


def banner_size(
    state: ModalViewState, line_h: int, *, screen_w: int
) -> tuple[int, int] | None:
    """Pixel size of the banner logo, or None when the dialog has none.

    It is a few lines tall and never wider than the text may run.
    """
    if state.banner is None:
        return None
    if state.kind == ModalKind.PROGRESS:
        max_w = progress_content_width(screen_w)
    else:
        max_w = message_max_width(screen_w)
    return logo_size(state.banner, line_h * BANNER_HEIGHT_LINES, max_w)


def title_lines(measure: TextMeasure, state: ModalViewState, *, screen_w: int) -> list[str]:
    """The title's lines. A progress title is one line, shortened to fit."""
    message = state.message or ""
    if state.kind == ModalKind.PROGRESS:
        return [fit_text_to_width(measure, message, progress_content_width(screen_w))]
    return message_lines(measure, message, screen_w=screen_w)


def body_lines(measure: TextMeasure, state: ModalViewState, *, screen_w: int) -> list[str]:
    """The body's lines. A progress body wraps inside the fixed panel width."""
    body = state.body or ""
    if state.kind == ModalKind.PROGRESS:
        return wrap_text_to_width(measure, body, progress_content_width(screen_w))
    return message_lines(measure, body, screen_w=screen_w)


def panel_labeled_lines(
    measure: TextMeasure, state: ModalViewState, *, screen_w: int
) -> tuple[ModalLabeledLine, ...]:
    """The labeled lines. A progress value is shortened to fit the panel."""
    if state.kind != ModalKind.PROGRESS:
        return state.labeled_lines
    content_w = progress_content_width(screen_w)
    return tuple(
        ModalLabeledLine(
            line.label,
            fit_text_to_width(
                measure, line.value, content_w - measure.size(line.prefix())[0]
            ),
        )
        for line in state.labeled_lines
    )


def option_text(label: str) -> str:
    return f"  {label}  "


def lines_block_height(count: int, line_h: int, line_gap: int) -> int:
    if count <= 0:
        return 0
    return count * line_h + (count - 1) * line_gap


def measure_labeled_lines(
    measure: TextMeasure,
    lines: tuple[ModalLabeledLine, ...],
    *,
    line_gap: int,
) -> tuple[int, int]:
    line_h = measure.get_linesize()
    if not lines:
        return 0, 0
    widths = [measure.size(line.display_text())[0] for line in lines]
    count = len(lines)
    total_h = count * line_h + max(0, count - 1) * line_gap
    return max(widths), total_h


def button_widths(measure: TextMeasure, labels: tuple[str, ...]) -> tuple[int, ...]:
    return tuple(measure.size(option_text(label))[0] for label in labels)


def button_height(measure: TextMeasure) -> int:
    return measure.get_linesize() + button_pad_y() * 2


def measure_button_row(
    measure: TextMeasure, labels: tuple[str, ...]
) -> tuple[int, int]:
    widths = button_widths(measure, labels)
    gaps = button_gap() * max(0, len(widths) - 1)
    return sum(widths) + gaps, button_height(measure)


def form_row_height(line_h: int) -> int:
    return line_h + form_row_pad_y() * 2


def form_field_height(line_h: int, row: FormRowView) -> int:
    """A field's rows: one, or one per option when vertical."""
    count = max(1, len(row.options)) if row.vertical else 1
    return form_row_height(line_h) * count


def form_control_width(measure: TextMeasure, row: FormRowView) -> int:
    """Width of a row's segments, combo, stepper, radio list, or locked value: it fits the
    widest option.
    """
    if row.vertical:
        return radio_width(measure, row.options)
    if row.locked:
        return measure.size(row.options[row.value])[0]
    if row.stepper:
        return stepper_width(
            measure, row.options, side=form_row_height(measure.get_linesize())
        )
    return choice_width(measure, row.options)


def form_value_offset(measure: TextMeasure, rows: tuple[FormRowView, ...]) -> int:
    """Where every field's control starts, from the form's left edge: a gap
    past the widest label (with its section indent), so the values line up in
    one column.
    """
    widest = max(
        (
            (form_section_indent() if row.indented else 0) + measure.size(row.label)[0]
            for row in rows
        ),
        default=0,
    )
    return widest + form_label_gap()


def form_value_x(
    measure: TextMeasure, rows: tuple[FormRowView, ...], content_w: int
) -> int:
    """Where the value column starts in a form *content_w* wide: as far right
    as lets the widest control end at the content's right edge, and never
    nearer the labels than ``form_value_offset``. A panel widened by its title,
    buttons, or minimum width puts the spare room between labels and values,
    not after the values.
    """
    offset = form_value_offset(measure, rows)
    widest = max((form_control_width(measure, row) for row in rows), default=0)
    return max(offset, content_w - widest)


def measure_form(
    measure: TextMeasure,
    state: ModalViewState,
    *,
    line_gap: int,
) -> tuple[int, int]:
    """Width and height of the field rows."""
    line_h = measure.get_linesize()
    value_x = form_value_offset(measure, state.form_rows)
    width = 0
    height = 0
    for index, row in enumerate(state.form_rows):
        if row.heading is not None:
            width = max(width, measure.size(row.heading)[0])
            height += form_heading_height(line_h, first=index == 0)
        width = max(width, value_x + form_control_width(measure, row))
        height += form_field_height(line_h, row)
    return width, height


def measure_panel(
    measure: TextMeasure,
    state: ModalViewState,
    *,
    line_gap: int,
    screen_w: int,
) -> tuple[int, int]:
    line_h = measure.get_linesize()
    content_w = 0
    content_h = 0
    has_message = state.message is not None or state.body is not None
    has_labeled = bool(state.labeled_lines)
    has_bar = state.progress_fraction is not None

    if state.message is not None:
        lines = title_lines(measure, state, screen_w=screen_w)
        msg_w = max((measure.size(line)[0] for line in lines), default=0)
        content_w = max(content_w, msg_w)
        content_h += len(lines) * line_h + max(0, len(lines) - 1) * line_gap
        content_h += title_bar_pad_y()

    banner = banner_size(state, line_h, screen_w=screen_w)
    if banner is not None:
        content_w = max(content_w, banner[0])
        content_h += panel_pad_y() + banner[1]

    if state.body is not None:
        if state.message is not None:
            content_h += panel_pad_y()
        lines = body_lines(measure, state, screen_w=screen_w)
        body_w = max((measure.size(line)[0] for line in lines), default=0)
        content_w = max(content_w, body_w)
        content_h += len(lines) * line_h + max(0, len(lines) - 1) * line_gap

    if state.form_info is not None:
        if has_message:
            content_h += line_gap
        content_w = max(content_w, measure.size(state.form_info)[0])
        content_h += line_h

    if has_labeled:
        if has_message:
            content_h += line_h + line_gap
        labeled_w, labeled_h = measure_labeled_lines(
            measure,
            panel_labeled_lines(measure, state, screen_w=screen_w),
            line_gap=line_gap,
        )
        content_w = max(content_w, labeled_w)
        content_h += labeled_h

    if has_bar:
        if has_message or has_labeled:
            content_h += line_h + line_gap
        content_h += progress_bar_height()

    if state.form_rows or state.form_info is not None:
        if has_message:
            content_h += line_h
        form_w, form_h = measure_form(measure, state, line_gap=line_gap)
        content_w = max(content_w, form_w)
        content_h += form_h

    if state.options:
        if has_message or has_labeled or has_bar:
            content_h += line_h + line_gap
        options_w, options_h = measure_button_row(measure, state.options)
        content_w = max(content_w, options_w)
        content_h += options_h

    if state.kind == ModalKind.PROGRESS:
        return progress_panel_width(screen_w), content_h + panel_pad_y() * 2
    return (
        max(content_w + panel_pad_x() * 2, panel_min_width(screen_w)),
        content_h + panel_pad_y() * 2,
    )


def text_cta_lines(state: ModalViewState) -> tuple[str, ...]:
    cta = state.cta if state.cta is not None else ""
    if state.editing:
        return (cta, EDITING_HINT)
    return (cta,)


def text_error_line(state: ModalViewState) -> str | None:
    error = state.error
    if error:
        return error
    return None


def text_field_lines(
    measure: TextMeasure,
    state: ModalViewState,
    *,
    screen_w: int,
) -> list[str]:
    draft = state.draft if state.draft is not None else ""
    if state.single_line:
        return [draft]
    if not draft:
        return [""]
    lines = message_lines(measure, draft, screen_w=screen_w)
    return lines if lines else [""]


def text_max_field_lines(
    *,
    line_h: int,
    line_gap: int,
    screen_h: int | None,
    cta_line_count: int,
    has_error: bool = False,
) -> int | None:
    if screen_h is None:
        return None
    max_panel_h = max(1, int(screen_h * MESSAGE_MAX_SCREEN_FRACTION))
    cta_h = text_cta_height(cta_line_count, line_h)
    section_gap = line_h + line_gap
    overhead = panel_pad_y() * 2 + cta_h + section_gap * 2 + line_h
    if has_error:
        overhead += line_h + line_gap
    max_field_h = max(line_h, max_panel_h - overhead)
    stride = line_h + line_gap
    return max(1, (max_field_h + line_gap) // stride)


def visible_field_lines(
    lines: list[str], caret_line: int, max_lines: int | None
) -> tuple[list[str], int]:
    if max_lines is None or len(lines) <= max_lines:
        return lines, max(0, min(caret_line, max(0, len(lines) - 1)))
    caret_line = max(0, min(caret_line, len(lines) - 1))
    start = max(0, min(caret_line - max_lines + 1, len(lines) - max_lines))
    return lines[start : start + max_lines], caret_line - start


def single_line_scroll_x(
    measure: TextMeasure,
    line: str,
    column: int,
    content_w: int,
) -> int:
    """Horizontal offset so the caret stays inside the field clip.

    Prefers showing the start of the string until the caret would leave the
    right edge. Empty and non-overflowing lines do not scroll.
    """
    if not line or content_w <= 0:
        return 0
    text_w = measure.size(line)[0]
    if text_w + CARET_WIDTH <= content_w:
        return 0
    column = max(0, min(column, len(line)))
    caret_x = measure.size(line[:column])[0]
    visible_caret_w = max(0, content_w - CARET_WIDTH)
    return max(0, caret_x - visible_caret_w)


def measure_text_panel(
    measure: TextMeasure,
    state: ModalViewState,
    *,
    line_gap: int,
    screen_w: int,
    screen_h: int | None = None,
) -> tuple[int, int]:
    line_h = measure.get_linesize()
    section_gap = line_h + line_gap
    wrap_w = message_max_width(screen_w)

    cta_lines = text_cta_lines(state)
    cta_w = max((measure.size(line)[0] for line in cta_lines), default=0)
    cta_h = text_cta_height(len(cta_lines), line_h)

    field_lines = text_field_lines(measure, state, screen_w=screen_w)
    field_w = max((measure.size(line)[0] for line in field_lines), default=0)
    field_w += CARET_WIDTH
    field_w = min(field_w, wrap_w)
    error_line = text_error_line(state)
    draft = state.draft if state.draft is not None else ""
    caret_line, _ = caret_line_column(draft, field_lines, state.caret_index)
    max_field_lines = text_max_field_lines(
        line_h=line_h,
        line_gap=line_gap,
        screen_h=screen_h,
        cta_line_count=len(cta_lines),
        has_error=error_line is not None,
    )
    visible_lines, _ = visible_field_lines(field_lines, caret_line, max_field_lines)
    field_h = lines_block_height(len(visible_lines), line_h, line_gap)

    buttons_w, buttons_h = measure_button_row(measure, TEXT_BUTTON_LABELS)

    content_w = max(cta_w, field_w, buttons_w)
    if error_line is not None:
        content_w = max(content_w, min(measure.size(error_line)[0], wrap_w))
    content_h = cta_h + section_gap + field_h + section_gap + buttons_h
    if error_line is not None:
        content_h += line_h + line_gap
    return (
        max(content_w + panel_pad_x() * 2, panel_min_width(screen_w)),
        content_h + panel_pad_y() * 2,
    )


def focus_highlight_rect(
    measure: TextMeasure,
    *,
    panel_width: int,
    y: int,
    line_h: int,
) -> tuple[int, int, int, int]:
    """Full panel width minus one character of padding on each side."""
    char_w = max(1, measure.size("M")[0])
    highlight_w = max(0, panel_width - 2 * char_w)
    return (char_w, y, highlight_w, line_h)


def _column_at_x(
    line: str, local_x: int, measure: TextMeasure, scroll_x: int
) -> int:
    """Largest column whose prefix ends at or before the click."""
    target = local_x + max(0, scroll_x)
    if target <= 0 or not line:
        return 0
    column = 0
    for index in range(1, len(line) + 1):
        if measure.size(line[:index])[0] <= target:
            column = index
        else:
            break
    return column


def caret_index_at_point(
    draft: str,
    lines: list[str],
    visible_start: int,
    local_x: int,
    local_y: int,
    measure: TextMeasure,
    line_gap: int,
    scroll_x: int,
) -> int:
    """Caret index for a click inside the field.

    ``local_y`` selects a visual line. ``visible_start`` is the first source
    line in that window. The column is the longest prefix of the line whose
    width fits the click, clamped to the line.
    """
    if not lines:
        return 0
    line_h = measure.get_linesize()
    stride = line_h + line_gap
    if stride <= 0 or local_y <= 0:
        visual = 0
    else:
        visual = local_y // stride
    visible_start = max(0, min(visible_start, len(lines) - 1))
    visual = max(0, min(visual, len(lines) - 1 - visible_start))
    source_line = visible_start + visual
    column = _column_at_x(lines[source_line], local_x, measure, scroll_x)
    return caret_index_for_line_column(draft, lines, source_line, column)
