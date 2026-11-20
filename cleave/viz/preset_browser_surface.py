"""ImGui preset browser, drawn in the navigator/inspector column.

Draw records hit rects and one pointer intent; it does not mutate the browser.
The controller applies :class:`BrowserPointerIntent` after the frame. ImGui
loads on draw, not at import, so the controller and tests import this freely.
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

from cleave.viz.file_picker_surface import (
    draw_text,
    index_at,
    list_child_flags,
    outset_list_row,
    paint_list_row,
    push_list_highlight_clip,
    request_hand,
    visible_row_range,
    wheel_scroll_px,
)
from cleave.viz.material_icons import FOLDER_GLYPH
from cleave.viz.preset_browser import (
    FILTER_PLACEHOLDER,
    BrowserFocus,
    BrowserRow,
    BrowserRowKind,
    BrowserViewState,
)
from cleave.viz.text_fit import fit_text_to_width

Rect = tuple[int, int, int, int]

PRESET_BROWSER_WINDOW = "##preset-browser"
PRESET_BROWSER_LIST = "##preset-browser-list"
CRUMB_SEPARATOR = " / "
FILTER_LABEL = "Filter: "
LOADING_LABEL = "Loading presets…"
# Divider between the path and the filter, as a fraction of the text line.
DIVIDER_LINES = 0.5
SPINNER_TURNS_PER_SEC = 1.2
SPINNER_ARC = math.pi * 1.5
_LEGEND_SEPARATOR = "   "


class BrowserPointerKind(Enum):
    SELECT_ROW = "select-row"
    OPEN_ROW = "open-row"
    GOTO_CRUMB = "goto-crumb"
    EDIT_FILTER = "edit-filter"


@dataclass(frozen=True)
class BrowserPointerIntent:
    kind: BrowserPointerKind
    index: int | None = None


def row_label(row: BrowserRow) -> str:
    """Display text for *row*, with the folder slash."""
    if row.kind is BrowserRowKind.FOLDER:
        return f"{row.label}/"
    return row.label


CRUMB_ELLIPSIS = "…"


@dataclass(frozen=True)
class CrumbSlot:
    """One drawn breadcrumb: the crumb a click goes to, its text, and its span."""

    index: int
    text: str
    x: int
    width: int


def _slots(
    pieces: list[tuple[int, str]], text_width
) -> tuple[CrumbSlot, ...]:
    gap = text_width(CRUMB_SEPARATOR)
    out: list[CrumbSlot] = []
    x = 0
    for position, (index, text) in enumerate(pieces):
        if position:
            x += gap
        width = text_width(text)
        out.append(CrumbSlot(index, text, x, width))
        x += width
    return tuple(out)


def _span(slots: tuple[CrumbSlot, ...]) -> int:
    return slots[-1].x + slots[-1].width if slots else 0


def fit_crumbs(
    labels: tuple[str, ...],
    content_w: int,
    text_width,
    fit_label,
) -> tuple[CrumbSlot, ...]:
    """Breadcrumbs that fit *content_w*, dropping parents from the left.

    Hidden parents become one :data:`CRUMB_ELLIPSIS` crumb that goes to the
    nearest of them, so every crumb shown stays clickable. The current folder
    is always last, shortened by *fit_label* (text, px) when even it alone
    does not fit.
    """
    if not labels:
        return ()
    count = len(labels)
    full = _slots(list(enumerate(labels)), text_width)
    if _span(full) <= content_w:
        return full
    for start in range(1, count):
        pieces = [(start - 1, CRUMB_ELLIPSIS), *((i, labels[i]) for i in range(start, count))]
        slots = _slots(pieces, text_width)
        if _span(slots) <= content_w:
            return slots
    last = count - 1
    if count == 1:
        return _slots([(0, fit_label(labels[0], content_w))], text_width)
    lead = text_width(CRUMB_ELLIPSIS) + text_width(CRUMB_SEPARATOR)
    room = max(0, content_w - lead)
    return _slots(
        [(last - 1, CRUMB_ELLIPSIS), (last, fit_label(labels[last], room))],
        text_width,
    )


@functools.cache
def _imgui():
    from imgui_bundle import imgui as imgui_mod

    return imgui_mod


def centred_line_y(top: float, bottom: float, ink_top: float, ink_bottom: float) -> int:
    """Line top that puts a glyph's ink (offsets from the line top) midway."""
    return int(round((top + bottom) / 2.0 - (ink_top + ink_bottom) / 2.0))


