"""Shell column geometry for the live editor window.

Rects are ``(x, y, w, h)`` in top-left origin pixels. One layout is computed
per frame and shared by the shell host, overlay placement, and the compositor.
"""

from __future__ import annotations

from dataclasses import dataclass

from cleave.config_schema.editor import (
    DEFAULT_INSPECTOR_WIDTH,
    DEFAULT_NAVIGATOR_WIDTH,
    MIN_COLUMN_WIDTH,
)

Rect = tuple[int, int, int, int]

NAVIGATOR_WIDTH = DEFAULT_NAVIGATOR_WIDTH
INSPECTOR_WIDTH = DEFAULT_INSPECTOR_WIDTH
# Hit-rects ``splitter`` role. Centered on each column boundary.
SPLITTER_HIT_PX = 6


def clamp_column_widths(
    display_w: int,
    nav: int,
    insp: int,
    *,
    min_column: int,
    min_visualiser: int = 1,
    help_width: int = 0,
) -> tuple[int, int, int, int]:
    """Navigator, visualiser, inspector, and help widths that sum to *display_w*.

    *nav*, *insp*, and *help_width* are requested side widths. Help is closed
    at 0 and does not take a column floor. The visualiser stays at least
    *min_visualiser* when the display is that wide. Each open side stays at
    least *min_column* when every open side's minimum and the visualiser fit.
    A narrower display keeps every width non-negative and shrinks the requested
    sides in proportion.
    """
    display_w = max(0, int(display_w))
    if display_w <= 0:
        return (0, 0, 0, 0)
    nav = max(0, int(nav))
    insp = max(0, int(insp))
    help_w = max(0, int(help_width))
    min_column = max(0, int(min_column))
    min_visualiser = max(0, int(min_visualiser))
    if display_w <= min_visualiser:
        return (0, display_w, 0, 0)

    requested = [nav, insp]
    if help_w > 0:
        requested.append(help_w)
    if display_w < min_column * len(requested) + min_visualiser:
        sides = _proportional_sides(display_w, requested, min_visualiser)
    else:
        sides = _floored_sides(
            display_w, requested, min_column, min_visualiser
        )
    if help_w <= 0:
        nav_w, insp_w = sides
        help_out = 0
    else:
        nav_w, insp_w, help_out = sides
    viz_w = display_w - nav_w - insp_w - help_out
    return (nav_w, viz_w, insp_w, help_out)


