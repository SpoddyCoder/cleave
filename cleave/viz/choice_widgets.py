"""Draw choice controls with ImGui: segments, a combo box, its open list, and a stepper.

Draw only. Callers turn the returned hit rects and ``ChoiceListPointer`` into
their own mutations, so the inspector and form dialogs share the look.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto

from imgui_bundle import imgui

from cleave.viz.choice_layout import (
    COMBO_CARET,
    FRect,
    STEPPER_BACK,
    STEPPER_FORWARD,
    Rect,
    choice_list_pad_y,
    choice_list_rects,
    combo_pad_x,
    rect_contains,
    rect_index_at,
    segment_rects,
    stepper_arrow_rects,
)
from cleave.viz.button_paint import (
    ButtonState,
    ButtonTone,
    button_look,
    paint_button,
)
from cleave.viz.choice_list import CHOICE_LIST_MAX_VISIBLE, ChoiceListView
from cleave.viz.icon_button import text_box
from cleave.viz.imgui_icon_button import paint_box
from cleave.viz.imgui_theme import rgba
from cleave.viz.pointer_cursor import PointerShape, request_pointer
from cleave.viz.text_fit import TextSizer
from cleave.viz.theme import (
    BORDER_WIDTH,
    BUTTON_PRIMARY_DIMMED_BG,
    CHOICE_LIST_BG,
    CHOICE_LIST_BORDER,
    CHOICE_LIST_TEXT,
    DISABLED,
    HIGHLIGHT,
    DISABLED_MUTED,
    LOCKED,
    LOCKED_MUTED,
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
# Width of the HIGHLIGHT bar on the open list's highlighted row.
_LIST_ACCENT_PX = 3


class ChoiceTone(Enum):
    """How a choice control reads beside its row.

    ``OFF`` greys a control that still edits, on a page that is switched off.
    ``LOCKED`` tints it like a locked row's value.
    """

    NORMAL = auto()
    OFF = auto()
    LOCKED = auto()


def _u32(role: tuple[int, int, int], alpha: float = 1.0) -> int:
    return imgui.get_color_u32(rgba(role, alpha))


def _vec(x: float, y: float) -> imgui.ImVec2:
    return imgui.ImVec2(float(x), float(y))


def _mouse() -> tuple[float, float]:
    pos = imgui.get_io().mouse_pos
    return float(pos.x), float(pos.y)


def _pointer_state(rect: Rect, mx: float, my: float) -> ButtonState:
    """HOVER under the pointer, PRESSED while the left button is down there."""
    if not rect_contains(rect, mx, my):
        return ButtonState.REST
    return ButtonState.PRESSED if imgui.is_mouse_down(0) else ButtonState.HOVER


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
    tone: ChoiceTone = ChoiceTone.NORMAL,
    hover: bool = True,
    hand: bool = True,
) -> tuple[Rect, ...]:
    """One box per option, the chosen one filled. Returns their rects.

    ``hover`` lights the box under the pointer; pass False while something
    else, such as an open list, owns the pointer. Pass ``hand`` False while
    a click would be refused, so the pointer stays an arrow. *tone* greys or
    tints the control to match its row.
    """
    rects = segment_rects(measure, labels, x=x, y=y, height=height)
    mx, my = _mouse()
    states = [ButtonState.REST] * len(rects)
    for index, rect in enumerate(rects):
        if index != chosen and enabled and hover:
            states[index] = _pointer_state(rect, mx, my)
            if states[index] is not ButtonState.REST and hand:
                request_pointer(PointerShape.HAND)
        if index == chosen:
            chosen_tone, fill = _chosen_look(enabled=enabled, tone=tone)
            paint_button(draw, rect, chosen_tone, ButtonState.REST, fill=fill)
        else:
            paint_button(draw, rect, ButtonTone.PLAIN, states[index])
    for index, rect in enumerate(rects):
        state = states[index]
        if state is not ButtonState.REST:
            # Neighbours share edges, so the lit border goes over theirs.
            rx, ry, rw, rh = rect
            border = button_look(ButtonTone.PLAIN, state).border
            draw.add_rect(_vec(rx, ry), _vec(rx + rw, ry + rh), _u32(border))
        role = _segment_text_role(index == chosen, enabled=enabled, tone=tone)
        lit_role = VALUE if state is not ButtonState.REST else role
        _centred_text(draw, measure, rect, labels[index], lit_role)
    return rects


def _chosen_look(
    *, enabled: bool, tone: ChoiceTone
) -> tuple[ButtonTone, tuple[int, int, int] | None]:
    """Tone and fill override of the chosen segment."""
    if tone is ChoiceTone.NORMAL:
        return (ButtonTone.PRIMARY, None) if enabled else (ButtonTone.PLAIN, None)
    return ButtonTone.PLAIN, BUTTON_PRIMARY_DIMMED_BG


def _segment_text_role(
    chosen: bool, *, enabled: bool, tone: ChoiceTone
) -> tuple[int, int, int]:
    """Chosen and unchosen option text. A lock tints even a refused control."""
    if tone is ChoiceTone.LOCKED:
        return LOCKED if chosen else LOCKED_MUTED
    if not enabled:
        return DISABLED
    if tone is ChoiceTone.OFF:
        return DISABLED if chosen else DISABLED_MUTED
    return VALUE if chosen else MUTED


def _combo_text_roles(
    *, enabled: bool, tone: ChoiceTone
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Value and caret colours of a combo."""
    if tone is ChoiceTone.LOCKED:
        return LOCKED, LOCKED_MUTED
    if tone is ChoiceTone.OFF:
        return DISABLED, DISABLED_MUTED
    return (VALUE, MUTED) if enabled else (DISABLED, DISABLED)


