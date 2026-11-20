"""ImGui modal panel. Draw records a pointer intent and does not call ModalHost."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Iterator

from imgui_bundle import imgui

from cleave.choice import ChoiceKind
from cleave.viz.brand import draw_logo
from cleave.viz.button_paint import ButtonState, ButtonTone, button_text_role, paint_button
from cleave.viz.choice_widgets import (
    draw_choice_list,
    draw_combo,
    draw_radio_list,
    draw_segments,
    draw_stepper,
)
from cleave.viz.imgui_theme import floating_surface, rgba
from cleave.viz.pointer_cursor import PointerShape, request_pointer
from cleave.viz.progress_bar import draw_progress_bar, progress_bar_height
from cleave.viz.row_paint import RowState, paint_row
from cleave.viz.text_edit import caret_line_column
from cleave.viz.modal import (
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
    banner_size,
    button_gap,
    button_widths,
    caret_index_at_point,
    focus_highlight_rect,
    form_control_width,
    form_field_height,
    form_heading_height,
    form_row_height,
    form_row_pad_y,
    form_section_indent,
    lines_block_height,
    measure_button_row,
    measure_panel,
    measure_text_panel,
    message_lines,
    body_lines,
    option_text,
    panel_labeled_lines,
    title_lines,
    panel_pad_x,
    panel_pad_y,
    single_line_scroll_x,
    text_cta_lines,
    text_error_line,
    text_field_lines,
    text_max_field_lines,
    title_bar_bottom,
    visible_field_lines,
)
from cleave.viz.title_bar import paint_title_bar
from cleave.viz.theme import BORDER_WIDTH, palette, tuning_ui_metrics

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
    PRESS_FORM_STEP = "press_form_step"
    RELEASE_FORM_STEP = "release_form_step"
    OPEN_FORM_CHOICE = "open_form_choice"
    HOVER_FORM_CHOICE = "hover_form_choice"
    PICK_FORM_CHOICE = "pick_form_choice"
    CLOSE_FORM_CHOICE = "close_form_choice"


@dataclass(frozen=True)
class ModalPointerIntent:
    """One pointer result for the frame.

    ``index`` is an option, a text button, or a form row. ``value`` is the form
    option chosen, the step for ``PRESS_FORM_STEP``, or the list row for
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
    elif kind is ModalPointerKind.PRESS_FORM_STEP:
        host.press_form_step(_intent_index(intent), intent.value)
    elif kind is ModalPointerKind.RELEASE_FORM_STEP:
        host.release_form_step()
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


def _outset(rect: Rect, pad: int = _HIGHLIGHT_PAD, *, pad_y: int | None = None) -> Rect:
    """Grow *rect* by *pad* on the sides and *pad_y* (default *pad*) top and bottom."""
    x, y, width, height = rect
    dy = pad if pad_y is None else pad_y
    return (x - pad, y - dy, width + 2 * pad, height + 2 * dy)


def _highlight_option(draw: imgui.ImDrawList, rect: Rect) -> None:
    """The focused row's look, matching a focused navigator or inspector row."""
    paint_row(draw, rect, RowState.FOCUSED)


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


def _draw_title_bar(
    draw: imgui.ImDrawList,
    panel: tuple[int, int, int],
    x: int,
    y: int,
    lines: list[str],
    line_h: int,
    line_gap: int,
    *,
    clip_w: int | None = None,
) -> int:
    """A modal's title in on_accent on a title bar across the panel, from its top
    border. *clip_w* cuts the title, not the bar. Returns the bar's bottom."""
    ox, oy, panel_w = panel
    bottom = title_bar_bottom(y, lines_block_height(len(lines), line_h, line_gap))
    paint_title_bar(
        draw,
        float(ox + BORDER_WIDTH),
        float(oy + BORDER_WIDTH),
        float(ox + panel_w - BORDER_WIDTH),
        float(bottom),
    )
    if clip_w is None:
        _draw_line_block(draw, x, y, lines, palette().on_accent, line_h, line_gap)
    else:
        with _clipped(draw, (x, y, clip_w, bottom - y)):
            _draw_line_block(draw, x, y, lines, palette().on_accent, line_h, line_gap)
    return bottom


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
        _text(draw, x, y, prefix, palette().label)
        _text(draw, x + measure.size(prefix)[0], y, line.value, palette().value)
        y += line_h
        if index + 1 < len(lines):
            y += line_gap
    return y


def _button_focused(view: ModalViewState, index: int, rect: Rect) -> bool:
    """A form's fields hold focus until Tab reaches the buttons. Hover still shows."""
    if view.kind is ModalKind.FORM and not view.form_buttons_focused:
        return _pointer_inside(rect)
    return index == view.focus_index


_BUTTON_TONES: dict[ButtonRole, ButtonTone] = {
    ButtonRole.PLAIN: ButtonTone.PLAIN,
    ButtonRole.PRIMARY: ButtonTone.PRIMARY,
    ButtonRole.DANGER: ButtonTone.DANGER,
}


