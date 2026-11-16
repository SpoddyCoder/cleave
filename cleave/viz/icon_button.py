"""Geometry for every icon button in the shell.

One rule for the navigator, the inspector, dialogs, the transport bar, and the
timeline strip: a button's box is as tall as its row's highlight band, an
icon's box is square, and the glyph sits centred in it. Callers choose the
glyph, colours, and state; they never size or place a box themselves.

Pure geometry, so the ImGui hosts, the pygame strip, and tests share it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from cleave.viz.theme import ui_chrome_px

# Top and bottom y of a row's highlight band.
Band = tuple[float, float]
# x, y, width, height.
FRect = tuple[float, float, float, float]

# Gap between neighbouring icon buttons, so lit fills read apart. Base pixels
# at a shell scale of 1.0.
ICON_GAP_PX = 2.0


def icon_gap() -> float:
    """Gap between neighbouring icon boxes at the live UI scale."""
    return float(round(ui_chrome_px(ICON_GAP_PX)))


def band_side(band: Band) -> float:
    """Side of an icon box on *band*: the band's height."""
    return band[1] - band[0]


def icon_box(x: float, band: Band) -> FRect:
    """Square box with its left edge at *x* and the band's top and bottom."""
    return float(round(x)), band[0], band_side(band), band_side(band)


def text_box(x: float, text_w: float, space_w: float, band: Band) -> FRect:
    """Box for a text glyph or label: the text plus a space, the band tall.

    *x* is where the text's box starts; the text sits centred in it.
    """
    return float(round(x)), band[0], text_w + space_w, band_side(band)


def glyph_x(box: FRect, glyph_w: float) -> float:
    """Left of a glyph *glyph_w* wide, centred in *box*, on a whole pixel.

    An odd spare pixel goes to the right margin, as in ``ink_origin``.
    """
    return float(box[0] + math.floor((box[2] - glyph_w) * 0.5))


def ink_origin(box: FRect, ink: FRect) -> tuple[float, float]:
    """Where to draw a glyph so its ink sits centred in *box*.

    *ink* is the painted bounds ``(x, y, w, h)`` relative to the glyph's draw
    origin, so a glyph's own uneven padding never shifts it. The ink lands on
    whole pixels; an odd spare pixel goes to the right and bottom margins.
    """
    bx, by, bw, bh = box
    ix, iy, iw, ih = ink
    return bx + math.floor((bw - iw) * 0.5) - ix, by + math.floor((bh - ih) * 0.5) - iy


def icon_columns(
    right_x: float, count: int, side: float, gap: float
) -> tuple[float, ...]:
    """Left edges of *count* icon columns ending flush at *right_x*, in order."""
    start = right_x - count * side - max(0, count - 1) * gap
    return tuple(start + index * (side + gap) for index in range(count))


def icon_row(
    left_x: float, count: int, side: float, gap: float
) -> tuple[float, ...]:
    """Left edges of *count* icon columns from *left_x*, left to right."""
    return tuple(left_x + index * (side + gap) for index in range(count))


def box_contains(box: FRect, x: float, y: float) -> bool:
    bx, by, bw, bh = box
    return bx <= x < bx + bw and by <= y < by + bh


def box_index_at(boxes: Sequence[FRect], x: float, y: float) -> int | None:
    """Index of the box under the point, or None."""
    for index, box in enumerate(boxes):
        if box_contains(box, x, y):
            return index
    return None
