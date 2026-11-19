"""ImGui preset browser, drawn in the navigator/inspector column.

Draw records hit rects and one pointer intent; it does not mutate the browser.
The controller applies :class:`BrowserPointerIntent` after the frame. ImGui
loads on draw, not at import, so the controller and tests import this freely.
"""

from __future__ import annotations

import functools
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
from cleave.viz.preset_browser import (
    FILTER_PLACEHOLDER,
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
_CARET = "_"
_LEGEND_SEPARATOR = "   "


class BrowserPointerKind(Enum):
    SELECT_ROW = "select-row"
    OPEN_ROW = "open-row"
    GOTO_CRUMB = "goto-crumb"


@dataclass(frozen=True)
class BrowserPointerIntent:
    kind: BrowserPointerKind
    index: int | None = None


def row_label(row: BrowserRow) -> str:
    """Display text for *row*, with the folder slash."""
    if row.kind is BrowserRowKind.FOLDER:
        return f"{row.label}/"
    return row.label


def crumb_layout(
    labels: tuple[str, ...], text_width
) -> tuple[tuple[int, int], ...]:
    """``(x, width)`` of each crumb label, separated by :data:`CRUMB_SEPARATOR`."""
    gap = text_width(CRUMB_SEPARATOR)
    out: list[tuple[int, int]] = []
    x = 0
    for index, label in enumerate(labels):
        if index:
            x += gap
        width = text_width(label)
        out.append((x, width))
        x += width
    return tuple(out)


@functools.cache
def _imgui():
    from imgui_bundle import imgui as imgui_mod

    return imgui_mod


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

        self._paint_crumbs(draw, measure, text_width, content_x, y, content_w, line_h)
        y += step
        self._paint_filter(draw, measure, content_x, y, content_w)
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
        self._paint_legend(draw, measure, content_x, legend_y, content_w)

    def _paint_crumbs(
        self, draw: Any, measure, text_width, x: int, y: int, content_w: int, line_h: int
    ) -> None:
        from cleave.viz.theme import palette

        labels = tuple(crumb.label for crumb in self.view.crumbs)
        layout = crumb_layout(labels, text_width)
        total = layout[-1][0] + layout[-1][1] if layout else 0
        if total > content_w:
            # Too long: show the folder being browsed, nothing to click.
            draw_text(
                draw,
                x,
                y,
                fit_text_to_width(measure, CRUMB_SEPARATOR.join(labels), content_w),
                palette().value,
            )
            return
        pointer = _imgui().get_io().mouse_pos
        rects: list[Rect] = []
        last = len(labels) - 1
        for index, (label, (cx, cw)) in enumerate(zip(labels, layout)):
            if index:
                draw_text(
                    draw,
                    x + cx - text_width(CRUMB_SEPARATOR),
                    y,
                    CRUMB_SEPARATOR,
                    palette().muted,
                )
            hit = outset_list_row((x + cx, y, cw, line_h))
            if index < last:
                hovered = (
                    hit[0] <= pointer.x < hit[0] + hit[2]
                    and hit[1] <= pointer.y < hit[1] + hit[3]
                )
                if hovered:
                    paint_list_row(draw, hit, "HOVER")
                    request_hand()
                rects.append(hit)
            role = palette().value if index == last else palette().label
            draw_text(draw, x + cx, y, label, role)
        self.crumb_rects = tuple(rects)

    def _paint_filter(self, draw: Any, measure, x: int, y: int, content_w: int) -> None:
        from cleave.viz.theme import palette

        draw_text(draw, x, y, FILTER_LABEL, palette().label)
        label_w = measure.size(FILTER_LABEL)[0]
        room = max(1, content_w - label_w - measure.size(_CARET)[0])
        text = self.view.filter_text
        if not text:
            draw_text(draw, x + label_w, y, _CARET, palette().highlight)
            draw_text(
                draw,
                x + label_w + measure.size(_CARET)[0],
                y,
                fit_text_to_width(measure, FILTER_PLACEHOLDER, room),
                palette().muted,
            )
            return
        # Keep the end of a long filter, where typing happens.
        shown = text
        while len(shown) > 1 and measure.size(shown)[0] > room:
            shown = shown[1:]
        draw_text(draw, x + label_w, y, shown, palette().value)
        draw_text(
            draw, x + label_w + measure.size(shown)[0], y, _CARET, palette().highlight
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
                        paint_list_row(draw, rect, "FOCUSED" if selected else "HOVER")
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
        crumb = index_at(self.crumb_rects, x, y)
        if clicked and crumb is not None:
            self.intent = BrowserPointerIntent(BrowserPointerKind.GOTO_CRUMB, crumb)