def draw_modal_button(
    draw: imgui.ImDrawList,
    rect: Rect,
    label: str,
    role: ButtonRole,
    measure: TextMeasure,
    *,
    focused: bool,
    off: bool = False,
) -> None:
    """The modal button in its role's tone, lit while *focused*, sunk while pressed.

    Focus follows the pointer, so a focused button is the one hovered or
    reached by key; it lights like any hovered shell button. An *off* button
    (the text dialog's buttons while the field holds the keys) rests in the
    darker OFF tone with dimmed text.
    """
    x, y, w, h = rect
    state = ButtonState.REST
    if focused:
        held = _pointer_inside(rect) and imgui.is_mouse_down(0)
        state = ButtonState.PRESSED if held else ButtonState.HOVER
    resting_off = off and state is ButtonState.REST
    tone = ButtonTone.OFF if resting_off else _BUTTON_TONES[role]
    paint_button(draw, rect, tone, state)
    text = option_text(label)
    text_w, text_h = measure.size(text)
    rest_text = palette().off_control_text if resting_off else palette().value
    text_role = button_text_role(tone, state) or rest_text
    _text(draw, x + (w - text_w) // 2, y + (h - text_h) // 2, text, text_role)


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
    held: int | None = None,
) -> list[_FormHit]:
    """Segments, a stepper, or a combo that opens the row's list, filling ``rect``."""
    x, y, _w, h = rect
    if row.stepper:
        back, forward = draw_stepper(
            draw,
            measure,
            row.options[row.value],
            rect=rect,
            at_start=row.value <= 0,
            at_end=row.value >= len(row.options) - 1,
            held=None if held is None else held > 0,
            hover=hover,
        )
        return [
            _FormHit(back, ModalPointerKind.PRESS_FORM_STEP, index, -1),
            _FormHit(forward, ModalPointerKind.PRESS_FORM_STEP, index, 1),
        ]
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


