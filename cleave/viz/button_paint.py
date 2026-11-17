"""How every framed shell button looks, at rest, under the pointer, and held.

One look for panel buttons, dialog buttons, segments, and combo boxes: a
vertical gradient (a sheen on top, a shade underneath), a 1px border, and for a
lit primary or danger button a soft outer glow in its own hue. A plain button
lights electric violet under the pointer; primary and danger brighten in their
own blue and red. OFF is a control on a switched-off or locked page, or one
that refuses a press: darker and recessed at rest so its text stays readable,
and lit like a plain button under the pointer. ``button_look`` is pure colour; ``paint_button`` draws it
with ImGui.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from imgui_bundle import imgui

from cleave.viz.imgui_theme import darken, lighten, rgba
from cleave.viz.theme import (
    BUTTON_ACTIVE_BG,
    BUTTON_BG,
    BUTTON_BORDER,
    BUTTON_DANGER_ACTIVE_BG,
    BUTTON_DANGER_BG,
    BUTTON_DANGER_HOVER_BG,
    BUTTON_DANGER_HOVER_BORDER,
    BUTTON_GLOW_ALPHA,
    BUTTON_HOVER_BG,
    BUTTON_HOVER_BORDER,
    BUTTON_OFF_BG,
    BUTTON_OFF_BORDER,
    BUTTON_PRIMARY_ACTIVE_BG,
    BUTTON_PRIMARY_BG,
    BUTTON_PRIMARY_HOVER_BG,
    BUTTON_PRIMARY_HOVER_BORDER,
    BUTTON_SHADE,
    BUTTON_SHEEN,
)

RGB = tuple[int, int, int]
Rect = tuple[float, float, float, float]


class ButtonTone(Enum):
    PLAIN = auto()
    PRIMARY = auto()
    DANGER = auto()
    OFF = auto()


class ButtonState(Enum):
    REST = auto()
    HOVER = auto()
    PRESSED = auto()


@dataclass(frozen=True)
class ButtonLook:
    top: RGB
    bottom: RGB
    border: RGB
    glow: RGB | None = None


# Rest fill, rest border, hover fill, hover border, pressed fill.
_TONES: dict[ButtonTone, tuple[RGB, RGB | None, RGB, RGB, RGB]] = {
    ButtonTone.PLAIN: (
        BUTTON_BG,
        BUTTON_BORDER,
        BUTTON_HOVER_BG,
        BUTTON_HOVER_BORDER,
        BUTTON_ACTIVE_BG,
    ),
    ButtonTone.OFF: (
        BUTTON_OFF_BG,
        BUTTON_OFF_BORDER,
        BUTTON_HOVER_BG,
        BUTTON_HOVER_BORDER,
        BUTTON_ACTIVE_BG,
    ),
    ButtonTone.PRIMARY: (
        BUTTON_PRIMARY_BG,
        None,
        BUTTON_PRIMARY_HOVER_BG,
        BUTTON_PRIMARY_HOVER_BORDER,
        BUTTON_PRIMARY_ACTIVE_BG,
    ),
    ButtonTone.DANGER: (
        BUTTON_DANGER_BG,
        None,
        BUTTON_DANGER_HOVER_BG,
        BUTTON_DANGER_HOVER_BORDER,
        BUTTON_DANGER_ACTIVE_BG,
    ),
}


def button_look(
    tone: ButtonTone, state: ButtonState, *, fill: RGB | None = None
) -> ButtonLook:
    """Gradient, border, and glow for a button of *tone* in *state*.

    *fill* replaces the rest fill (a dimmed chosen segment); its border is a
    lighter shade of it. A pressed button sinks: the shade moves to the top.
    """
    rest, rest_border, hover, hover_border, pressed = _TONES[tone]
    if state is ButtonState.REST:
        base = rest if fill is None else fill
        border = rest_border if fill is None and rest_border else lighten(base, 0.18)
        return ButtonLook(
            lighten(base, BUTTON_SHEEN), darken(base, BUTTON_SHADE * 0.5), border
        )
    glow = None if tone in (ButtonTone.PLAIN, ButtonTone.OFF) else hover
    if state is ButtonState.PRESSED:
        return ButtonLook(darken(pressed, BUTTON_SHADE), pressed, hover_border, glow)
    return ButtonLook(lighten(hover, BUTTON_SHEEN), darken(hover, BUTTON_SHADE), hover_border, glow)


def _u32(rgb: RGB, alpha: float = 1.0) -> int:
    return int(imgui.get_color_u32(rgba(rgb, alpha)))


def paint_look(draw: imgui.ImDrawList, rect: Rect, look: ButtonLook) -> None:
    """Paint *look* over *rect*: glow, gradient, then border."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    if look.glow is not None:
        for ring, alpha in ((1.0, BUTTON_GLOW_ALPHA), (2.0, BUTTON_GLOW_ALPHA * 0.45)):
            draw.add_rect(
                imgui.ImVec2(x - ring, y - ring),
                imgui.ImVec2(x + w + ring, y + h + ring),
                _u32(look.glow, alpha),
            )
    top, bottom = _u32(look.top), _u32(look.bottom)
    draw.add_rect_filled_multi_color(
        imgui.ImVec2(x, y), imgui.ImVec2(x + w, y + h), top, top, bottom, bottom
    )
    draw.add_rect(imgui.ImVec2(x, y), imgui.ImVec2(x + w, y + h), _u32(look.border))


def paint_button(
    draw: imgui.ImDrawList,
    rect: Rect,
    tone: ButtonTone,
    state: ButtonState,
    *,
    fill: RGB | None = None,
) -> None:
    """One framed button's background in *tone* and *state*."""
    paint_look(draw, rect, button_look(tone, state, fill=fill))
