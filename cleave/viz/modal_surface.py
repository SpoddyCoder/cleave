"""ImGui modal panel. Draw records a pointer intent and does not call ModalHost."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Iterator

from imgui_bundle import imgui

from cleave.viz.imgui_theme import rgba
from cleave.viz.modal import (
    ModalHost,
    ModalKind,
    ModalLabeledLine,
    ModalViewState,
    TextFocusRegion,
    caret_line_column,
)
from cleave.viz.modal_layout import (
    BAR_HEIGHT,
    CARET_WIDTH,
    PANEL_PAD_X,
    PANEL_PAD_Y,
    TEXT_BUTTON_GAP,
    TEXT_BUTTON_LABELS,
    TextMeasure,
    caret_index_at_point,
    focus_highlight_rect,
    lines_block_height,
    measure_options,
    measure_panel,
    measure_text_panel,
    message_lines,
    option_text,
    single_line_scroll_x,
    text_button_widths,
    text_cta_lines,
    text_error_line,
    text_field_lines,
    text_max_field_lines,
    visible_field_lines,
)
from cleave.viz.theme import (
    BORDER_COLOR,
    BORDER_WIDTH,
    DISABLED,
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


class ModalPointerKind(Enum):
    HOVER_OPTION = "hover_option"
    ACTIVATE_OPTION = "activate_option"
    CANCEL = "cancel"
    FOCUS_TEXT_FIELD = "focus_text_field"
    HOVER_TEXT_FIELD = "hover_text_field"
    HOVER_TEXT_BUTTON = "hover_text_button"
    ACTIVATE_TEXT_BUTTON = "activate_text_button"


@dataclass(frozen=True)
class ModalPointerIntent:
    """One pointer result for the frame. ``index`` is an option or text button."""

    kind: ModalPointerKind
    index: int | None = None
    caret_index: int | None = None


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
    inner_h = BAR_HEIGHT - 2 * BORDER_WIDTH
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
        imgui.ImVec2(float(x + width), float(y + BAR_HEIGHT)),
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
    content_w = panel_w - PANEL_PAD_X * 2
    option_x = ox + PANEL_PAD_X + max(0, (content_w - options_w) // 2)
    rects: list[Rect] = []
    for index, label in enumerate(labels):
        focused = index == view.focus_index
        hx, hy, hw, hh = focus_highlight_rect(
            measure, panel_width=panel_w, y=y - oy, line_h=line_h
        )
        rect = (ox + hx, oy + hy, hw, hh)
        if focused:
            _wash(draw, rect)
        text = option_text(label)
        text_w = measure.size(text)[0]
        text_x = option_x + max(0, (options_w - text_w) // 2)
        _text(draw, text_x, y, text, HIGHLIGHT if focused else VALUE)
        rects.append(rect)
        y += line_h + line_gap
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
    confirm_w, cancel_w = text_button_widths(measure)
    total_w = confirm_w + TEXT_BUTTON_GAP + cancel_w
    content_w = panel_w - PANEL_PAD_X * 2
    bx = ox + PANEL_PAD_X + max(0, (content_w - total_w) // 2)
    buttons_focused = view.focus_region == TextFocusRegion.BUTTONS
    field_focused = view.focus_region == TextFocusRegion.FIELD
    rects: list[Rect] = []
    for index, label in enumerate(TEXT_BUTTON_LABELS):
        width = (confirm_w, cancel_w)[index]
        rect = (bx, y, width, line_h)
        focused = buttons_focused and view.button_index == index
        if focused:
            _wash(draw, rect)
            role: _Role = HIGHLIGHT
        elif field_focused:
            role = DISABLED
        else:
            role = VALUE
        _text(draw, bx, y, option_text(label), role)
        rects.append(rect)
        bx += width + TEXT_BUTTON_GAP
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
        self.text_field_rect: Rect | None = None
        self._text_field_hit: _TextFieldHit | None = None

    def draw(self) -> Rect:
        self.intent = None
        self.panel_rect = None
        self.option_rects = ()
        self.text_button_rects = ()
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
            return panel
        finally:
            try:
                if begun:
                    imgui.end()
            finally:
                if pushed:
                    imgui.pop_style_var(pushed)

    def _draw_standard(
        self, ox: int, oy: int, panel_w: int, line_gap: int, screen_w: int
    ) -> None:
        view = self.view
        measure = self.measure
        line_h = measure.get_linesize()
        x = ox + PANEL_PAD_X
        y = oy + PANEL_PAD_Y
        draw = imgui.get_window_draw_list()
        has_message = view.message is not None
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
                panel_w - PANEL_PAD_X * 2,
                view.progress_fraction or 0.0,
            )
            y += BAR_HEIGHT
        if view.options:
            if has_message or has_labeled or has_bar:
                y += line_h + line_gap
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
        x = ox + PANEL_PAD_X
        content_w = panel_w - PANEL_PAD_X * 2
        y = oy + PANEL_PAD_Y
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
        if clicked and not _contains(panel, x, y):
            self.intent = ModalPointerIntent(ModalPointerKind.CANCEL)
            return
        if hit is not None:
            self.intent = ModalPointerIntent(
                ModalPointerKind.HOVER_OPTION, index=hit
            )

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
        if button is not None:
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
