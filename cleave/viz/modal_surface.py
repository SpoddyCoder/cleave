"""ImGui modal panel. Draw records a pointer intent and does not call ModalHost."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Iterator

from imgui_bundle import imgui

from cleave.choice import ChoiceKind
from cleave.viz.choice_widgets import draw_choice_list, draw_combo, draw_segments
from cleave.viz.imgui_theme import rgba
from cleave.viz.text_edit import caret_line_column
from cleave.viz.modal import (
    BUTTON_ROW_KINDS,
    ButtonRole,
    FormRowView,
    ModalHost,
    ModalKind,
    ModalLabeledLine,
    ModalViewState,
    TextFocusRegion,
)
from cleave.viz.modal_layout import (
    CARET_WIDTH,
    TEXT_BUTTON_LABELS,
    TextMeasure,
    bar_height,
    button_gap,
    button_widths,
    caret_index_at_point,
    focus_highlight_rect,
    form_control_width,
    form_row_height,
    form_row_pad_y,
    lines_block_height,
    measure_button_row,
    measure_options,
    measure_panel,
    measure_text_panel,
    message_lines,
    option_text,
    panel_pad_x,
    panel_pad_y,
    single_line_scroll_x,
    text_cta_lines,
    text_error_line,
    text_field_lines,
    text_max_field_lines,
    visible_field_lines,
)
from cleave.viz.theme import (
    BORDER_COLOR,
    BORDER_WIDTH,
    BUTTON_BG,
    BUTTON_BORDER,
    BUTTON_DANGER_BG,
    BUTTON_PRIMARY_BG,
    DISABLED,
    FOCUS_BORDER_ALPHA,
    FOCUS_WASH_ALPHA,
    HIGHLIGHT,
    LABEL,
    VALUE,
    tuning_ui_metrics,
)

Rect = tuple[int, int, int, int]
_Role = tuple[int, int, int]

_MODAL_WINDOW = "##modal"
_MODAL_FLAGS = (
    int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_nav)
    | int(imgui.WindowFlags_.no_bring_to_front_on_focus)
    | int(imgui.WindowFlags_.no_scrollbar)
)
_WASH_ALPHA = FOCUS_WASH_ALPHA / 255.0
_FOCUS_BORDER_ALPHA = FOCUS_BORDER_ALPHA / 255.0
_FOCUS_BORDER_THICKNESS = 1.0
_HIGHLIGHT_PAD = 2


class ModalPointerKind(Enum):
    HOVER_OPTION = "hover_option"
    ACTIVATE_OPTION = "activate_option"
    CANCEL = "cancel"
    FOCUS_TEXT_FIELD = "focus_text_field"
    HOVER_TEXT_FIELD = "hover_text_field"
    HOVER_TEXT_BUTTON = "hover_text_button"
    ACTIVATE_TEXT_BUTTON = "activate_text_button"
    FOCUS_FORM_ROW = "focus_form_row"
    SET_FORM_VALUE = "set_form_value"
    STEP_FORM_VALUE = "step_form_value"
    OPEN_FORM_CHOICE = "open_form_choice"
    HOVER_FORM_CHOICE = "hover_form_choice"
    PICK_FORM_CHOICE = "pick_form_choice"
    CLOSE_FORM_CHOICE = "close_form_choice"


@dataclass(frozen=True)
class ModalPointerIntent:
    """One pointer result for the frame.

    ``index`` is an option, a text button, or a form row. ``value`` is the form
    option chosen, the step for ``STEP_FORM_VALUE``, or the list row for
    ``HOVER_FORM_CHOICE`` and ``PICK_FORM_CHOICE``.
    """

    kind: ModalPointerKind
    index: int | None = None
    caret_index: int | None = None
    value: int = 0


def _intent_index(intent: ModalPointerIntent) -> int:
    return 0 if intent.index is None else intent.index


def apply_modal_pointer(host: ModalHost, intent: ModalPointerIntent | None) -> None:
    """Map one recorded intent onto ``ModalHost``. ``None`` does nothing."""
    if intent is None:
        return
    kind = intent.kind
    if kind is ModalPointerKind.HOVER_OPTION:
        host.hover_option(_intent_index(intent))
    elif kind is ModalPointerKind.ACTIVATE_OPTION:
        host.activate_option(_intent_index(intent))
    elif kind is ModalPointerKind.CANCEL:
        host.cancel()
    elif kind is ModalPointerKind.FOCUS_TEXT_FIELD:
        caret = 0 if intent.caret_index is None else intent.caret_index
        host.focus_text_field(caret)
    elif kind is ModalPointerKind.HOVER_TEXT_FIELD:
        host.hover_text_field()
    elif kind is ModalPointerKind.HOVER_TEXT_BUTTON:
        host.hover_text_button(_intent_index(intent))
    elif kind is ModalPointerKind.ACTIVATE_TEXT_BUTTON:
        host.activate_text_button(_intent_index(intent))
    elif kind is ModalPointerKind.FOCUS_FORM_ROW:
        host.focus_form_row(_intent_index(intent))
    elif kind is ModalPointerKind.SET_FORM_VALUE:
        host.set_form_value(_intent_index(intent), intent.value)
    elif kind is ModalPointerKind.STEP_FORM_VALUE:
        host.step_form_value(_intent_index(intent), intent.value)
    elif kind is ModalPointerKind.OPEN_FORM_CHOICE:
        host.open_form_choice(_intent_index(intent))
    elif kind is ModalPointerKind.HOVER_FORM_CHOICE:
        host.hover_form_choice(intent.value)
    elif kind is ModalPointerKind.PICK_FORM_CHOICE:
        host.pick_form_choice(intent.value)
    elif kind is ModalPointerKind.CLOSE_FORM_CHOICE:
        host.close_form_choice()


@dataclass(frozen=True)
class _TextFieldHit:
    lines: tuple[str, ...]
    visible_start: int
    scroll_x: int
    line_gap: int


class ImGuiTextMeasure:
    """``TextMeasure`` for the current ImGui font. Valid only inside a frame."""

    def size(self, text: str) -> tuple[int, int]:
        measured = imgui.calc_text_size(text)
        return (int(measured.x), int(measured.y))

    def get_linesize(self) -> int:
        return max(1, int(round(imgui.get_text_line_height())))


def text_field_wrap(display_w: int) -> Callable[[str], list[str]]:
    """Wrap a draft the way the field is drawn. The font must already be current."""
    measure = ImGuiTextMeasure()

    def wrap_draft(draft: str) -> list[str]:
        if not draft:
            return [""]
        lines = message_lines(measure, draft, screen_w=display_w)
        return lines if lines else [""]

    return wrap_draft


def _packed(role: _Role, alpha: float = 1.0) -> int:
    return int(imgui.get_color_u32(rgba(role, alpha)))


def _contains(rect: Rect, x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rw > 0 and rh > 0 and rx <= x < rx + rw and ry <= y < ry + rh


def _index_at(rects: tuple[Rect, ...], x: float, y: float) -> int | None:
    for index, rect in enumerate(rects):
        if _contains(rect, x, y):
            return index
    return None


def _raise_modal() -> None:
    imgui.internal.bring_window_to_display_front(
        imgui.internal.find_window_by_name(_MODAL_WINDOW)
    )


def _text(draw: imgui.ImDrawList, x: int, y: int, text: str, role: _Role) -> None:
    if not text:
        return
    draw.add_text(imgui.ImVec2(float(x), float(y)), _packed(role), text)


def _wash(draw: imgui.ImDrawList, rect: Rect) -> None:
    x, y, width, height = rect
    if width <= 0 or height <= 0:
        return
    draw.add_rect_filled(
        imgui.ImVec2(float(x), float(y)),
        imgui.ImVec2(float(x + width), float(y + height)),
        _packed(HIGHLIGHT, _WASH_ALPHA),
    )


def _focus_border(draw: imgui.ImDrawList, rect: Rect) -> None:
    """1px highlight outline, matching a focused navigator or inspector row."""
    x, y, width, height = rect
    if width <= 0 or height <= 0:
        return
    draw.add_rect(
        imgui.ImVec2(float(x), float(y)),
        imgui.ImVec2(float(x + width), float(y + height)),
        _packed(HIGHLIGHT, _FOCUS_BORDER_ALPHA),
        0.0,
        0,
        _FOCUS_BORDER_THICKNESS,
    )


def _outset(rect: Rect, pad: int = _HIGHLIGHT_PAD, *, pad_y: int | None = None) -> Rect:
    """Grow *rect* by *pad* on the sides and *pad_y* (default *pad*) top and bottom."""
    x, y, width, height = rect
    dy = pad if pad_y is None else pad_y
    return (x - pad, y - dy, width + 2 * pad, height + 2 * dy)


def _highlight_option(draw: imgui.ImDrawList, rect: Rect) -> None:
    _wash(draw, rect)
    _focus_border(draw, rect)


def _pointer_inside(rect: Rect) -> bool:
    pos = imgui.get_io().mouse_pos
    return _contains(rect, float(pos.x), float(pos.y))


@contextmanager
def _clipped(draw: imgui.ImDrawList, rect: Rect) -> Iterator[None]:
    x, y, width, height = rect
    draw.push_clip_rect(
        imgui.ImVec2(float(x), float(y)),
        imgui.ImVec2(float(x + width), float(y + height)),
        True,
    )
    try:
        yield
    finally:
        draw.pop_clip_rect()


def _draw_line_block(
    draw: imgui.ImDrawList,
    x: int,
    y: int,
    lines: list[str],
    role: _Role,
    line_h: int,
    line_gap: int,
) -> int:
    for index, line in enumerate(lines):
        _text(draw, x, y, line, role)
        y += line_h
        if index + 1 < len(lines):
            y += line_gap
    return y


def _draw_labeled(
    draw: imgui.ImDrawList,
    x: int,
    y: int,
    lines: tuple[ModalLabeledLine, ...],
    measure: TextMeasure,
    line_h: int,
    line_gap: int,
) -> int:
    for index, line in enumerate(lines):
        prefix = line.prefix()
        _text(draw, x, y, prefix, LABEL)
        _text(draw, x + measure.size(prefix)[0], y, line.value, VALUE)
        y += line_h
        if index + 1 < len(lines):
            y += line_gap
    return y


def _draw_bar(
    draw: imgui.ImDrawList, x: int, y: int, width: int, fraction: float
) -> None:
    if width <= 0:
        return
    frac = max(0.0, min(1.0, fraction))
    inner_w = width - 2 * BORDER_WIDTH
    inner_h = bar_height() - 2 * BORDER_WIDTH
    fill_w = min(inner_w, int(round(inner_w * frac)))
    if fill_w > 0 and inner_h > 0:
        draw.add_rect_filled(
            imgui.ImVec2(float(x + BORDER_WIDTH), float(y + BORDER_WIDTH)),
            imgui.ImVec2(
                float(x + BORDER_WIDTH + fill_w),
                float(y + BORDER_WIDTH + inner_h),
            ),
            _packed(VALUE),
        )
    draw.add_rect(
        imgui.ImVec2(float(x), float(y)),
        imgui.ImVec2(float(x + width), float(y + bar_height())),
        _packed(BORDER_COLOR),
        0.0,
        0,
        float(BORDER_WIDTH),
    )


def _draw_options(
    draw: imgui.ImDrawList,
    view: ModalViewState,
    measure: TextMeasure,
    *,
    ox: int,
    oy: int,
    panel_w: int,
    y: int,
    line_h: int,
    line_gap: int,
) -> tuple[Rect, ...]:
    labels = view.options
    options_w, _ = measure_options(measure, labels, line_gap=line_gap)
    content_w = panel_w - panel_pad_x() * 2
    option_x = ox + panel_pad_x() + max(0, (content_w - options_w) // 2)
    rects: list[Rect] = []
    for index, label in enumerate(labels):
        focused = index == view.focus_index
        hx, hy, hw, hh = focus_highlight_rect(
            measure, panel_width=panel_w, y=y - oy, line_h=line_h
        )
        rect = _outset((ox + hx, oy + hy, hw, hh))
        if focused:
            _highlight_option(draw, rect)
        text = option_text(label)
        text_w = measure.size(text)[0]
        text_x = option_x + max(0, (options_w - text_w) // 2)
        _text(draw, text_x, y, text, HIGHLIGHT if focused else VALUE)
        rects.append(rect)
        y += line_h + line_gap
    return tuple(rects)


def _button_focused(view: ModalViewState, index: int, rect: Rect) -> bool:
    """A form's fields hold focus until Tab reaches the buttons. Hover still shows."""
    if view.kind is ModalKind.FORM and not view.form_buttons_focused:
        return _pointer_inside(rect)
    return index == view.focus_index