def folder_glyph_ink() -> tuple[float, float]:
    """Top and bottom of the folder mark's ink, from the top of its line."""
    imgui = _imgui()
    font = imgui.get_io().font_default.get_font_baked(imgui.get_style().font_size_base)
    glyph = font.find_glyph(ord(FOLDER_GLYPH))
    return float(glyph.y0), float(glyph.y1)


def _contains(rect: Rect, x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rx <= x < rx + rw and ry <= y < ry + rh


def _row_role(row: BrowserRow):
    from cleave.viz.theme import palette

    if row.kind is BrowserRowKind.NOTE:
        return palette().disabled
    if row.kind is BrowserRowKind.PARENT:
        return palette().label
    if row.kind in (BrowserRowKind.FOLDER, BrowserRowKind.COLLECTION):
        return palette().preset_icon
    return palette().value


class PresetBrowserSurface:
    """One frame of the browser. ``intent`` is that frame's pointer result."""

    def __init__(self, view: BrowserViewState) -> None:
        self.view = view
        self.intent: BrowserPointerIntent | None = None
        self.row_rects: tuple[Rect, ...] = ()
        self.row_indices: tuple[int, ...] = ()
        self.crumb_rects: tuple[Rect, ...] = ()
        self.crumb_indices: tuple[int, ...] = ()
        self.filter_rect: Rect | None = None
        self.list_rect: Rect | None = None

    def row_at(self, x: float, y: float) -> int | None:
        """Row index under (*x*, *y*) in the last draw, if any."""
        if self.list_rect is None or index_at((self.list_rect,), x, y) is None:
            return None
        hit = index_at(self.row_rects, x, y)
        return None if hit is None else self.row_indices[hit]

    def draw(self, rect: Rect, *, active: bool) -> None:
        from cleave.viz.shell_windows import draw_fixed_window
        from cleave.viz.theme import palette

        self.intent = None
        self.row_rects = ()
        self.row_indices = ()
        self.crumb_rects = ()
        self.crumb_indices = ()
        self.filter_rect = None
        self.list_rect = None
        draw_fixed_window(
            PRESET_BROWSER_WINDOW,
            rect,
            active=active,
            idle_border=palette().panel_edge,
            body=self._body,
        )
        self._record_pointer()

    # -- painting ------------------------------------------------------------

    def _body(self) -> None:
        from cleave.viz.modal_layout import form_row_height, form_row_pad_y
        from cleave.viz.modal_surface import ImGuiTextMeasure
        from cleave.viz.shell_widgets import stroke_h_rule
        from cleave.viz.theme import palette, tuning_ui_metrics
        from cleave.viz.title_bar import paint_title_bar

        imgui = _imgui()
        view = self.view
        measure = ImGuiTextMeasure()
        metrics = tuning_ui_metrics()
        pos = imgui.get_window_pos()
        size = imgui.get_window_size()
        ox, oy = int(pos.x), int(pos.y)
        width, height = int(size.x), int(size.y)
        pad = imgui.get_style().window_padding
        pad_x, pad_y = int(pad.x), int(pad.y)
        line_h = measure.get_linesize()
        step = line_h + metrics.line_gap
        content_x = ox + pad_x
        content_w = max(1, width - 2 * pad_x)
        text_width = lambda text: measure.size(text)[0]
        draw = imgui.get_window_draw_list()

        y = oy + pad_y
        bar_bottom = y + line_h + metrics.line_gap
        paint_title_bar(
            draw, float(ox + 1), float(oy + 1), float(ox + width - 1), float(bar_bottom)
        )
        draw_text(
            draw,
            content_x,
            y,
            fit_text_to_width(measure, view.title, content_w),
            palette().on_accent,
        )
        y = bar_bottom + metrics.line_gap + form_row_pad_y()
        divider_h = max(1, int(line_h * DIVIDER_LINES))
        rule_y = y + step + divider_h // 2

        # The folder mark, then the path, as in the file picker, with the
        # mark's ink centred between the title bar and the divider.
        path_y = centred_line_y(bar_bottom, rule_y, *folder_glyph_ink())
        draw_text(draw, content_x, path_y, FOLDER_GLYPH, palette().preset_icon)
        icon_w = measure.size(FOLDER_GLYPH)[0] + metrics.icon_label_gap
        self._paint_crumbs(
            draw,
            measure,
            text_width,
            content_x + icon_w,
            path_y,
            max(1, content_w - icon_w),
            line_h,
        )

        stroke_h_rule(
            float(content_x),
            float(content_x + content_w),
            float(rule_y),
            palette().inspector_divider,
        )
        y += step + divider_h + form_row_pad_y()

        self._paint_filter(draw, measure, content_x, y, content_w, line_h)
        y += step + form_row_pad_y()

        legend_y = oy + height - pad_y - line_h
        list_h = max(1, legend_y - metrics.line_gap - y)
        self._paint_list(
            measure,
            content_x,
            y,
            content_w,
            list_h,
            line_h,
            form_row_height(line_h),
            metrics.scrollbar_width,
        )
        if view.loading:
            self._paint_spinner(draw, measure, content_x, y, content_w, list_h)
        self._paint_legend(draw, measure, content_x, legend_y, content_w)

    def _paint_crumbs(
        self, draw: Any, measure, text_width, x: int, y: int, content_w: int, line_h: int
    ) -> None:
        from cleave.viz.file_picker_surface import location_text_lift
        from cleave.viz.theme import palette

        labels = tuple(crumb.label for crumb in self.view.crumbs)
        slots = fit_crumbs(
            labels,
            content_w,
            text_width,
            lambda text, px: fit_text_to_width(measure, text, px),
        )
        lift = location_text_lift()
        text_y = y + lift
        pointer = _imgui().get_io().mouse_pos
        rects: list[Rect] = []
        indices: list[int] = []
        last = len(labels) - 1
        for position, slot in enumerate(slots):
            if position:
                draw_text(
                    draw,
                    x + slot.x - text_width(CRUMB_SEPARATOR),
                    text_y,
                    CRUMB_SEPARATOR,
                    palette().muted,
                )
            current = slot.index == last and slot.text != CRUMB_ELLIPSIS
            if not current:
                hit = outset_list_row((x + slot.x, text_y, slot.width, line_h))
                if _contains(hit, pointer.x, pointer.y):
                    paint_list_row(draw, hit, "HOVER")
                    request_hand()
                rects.append(hit)
                indices.append(slot.index)
            role = palette().value if current else palette().label
            draw_text(draw, x + slot.x, text_y, slot.text, role)
        self.crumb_rects = tuple(rects)
        self.crumb_indices = tuple(indices)

    def _paint_filter(
        self, draw: Any, measure, x: int, y: int, content_w: int, line_h: int
    ) -> None:
        from cleave.viz.inline_edit import InlineTextView
        from cleave.viz.pointer_cursor import PointerShape, request_pointer
        from cleave.viz.shell_widgets import InlineField
        from cleave.viz.theme import palette

        imgui = _imgui()
        view = self.view
        row = outset_list_row((x, y, content_w, line_h))
        self.filter_rect = row
        pointer = imgui.get_io().mouse_pos
        hovered = _contains(row, pointer.x, pointer.y)
        if hovered:
            request_pointer(PointerShape.TEXT)
        label_w = measure.size(FILTER_LABEL)[0]
        if view.editing:
            draw_text(draw, x, y, FILTER_LABEL, palette().label)
            field_min = imgui.ImVec2(float(x + label_w), float(row[1]))
            field_max = imgui.ImVec2(float(row[0] + row[2]), float(row[1] + row[3]))
            InlineField().paint(
                field_min,
                field_max,
                InlineTextView(view.draft, view.caret_index, view.caret_visible, None),
                text_y=float(y),
            )
            return
        if view.focus is BrowserFocus.FILTER:
            paint_list_row(draw, row, "FOCUSED")
        elif hovered:
            paint_list_row(draw, row, "HOVER")
        draw_text(draw, x, y, FILTER_LABEL, palette().label)
        room = max(1, content_w - label_w)
        if view.filter_text:
            draw_text(
                draw,
                x + label_w,
                y,
                fit_text_to_width(measure, view.filter_text, room),
                palette().value,
            )
        else:
            draw_text(
                draw,
                x + label_w,
                y,
                fit_text_to_width(measure, FILTER_PLACEHOLDER, room),
                palette().muted,
            )

    def _paint_spinner(
        self, draw: Any, measure, x: int, top: int, width: int, height: int
    ) -> None:
        """A turning arc over the list while a listing loads."""
        from cleave.viz.imgui_theme import rgba
        from cleave.viz.theme import palette

        imgui = _imgui()
        line_h = measure.get_linesize()
        radius = max(4.0, line_h * 0.7)
        centre_y = top + min(height / 2.0, line_h * 4.0)
        centre = imgui.ImVec2(x + width / 2.0, centre_y)
        start = (imgui.get_time() * SPINNER_TURNS_PER_SEC * 2.0 * math.pi) % (
            2.0 * math.pi
        )
        draw.path_clear()
        draw.path_arc_to(centre, radius, start, start + SPINNER_ARC, 24)
        draw.path_stroke(
            imgui.get_color_u32(rgba(palette().highlight)),
            thickness=max(2.0, line_h / 6.0),
        )
        label_w = measure.size(LOADING_LABEL)[0]
        draw_text(
            draw,
            int(x + (width - label_w) / 2),
            int(centre_y + radius + line_h / 2),
            LOADING_LABEL,
            palette().muted,
        )

    def _paint_legend(self, draw: Any, measure, x: int, y: int, content_w: int) -> None:
        from cleave.viz.theme import palette

        cursor = x
        right = x + content_w
        gap = measure.size(_LEGEND_SEPARATOR)[0]
        for index, (key, label) in enumerate(self.view.legend):
            prefix = f"{key}: "
            entry_w = measure.size(prefix)[0] + measure.size(label)[0]
            start = cursor + (gap if index else 0)
            if start + entry_w > right:
                break
            draw_text(draw, start, y, prefix, palette().label)
            draw_text(draw, start + measure.size(prefix)[0], y, label, palette().value)
            cursor = start + entry_w

    def _paint_list(
        self,
        measure,
        x: int,
        top: int,
        width: int,
        height: int,
        line_h: int,
        row_step: int,
        scrollbar_width: int,
    ) -> None:
        from cleave.viz.imgui_theme import floating_surface
        from cleave.viz.modal_layout import form_row_pad_y

        imgui = _imgui()
        view = self.view
        total = len(view.rows)
        self.list_rect = (x, top, width, height)
        imgui.set_cursor_screen_pos(imgui.ImVec2(float(x), float(top)))
        imgui.set_next_window_content_size(imgui.ImVec2(0.0, float(total * row_step)))
        imgui.push_style_var(imgui.StyleVar_.window_padding, imgui.ImVec2(0.0, 0.0))
        imgui.push_style_var(imgui.StyleVar_.item_spacing, imgui.ImVec2(0.0, 0.0))
        imgui.push_style_var(imgui.StyleVar_.scrollbar_size, float(scrollbar_width))
        flags = list_child_flags()
        if total * row_step > height:
            flags |= int(imgui.WindowFlags_.always_vertical_scrollbar)
        begun = False
        try:
            with floating_surface():
                imgui.begin_child(
                    PRESET_BROWSER_LIST,
                    imgui.ImVec2(float(width), float(height)),
                    0,
                    flags,
                )
            begun = True
            origin = imgui.get_window_pos()
            scroll_y = self._sync_scroll(row_step, float(height))
            row_w = max(1, int(imgui.get_content_region_avail().x) - 3)
            if total:
                imgui.dummy(imgui.ImVec2(1.0, float(total * row_step)))
            start, end = visible_row_range(scroll_y, float(height), row_step, total)
            left = int(origin.x)
            draw = imgui.get_window_draw_list()
            pointer = imgui.get_io().mouse_pos
            hovered_window = bool(imgui.is_window_hovered())
            rects: list[Rect] = []
            indices: list[int] = []
            for index in range(start, end):
                row_top = int(round(float(origin.y) + index * row_step - scroll_y))
                text_y = row_top + form_row_pad_y()
                rect = outset_list_row((left, text_y, row_w, line_h))
                row = view.rows[index]
                selected = index == view.selected_index
                hovered = (
                    hovered_window
                    and rect[0] <= pointer.x < rect[0] + rect[2]
                    and rect[1] <= pointer.y < rect[1] + rect[3]
                )
                if selected or hovered:
                    push_list_highlight_clip(draw)
                    try:
                        if not selected:
                            paint_list_row(draw, rect, "HOVER")
                        elif view.focus is BrowserFocus.LIST and not view.loading:
                            paint_list_row(draw, rect, "FOCUSED")
                        else:
                            # The filter holds the keys; the row stays chosen.
                            paint_list_row(draw, rect, "SELECTED")
                    finally:
                        draw.pop_clip_rect()
                self._paint_row(draw, measure, row, left, text_y, row_w, selected)
                rects.append(rect)
                indices.append(index)
            self.row_rects = tuple(rects)
            self.row_indices = tuple(indices)
        finally:
            if begun:
                imgui.end_child()
            imgui.pop_style_var(3)

    def _paint_row(
        self,
        draw: Any,
        measure,
        row: BrowserRow,
        x: int,
        y: int,
        width: int,
        selected: bool,
    ) -> None:
        from cleave.viz.theme import palette

        detail = row.detail
        detail_w = measure.size(detail)[0] if detail else 0
        gap = measure.size("  ")[0] if detail else 0
        label_room = max(1, width - detail_w - gap)
        label = fit_text_to_width(measure, row_label(row), label_room)
        if self.view.loading:
            role = palette().disabled
        else:
            role = palette().value if selected else _row_role(row)
        draw_text(draw, x, y, label, role)
        if detail:
            detail_role = palette().muted if row.kind is BrowserRowKind.FOLDER else palette().highlight
            draw_text(draw, x + width - detail_w, y, detail, detail_role)

    def _sync_scroll(self, row_step: int, view_h: float) -> float:
        """Keep the selection on screen when it or the listing changes; apply the wheel."""
        from cleave.viz.scroll_follow import clamp_scroll, scroll_to_reveal

        imgui = _imgui()
        view = self.view
        storage = imgui.get_state_storage()
        loc_id = imgui.get_id("##browse-loc")
        sel_id = imgui.get_id("##browse-sel")
        loc_key = int(imgui.get_id(view.location_key)) & 0x7FFFFFFF
        prev_loc = storage.get_int(loc_id, -1)
        prev_sel = storage.get_int(sel_id, -1)
        scroll_y = float(imgui.get_scroll_y())
        count = len(view.rows)
        max_scroll = max(0.0, count * row_step - view_h)
        wheel = float(imgui.get_io().mouse_wheel)
        wheeled = bool(imgui.is_window_hovered()) and wheel != 0.0 and max_scroll > 0.0
        moved = prev_loc != loc_key
        if moved:
            scroll_y = 0.0
        if wheeled:
            scroll_y = clamp_scroll(
                scroll_y + wheel_scroll_px(wheel, row_step),
                row_stride=row_step,
                view_height=view_h,
                row_count=count,
            )
        elif moved or prev_sel != view.selected_index:
            scroll_y = scroll_to_reveal(
                scroll_y,
                view.selected_index,
                row_stride=row_step,
                view_height=view_h,
                row_count=count,
            )
        if abs(scroll_y - float(imgui.get_scroll_y())) > 0.01:
            imgui.set_scroll_y(float(scroll_y))
            window = imgui.internal.get_current_window()
            window.scroll = imgui.ImVec2(float(window.scroll.x), float(scroll_y))
        storage.set_int(loc_id, loc_key)
        storage.set_int(sel_id, view.selected_index)
        return scroll_y

    # -- pointer -------------------------------------------------------------

    def _record_pointer(self) -> None:
        imgui = _imgui()
        io = imgui.get_io()
        x, y = float(io.mouse_pos.x), float(io.mouse_pos.y)
        clicked = bool(io.mouse_clicked[0])
        double = bool(imgui.is_mouse_double_clicked(0))
        row = self.row_at(x, y)
        if double and row is not None:
            self.intent = BrowserPointerIntent(BrowserPointerKind.OPEN_ROW, row)
            return
        if clicked and row is not None:
            self.intent = BrowserPointerIntent(BrowserPointerKind.SELECT_ROW, row)
            return
        if (
            clicked
            and self.filter_rect is not None
            and _contains(self.filter_rect, x, y)
        ):
            self.intent = BrowserPointerIntent(BrowserPointerKind.EDIT_FILTER)
            return
        crumb = index_at(self.crumb_rects, x, y)
        if clicked and crumb is not None:
            self.intent = BrowserPointerIntent(
                BrowserPointerKind.GOTO_CRUMB, self.crumb_indices[crumb]
            )
