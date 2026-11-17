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
from cleave.viz.theme import palette

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


def _tone_colours(tone: ButtonTone) -> tuple[RGB, RGB | None, RGB, RGB, RGB]:
    """Rest fill, rest border, hover fill, hover border, and pressed fill."""
    p = palette()
    if tone is ButtonTone.PRIMARY:
        return (
            p.button_primary_bg,
            None,
            p.button_primary_hover_bg,
            p.button_primary_hover_border,
            p.button_primary_active_bg,
        )
    if tone is ButtonTone.DANGER:
        return (
            p.button_danger_bg,
            None,
            p.button_danger_hover_bg,
            p.button_danger_hover_border,
            p.button_danger_active_bg,
        )
    off = tone is ButtonTone.OFF
    return (
        p.button_off_bg if off else p.button_bg,
        p.button_off_border if off else p.button_border,
        p.button_hover_bg,
        p.button_hover_border,
        p.button_active_bg,
    )


def button_look(
    tone: ButtonTone, state: ButtonState, *, fill: RGB | None = None
) -> ButtonLook:
    """Gradient, border, and glow for a button of *tone* in *state*.

    *fill* replaces the rest fill (a dimmed chosen segment); its border is a
    lighter shade of it. A pressed button sinks: the shade moves to the top.
    """
    rest, rest_border, hover, hover_border, pressed = _tone_colours(tone)
    sheen, shade = palette().button_sheen, palette().button_shade
    if state is ButtonState.REST:
        base = rest if fill is None else fill
        border = rest_border if fill is None and rest_border else lighten(base, 0.18)
        return ButtonLook(lighten(base, sheen), darken(base, shade * 0.5), border)
    glow = None if tone in (ButtonTone.PLAIN, ButtonTone.OFF) else hover
    if state is ButtonState.PRESSED:
        return ButtonLook(darken(pressed, shade), pressed, hover_border, glow)
    return ButtonLook(lighten(hover, sheen), darken(hover, shade), hover_border, glow)


def _u32(rgb: RGB, alpha: float = 1.0) -> int:
    return int(imgui.get_color_u32(rgba(rgb, alpha)))


def paint_look(draw: imgui.ImDrawList, rect: Rect, look: ButtonLook) -> None:
    """Paint *look* over *rect*: glow, gradient, then border."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    if look.glow is not None:
        glow_alpha = palette().button_glow_alpha
        for ring, alpha in ((1.0, glow_alpha), (2.0, glow_alpha * 0.45)):
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
