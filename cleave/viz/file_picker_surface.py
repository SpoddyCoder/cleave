"""ImGui file picker. Draw records hit rects and one pointer intent.

Does not mutate :class:`FilePicker`. The host applies :func:`apply_picker_pointer`
after the frame. ImGui and the theme bridge load on draw, not at import.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from cleave.open_target import OpenTarget
from cleave.viz.file_picker import (
    FilePicker,
    PickerFocus,
    PickerRow,
    PickerRowKind,
    PickerViewState,
)
from cleave.viz.material_icons import FOLDER_GLYPH
from cleave.viz.text_fit import (
    fit_path_label_to_width,
    fit_text_to_width,
    wrap_text_to_width,
)
from cleave.viz.theme import (
    ACTION,
    BORDER_WIDTH,
    DISABLED,
    ERROR_NOTIFICATION,
    FOCUS_WASH_ALPHA,
    HIGHLIGHT,
    LABEL,
    PRESET_ICON,
    VALUE,
    tuning_ui_metrics,
)

Rect = tuple[int, int, int, int]
_Role = tuple[int, int, int]
TextWidth = Callable[[str], int]

FILE_PICKER_WINDOW = "##file-picker"

_PANEL_WIDTH_FRACTION = 0.6
_PANEL_HEIGHT_FRACTION = 0.7
_PROJECT_SUFFIX = "  [project]"
_DIRECTORY_SUFFIX = "/"
_SHORTCUT_SEPARATOR = "   "
_SHORTCUT_HIGHLIGHT_PAD = 4
_WASH_ALPHA = FOCUS_WASH_ALPHA / 255.0


class PickerPointerKind(Enum):
    """One pointer result for the frame."""

    SELECT_ROW = "select-row"
    OPEN_ROW = "open-row"
    GOTO_SHORTCUT = "goto-shortcut"
    SCROLL_ROWS = "scroll-rows"


@dataclass(frozen=True)
class PickerPointerIntent:
    """``index`` is a listing row or a shortcut. ``delta`` is a list step."""

    kind: PickerPointerKind
    index: int | None = None
    delta: int = 0


class _CallableSizer:
    """Adapt a width callback to the text fitter protocol."""

    def __init__(self, text_width: TextWidth) -> None:
        self._text_width = text_width

    def size(self, text: str) -> tuple[int, int]:
        return (self._text_width(text), 0)


def visible_slice(total: int, selected: int, capacity: int) -> tuple[int, int]:
    """Return the [start, end) row window that keeps *selected* on screen."""
    if capacity <= 0 or total <= 0:
        return 0, 0
    if total <= capacity:
        return 0, total
    start = min(max(0, selected - capacity // 2), total - capacity)
    return start, start + capacity


def row_text(row: PickerRow) -> str:
    """Return the display text for *row*, including its kind marker."""
    if row.kind is PickerRowKind.PROJECT:
        return f"{row.label}{_DIRECTORY_SUFFIX}{_PROJECT_SUFFIX}"
    if row.kind is PickerRowKind.DIRECTORY:
        return f"{row.label}{_DIRECTORY_SUFFIX}"
    return row.label


def shortcut_is_selected(state: PickerViewState, index: int) -> bool:
    """True when the header has focus and *index* is the highlighted shortcut."""
    return state.focus is PickerFocus.SHORTCUTS and index == state.selected_shortcut


def shortcut_is_current(state: PickerViewState, index: int) -> bool:
    """True when *index* is the shortcut for the directory being listed."""
    return state.active_shortcut == index


def shortcut_chip_layout(
    state: PickerViewState,
    *,
    content_w: int,
    text_width: TextWidth,
) -> tuple[tuple[int, str, int, int], ...]:
    """Return ``(index, text, x, width)`` for each shortcut that fits.

    ``x`` is relative to the content origin. Chips past *content_w* are omitted.
    """
    chips: list[tuple[int, str, int, int]] = []
    cursor = 0
    gap = text_width(_SHORTCUT_SEPARATOR)
    for index, shortcut in enumerate(state.shortcuts):
        text = f"[{shortcut.label}]"
        width = text_width(text)
        if chips:
            cursor += gap
        if cursor + width > content_w:
            break
        chips.append((index, text, cursor, width))
        cursor += width
    return tuple(chips)


def legend_rows(
    entries: tuple[tuple[str, str], ...],
    content_w: int,
    text_width: TextWidth,
) -> tuple[tuple[tuple[str, str], ...], ...]:
    """Pack ``key: label`` items onto as many lines as *content_w* needs."""
    gap = text_width(_SHORTCUT_SEPARATOR)
    rows: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    used = 0
    for entry in entries:
        width = text_width(f"{entry[0]}: {entry[1]}")
        extra = 0 if not current else gap
        if current and used + extra + width > content_w:
            rows.append(current)
            current = [entry]
            used = width
            continue
        used += extra + width
        current.append(entry)
    if current:
        rows.append(current)
    return tuple(tuple(row) for row in rows)


def location_text(location: str, content_w: int, text_width: TextWidth) -> str:
    """Fit the browse path, keeping the tail so the current folder stays visible."""
    return fit_path_label_to_width(_CallableSizer(text_width), location, content_w)


def apply_picker_pointer(
    picker: FilePicker, intent: PickerPointerIntent | None
) -> OpenTarget | None:
    """Map one recorded intent onto ``FilePicker``. ``None`` does nothing.

    Returns an open target when the intent opens an audio file or a project.
    """
    if intent is None:
        return None
    kind = intent.kind
    if kind is PickerPointerKind.SELECT_ROW:
        if intent.index is not None:
            picker.select_row(intent.index)
        return None
    if kind is PickerPointerKind.OPEN_ROW:
        if intent.index is not None:
            picker.select_row(intent.index)
        return picker.open_row()
    if kind is PickerPointerKind.GOTO_SHORTCUT:
        if intent.index is not None:
            picker.goto_shortcut(intent.index)
        return None
    if kind is PickerPointerKind.SCROLL_ROWS:
        picker.scroll_rows(intent.delta)
    return None


def _row_color(row: PickerRow) -> _Role:
    if row.kind is PickerRowKind.NOTE:
        return DISABLED
    if row.kind in (PickerRowKind.PARENT, PickerRowKind.DRIVE):
        return ACTION
    if row.kind is PickerRowKind.PROJECT:
        return HIGHLIGHT
    return VALUE


@functools.cache
def _imgui():
    from imgui_bundle import imgui as imgui_mod

    return imgui_mod


@functools.cache
def _window_flags() -> int:
    imgui = _imgui()
    return (
        int(imgui.WindowFlags_.no_title_bar)
        | int(imgui.WindowFlags_.no_resize)
        | int(imgui.WindowFlags_.no_move)
        | int(imgui.WindowFlags_.no_saved_settings)
        | int(imgui.WindowFlags_.no_focus_on_appearing)
        | int(imgui.WindowFlags_.no_nav)
        | int(imgui.WindowFlags_.no_bring_to_front_on_focus)
        | int(imgui.WindowFlags_.no_scrollbar)
        | int(imgui.WindowFlags_.no_scroll_with_mouse)
    )


def _measure():
    from cleave.viz.modal_surface import ImGuiTextMeasure

    return ImGuiTextMeasure()


def _packed(role: _Role, alpha: float = 1.0) -> int:
    imgui = _imgui()
    from cleave.viz.imgui_theme import rgba

    return int(imgui.get_color_u32(rgba(role, alpha)))


def _contains(rect: Rect, x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rw > 0 and rh > 0 and rx <= x < rx + rw and ry <= y < ry + rh


def _index_at(rects: tuple[Rect, ...], x: float, y: float) -> int | None:
    for index, rect in enumerate(rects):
        if _contains(rect, x, y):
            return index
    return None


def _text(draw: Any, x: int, y: int, text: str, role: _Role) -> None:
    if not text:
        return
    imgui = _imgui()
    draw.add_text(imgui.ImVec2(float(x), float(y)), _packed(role), text)


def _wash(draw: Any, rect: Rect) -> None:
    x, y, width, height = rect
    if width <= 0 or height <= 0:
        return
    imgui = _imgui()
    draw.add_rect_filled(
        imgui.ImVec2(float(x), float(y)),
        imgui.ImVec2(float(x + width), float(y + height)),
        _packed(HIGHLIGHT, _WASH_ALPHA),
    )


def _raise_window() -> None:
    imgui = _imgui()
    imgui.internal.bring_window_to_display_front(
        imgui.internal.find_window_by_name(FILE_PICKER_WINDOW)
    )


def _wheel_delta(wheel: float) -> int:
    """Map ImGui wheel (positive scrolls up) onto a list step (negative is up)."""
    delta = -int(round(wheel))
    if delta == 0:
        return -1 if wheel > 0.0 else 1
    return delta


class FilePickerSurface:
    """Centred picker window. ``intent`` is the pointer result of the last draw.

    ``panel_rect``, ``row_rects``, and ``chip_rects`` are that frame's hit
    targets, in screen pixels. ``row_indices`` and ``chip_indices`` match them.
    """

    def __init__(self, view: PickerViewState) -> None:
        self.view = view
        self.intent: PickerPointerIntent | None = None
        self.panel_rect: Rect | None = None
        self.row_rects: tuple[Rect, ...] = ()
        self.row_indices: tuple[int, ...] = ()
        self.chip_rects: tuple[Rect, ...] = ()
        self.chip_indices: tuple[int, ...] = ()
        self._list_rect: Rect | None = None

    def draw(self) -> Rect:
        self.intent = None
        self.panel_rect = None
        self.row_rects = ()
        self.row_indices = ()
        self.chip_rects = ()
        self.chip_indices = ()
        self._list_rect = None

        imgui = _imgui()
        display = imgui.get_io().display_size
        screen_w = max(1, int(display.x))
        screen_h = max(1, int(display.y))
        panel_w = max(1, int(screen_w * _PANEL_WIDTH_FRACTION))
        panel_h = max(1, int(screen_h * _PANEL_HEIGHT_FRACTION))
        imgui.set_next_window_pos(
            imgui.ImVec2(display.x * 0.5, display.y * 0.5),
            imgui.Cond_.always,
            imgui.ImVec2(0.5, 0.5),
        )
        imgui.set_next_window_size(
            imgui.ImVec2(float(panel_w), float(panel_h)),
            imgui.Cond_.always,
        )
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
            imgui.begin(FILE_PICKER_WINDOW, None, _window_flags())
            begun = True
            _raise_window()
            pos = imgui.get_window_pos()
            size = imgui.get_window_size()
            ox, oy = int(pos.x), int(pos.y)
            width = max(1, int(size.x))
            height = max(1, int(size.y))
            self._paint(ox, oy, width, height, _measure())
            panel = (ox, oy, width, height)
            self.panel_rect = panel
            self._record_pointer()
            return panel
        finally:
            try:
                if begun:
                    imgui.end()
            finally:
                if pushed:
                    imgui.pop_style_var(pushed)

    def _paint(self, ox: int, oy: int, panel_w: int, panel_h: int, measure) -> None:
        view = self.view
        metrics = tuning_ui_metrics()
        pad_x = metrics.modal_panel_pad_x
        pad_y = metrics.modal_panel_pad_y
        line_gap = metrics.line_gap
        line_h = measure.get_linesize()
        step = line_h + line_gap
        content_x = ox + pad_x
        content_w = max(1, panel_w - pad_x * 2)
        text_width: TextWidth = lambda text: measure.size(text)[0]
        draw = _imgui().get_window_draw_list()

        y = oy + pad_y
        title_lines = wrap_text_to_width(measure, view.title, content_w) or [
            view.title
        ]
        for line in title_lines:
            _text(draw, content_x, y, fit_text_to_width(measure, line, content_w), LABEL)
            y += step

        self._paint_chips(
            draw, view, content_x, y, content_w, line_h, text_width
        )
        y += step * 2
        self._paint_location(
            draw,
            view.location,
            measure,
            content_x,
            y,
            content_w,
            metrics.icon_label_gap,
        )
        y += step

        footer = legend_rows(view.legend, content_w, text_width)
        footer_lines = len(footer) + (1 if view.status else 0)
        list_top = y
        list_bottom = oy + panel_h - pad_y - (footer_lines + 1) * step
        capacity = max(1, (list_bottom - list_top) // step)
        start, end = visible_slice(len(view.rows), view.selected_index, capacity)
        self._paint_rows(
            draw,
            view,
            measure,
            content_x,
            list_top,
            content_w,
            line_h,
            step,
            start,
            end,
        )

        footer_y = oy + panel_h - pad_y - footer_lines * step
        for row in footer:
            self._paint_legend_row(
                draw, measure, row, content_x, footer_y, text_width
            )
            footer_y += step
        if view.status:
            _text(
                draw,
                content_x,
                footer_y,
                fit_text_to_width(measure, view.status, content_w),
                ERROR_NOTIFICATION,
            )

    def _paint_chips(
        self,
        draw: Any,
        view: PickerViewState,
        content_x: int,
        y: int,
        content_w: int,
        line_h: int,
        text_width: TextWidth,
    ) -> None:
        rects: list[Rect] = []
        indices: list[int] = []
        for index, text, chip_x, width in shortcut_chip_layout(
            view, content_w=content_w, text_width=text_width
        ):
            screen_x = content_x + chip_x
            selected = shortcut_is_selected(view, index)
            current = shortcut_is_current(view, index)
            hit = (
                screen_x - _SHORTCUT_HIGHLIGHT_PAD,
                y,
                width + _SHORTCUT_HIGHLIGHT_PAD * 2,
                line_h,
            )
            if selected:
                _wash(draw, hit)
            color = HIGHLIGHT if selected or current else ACTION
            _text(draw, screen_x, y, text, color)
            rects.append(hit)
            indices.append(index)
        self.chip_rects = tuple(rects)
        self.chip_indices = tuple(indices)

    def _paint_location(
        self,
        draw: Any,
        location: str,
        measure,
        x: int,
        y: int,
        content_w: int,
        icon_gap: int,
    ) -> None:
        _text(draw, x, y, FOLDER_GLYPH, PRESET_ICON)
        prefix_w = measure.size(FOLDER_GLYPH)[0] + icon_gap
        text_w = max(1, content_w - prefix_w)
        fitted = location_text(location, text_w, lambda text: measure.size(text)[0])
        _text(draw, x + prefix_w, y, fitted, VALUE)

    def _paint_rows(
        self,
        draw: Any,
        view: PickerViewState,
        measure,
        content_x: int,
        list_top: int,
        content_w: int,
        line_h: int,
        step: int,
        start: int,
        end: int,
    ) -> None:
        rects: list[Rect] = []
        indices: list[int] = []
        y = list_top
        for index in range(start, end):
            row = view.rows[index]
            rect = (content_x, y, content_w, line_h)
            selected = (
                index == view.selected_index and view.focus is PickerFocus.LIST
            )
            if selected:
                _wash(draw, rect)
            color = HIGHLIGHT if selected else _row_color(row)
            _text(
                draw,
                content_x,
                y,
                fit_text_to_width(measure, row_text(row), content_w),
                color,
            )
            rects.append(rect)
            indices.append(index)
            y += step
        self.row_rects = tuple(rects)
        self.row_indices = tuple(indices)
        if rects:
            bottom = rects[-1][1] + rects[-1][3]
            self._list_rect = (content_x, list_top, content_w, bottom - list_top)

    def _paint_legend_row(
        self,
        draw: Any,
        measure,
        entries: tuple[tuple[str, str], ...],
        x: int,
        y: int,
        text_width: TextWidth,
    ) -> None:
        cursor = x
        gap = text_width(_SHORTCUT_SEPARATOR)
        for index, (key, label) in enumerate(entries):
            if index:
                cursor += gap
            prefix = f"{key}: "
            _text(draw, cursor, y, prefix, LABEL)
            cursor += measure.size(prefix)[0]
            _text(draw, cursor, y, label, VALUE)
            cursor += measure.size(label)[0]

    def _record_pointer(self) -> None:
        imgui = _imgui()
        io = imgui.get_io()
        pos = io.mouse_pos
        x, y = float(pos.x), float(pos.y)
        clicked = bool(io.mouse_clicked[0])
        double = bool(imgui.is_mouse_double_clicked(0))
        row_at = _index_at(self.row_rects, x, y)
        chip_at = _index_at(self.chip_rects, x, y)
        if double and row_at is not None:
            self.intent = PickerPointerIntent(
                PickerPointerKind.OPEN_ROW, index=self.row_indices[row_at]
            )
            return
        if clicked and row_at is not None:
            self.intent = PickerPointerIntent(
                PickerPointerKind.SELECT_ROW, index=self.row_indices[row_at]
            )
            return
        if clicked and chip_at is not None:
            self.intent = PickerPointerIntent(
                PickerPointerKind.GOTO_SHORTCUT, index=self.chip_indices[chip_at]
            )
            return
        wheel = float(io.mouse_wheel)
        list_rect = self._list_rect
        if wheel != 0.0 and list_rect is not None and _contains(list_rect, x, y):
            self.intent = PickerPointerIntent(
                PickerPointerKind.SCROLL_ROWS, delta=_wheel_delta(wheel)
            )
