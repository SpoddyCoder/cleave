"""Modal panel geometry. No pygame or ImGui."""

from __future__ import annotations

from typing import Protocol

from cleave.viz.modal import (
    ModalLabeledLine,
    ModalViewState,
    caret_index_for_line_column,
    caret_line_column,
)
from cleave.viz.text_fit import TextSizer, wrap_text_to_width
from cleave.viz.theme import UI_SCALE, scale_px, tuning_ui_metrics

# Message wrap width and text-panel height cap, as a fraction of the viewport.
MESSAGE_MAX_SCREEN_FRACTION = 0.5
# Modal panel minimum width as a fraction of the viewport.
PANEL_MIN_SCREEN_FRACTION = 0.2

_tuning_ui = tuning_ui_metrics()
PANEL_PAD_X = _tuning_ui.modal_panel_pad_x
PANEL_PAD_Y = _tuning_ui.modal_panel_pad_y
BAR_HEIGHT = scale_px(10, scale=UI_SCALE)
TEXT_BUTTON_LABELS = ("Confirm", "Cancel")
TEXT_BUTTON_GAP = scale_px(24, scale=UI_SCALE)
EDITING_HINT = "Press Enter to confirm or ESC to cancel"
CARET_WIDTH = 2


class TextMeasure(TextSizer, Protocol):
    """Text size plus line height. A pygame font satisfies this."""

    def get_linesize(self) -> int: ...


def message_max_width(screen_w: int) -> int:
    return max(1, int(screen_w * MESSAGE_MAX_SCREEN_FRACTION))


def panel_min_width(screen_w: int) -> int:
    return max(1, int(screen_w * PANEL_MIN_SCREEN_FRACTION))


def message_lines(measure: TextMeasure, message: str, *, screen_w: int) -> list[str]:
    return wrap_text_to_width(measure, message, message_max_width(screen_w))


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


def measure_options(
    measure: TextMeasure,
    labels: tuple[str, ...],
    *,
    line_gap: int,
) -> tuple[int, int]:
    line_h = measure.get_linesize()
    widths = [measure.size(option_text(label))[0] for label in labels]
    total_w = max(widths) if widths else 0
    count = len(labels)
    total_h = count * line_h + max(0, count - 1) * line_gap
    return total_w, total_h


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
    has_message = state.message is not None
    has_labeled = bool(state.labeled_lines)
    has_bar = state.progress_fraction is not None

    if state.message is not None:
        lines = message_lines(measure, state.message, screen_w=screen_w)
        msg_w = max((measure.size(line)[0] for line in lines), default=0)
        content_w = max(content_w, msg_w)
        content_h += len(lines) * line_h + max(0, len(lines) - 1) * line_gap

    if has_labeled:
        if has_message:
            content_h += line_h + line_gap
        labeled_w, labeled_h = measure_labeled_lines(
            measure, state.labeled_lines, line_gap=line_gap
        )
        content_w = max(content_w, labeled_w)
        content_h += labeled_h

    if has_bar:
        if has_message or has_labeled:
            content_h += line_h + line_gap
        content_h += BAR_HEIGHT

    if state.options:
        if has_message or has_labeled or has_bar:
            content_h += line_h + line_gap
        options_w, options_h = measure_options(
            measure, state.options, line_gap=line_gap
        )
        content_w = max(content_w, options_w)
        content_h += options_h

    return (
        max(content_w + PANEL_PAD_X * 2, panel_min_width(screen_w)),
        content_h + PANEL_PAD_Y * 2,
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


def text_button_widths(measure: TextMeasure) -> tuple[int, int]:
    return (
        measure.size(option_text(TEXT_BUTTON_LABELS[0]))[0],
        measure.size(option_text(TEXT_BUTTON_LABELS[1]))[0],
    )


def text_buttons_width(measure: TextMeasure) -> int:
    confirm_w, cancel_w = text_button_widths(measure)
    return confirm_w + TEXT_BUTTON_GAP + cancel_w


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
    cta_h = lines_block_height(cta_line_count, line_h, line_gap)
    section_gap = line_h + line_gap
    overhead = PANEL_PAD_Y * 2 + cta_h + section_gap * 2 + line_h
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
    cta_h = lines_block_height(len(cta_lines), line_h, line_gap)

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

    buttons_w = text_buttons_width(measure)
    buttons_h = line_h

    content_w = max(cta_w, field_w, buttons_w)
    if error_line is not None:
        content_w = max(content_w, min(measure.size(error_line)[0], wrap_w))
    content_h = cta_h + section_gap + field_h + section_gap + buttons_h
    if error_line is not None:
        content_h += line_h + line_gap
    return (
        max(content_w + PANEL_PAD_X * 2, panel_min_width(screen_w)),
        content_h + PANEL_PAD_Y * 2,
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