def _proportional_sides(
    display_w: int,
    requested: list[int],
    min_visualiser: int,
) -> list[int]:
    remaining = display_w - min_visualiser
    total = sum(requested)
    if total <= 0:
        nav_w = remaining // 2
        return [nav_w, remaining - nav_w]
    widths = [remaining * width // total for width in requested[:-1]]
    widths.append(remaining - sum(widths))
    return widths


def _floored_sides(
    display_w: int,
    requested: list[int],
    min_column: int,
    min_visualiser: int,
) -> list[int]:
    floored = [max(width, min_column) for width in requested]
    if sum(floored) + min_visualiser <= display_w:
        return floored
    budget = display_w - min_visualiser
    extra = budget - min_column * len(floored)
    extras = [width - min_column for width in floored]
    extra_total = sum(extras)
    widths = [
        min_column + extra * extra_i // extra_total for extra_i in extras[:-1]
    ]
    widths.append(budget - sum(widths))
    return widths


def _column_widths(
    display_w: int,
    nav: int | None = None,
    insp: int | None = None,
    help_width: int | None = None,
) -> tuple[int, int, int, int]:
    """Resolve nominal or requested widths, then clamp them into *display_w*.

    Missing requests use the nominal navigator and inspector widths and no
    column floor, so callers that omit overrides keep the proportional
    narrow-window split. Help stays closed unless a positive width is requested.
    """
    help_request = 0 if help_width is None else help_width
    overridden = nav is not None or insp is not None or help_request > 0
    nav_w = DEFAULT_NAVIGATOR_WIDTH if nav is None else nav
    insp_w = DEFAULT_INSPECTOR_WIDTH if insp is None else insp
    floor = MIN_COLUMN_WIDTH if overridden else 0
    return clamp_column_widths(
        display_w,
        nav_w,
        insp_w,
        min_column=floor,
        help_width=help_request,
    )


def splitter_hit(
    layout: ShellLayout,
    x: float,
    y: float,
    *,
    hit_px: float = SPLITTER_HIT_PX,
) -> str | None:
    """``nav``, ``insp``, or ``help`` when (*x*, *y*) is in that hit zone.

    Each zone is *hit_px* wide, centered on the boundary, and only as tall as
    the columns. Help's zone exists only when that column has positive width.
    The hit-rects role is ``splitter``.
    """
    _origin_x, top, _width, height = layout.navigator
    if height <= 0 or hit_px <= 0 or y < top or y >= top + height:
        return None
    half = hit_px / 2.0
    zones = [("nav", float(layout.navigator[0] + layout.navigator[2]))]
    if layout.docked:
        zones.append(("insp", float(layout.inspector[0] + layout.inspector[2])))
    else:
        zones.append(("insp", float(layout.inspector[0])))
    if layout.help[2] > 0:
        if layout.docked:
            help_edge = float(layout.help[0] + layout.help[2])
        else:
            help_edge = float(layout.help[0])
        zones.append(("help", help_edge))
    best: str | None = None
    best_dist: float | None = None
    for name, edge in zones:
        if (edge - half) <= x < (edge + half):
            dist = abs(x - edge)
            if best_dist is None or dist < best_dist:
                best = name
                best_dist = dist
    return best


def splitter_request_width(layout: ShellLayout, which: str, pointer_x: float) -> int:
    """Unclamped column width *pointer_x* is asking for.

    ``nav`` grows as the pointer moves right. In split mode ``insp`` and
    ``help`` grow as the pointer moves left; in docked mode both grow
    rightward. ``help`` changes only the help column.
    """
    if which == "nav":
        width = pointer_x - float(layout.navigator[0])
    elif which == "help":
        if layout.docked:
            width = pointer_x - float(layout.help[0])
        else:
            right = layout.help[0] + layout.help[2]
            width = float(right) - pointer_x
    elif layout.docked:
        width = pointer_x - float(layout.inspector[0])
    else:
        right = layout.inspector[0] + layout.inspector[2]
        width = float(right) - pointer_x
    return max(0, int(round(width)))


@dataclass(frozen=True)
class ShellLayout:
    menu: Rect
    transport: Rect
    navigator: Rect
    visualiser: Rect
    inspector: Rect
    help: Rect
    timeline: Rect
    docked: bool = False

    @staticmethod
    def compute(
        display_w: int,
        display_h: int,
        menu_h: int,
        transport_h: int,
        timeline_h: int,
        nav_width: int | None = None,
        insp_width: int | None = None,
        help_width: int | None = None,
        *,
        docked: bool = False,
    ) -> ShellLayout:
        """Column rects for one frame.

        *nav_width* and *insp_width* replace the nominal 230 and 495. None
        keeps that nominal width. *help_width* None or 0 leaves the help
        column closed. Requests are clamped into this layout and are not
        written back.
        """
        display_w = max(0, int(display_w))
        display_h = max(0, int(display_h))
        menu_h = max(0, int(menu_h))
        transport_h = max(0, int(transport_h))
        timeline_h = max(0, int(timeline_h))
        if timeline_h > display_h:
            timeline_h = display_h

        columns_y = menu_h + transport_h
        columns_h = max(0, display_h - columns_y - timeline_h)
        nav_w, viz_w, insp_w, help_w = _column_widths(
            display_w, nav_width, insp_width, help_width
        )

        if timeline_h > 0:
            timeline = (0, display_h - timeline_h, display_w, timeline_h)
        else:
            timeline = (0, display_h, display_w, 0)

        if docked:
            navigator = (0, columns_y, nav_w, columns_h)
            inspector = (nav_w, columns_y, insp_w, columns_h)
            help_rect = (nav_w + insp_w, columns_y, help_w, columns_h)
            visualiser = (nav_w + insp_w + help_w, columns_y, viz_w, columns_h)
        else:
            navigator = (0, columns_y, nav_w, columns_h)
            visualiser = (nav_w, columns_y, viz_w, columns_h)
            inspector = (nav_w + viz_w, columns_y, insp_w, columns_h)
            help_rect = (nav_w + viz_w + insp_w, columns_y, help_w, columns_h)

        return ShellLayout(
            menu=(0, 0, display_w, menu_h),
            transport=(0, menu_h, display_w, transport_h),
            navigator=navigator,
            visualiser=visualiser,
            inspector=inspector,
            help=help_rect,
            timeline=timeline,
            docked=docked,
        )