def draw_combo(
    draw: imgui.ImDrawList,
    measure: TextSizer,
    text: str,
    *,
    rect: Rect,
    open_: bool,
    enabled: bool = True,
    tone: ChoiceTone = ChoiceTone.NORMAL,
    hover: bool = True,
    hand: bool = True,
) -> None:
    """A framed value with a caret at its right edge.

    Pass ``hand`` False while a click would be refused. *tone* greys or
    tints the combo to match its row.
    """
    x, y, w, h = rect
    mx, my = _mouse()
    hovered = enabled and hover and rect_contains(rect, mx, my)
    if hovered and hand:
        request_pointer(PointerShape.HAND)
    if hovered and imgui.is_mouse_down(0):
        state = ButtonState.PRESSED
    elif open_ or hovered:
        state = ButtonState.HOVER
    else:
        state = ButtonState.REST
    paint_button(draw, rect, ButtonTone.PLAIN, state)
    role, caret_role = _combo_text_roles(enabled=enabled, tone=tone)
    if state is not ButtonState.REST:
        role, caret_role = VALUE, HIGHLIGHT
    th = measure.size(text)[1]
    text_y = y + (h - th) // 2
    draw.add_text(_vec(x + combo_pad_x(), text_y), _u32(role), text)
    caret_w = measure.size(COMBO_CARET)[0]
    draw.add_text(
        _vec(x + w - combo_pad_x() - caret_w, text_y), _u32(caret_role), COMBO_CARET
    )


def paint_stepper_hover(arrow: FRect, *, forward: bool) -> None:
    """Light one stepper arrow: the hover wash, then its glyph in the hover colour.

    ``arrow`` covers the painted glyph and its gap space, and is the band
    tall. The lit box is the arrow character plus a space, centred on the
    character. The inspector and form dialogs share this, so a stepper looks
    the same in both.
    """
    x, y, _w, h = arrow
    char = ">" if forward else "<"
    char_w = imgui.calc_text_size(char).x
    space_w = imgui.calc_text_size(" ").x
    # The gap space sits before ">" and after "<"; centre the box on the char.
    left = x + (space_w if forward else 0.0) - space_w * 0.5
    paint_box(
        text_box(left, char_w, space_w, (y, y + h)),
        char,
        color=DISABLED,
        hovered=True,
        icon=False,
    )


def draw_stepper(
    draw: imgui.ImDrawList,
    measure: TextSizer,
    text: str,
    *,
    rect: Rect,
    at_start: bool,
    at_end: bool,
    held: bool | None = None,
    hover: bool = True,
) -> tuple[Rect, Rect]:
    """``< value >`` with the value centred. Returns the back and forward arrows.

    Drawn like an inspector stepper: dim arrows, and the arrow under the
    pointer lit. ``held`` names an arrow being held (True for forward), which
    stays lit while the pointer wanders. An arrow at its end of the range does
    not light and keeps the arrow pointer.
    """
    back, forward = stepper_arrow_rects(measure, rect)
    x, y, w, h = rect
    text_y = y + (h - measure.size(text)[1]) // 2
    _centred_text(draw, measure, rect, text, VALUE)
    draw.add_text(_vec(back[0], text_y), _u32(DISABLED), STEPPER_BACK)
    draw.add_text(_vec(forward[0], text_y), _u32(DISABLED), STEPPER_FORWARD)
    mx, my = _mouse()
    lit: bool | None = held
    if lit is None and hover:
        if not at_start and rect_contains(back, mx, my):
            lit = False
        elif not at_end and rect_contains(forward, mx, my):
            lit = True
    if lit is not None:
        request_pointer(PointerShape.HAND)
        paint_stepper_hover(
            tuple(float(v) for v in (forward if lit else back)), forward=lit
        )
    return back, forward


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
    imgui.push_style_color(imgui.Col_.window_bg, rgba(CHOICE_LIST_BG))
    imgui.push_style_color(imgui.Col_.border, rgba(CHOICE_LIST_BORDER))
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
        rx, ry, rw, rh = rect
        lit = index == view.highlighted
        if lit:
            look = button_look(ButtonTone.PLAIN, ButtonState.HOVER)
            draw.add_rect_filled_multi_color(
                _vec(rx, ry),
                _vec(rx + rw, ry + rh),
                _u32(look.top),
                _u32(look.top),
                _u32(look.bottom),
                _u32(look.bottom),
            )
            draw.add_rect_filled(
                _vec(rx, ry), _vec(rx + _LIST_ACCENT_PX, ry + rh), _u32(HIGHLIGHT)
            )
        chosen = index == view.chosen
        th = measure.size(view.options[index])[1]
        text_x = rx + combo_pad_x()
        text_y = ry + (rh - th) // 2
        if chosen:
            draw.add_text(_vec(text_x, text_y), _u32(HIGHLIGHT), _CHOSEN_MARK)
        mark_w = measure.size(_CHOSEN_MARK)[0]
        draw.add_text(
            _vec(text_x + mark_w, text_y),
            _u32(VALUE if lit or chosen else CHOICE_LIST_TEXT),
            view.options[index],
        )
    picked = hovered if imgui.is_mouse_clicked(0) and not just_opened else None
    # A resting pointer leaves a highlight moved by key alone.
    delta = imgui.get_io().mouse_delta
    moved = delta.x != 0.0 or delta.y != 0.0
    return ChoiceListPointer(
        hovered=hovered if moved else None, picked=picked, rows=rects
    )
