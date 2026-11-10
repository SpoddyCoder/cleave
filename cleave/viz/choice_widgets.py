"""Draw choice controls with ImGui: segments, a combo box, and its open list.

Draw only. Callers turn the returned hit rects and ``ChoiceListPointer`` into
their own mutations, so the inspector and form dialogs share the look.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from imgui_bundle import imgui

from cleave.viz.choice_layout import (
    COMBO_CARET,
    Rect,
    choice_list_pad_y,
    choice_list_rects,
    combo_pad_x,
    rect_contains,
    rect_index_at,
    segment_rects,
)
from cleave.viz.choice_list import CHOICE_LIST_MAX_VISIBLE, ChoiceListView
from cleave.viz.imgui_theme import rgba
from cleave.viz.pointer_cursor import PointerShape, request_pointer
from cleave.viz.text_fit import TextSizer
from cleave.viz.theme import (
    BORDER_WIDTH,
    BUTTON_BG,
    BUTTON_BORDER,
    BUTTON_HOVER_BG,
    BUTTON_PRIMARY_BG,
    DISABLED,
    MUTED,
    VALUE,
)

_LIST_WINDOW_FLAGS = (
    int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_nav)
    | int(imgui.WindowFlags_.no_scrollbar)
)
_CHOSEN_MARK = "✓ "
_UNCHOSEN_MARK = "  "


def _u32(role: tuple[int, int, int], alpha: float = 1.0) -> int:
    return imgui.get_color_u32(rgba(role, alpha))


def _vec(x: float, y: float) -> imgui.ImVec2:
    return imgui.ImVec2(float(x), float(y))


def _mouse() -> tuple[float, float]:
    pos = imgui.get_io().mouse_pos
    return float(pos.x), float(pos.y)


def _fill(draw: imgui.ImDrawList, rect: Rect, role: tuple[int, int, int]) -> None:
    x, y, w, h = rect
    draw.add_rect_filled(_vec(x, y), _vec(x + w, y + h), _u32(role))


def _border(draw: imgui.ImDrawList, rect: Rect) -> None:
    x, y, w, h = rect
    draw.add_rect(_vec(x, y), _vec(x + w, y + h), _u32(BUTTON_BORDER))


def _centred_text(
    draw: imgui.ImDrawList,
    measure: TextSizer,
    rect: Rect,
    text: str,
    role: tuple[int, int, int],
) -> None:
    x, y, w, h = rect
    tw, th = measure.size(text)
    draw.add_text(_vec(x + (w - tw) // 2, y + (h - th) // 2), _u32(role), text)


def draw_segments(
    draw: imgui.ImDrawList,
    measure: TextSizer,
    labels: Sequence[str],
    chosen: int,
    *,
    x: int,
    y: int,
    height: int,
    enabled: bool = True,
    hover: bool = True,
) -> tuple[Rect, ...]:
    """One box per option, the chosen one filled. Returns their rects.

    ``hover`` lights the box under the pointer; pass False while something
    else, such as an open list, owns the pointer.
    """
    rects = segment_rects(measure, labels, x=x, y=y, height=height)
    mx, my = _mouse()
    for index, rect in enumerate(rects):
        is_chosen = index == chosen
        if is_chosen:
            _fill(draw, rect, BUTTON_PRIMARY_BG if enabled else BUTTON_BG)
        elif enabled and hover and rect_contains(rect, mx, my):
            _fill(draw, rect, BUTTON_HOVER_BG)
            request_pointer(PointerShape.HAND)
        _border(draw, rect)
        role = DISABLED if not enabled else (VALUE if is_chosen else MUTED)
        _centred_text(draw, measure, rect, labels[index], role)
    return rects


def draw_combo(
    draw: imgui.ImDrawList,
    measure: TextSizer,
    text: str,
    *,
    rect: Rect,
    open_: bool,
    enabled: bool = True,
    hover: bool = True,
) -> None:
    """A framed value with a caret at its right edge."""
    x, y, w, h = rect
    mx, my = _mouse()
    hovered = enabled and hover and rect_contains(rect, mx, my)
    if hovered:
        request_pointer(PointerShape.HAND)
    lit = open_ or hovered
    _fill(draw, rect, BUTTON_HOVER_BG if lit else BUTTON_BG)
    _border(draw, rect)
    role = VALUE if enabled else DISABLED
    th = measure.size(text)[1]
    text_y = y + (h - th) // 2
    draw.add_text(_vec(x + combo_pad_x(), text_y), _u32(role), text)
    caret_w = measure.size(COMBO_CARET)[0]
    caret_role = MUTED if enabled else DISABLED
    draw.add_text(
        _vec(x + w - combo_pad_x() - caret_w, text_y), _u32(caret_role), COMBO_CARET
    )


@dataclass(frozen=True)
class ChoiceListPointer:
    """What the pointer did to an open list this frame.

    ``hovered`` is the option under the pointer. ``picked`` is the option
    clicked. ``outside`` is a click anywhere else, which should close the list.
    """

    hovered: int | None = None
    picked: int | None = None
    outside: bool = False
    rows: tuple[Rect, ...] = ()


@dataclass
class _ListMemory:
    target: object
    opened_frame: int
    drawn_frame: int
    highlighted: int


_list_memory: dict[str, _ListMemory] = {}


def draw_choice_list(
    window_id: str,
    view: ChoiceListView,
    measure: TextSizer,
    *,
    anchor: Rect,
) -> ChoiceListPointer:
    """The open list as its own window under ``anchor``, above every other window.

    It is at least as wide as the anchor and scrolls past
    ``CHOICE_LIST_MAX_VISIBLE`` rows, keeping the highlighted row in view. The
    click that opened it does not count as a click outside.
    """
    frame = imgui.get_frame_count()
    memory = _list_memory.get(window_id)
    reopened = memory is not None and memory.drawn_frame not in (frame, frame - 1)
    if memory is None or reopened or memory.target != view.target:
        memory = _ListMemory(view.target, frame, frame, -1)
        _list_memory[window_id] = memory
    memory.drawn_frame = frame
    just_opened = frame == memory.opened_frame
    line_h = int(imgui.get_text_line_height())
    widest = max(
        (measure.size(f"{_CHOSEN_MARK}{label}")[0] for label in view.options),
        default=0,
    )
    ax, ay, aw, ah = anchor
    width = max(aw, widest + combo_pad_x() * 2)
    row_h = line_h + choice_list_pad_y() * 2
    visible = min(len(view.options), CHOICE_LIST_MAX_VISIBLE)
    height = visible * row_h + BORDER_WIDTH * 2

    display = imgui.get_io().display_size
    x = min(ax, max(0, int(display.x) - width))
    y = ay + ah
    if y + height > display.y and ay - height >= 0:
        y = ay - height

    window_name = f"##{window_id}"
    imgui.set_next_window_pos(_vec(x, y), imgui.Cond_.always)
    imgui.set_next_window_size(_vec(width, height), imgui.Cond_.always)
    imgui.push_style_var(imgui.StyleVar_.window_padding, _vec(0, 0))
    imgui.push_style_var(imgui.StyleVar_.window_border_size, float(BORDER_WIDTH))
    imgui.push_style_color(imgui.Col_.window_bg, rgba(BUTTON_BG))
    imgui.push_style_color(imgui.Col_.border, rgba(BUTTON_BORDER))
    try:
        imgui.begin(window_name, None, _LIST_WINDOW_FLAGS)
        try:
            imgui.internal.bring_window_to_display_front(
                imgui.internal.find_window_by_name(window_name)
            )
            result = _draw_list_rows(
                view, measure, memory, width, row_h, visible, just_opened=just_opened
            )
            hovered_window = imgui.is_window_hovered(
                imgui.HoveredFlags_.root_and_child_windows
            )
        finally:
            imgui.end()
    finally:
        imgui.pop_style_color(2)
        imgui.pop_style_var(2)
    clicked = imgui.is_mouse_clicked(0) and not just_opened
    if clicked and result.picked is None and not hovered_window:
        return ChoiceListPointer(hovered=result.hovered, outside=True, rows=result.rows)
    return result


def _draw_list_rows(
    view: ChoiceListView,
    measure: TextSizer,
    memory: _ListMemory,
    width: int,
    row_h: int,
    visible: int,
    *,
    just_opened: bool,
) -> ChoiceListPointer:
    count = len(view.options)
    scroll = imgui.get_scroll_y()
    max_scroll = max(0, (count - visible) * row_h)
    if view.highlighted != memory.highlighted:
        # Keep a row moved to by key, or the chosen row on open, in view.
        top = view.highlighted * row_h
        if top < scroll:
            scroll = top
        elif top + row_h > scroll + visible * row_h:
            scroll = top + row_h - visible * row_h
        memory.highlighted = view.highlighted
    wheel = imgui.get_io().mouse_wheel
    if wheel and imgui.is_window_hovered():
        scroll -= wheel * row_h * 3
    scroll = max(0, min(max_scroll, scroll))
    imgui.set_scroll_y(scroll)
    imgui.dummy(_vec(width, count * row_h))

    origin = imgui.get_window_pos()
    ox = int(origin.x) + BORDER_WIDTH
    oy = int(origin.y) + BORDER_WIDTH - int(scroll)
    rects = choice_list_rects(
        x=ox,
        y=oy,
        width=width - BORDER_WIDTH * 2,
        line_h=row_h - choice_list_pad_y() * 2,
        count=count,
    )
    draw = imgui.get_window_draw_list()
    mx, my = _mouse()
    inside = imgui.is_window_hovered()
    hovered = rect_index_at(rects, mx, my) if inside else None
    for index, rect in enumerate(rects):
        if index == view.highlighted:
            _fill(draw, rect, BUTTON_HOVER_BG)
        mark = _CHOSEN_MARK if index == view.chosen else _UNCHOSEN_MARK
        rx, ry, _rw, rh = rect
        th = measure.size(view.options[index])[1]
        draw.add_text(
            _vec(rx + combo_pad_x(), ry + (rh - th) // 2),
            _u32(VALUE),
            f"{mark}{view.options[index]}",
        )
    picked = hovered if imgui.is_mouse_clicked(0) and not just_opened else None
    # A resting pointer leaves a highlight moved by key alone.
    delta = imgui.get_io().mouse_delta
    moved = delta.x != 0.0 or delta.y != 0.0
    return ChoiceListPointer(
        hovered=hovered if moved else None, picked=picked, rows=rects
    )