_BUTTON_FILLS: dict[ButtonRole, _Role] = {
    ButtonRole.PLAIN: BUTTON_BG,
    ButtonRole.PRIMARY: BUTTON_PRIMARY_BG,
    ButtonRole.DANGER: BUTTON_DANGER_BG,
}


def _draw_button(
    draw: imgui.ImDrawList,
    rect: Rect,
    label: str,
    role: ButtonRole,
    measure: TextMeasure,
    *,
    focused: bool,
    text_role: _Role = VALUE,
) -> None:
    """The modal button: role fill, border, centred label, focus outline."""
    x, y, w, h = rect
    top_left = imgui.ImVec2(float(x), float(y))
    bottom_right = imgui.ImVec2(float(x + w), float(y + h))
    border = role is ButtonRole.PLAIN
    fill = _BUTTON_FILLS[role]
    draw.add_rect_filled(top_left, bottom_right, _packed(fill))
    draw.add_rect(top_left, bottom_right, _packed(BUTTON_BORDER if border else fill))
    text = option_text(label)
    text_w, text_h = measure.size(text)
    _text(draw, x + (w - text_w) // 2, y + (h - text_h) // 2, text, text_role)
    if focused:
        _focus_border(draw, _outset(rect))


@dataclass(frozen=True)
class _FormHit:
    """A clickable part of a form row. ``kind`` says what a click does."""

    rect: Rect
    kind: ModalPointerKind
    row: int
    value: int = 0


def _draw_form_control(
    draw: imgui.ImDrawList,
    measure: TextMeasure,
    row: FormRowView,
    index: int,
    *,
    rect: Rect,
    open_: bool,
    hover: bool,
) -> list[_FormHit]:
    """Segments, or a combo that opens the row's list, filling ``rect``."""
    x, y, _w, h = rect
    if row.kind is ChoiceKind.SEGMENT:
        rects = draw_segments(
            draw, measure, row.options, row.value, x=x, y=y, height=h, hover=hover
        )
        return [
            _FormHit(segment, ModalPointerKind.SET_FORM_VALUE, index, option)
            for option, segment in enumerate(rects)
        ]
    draw_combo(
        draw, measure, row.options[row.value], rect=rect, open_=open_, hover=hover
    )
    return [_FormHit(rect, ModalPointerKind.OPEN_FORM_CHOICE, index)]


def _draw_form_rows(
    draw: imgui.ImDrawList,
    view: ModalViewState,
    measure: TextMeasure,
    *,
    ox: int,
    panel_w: int,
    y: int,
    line_h: int,
    line_gap: int,
) -> tuple[int, tuple[_FormHit, ...], dict[int, Rect]]:
    """Draw every field.

    Returns the y below them, the clickable parts, and each row's control rect
    (the anchor for an open list).
    """
    hits: list[_FormHit] = []
    controls: dict[int, Rect] = {}
    open_row = None if view.form_choice is None else view.form_choice.target
    left = ox + panel_pad_x()
    right = ox + panel_w - panel_pad_x()
    for index, row in enumerate(view.form_rows):
        height = form_row_height(line_h)
        rect = (left, y, right - left, height)
        hits.append(_FormHit(rect, ModalPointerKind.FOCUS_FORM_ROW, index))
        if row.focused:
            # A 2px gap between the outline and the label / control.
            _highlight_option(draw, _outset(rect, _HIGHLIGHT_PAD + 1, pad_y=0))
        text_y = y + form_row_pad_y()
        _text(draw, left, text_y, row.label, HIGHLIGHT if row.focused else LABEL)
        width = form_control_width(measure, row)
        control = (right - width, text_y, width, line_h)
        controls[index] = control
        parts = _draw_form_control(
            draw,
            measure,
            row,
            index,
            rect=control,
            open_=open_row == index,
            hover=open_row is None,
        )
        hits.extend(parts)
        y += height
    return y, tuple(hits), controls


def _draw_button_row(
    draw: imgui.ImDrawList,
    view: ModalViewState,
    measure: TextMeasure,
    *,
    ox: int,
    panel_w: int,
    y: int,
) -> tuple[Rect, ...]:
    """Buttons along the bottom right of the panel, in option order."""
    widths = button_widths(measure, view.options)
    total_w, height = measure_button_row(measure, view.options)
    x = ox + panel_w - panel_pad_x() - total_w
    rects: list[Rect] = []
    for index, label in enumerate(view.options):
        rect = (x, y, widths[index], height)
        _draw_button(
            draw,
            rect,
            label,
            view.option_roles[index],
            measure,
            focused=_button_focused(view, index, rect),
        )
        rects.append(rect)
        x += widths[index] + button_gap()
    return tuple(rects)


def _draw_text_buttons(
    draw: imgui.ImDrawList,
    view: ModalViewState,
    measure: TextMeasure,
    *,
    ox: int,
    panel_w: int,
    y: int,
    line_h: int,
) -> tuple[Rect, ...]:
    widths = button_widths(measure, TEXT_BUTTON_LABELS)
    total_w, height = measure_button_row(measure, TEXT_BUTTON_LABELS)
    bx = ox + panel_w - panel_pad_x() - total_w
    buttons_focused = view.focus_region == TextFocusRegion.BUTTONS
    field_focused = view.focus_region == TextFocusRegion.FIELD
    rects: list[Rect] = []
    for index, label in enumerate(TEXT_BUTTON_LABELS):
        width = widths[index]
        rect = (bx, y, width, height)
        focused = buttons_focused and view.button_index == index
        # The caret stays put while editing. The button under the pointer
        # still takes the hover highlight; only a click leaves the field.
        pointer_hover = view.editing and _pointer_inside(rect)
        _draw_button(
            draw,
            rect,
            label,
            ButtonRole.PRIMARY if index == 0 else ButtonRole.PLAIN,
            measure,
            focused=focused or pointer_hover,
            text_role=DISABLED if field_focused and not pointer_hover else VALUE,
        )
        rects.append(rect)
        bx += width + button_gap()
    return tuple(rects)


class ModalSurface:
    """Centred modal window. ``modal`` keeps the top-layer scrim up.

    ``intent`` is the pointer result of the last ``draw`` (one, or None).
    ``panel_rect``, ``option_rects``, ``text_button_rects``, and
    ``text_field_rect`` are that frame's hit targets, in screen pixels.
    """

    modal = True

    def __init__(self, view: ModalViewState, measure: TextMeasure) -> None:
        self.view = view
        self.measure = measure
        self.intent: ModalPointerIntent | None = None
        self.panel_rect: Rect | None = None
        self.option_rects: tuple[Rect, ...] = ()
        self.text_button_rects: tuple[Rect, ...] = ()
        self._form_hits: tuple[_FormHit, ...] = ()
        self._form_controls: dict[int, Rect] = {}
        self.choice_list_rows: tuple[Rect, ...] = ()
        self.text_field_rect: Rect | None = None
        self._text_field_hit: _TextFieldHit | None = None

    def draw(self) -> Rect:
        self.intent = None
        self.panel_rect = None
        self.option_rects = ()
        self.text_button_rects = ()
        self._form_hits = ()
        self._form_controls = {}
        self.choice_list_rows = ()
        self.text_field_rect = None
        self._text_field_hit = None

        display = imgui.get_io().display_size
        screen_w = max(1, int(display.x))
        screen_h = max(1, int(display.y))
        line_gap = tuning_ui_metrics().line_gap
        view = self.view
        if view.kind == ModalKind.TEXT:
            panel_w, panel_h = measure_text_panel(
                self.measure,
                view,
                line_gap=line_gap,
                screen_w=screen_w,
                screen_h=screen_h,
            )
        else:
            panel_w, panel_h = measure_panel(
                self.measure, view, line_gap=line_gap, screen_w=screen_w
            )

        imgui.set_next_window_pos(
            imgui.ImVec2(display.x * 0.5, display.y * 0.5),
            imgui.Cond_.always,
            imgui.ImVec2(0.5, 0.5),
        )
        imgui.set_next_window_size(
            imgui.ImVec2(float(panel_w), float(panel_h)),
            imgui.Cond_.always,
        )
        # Pad is inside the measured size. Zero ImGui padding keeps that inset.
        # Pop however many pushes landed so a failure between them cannot leak.
        pushed = 0
        begun = False
        try:
            imgui.push_style_var(
                imgui.StyleVar_.window_padding, imgui.ImVec2(0.0, 0.0)
            )
            pushed += 1
            imgui.push_style_var(
                imgui.StyleVar_.window_border_size, float(BORDER_WIDTH)
            )
            pushed += 1
            imgui.begin(_MODAL_WINDOW, None, _MODAL_FLAGS)
            begun = True
            _raise_modal()
            pos = imgui.get_window_pos()
            size = imgui.get_window_size()
            ox, oy = int(pos.x), int(pos.y)
            if view.kind == ModalKind.TEXT:
                self._draw_text(ox, oy, panel_w, line_gap, screen_w, screen_h)
            else:
                self._draw_standard(ox, oy, panel_w, line_gap, screen_w)
            panel = (ox, oy, max(0, int(size.x)), max(0, int(size.y)))
            self.panel_rect = panel
            self._record_pointer(panel)
        finally:
            try:
                if begun:
                    imgui.end()
            finally:
                if pushed:
                    imgui.pop_style_var(pushed)
        self._draw_form_choice()
        return panel

    def _draw_form_choice(self) -> None:
        """The open combo list of a form row, above the panel. It owns the pointer."""
        choice = self.view.form_choice
        if choice is None:
            return
        anchor = self._form_controls.get(int(choice.target))
        if anchor is None:
            return
        pointer = draw_choice_list(
            "modal-choice-list", choice, self.measure, anchor=anchor
        )
        self.choice_list_rows = pointer.rows
        if pointer.picked is not None:
            self.intent = ModalPointerIntent(
                ModalPointerKind.PICK_FORM_CHOICE, value=pointer.picked
            )
        elif pointer.outside:
            self.intent = ModalPointerIntent(ModalPointerKind.CLOSE_FORM_CHOICE)
        elif pointer.hovered is not None:
            self.intent = ModalPointerIntent(
                ModalPointerKind.HOVER_FORM_CHOICE, value=pointer.hovered
            )

    def _draw_standard(
        self, ox: int, oy: int, panel_w: int, line_gap: int, screen_w: int
    ) -> None:
        view = self.view
        measure = self.measure
        line_h = measure.get_linesize()
        x = ox + panel_pad_x()
        y = oy + panel_pad_y()
        draw = imgui.get_window_draw_list()
        has_message = view.message is not None or view.body is not None
        has_labeled = bool(view.labeled_lines)
        has_bar = view.progress_fraction is not None
        if view.message is not None:
            y = _draw_line_block(
                draw,
                x,
                y,
                message_lines(measure, view.message, screen_w=screen_w),
                LABEL,
                line_h,
                line_gap,
            )
        if view.body is not None:
            if view.message is not None:
                y += line_gap
            y = _draw_line_block(
                draw,
                x,
                y,
                message_lines(measure, view.body, screen_w=screen_w),
                VALUE,
                line_h,
                line_gap,
            )
        if has_labeled:
            if has_message:
                y += line_h + line_gap
            y = _draw_labeled(
                draw, x, y, view.labeled_lines, measure, line_h, line_gap
            )
        if has_bar:
            if has_message or has_labeled:
                y += line_h + line_gap
            _draw_bar(
                draw,
                x,
                y,
                panel_w - panel_pad_x() * 2,
                view.progress_fraction or 0.0,
            )
            y += bar_height()
        if view.form_rows or view.form_info is not None:
            if has_message:
                y += line_h
            y, self._form_hits, self._form_controls = _draw_form_rows(
                draw,
                view,
                measure,
                ox=ox,
                panel_w=panel_w,
                y=y,
                line_h=line_h,
                line_gap=line_gap,
            )
            if view.form_info is not None:
                y += line_gap
                _text(draw, x, y, view.form_info, HIGHLIGHT)
                y += line_h
        if view.options:
            if has_message or has_labeled or has_bar:
                y += line_h + line_gap
            if view.kind in BUTTON_ROW_KINDS:
                self.option_rects = _draw_button_row(
                    draw, view, measure, ox=ox, panel_w=panel_w, y=y
                )
                return
            self.option_rects = _draw_options(
                draw,
                view,
                measure,
                ox=ox,
                oy=oy,
                panel_w=panel_w,
                y=y,
                line_h=line_h,
                line_gap=line_gap,
            )

    def _draw_text(
        self,
        ox: int,
        oy: int,
        panel_w: int,
        line_gap: int,
        screen_w: int,
        screen_h: int,
    ) -> None:
        view = self.view
        measure = self.measure
        line_h = measure.get_linesize()
        section_gap = line_h + line_gap
        x = ox + panel_pad_x()
        content_w = panel_w - panel_pad_x() * 2
        y = oy + panel_pad_y()
        draw = imgui.get_window_draw_list()

        cta = text_cta_lines(view)
        for index, line in enumerate(cta):
            role = DISABLED if index > 0 else LABEL
            with _clipped(draw, (x, y, content_w, line_h)):
                _text(draw, x, y, line, role)
            y += line_h
            if index + 1 < len(cta):
                y += line_gap
        y += section_gap

        draft = view.draft if view.draft is not None else ""
        field_lines = text_field_lines(measure, view, screen_w=screen_w)
        error = text_error_line(view)
        caret_line, caret_col = caret_line_column(
            draft, field_lines, view.caret_index
        )
        max_lines = text_max_field_lines(
            line_h=line_h,
            line_gap=line_gap,
            screen_h=screen_h,
            cta_line_count=len(cta),
            has_error=error is not None,
        )
        visible, visual_caret = visible_field_lines(
            field_lines, caret_line, max_lines
        )
        clamped = max(0, min(caret_line, max(0, len(field_lines) - 1)))
        field_h = lines_block_height(len(visible), line_h, line_gap)
        field_rect = (x, y, content_w, field_h)
        scroll_x = 0
        if view.single_line:
            field_line = visible[0] if visible else ""
            scroll_x = single_line_scroll_x(
                measure, field_line, caret_col, content_w
            )
        self.text_field_rect = field_rect
        self._text_field_hit = _TextFieldHit(
            lines=tuple(field_lines),
            visible_start=clamped - visual_caret,
            scroll_x=scroll_x,
            line_gap=line_gap,
        )

        if not view.editing and view.focus_region == TextFocusRegion.FIELD:
            hx, hy, hw, hh = focus_highlight_rect(
                measure, panel_width=panel_w, y=y - oy, line_h=field_h
            )
            _wash(draw, (ox + hx, oy + hy, hw, hh))

        with _clipped(draw, field_rect):
            line_y = y
            for index, line in enumerate(visible):
                _text(draw, x - scroll_x, line_y, line, VALUE)
                line_y += line_h
                if index + 1 < len(visible):
                    line_y += line_gap
            if view.caret_visible and visible:
                caret_text = (
                    visible[visual_caret]
                    if 0 <= visual_caret < len(visible)
                    else ""
                )
                column = max(0, min(caret_col, len(caret_text)))
                caret_x = x + measure.size(caret_text[:column])[0] - scroll_x
                caret_y = y + visual_caret * (line_h + line_gap)
                draw.add_rect_filled(
                    imgui.ImVec2(float(caret_x), float(caret_y)),
                    imgui.ImVec2(
                        float(caret_x + CARET_WIDTH), float(caret_y + line_h)
                    ),
                    _packed(HIGHLIGHT),
                )

        y += field_h
        if error is not None:
            y += line_gap
            with _clipped(draw, (x, y, content_w, line_h)):
                _text(draw, x, y, error, HIGHLIGHT)
            y += line_h
        y += section_gap
        self.text_button_rects = _draw_text_buttons(
            draw,
            view,
            measure,
            ox=ox,
            panel_w=panel_w,
            y=y,
            line_h=line_h,
        )

    def _record_pointer(self, panel: Rect) -> None:
        if self.view.kind == ModalKind.PROGRESS:
            return
        if self.view.form_choice is not None:
            # The open list takes the pointer; see _draw_form_choice.
            return
        io = imgui.get_io()
        pos = io.mouse_pos
        x, y = float(pos.x), float(pos.y)
        clicked = bool(io.mouse_clicked[0])
        if self.view.kind == ModalKind.TEXT:
            self._record_text(panel, x, y, clicked)
            return
        hit = _index_at(self.option_rects, x, y)
        if clicked and hit is not None:
            self.intent = ModalPointerIntent(
                ModalPointerKind.ACTIVATE_OPTION, index=hit
            )
            return
        if clicked and self._record_form_click(x, y):
            return
        if clicked and not _contains(panel, x, y):
            self.intent = ModalPointerIntent(ModalPointerKind.CANCEL)
            return
        if hit is not None:
            self.intent = ModalPointerIntent(
                ModalPointerKind.HOVER_OPTION, index=hit
            )

    def _record_form_click(self, x: float, y: float) -> bool:
        """Take the smallest part under the pointer: a control over its row."""
        for form_hit in reversed(self._form_hits):
            if _contains(form_hit.rect, x, y):
                self.intent = ModalPointerIntent(
                    form_hit.kind, index=form_hit.row, value=form_hit.value
                )
                return True
        return False

    def _record_text(
        self, panel: Rect, x: float, y: float, clicked: bool
    ) -> None:
        field = self.text_field_rect
        in_field = field is not None and _contains(field, x, y)
        button = _index_at(self.text_button_rects, x, y)
        if clicked and in_field:
            self.intent = ModalPointerIntent(
                ModalPointerKind.FOCUS_TEXT_FIELD,
                caret_index=self._caret_at(x, y),
            )
            return
        if clicked and button is not None:
            self.intent = ModalPointerIntent(
                ModalPointerKind.ACTIVATE_TEXT_BUTTON, index=button
            )
            return
        if clicked and not _contains(panel, x, y):
            self.intent = ModalPointerIntent(ModalPointerKind.CANCEL)
            return
        if in_field:
            self.intent = ModalPointerIntent(ModalPointerKind.HOVER_TEXT_FIELD)
            return
        # Hover must not steal the caret. A click on the button is
        # ACTIVATE_TEXT_BUTTON, which commits or discards and runs it.
        if button is not None and not self.view.editing:
            self.intent = ModalPointerIntent(
                ModalPointerKind.HOVER_TEXT_BUTTON, index=button
            )

    def _caret_at(self, x: float, y: float) -> int:
        hit = self._text_field_hit
        field = self.text_field_rect
        if hit is None or field is None:
            return 0
        return caret_index_at_point(
            self.view.draft if self.view.draft is not None else "",
            list(hit.lines),
            hit.visible_start,
            int(x - field[0]),
            int(y - field[1]),
            self.measure,
            hit.line_gap,
            hit.scroll_x,
        )
