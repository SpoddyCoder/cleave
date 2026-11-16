"""The one icon button for ImGui hosts.

Every icon or arrow a press acts on (navigator twisties and toggles, the
inspector title arrows, row icons, steppers, the transport bar) draws here.
Callers pass the glyph, its colours and state, and the row's band; the box,
the hover wash, glyph placement, the pointer, and the tooltip are the same
everywhere. Geometry lives in ``icon_button``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from imgui_bundle import imgui

from cleave.viz.icon_button import Band, FRect, glyph_x, icon_box, ink_origin
from cleave.viz.imgui_theme import rgba
from cleave.viz.pointer_cursor import PointerShape, request_pointer
from cleave.viz.theme import NUDGE_HOVER_BG, NUDGE_HOVER_BG_ALPHA, NUDGE_HOVER_FG
from cleave.viz.tooltips import show_tooltip


# An RGB theme role, or a colour already resolved for ImGui.
Color = tuple[int, int, int] | imgui.ImVec4
# Hover text, or a callable that builds it only when hovered.
Tooltip = str | Callable[[], str] | None


@dataclass(frozen=True)
class IconButtonState:
    pressed: bool
    hovered: bool
    held: bool
    activated: bool
    released: bool


def glyph_drop(glyph: str) -> float:
    """Pixels to lower a merged icon so it centres on the capitals beside it."""
    font = imgui.get_font()
    icon = font.find_glyph(ord(glyph))
    cap = font.find_glyph(ord("A"))
    return float(round(((cap.y0 + cap.y1) - (icon.y0 + icon.y1)) * 0.5))


def glyph_ink(glyph: str) -> FRect:
    """Painted bounds of *glyph* in the current font, relative to its draw origin."""
    g = imgui.get_font().find_glyph(ord(glyph))
    return g.x0, g.y0, g.x1 - g.x0, g.y1 - g.y0


def _u32(color: Color) -> int:
    return imgui.get_color_u32(color if isinstance(color, imgui.ImVec4) else rgba(color))


def text_top(box: FRect) -> float:
    """Top of a text line centred in *box*, on a whole pixel."""
    return float(box[1] + round((box[3] - imgui.get_text_line_height()) * 0.5))


def paint_box(
    box: FRect,
    text: str,
    *,
    color: Color,
    hovered: bool = False,
    fill: tuple[int, int, int] | None = None,
    fill_alpha: float = 1.0,
    icon: bool = True,
) -> None:
    """Paint one button: its fill, the hover wash, then *text* centred.

    A hovered button with no fill draws its text in the hover colour. With
    *icon*, a single glyph centres by its ink, so its own padding never shifts
    it; text centres on its line, to stay level with the text beside it.
    """
    if fill is not None:
        paint_wash(box, fill, fill_alpha)
    if hovered:
        paint_wash(box)
    text_color = NUDGE_HOVER_FG if hovered and fill is None else color
    if icon and len(text) == 1:
        x, y = ink_origin(box, glyph_ink(text))
    else:
        x, y = glyph_x(box, imgui.calc_text_size(text).x), text_top(box)
    imgui.get_window_draw_list().add_text(imgui.ImVec2(x, y), _u32(text_color), text)


def paint_wash(
    box: FRect,
    color: tuple[int, int, int] = NUDGE_HOVER_BG,
    alpha: float = NUDGE_HOVER_BG_ALPHA / 255.0,
) -> None:
    """Fill *box*: the hover wash by default, or a lit button's colour.

    The box may run into the window padding, so only the window clips it.
    """
    draw = imgui.get_window_draw_list()
    x, y, w, h = box
    win_pos = imgui.get_window_pos()
    win_size = imgui.get_window_size()
    draw.push_clip_rect(
        win_pos, imgui.ImVec2(win_pos.x + win_size.x, win_pos.y + win_size.y), False
    )
    try:
        draw.add_rect_filled(
            imgui.ImVec2(x, y),
            imgui.ImVec2(x + w, y + h),
            imgui.get_color_u32(rgba(color, alpha)),
        )
    finally:
        draw.pop_clip_rect()


def box_button(
    item_id: str,
    box: FRect,
    *,
    enabled: bool = True,
    inert: bool = False,
    pointer: PointerShape = PointerShape.HAND,
    tooltip: Tooltip = None,
) -> IconButtonState:
    """Take hover and press over *box* without moving the layout cursor.

    The hit area is the whole box, so it matches the wash. A row selectable
    drawn first must allow overlap. A disabled button never reports hover;
    an inert one hovers but keeps the arrow pointer.
    """
    x, y, w, h = box
    rect = imgui.internal.ImRect(imgui.ImVec2(x, y), imgui.ImVec2(x + w, y + h))
    iid = imgui.get_id(item_id)
    if not imgui.internal.item_add(rect, iid):
        return IconButtonState(False, False, False, False, False)
    pressed, hovered, held = imgui.internal.button_behavior(rect, iid, False, False)
    if hovered and tooltip is not None:
        show_tooltip(tooltip() if callable(tooltip) else tooltip)
    live = hovered and enabled
    if live and not inert:
        request_pointer(pointer)
    return IconButtonState(
        pressed=pressed,
        hovered=live,
        held=held,
        activated=imgui.is_item_activated(),
        released=imgui.is_item_deactivated(),
    )


def icon_button(
    item_id: str,
    glyph: str,
    x: float,
    band: Band,
    *,
    color: Color,
    fill: tuple[int, int, int] | None = None,
    fill_alpha: float = 1.0,
    enabled: bool = True,
    inert: bool = False,
    pointer: PointerShape = PointerShape.HAND,
    tooltip: Tooltip = None,
) -> IconButtonState:
    """A square icon button on *band* with its left edge at *x*."""
    box = icon_box(x, band)
    state = box_button(
        item_id, box, enabled=enabled, inert=inert, pointer=pointer, tooltip=tooltip
    )
    paint_box(
        box, glyph, color=color, hovered=state.hovered, fill=fill, fill_alpha=fill_alpha
    )
    return state
