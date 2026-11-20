"""Breadcrumb paths that fit a width, shared by the preset browser and the inspector.

Pure layout: the caller measures text and draws. Parents that do not fit fold
into one :data:`CRUMB_ELLIPSIS` crumb that goes to the nearest of them, so
every crumb shown stays clickable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

CRUMB_SEPARATOR = " / "

TextWidth = Callable[[str], int]
FitLabel = Callable[[str, int], str]
CRUMB_ELLIPSIS = "…"


@dataclass(frozen=True)
class CrumbSlot:
    """One drawn breadcrumb: the crumb a click goes to, its text, and its span."""

    index: int
    text: str
    x: int
    width: int


def _slots(
    pieces: list[tuple[int, str]], text_width: TextWidth
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
    text_width: TextWidth,
    fit_label: FitLabel,
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
