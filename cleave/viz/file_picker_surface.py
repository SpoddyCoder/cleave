"""ImGui file picker. Draw records hit rects and one pointer intent.

Does not mutate :class:`FilePicker`. The host applies :func:`apply_picker_pointer`
after the frame. The directory list is a child window: a scrollbar appears when
the rows do not fit, and the wheel scrolls that window. ImGui and the theme
bridge load on draw, not at import.
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
    FOCUS_BORDER_ALPHA,
    FOCUS_WASH_ALPHA,
    HIGHLIGHT,
    LABEL,
    PRESET_ICON,
    SCROLLBAR_THUMB,
    SCROLLBAR_TRACK,
    VALUE,
    tuning_ui_metrics,
)

Rect = tuple[int, int, int, int]
_Role = tuple[int, int, int]
TextWidth = Callable[[str], int]

FILE_PICKER_WINDOW = "##file-picker"
FILE_PICKER_LIST = "##file-picker-list"
_WHEEL_ROWS = 3

_PANEL_WIDTH_FRACTION = 0.6
_PANEL_HEIGHT_FRACTION = 0.7
_PROJECT_SUFFIX = "  [project]"
_DIRECTORY_SUFFIX = "/"
_SHORTCUT_SEPARATOR = "   "
_SHORTCUT_HIGHLIGHT_PAD = 4
_WASH_ALPHA = FOCUS_WASH_ALPHA / 255.0
_FOCUS_BORDER_ALPHA = FOCUS_BORDER_ALPHA / 255.0
_FOCUS_BORDER_THICKNESS = 1.0
_HIGHLIGHT_PAD = 2


class PickerPointerKind(Enum):
    """One pointer result for the frame."""

    SELECT_ROW = "select-row"
    OPEN_ROW = "open-row"
    GOTO_SHORTCUT = "goto-shortcut"
    SUPPRESS_KEYBOARD_HIGHLIGHT = "suppress-keyboard-highlight"


@dataclass(frozen=True)
class PickerPointerIntent:
    """``index`` is a listing row or a shortcut.

    ``pointer_over_item`` hides the keyboard highlight. Hover with no click,
    and a wheel over the scrolling list, use
    :attr:`PickerPointerKind.SUPPRESS_KEYBOARD_HIGHLIGHT`.
    """

    kind: PickerPointerKind
    index: int | None = None
    pointer_over_item: bool = False


class _CallableSizer:
    """Adapt a width callback to the text fitter protocol."""

    def __init__(self, text_width: TextWidth) -> None:
        self._text_width = text_width

    def size(self, text: str) -> tuple[int, int]:
        return (self._text_width(text), 0)


def clamp_scroll(
    scroll_y: float,
    *,
    row_stride: int,
    view_height: float,
    row_count: int,
) -> float:
    """Clamp a list scroll offset so the last row can sit at the bottom."""
    if row_stride <= 0 or view_height <= 0 or row_count <= 0:
        return 0.0
    limit = max(0.0, row_count * row_stride - view_height)
    return min(max(0.0, scroll_y), limit)


def scroll_to_reveal(
    scroll_y: float,
    row: int,
    *,
    row_stride: int,
    view_height: float,
    row_count: int,
) -> float:
    """Move *scroll_y* the least amount that puts *row* fully in the view."""
    if row_stride <= 0 or view_height <= 0 or row_count <= 0:
        return 0.0
    row = min(max(0, row), row_count - 1)
    top = float(row * row_stride)
    bottom = top + float(row_stride)
    if top < scroll_y:
        scroll_y = top
    elif bottom > scroll_y + view_height:
        scroll_y = bottom - view_height
    return clamp_scroll(
        scroll_y,
        row_stride=row_stride,
        view_height=view_height,
        row_count=row_count,
    )


def visible_row_range(
    scroll_y: float,
    view_height: float,
    row_stride: int,
    row_count: int,
) -> tuple[int, int]:
    """Return the [start, end) rows that intersect the scrolled view."""
    if row_count <= 0 or row_stride <= 0 or view_height <= 0:
        return 0, 0
    start = min(row_count, max(0, int(scroll_y // row_stride)))
    end = min(row_count, int((scroll_y + view_height - 1e-3) // row_stride) + 1)
    return start, max(start, end)


def wheel_scroll_px(wheel: float, row_stride: int) -> float:
    """Pixels to add to the scroll offset. A positive *wheel* moves the list up."""
    if wheel == 0.0 or row_stride <= 0:
        return 0.0
    return -wheel * float(row_stride * _WHEEL_ROWS)


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


def location_text_lift() -> int:
    """Pixels to raise the path so its caps center on the folder mark."""
    font = _imgui().get_io().font_default
    icon = font.find_glyph(ord(FOLDER_GLYPH))
    cap = font.find_glyph(ord("A"))
    icon_mid = (icon.y0 + icon.y1) * 0.5
    cap_mid = (cap.y0 + cap.y1) * 0.5
    return int(round(icon_mid - cap_mid))


def apply_picker_pointer(
    picker: FilePicker, intent: PickerPointerIntent | None
) -> OpenTarget | None:
    """Map one recorded intent onto ``FilePicker``. ``None`` does nothing.

    Returns an open target when the intent opens an audio file or a project.
    A pointer over a row or shortcut hides the keyboard highlight.
    """
    if intent is None:
        return None
    kind = intent.kind
    if (
        kind is PickerPointerKind.SUPPRESS_KEYBOARD_HIGHLIGHT
        or intent.pointer_over_item
    ):
        picker.suppress_keyboard_highlight()
    if kind is PickerPointerKind.SUPPRESS_KEYBOARD_HIGHLIGHT:
        return None
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


def _focus_border(draw: Any, rect: Rect) -> None:
    """1px highlight outline, matching a focused navigator or inspector row."""
    x, y, width, height = rect
    if width <= 0 or height <= 0:
        return
    imgui = _imgui()
    draw.add_rect(
        imgui.ImVec2(float(x), float(y)),
        imgui.ImVec2(float(x + width), float(y + height)),
        _packed(HIGHLIGHT, _FOCUS_BORDER_ALPHA),
        0.0,
        0,
        _FOCUS_BORDER_THICKNESS,
    )


def _highlight(draw: Any, rect: Rect) -> None:
    """Wash plus the 1px focus border, for keyboard selection and pointer hover."""
    _wash(draw, rect)
    _focus_border(draw, rect)


def _push_list_highlight_clip(draw: Any) -> None:
    """Let the row outline draw into the padding around the list.

    The directory list is a child window whose clip starts on the text. The
    highlight sits ``_HIGHLIGHT_PAD`` outside that text, and the outline's
    anti-aliased fringe needs two more pixels so the scissor does not cut it.
    Without this, the left edge is clipped on every row, and the top edge is
    clipped on the first row.
    """
    imgui = _imgui()
    clip_min = draw.get_clip_rect_min()
    clip_max = draw.get_clip_rect_max()
    slack = float(_HIGHLIGHT_PAD + 2)
    draw.push_clip_rect(
        imgui.ImVec2(float(clip_min.x) - slack, float(clip_min.y) - slack),
        imgui.ImVec2(float(clip_max.x) + slack, float(clip_max.y) + slack),
        False,
    )


def _highlight_visible(
    keyboard: bool,
    hovered: bool,
    pointer_over_item: bool,
    keyboard_highlight: bool,
) -> bool:
    """The row or chip under the pointer, or the keyboard selection.

    A pointer over a row or chip shows that item alone. The keyboard
    selection stays visible until that happens, then stays hidden until
    the next key move.
    """
    return hovered or (
        keyboard and keyboard_highlight and not pointer_over_item
    )


def _outset(rect: Rect, pad: int = _HIGHLIGHT_PAD) -> Rect:
    """Grow *rect* by *pad* on every side."""
    x, y, width, height = rect
    return (x - pad, y - pad, width + 2 * pad, height + 2 * pad)


def _chip_hits(
    view: PickerViewState,
    content_x: int,
    y: int,
    content_w: int,
    line_h: int,
    text_width: TextWidth,
) -> tuple[tuple[int, str, int, Rect], ...]:
    """``(shortcut index, text, text x, hit rect)`` for each visible chip."""
    hits: list[tuple[int, str, int, Rect]] = []
    for index, text, chip_x, width in shortcut_chip_layout(
        view, content_w=content_w, text_width=text_width
    ):
        screen_x = content_x + chip_x
        hit = _outset(
            (
                screen_x - _SHORTCUT_HIGHLIGHT_PAD,
                y,
                width + _SHORTCUT_HIGHLIGHT_PAD * 2,
                line_h,
            )
        )
        hits.append((index, text, screen_x, hit))
    return tuple(hits)


def _row_hits(
    content_x: int,
    list_top: int,
    content_w: int,
    line_h: int,
    step: int,
    start: int,
    end: int,
) -> tuple[tuple[int, int, Rect], ...]:
    """``(row index, text y, hit rect)`` for the visible window."""
    hits: list[tuple[int, int, Rect]] = []
    y = list_top
    for index in range(start, end):
        hits.append((index, y, _outset((content_x, y, content_w, line_h))))
        y += step
    return tuple(hits)


def _pointer_hover(
    chips: tuple[tuple[int, str, int, Rect], ...],
    rows: tuple[tuple[int, int, Rect], ...],
) -> tuple[int | None, int | None]:
    """Shortcut index and row index under the pointer. A row wins if both match."""
    pos = _imgui().get_io().mouse_pos
    x, y = float(pos.x), float(pos.y)
    row_at = _index_at(tuple(row[2] for row in rows), x, y)
    if row_at is not None:
        return None, rows[row_at][0]
    chip_at = _index_at(tuple(chip[3] for chip in chips), x, y)
    if chip_at is not None:
        return chips[chip_at][0], None
    return None, None


def _raise_window() -> None:
    imgui = _imgui()
    imgui.internal.bring_window_to_display_front(
        imgui.internal.find_window_by_name(FILE_PICKER_WINDOW)
    )


def _list_flags() -> int:
    imgui = _imgui()
    # The wheel is applied by this overlay. NoScrollWithMouse keeps ImGui from
    # scrolling the child again, and leaves the scrollbar in place.
    return (
        int(imgui.WindowFlags_.no_saved_settings)
        | int(imgui.WindowFlags_.no_nav)
        | int(imgui.WindowFlags_.no_focus_on_appearing)
        | int(imgui.WindowFlags_.no_scroll_with_mouse)
    )


def _push_scrollbar_colors() -> int:
    imgui = _imgui()
    imgui.push_style_color(imgui.Col_.scrollbar_bg, _packed(SCROLLBAR_TRACK))
    imgui.push_style_color(imgui.Col_.scrollbar_grab, _packed(SCROLLBAR_THUMB))
    imgui.push_style_color(imgui.Col_.scrollbar_grab_hovered, _packed(HIGHLIGHT))
    imgui.push_style_color(imgui.Col_.scrollbar_grab_active, _packed(HIGHLIGHT))
    return 4


class FilePickerSurface:
    """Centred picker window. ``modal`` keeps the top-layer scrim up.

    ``intent`` is the pointer result of the last draw.

    ``panel_rect``, ``row_rects``, and ``chip_rects`` are that frame's hit
    targets, in screen pixels. ``row_indices`` and ``chip_indices`` match them.
    """

    modal = True

    def __init__(self, view: PickerViewState) -> None:
        self.view = view
        self.intent: PickerPointerIntent | None = None
        self.panel_rect: Rect | None = None
        self.row_rects: tuple[Rect, ...] = ()
        self.row_indices: tuple[int, ...] = ()
        self.chip_rects: tuple[Rect, ...] = ()
        self.chip_indices: tuple[int, ...] = ()
        self._wheeled = False

    def draw(self) -> Rect:
        self.intent = None
        self.panel_rect = None
        self.row_rects = ()
        self.row_indices = ()
        self.chip_rects = ()
        self.chip_indices = ()
        self._wheeled = False

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

        chip_y = y
        y += step * 2
        location_y = y
        y += step
        list_top = y

        footer = legend_rows(view.legend, content_w, text_width)
        footer_lines = len(footer) + (1 if view.status else 0)
        list_bottom = oy + panel_h - pad_y - (footer_lines + 1) * step
        list_h = max(1, list_bottom - list_top)
        chips = _chip_hits(
            view, content_x, chip_y, content_w, line_h, text_width
        )
        self._paint_location(
            draw,
            view.location,
            measure,
            content_x,
            location_y,
            content_w,
            metrics.icon_label_gap,
        )
        hover_chip, hover_row = self._paint_list(
            view,
            measure,
            content_x,
            list_top,
            content_w,
            list_h,
            line_h,
            step,
            metrics.scrollbar_width,
            chips,
        )
        self._paint_chips(draw, view, chip_y, chips, hover_chip, hover_row)

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
        y: int,
        chips: tuple[tuple[int, str, int, Rect], ...],
        hover_chip: int | None,
        hover_row: int | None,
    ) -> None:
        pointer_over_item = hover_chip is not None or hover_row is not None
        rects: list[Rect] = []
        indices: list[int] = []
        for index, text, screen_x, hit in chips:
            selected = shortcut_is_selected(view, index)
            current = shortcut_is_current(view, index)
            hovered = hover_chip == index
            lit = _highlight_visible(
                selected, hovered, pointer_over_item, view.keyboard_highlight
            )
            if lit:
                _highlight(draw, hit)
            color = HIGHLIGHT if lit or current else ACTION
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
        _text(draw, x + prefix_w, y + location_text_lift(), fitted, VALUE)

    def _paint_list(
        self,
        view: PickerViewState,
        measure,
        content_x: int,
        list_top: int,
        content_w: int,
        list_h: int,
        line_h: int,
        step: int,
        scrollbar_width: int,
        chips: tuple[tuple[int, str, int, Rect], ...],
    ) -> tuple[int | None, int | None]:
        """Scrollable directory list. Returns the shortcut and row under the pointer."""
        imgui = _imgui()
        total = len(view.rows)
        imgui.set_cursor_screen_pos(imgui.ImVec2(float(content_x), float(list_top)))
        imgui.set_next_window_content_size(imgui.ImVec2(0.0, float(total * step)))
        colors = _push_scrollbar_colors()
        imgui.push_style_var(imgui.StyleVar_.window_padding, imgui.ImVec2(0.0, 0.0))
        imgui.push_style_var(imgui.StyleVar_.item_spacing, imgui.ImVec2(0.0, 0.0))
        imgui.push_style_var(imgui.StyleVar_.scrollbar_size, float(scrollbar_width))
        flags = _list_flags()
        if total * step > list_h:
            flags |= int(imgui.WindowFlags_.always_vertical_scrollbar)
        begun = False
        hover_chip: int | None = None
        hover_row: int | None = None
        try:
            imgui.begin_child(
                FILE_PICKER_LIST,
                imgui.ImVec2(float(content_w), float(list_h)),
                0,
                flags,
            )
            begun = True
            origin = imgui.get_window_pos()
            scroll_y = self._sync_list_scroll(view, step, float(list_h))
            row_w = max(1, int(imgui.get_content_region_avail().x) - _HIGHLIGHT_PAD)
            if total:
                imgui.dummy(imgui.ImVec2(1.0, float(total * step)))
            start, end = visible_row_range(scroll_y, float(list_h), step, total)
            left = int(origin.x)
            rows_list: list[tuple[int, int, Rect]] = []
            for index in range(start, end):
                y = int(round(float(origin.y) + index * step - scroll_y))
                rows_list.append((index, y, _outset((left, y, row_w, line_h))))
            rows = tuple(rows_list)
            hover_chip, hover_row = _pointer_hover(chips, rows)
            self._paint_rows(
                imgui.get_window_draw_list(),
                view,
                measure,
                left,
                row_w,
                rows,
                hover_chip,
                hover_row,
            )
        finally:
            if begun:
                imgui.end_child()
            imgui.pop_style_var(3)
            if colors:
                imgui.pop_style_color(colors)
        return hover_chip, hover_row

    def _sync_list_scroll(
        self, view: PickerViewState, step: int, view_h: float
    ) -> float:
        """Keep the keyboard selection on screen, and apply the wheel."""
        imgui = _imgui()
        storage = imgui.get_state_storage()
        loc_id = imgui.get_id("##scroll-loc")
        sel_id = imgui.get_id("##scroll-sel")
        key_id = imgui.get_id("##scroll-key")
        loc_key = int(imgui.get_id(view.location)) & 0x7FFFFFFF
        prev_loc = storage.get_int(loc_id, -1)
        prev_sel = storage.get_int(sel_id, -1)
        prev_keys = storage.get_bool(key_id, False)
        keys = view.keyboard_highlight and view.focus is PickerFocus.LIST
        scroll_y = float(imgui.get_scroll_y())
        max_scroll = max(0.0, len(view.rows) * step - view_h)
        wheel = float(imgui.get_io().mouse_wheel)
        wheeled = (
            bool(imgui.is_window_hovered()) and wheel != 0.0 and max_scroll > 0.0
        )
        moved = prev_loc != loc_key
        if moved:
            scroll_y = 0.0
        if wheeled:
            scroll_y = clamp_scroll(
                scroll_y + wheel_scroll_px(wheel, step),
                row_stride=step,
                view_height=view_h,
                row_count=len(view.rows),
            )
        elif moved or (
            view.focus is PickerFocus.LIST
            and (prev_sel != view.selected_index or (keys and not prev_keys))
        ):
            scroll_y = scroll_to_reveal(
                scroll_y,
                view.selected_index,
                row_stride=step,
                view_height=view_h,
                row_count=len(view.rows),
            )
        if abs(scroll_y - float(imgui.get_scroll_y())) > 0.01:
            imgui.set_scroll_y(float(scroll_y))
            # SetScrollY lands next frame. Write the window scroll now so the
            # thumb matches the rows drawn this frame.
            window = imgui.internal.get_current_window()
            window.scroll = imgui.ImVec2(float(window.scroll.x), float(scroll_y))
        storage.set_int(loc_id, loc_key)
        storage.set_int(sel_id, view.selected_index)
        storage.set_bool(key_id, keys)
        self._wheeled = wheeled
        return scroll_y

    def _paint_rows(
        self,
        draw: Any,
        view: PickerViewState,
        measure,
        content_x: int,
        content_w: int,
        rows: tuple[tuple[int, int, Rect], ...],
        hover_chip: int | None,
        hover_row: int | None,
    ) -> None:
        pointer_over_item = hover_chip is not None or hover_row is not None
        rects: list[Rect] = []
        indices: list[int] = []
        for index, y, rect in rows:
            row = view.rows[index]
            selected = (
                index == view.selected_index and view.focus is PickerFocus.LIST
            )
            hovered = hover_row == index
            lit = _highlight_visible(
                selected, hovered, pointer_over_item, view.keyboard_highlight
            )
            if lit:
                _push_list_highlight_clip(draw)
                try:
                    _highlight(draw, rect)
                finally:
                    draw.pop_clip_rect()
            color = HIGHLIGHT if lit else _row_color(row)
            _text(
                draw,
                content_x,
                y,
                fit_text_to_width(measure, row_text(row), content_w),
                color,
            )
            rects.append(rect)
            indices.append(index)
        self.row_rects = tuple(rects)
        self.row_indices = tuple(indices)

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
        on_item = row_at is not None or chip_at is not None
        if double and row_at is not None:
            self.intent = PickerPointerIntent(
                PickerPointerKind.OPEN_ROW,
                index=self.row_indices[row_at],
                pointer_over_item=True,
            )
            return
        if clicked and row_at is not None:
            self.intent = PickerPointerIntent(
                PickerPointerKind.SELECT_ROW,
                index=self.row_indices[row_at],
                pointer_over_item=True,
            )
            return
        if clicked and chip_at is not None:
            self.intent = PickerPointerIntent(
                PickerPointerKind.GOTO_SHORTCUT,
                index=self.chip_indices[chip_at],
                pointer_over_item=True,
            )
            return
        if self._wheeled:
            self.intent = PickerPointerIntent(
                PickerPointerKind.SUPPRESS_KEYBOARD_HIGHLIGHT,
                pointer_over_item=on_item,
            )
            return
        if on_item:
            self.intent = PickerPointerIntent(
                PickerPointerKind.SUPPRESS_KEYBOARD_HIGHLIGHT,
                pointer_over_item=True,
            )