def _draw_form_radio_list(
    draw: imgui.ImDrawList,
    measure: TextMeasure,
    row: FormRowView,
    index: int,
    *,
    left: int,
    right: int,
    y: int,
    line_h: int,
    hover: bool,
) -> list[_FormHit]:
    """A vertical field's options, one radio button per line, the first beside its label."""
    row_h = form_row_height(line_h)
    # The hover band reaches past the glyph like the focus outline does.
    band_left = left - _HIGHLIGHT_PAD - 1
    rows = tuple(
        (band_left, y + option * row_h, right - band_left, row_h)
        for option in range(len(row.options))
    )
    draw_radio_list(
        draw, measure, row.options, row.value, rows=rows, text_x=left, hover=hover
    )
    return [
        _FormHit(rect, ModalPointerKind.SET_FORM_VALUE, index, option)
        for option, rect in enumerate(rows)
    ]


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
    held_row, held_step = view.form_step_held or (None, None)
    left = ox + panel_pad_x()
    right = ox + panel_w - panel_pad_x()
    for index, row in enumerate(view.form_rows):
        if row.heading is not None:
            heading_h = form_heading_height(line_h, first=index == 0)
            heading_y = y + heading_h - form_row_height(line_h) + form_row_pad_y()
            _text(draw, left, heading_y, row.heading, palette().muted)
            y += heading_h
        height = form_field_height(line_h, row)
        row_left = left + (form_section_indent() if row.indented else 0)
        rect = (row_left, y, right - row_left, height)
        hits.append(_FormHit(rect, ModalPointerKind.FOCUS_FORM_ROW, index))
        if row.focused:
            # A 2px gap between the outline and the label / control.
            _highlight_option(draw, _outset(rect, _HIGHLIGHT_PAD + 1, pad_y=0))
        text_y = y + form_row_pad_y()
        label_rgb = palette().value if row.focused else palette().label
        _text(draw, row_left, text_y, row.label, label_rgb)
        width = form_control_width(measure, row)
        if row.vertical:
            controls[index] = (right - width, y, width, height)
            hits.extend(
                _draw_form_radio_list(
                    draw,
                    measure,
                    row,
                    index,
                    left=right - width,
                    right=right,
                    y=y,
                    line_h=line_h,
                    hover=open_row is None and held_row is None,
                )
            )
            y += height
            continue
        control = (right - width, text_y, width, line_h)
        controls[index] = control
        parts = _draw_form_control(
            draw,
            measure,
            row,
            index,
            rect=control,
            open_=open_row == index,
            hover=open_row is None and held_row is None,
            held=held_step if held_row == index else None,
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
        draw_modal_button(
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
        draw_modal_button(
            draw,
            rect,
            label,
            ButtonRole.PRIMARY if index == 0 else ButtonRole.PLAIN,
            measure,
            focused=focused or pointer_hover,
            off=field_focused and not pointer_hover,
        )
        rects.append(rect)
        bx += width + button_gap()
    return tuple(rects)


class ModalSurface:
    """Centred modal window. ``modal`` keeps the top-layer scrim up.

    ``intent`` is the pointer result of the last ``draw`` (one, or None).
    ``panel_rect``, ``option_rects``, ``text_button_rects``, and
    ``text_field_rect`` are that frame's hit targets, in screen pixels.
    ``passthrough`` returns rects, read at draw time, where a press does not
    cancel.
    """

    modal = True

    def __init__(
        self,
        view: ModalViewState,
        measure: TextMeasure,
        *,
        passthrough: Callable[[], tuple[Rect, ...]] = tuple,
    ) -> None:
        self.view = view
        self.measure = measure
        self._passthrough = passthrough
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
            with floating_surface():
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
            lines = title_lines(measure, view, screen_w=screen_w)
            y = _draw_title_bar(
                draw,
                (ox, oy, panel_w),
                x,
                y,
                lines,
                line_h,
                line_gap,
            )
        banner = banner_size(view, line_h, screen_w=screen_w)
        if view.banner is not None and banner is not None:
            y += panel_pad_y()
            banner_w, banner_h = banner
            draw_logo(
                draw,
                view.banner,
                (ox + (panel_w - banner_w) // 2, y, banner_w, banner_h),
                backdrop=palette().surface_bg,
            )
            y += banner_h
        if view.body is not None:
            if view.message is not None:
                y += panel_pad_y()
            y = _draw_line_block(
                draw,
                x,
                y,
                body_lines(measure, view, screen_w=screen_w),
                palette().value,
                line_h,
                line_gap,
            )
        if view.form_info is not None:
            if has_message:
                y += line_gap
            _text(draw, x, y, view.form_info, palette().highlight)
            y += line_h
        if has_labeled:
            if has_message:
                y += line_h + line_gap
            y = _draw_labeled(
                draw,
                x,
                y,
                panel_labeled_lines(measure, view, screen_w=screen_w),
                measure,
                line_h,
                line_gap,
            )
        if has_bar:
            if has_message or has_labeled:
                y += line_h + line_gap
            bar_h = progress_bar_height()
            draw_progress_bar(
                draw,
                (x, y, panel_w - panel_pad_x() * 2, bar_h),
                view.progress_fraction or 0.0,
            )
            y += bar_h
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
        if view.options:
            if has_message or has_labeled or has_bar:
                y += line_h + line_gap
            self.option_rects = _draw_button_row(
                draw, view, measure, ox=ox, panel_w=panel_w, y=y
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
        y = _draw_title_bar(
            draw,
            (ox, oy, panel_w),
            x,
            y,
            list(cta[:1]),
            line_h,
            line_gap,
            clip_w=content_w,
        )
        for line in cta[1:]:
            y += panel_pad_y()
            with _clipped(draw, (x, y, content_w, line_h)):
                _text(draw, x, y, line, palette().disabled)
            y += line_h
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
            _highlight_option(draw, (ox + hx, oy + hy, hw, hh))

        with _clipped(draw, field_rect):
            line_y = y
            for index, line in enumerate(visible):
                _text(draw, x - scroll_x, line_y, line, palette().value)
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
                    _packed(palette().highlight),
                )

        y += field_h
        if error is not None:
            y += line_gap
            with _clipped(draw, (x, y, content_w, line_h)):
                _text(draw, x, y, error, palette().highlight)
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
        progress = self.view.kind == ModalKind.PROGRESS
        if progress and not self.view.options:
            return
        if self.view.form_choice is not None:
            # The open list takes the pointer; see _draw_form_choice.
            return
        io = imgui.get_io()
        if self.view.form_step_held is not None:
            # A held stepper arrow owns the pointer until the button comes up.
            if not io.mouse_down[0]:
                self.intent = ModalPointerIntent(ModalPointerKind.RELEASE_FORM_STEP)
            return
        pos = io.mouse_pos
        x, y = float(pos.x), float(pos.y)
        clicked = bool(io.mouse_clicked[0])
        if any(_contains(rect, x, y) for rect in self._passthrough()):
            return
        if self.view.kind == ModalKind.TEXT:
            self._record_text(panel, x, y, clicked)
            return
        hit = _index_at(self.option_rects, x, y)
        if hit is not None:
            request_pointer(PointerShape.HAND)
        if clicked and hit is not None:
            self.intent = ModalPointerIntent(
                ModalPointerKind.ACTIVATE_OPTION, index=hit
            )
            return
        if clicked and self._record_form_click(x, y):
            return
        if clicked and not progress and not _contains(panel, x, y):
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
        if in_field:
            request_pointer(PointerShape.TEXT)
        elif button is not None:
            request_pointer(PointerShape.HAND)
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
