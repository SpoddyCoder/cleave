"""How every list row looks under the pointer, selected, focused, and lit.

One look for navigator and inspector rows, dialog form rows, file picker rows
and shortcuts, menu and context menu rows, the open choice list, and the
timeline strip's focused row:

- HOVER: a flat violet wash, the pointer's hue (as on buttons and icons).
- SELECTED: a blue band fading left to right, with a blue marker bar on its
  left edge. The current navigator page, or a chosen row whose list does not
  hold the keys.
- FOCUSED: a stronger band, a bright marker bar, and a 1px blue edge. The row
  the keys act on.
- LIT: the plain button hover gradient with a yellow marker bar. The
  highlighted row of an open menu or choice list.

``row_look`` is pure colour; ``paint_row`` draws it with ImGui and
``row_band`` paints it under a selectable whose text ImGui draws itself.
ImGui loads on draw, not at import, so the pygame timeline strip (on the
frozen play path) can share the look without pulling in ImGui.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from cleave.viz.theme import ROW_BAR_PX, palette, ui_chrome_px

if TYPE_CHECKING:
    from imgui_bundle import imgui

RGB = tuple[int, int, int]
RGBA = tuple[RGB, float]
Rect = tuple[float, float, float, float]


class RowState(Enum):
    HOVER = auto()
    SELECTED = auto()
    FOCUSED = auto()
    LIT = auto()


@dataclass(frozen=True)
class RowLook:
    """A row's band from *start* to *end* (left to right, or top to bottom when
    *vertical*), an optional 1px *edge*, and an optional left marker *bar*."""

    start: RGBA
    end: RGBA
    vertical: bool = False
    edge: RGB | None = None
    bar: RGB | None = None


def row_look(state: RowState, *, bar: bool = True) -> RowLook:
    """Band, edge, and marker bar for a row in *state*. *bar* False drops the bar."""
    if state is RowState.HOVER:
        wash = (palette().hover, palette().hover_bg_alpha / 255.0)
        return RowLook(wash, wash)
    if state is RowState.LIT:
        from cleave.viz.button_paint import ButtonState, ButtonTone, button_look

        lit = button_look(ButtonTone.PLAIN, ButtonState.HOVER)
        return RowLook(
            (lit.top, 1.0),
            (lit.bottom, 1.0),
            vertical=True,
            bar=palette().highlight if bar else None,
        )
    if state is RowState.SELECTED:
        left, right = palette().row_selected_alpha
        return RowLook(
            (palette().row_select_tint, left),
            (palette().row_select_tint, right),
            bar=palette().row_selected_bar if bar else None,
        )
    left, right = palette().row_focused_alpha
    return RowLook(
        (palette().row_select_tint, left),
        (palette().row_select_tint, right),
        edge=palette().row_focus_edge,
        bar=palette().row_focused_bar if bar else None,
    )


def row_bar_px() -> float:
    """Marker bar width at the live UI scale, in whole pixels."""
    return float(max(1, round(ui_chrome_px(ROW_BAR_PX))))


def _u32(color: RGBA) -> int:
    from imgui_bundle import imgui

    from cleave.viz.imgui_theme import rgba

    return int(imgui.get_color_u32(rgba(color[0], color[1])))


def paint_look(draw: imgui.ImDrawList, rect: Rect, look: RowLook) -> None:
    """Paint *look* over *rect*: band, marker bar, then edge."""
    from imgui_bundle import imgui

    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    start, end = _u32(look.start), _u32(look.end)
    lo, hi = imgui.ImVec2(x, y), imgui.ImVec2(x + w, y + h)
    if look.start == look.end:
        draw.add_rect_filled(lo, hi, start)
    elif look.vertical:
        draw.add_rect_filled_multi_color(lo, hi, start, start, end, end)
    else:
        draw.add_rect_filled_multi_color(lo, hi, start, end, end, start)
    if look.bar is not None:
        draw.add_rect_filled(
            lo, imgui.ImVec2(x + min(w, row_bar_px()), y + h), _u32((look.bar, 1.0))
        )
    if look.edge is not None:
        draw.add_rect(lo, hi, _u32((look.edge, 1.0)))


def paint_row(
    draw: imgui.ImDrawList, rect: Rect, state: RowState, *, bar: bool = True
) -> None:
    """One row's background in *state*."""
    paint_look(draw, rect, row_look(state, bar=bar))


@contextmanager
def row_band(
    state: RowState | None, *, bar: bool = True
) -> Iterator[Callable[[float], None]]:
    """Paint *state*'s look under the selectable drawn inside, then restore.

    ImGui draws a selectable's text with its fill, so the band goes on a lower
    draw channel. Call the yielded function right after the selectable with
    the band's left x; the band runs from there to the item's right edge over
    the item's height. With *state* None the selectable keeps the theme's own
    fill (the hover wash) and the function does nothing.
    """
    if state is None:
        yield lambda _left: None
        return
    from imgui_bundle import imgui

    slots = (imgui.Col_.header, imgui.Col_.header_hovered, imgui.Col_.header_active)
    draw = imgui.get_window_draw_list()
    draw.channels_split(2)
    draw.channels_set_current(1)
    for slot in slots:
        imgui.push_style_color(slot, imgui.ImVec4(0.0, 0.0, 0.0, 0.0))
    marked: list[Rect] = []

    def mark(left: float) -> None:
        rect_min = imgui.get_item_rect_min()
        rect_max = imgui.get_item_rect_max()
        marked.append((left, rect_min.y, rect_max.x - left, rect_max.y - rect_min.y))

    try:
        yield mark
    finally:
        imgui.pop_style_color(len(slots))
        draw.channels_set_current(0)
        for rect in marked[-1:]:
            paint_row(draw, rect, state, bar=bar)
        draw.channels_merge()
