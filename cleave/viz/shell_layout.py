"""Shell column geometry for the live editor window.

Rects are ``(x, y, w, h)`` in top-left origin pixels. One layout is computed
per frame and shared by the shell host, overlay placement, and the compositor.

The navigator and the inspector share one side column. The navigator is the
top of that column. It fits its rows until the user drags the boundary, then
keeps that height. The inspector is the remainder.
Help is its own full-height column. Each column chooses left or right. When
they share a side, help sits at the window edge and the navigator column
stays against the visualiser.
"""

from __future__ import annotations

from dataclasses import dataclass

from cleave.config_schema.editor import (
    DEFAULT_HELP_SIDE,
    DEFAULT_INSPECTOR_WIDTH,
    DEFAULT_NAVIGATOR_SIDE,
    MIN_COLUMN_WIDTH,
    ColumnSide,
)
from cleave.viz.theme import tuning_ui_metrics

Rect = tuple[int, int, int, int]

INSPECTOR_WIDTH = DEFAULT_INSPECTOR_WIDTH
# Same extra frame padding as the menu bar, so an unmeasured navigator is one
# text row tall and can be measured on the next frame.
_NAV_ROW_FRAME_PAD_Y = 8.0
# Hit-rects ``splitter`` role. Centered on each column boundary.
SPLITTER_HIT_PX = 6


def navigator_row_px() -> int:
    """One navigator row when the list height is not yet measured."""
    font_size = float(tuning_ui_metrics().font_size)
    return max(1, int(round(font_size + _NAV_ROW_FRAME_PAD_Y * 2.0)))


def clamp_column_widths(
    display_w: int,
    stack: int,
    *,
    min_column: int,
    min_visualiser: int = 1,
    help_width: int = 0,
) -> tuple[int, int, int]:
    """Stack, visualiser, and help widths that sum to *display_w*.

    *stack* and *help_width* are requested side widths. Help is closed at 0
    and does not take a column floor. The visualiser stays at least
    *min_visualiser* when the display is that wide. Each open side stays at
    least *min_column* when every open side's minimum and the visualiser fit.
    A narrower display keeps every width non-negative and shrinks the requested
    sides in proportion.
    """
    display_w = max(0, int(display_w))
    if display_w <= 0:
        return (0, 0, 0)
    stack_w = max(0, int(stack))
    help_w = max(0, int(help_width))
    min_column = max(0, int(min_column))
    min_visualiser = max(0, int(min_visualiser))
    if display_w <= min_visualiser:
        return (0, display_w, 0)

    requested = [stack_w]
    if help_w > 0:
        requested.append(help_w)
    if display_w < min_column * len(requested) + min_visualiser:
        sides = _proportional_sides(display_w, requested, min_visualiser)
    else:
        sides = _floored_sides(
            display_w, requested, min_column, min_visualiser
        )
    if help_w <= 0:
        stack_out = sides[0]
        help_out = 0
    else:
        stack_out, help_out = sides
    viz_w = display_w - stack_out - help_out
    return (stack_out, viz_w, help_out)


def _proportional_sides(
    display_w: int,
    requested: list[int],
    min_visualiser: int,
) -> list[int]:
    remaining = display_w - min_visualiser
    total = sum(requested)
    if not requested or total <= 0:
        return [0] * len(requested)
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
    if extra_total <= 0:
        return [0] * len(requested)
    widths = [
        min_column + extra * extra_i // extra_total for extra_i in extras[:-1]
    ]
    widths.append(budget - sum(widths))
    return widths


def _column_widths(
    display_w: int,
    insp: int | None = None,
    help_width: int | None = None,
) -> tuple[int, int, int]:
    """Resolve nominal or requested widths, then clamp them into *display_w*.

    A missing inspector request uses the nominal stack width and no column
    floor, so callers that omit overrides keep the proportional narrow-window
    widths. Help stays closed unless a positive width is requested.
    """
    help_request = 0 if help_width is None else help_width
    overridden = insp is not None or help_request > 0
    stack_w = DEFAULT_INSPECTOR_WIDTH if insp is None else insp
    floor = MIN_COLUMN_WIDTH if overridden else 0
    return clamp_column_widths(
        display_w,
        stack_w,
        min_column=floor,
        help_width=help_request,
    )


def _stack_heights(
    columns_h: int,
    nav_content_h: int | None,
    navigator_height: int | None = None,
) -> tuple[int, int]:
    """Navigator and inspector heights that sum to the column band.

    A positive *navigator_height* is the user's split. It is clamped so each
    side keeps at least one row. Otherwise the navigator fits its rows: a
    missing or non-positive content height is one row, so the first frame can
    be measured, and the inspector keeps at least half the band. A band
    shorter than two rows gives the navigator one row and the inspector the
    rest. A taller tree scrolls inside the navigator window.
    """
    columns_h = max(0, int(columns_h))
    if columns_h <= 0:
        return (0, 0)
    row = navigator_row_px()
    if columns_h >= row * 2 and navigator_height is not None and navigator_height > 0:
        nav_h = max(row, min(int(navigator_height), columns_h - row))
        return (nav_h, columns_h - nav_h)
    if nav_content_h is None or int(nav_content_h) <= 0:
        requested = row
    else:
        requested = int(nav_content_h)
    if columns_h < row * 2:
        nav_h = min(row, columns_h)
        return (nav_h, columns_h - nav_h)
    nav_h = min(requested, columns_h // 2)
    return (nav_h, columns_h - nav_h)


def splitter_hit(
    layout: ShellLayout,
    x: float,
    y: float,
    *,
    hit_px: float = SPLITTER_HIT_PX,
) -> str | None:
    """``insp``, ``help``, or ``nav`` when (*x*, *y*) is in that hit zone.

    Each zone is *hit_px* across, centered on its boundary. ``insp`` and
    ``help`` are vertical boundaries only as tall as the column band. ``insp``
    resizes the shared stack. Help's zone exists only when that column has
    positive width. The stack zone exists only when the stack has positive
    width. ``nav`` is the horizontal navigator/inspector boundary, only as
    wide as the stack, and exists only when the inspector has positive
    height. The nearest boundary wins. The hit-rects role is ``splitter``.
    """
    top = layout.visualiser[1]
    height = layout.visualiser[3]
    if height <= 0 or hit_px <= 0 or y < top or y >= top + height:
        return None
    half = hit_px / 2.0
    zones: list[tuple[str, float, float]] = []
    stack_x, _stack_y, stack_w, _nav_h = layout.navigator
    if stack_w > 0:
        zones.append(
            ("insp", _inner_edge(layout.navigator, layout.navigator_side), x)
        )
        if layout.inspector[3] > 0 and stack_x <= x < stack_x + stack_w:
            zones.append(("nav", float(layout.inspector[1]), y))
    if layout.help[2] > 0:
        zones.append(("help", _inner_edge(layout.help, layout.help_side), x))
    best: str | None = None
    best_dist: float | None = None
    for name, edge, coord in zones:
        if (edge - half) <= coord < (edge + half):
            dist = abs(coord - edge)
            if best_dist is None or dist < best_dist:
                best = name
                best_dist = dist
    return best


def _inner_edge(rect: Rect, side: ColumnSide) -> float:
    """Edge of *rect* that faces the visualiser."""
    if side == "left":
        return float(rect[0] + rect[2])
    return float(rect[0])


def splitter_request_width(layout: ShellLayout, which: str, pointer_x: float) -> int:
    """Unclamped column width *pointer_x* is asking for.

    A column on the left grows as the pointer moves right. A column on the
    right grows as the pointer moves left. ``insp`` is the navigator column.
    ``help`` changes only the help column.
    """
    if which == "help":
        rect = layout.help
        side = layout.help_side
    elif which == "insp":
        rect = layout.inspector
        side = layout.navigator_side
    else:
        return 0
    if side == "left":
        width = pointer_x - float(rect[0])
    else:
        right = rect[0] + rect[2]
        width = float(right) - pointer_x
    return max(0, int(round(width)))


def splitter_request_height(layout: ShellLayout, pointer_y: float) -> int:
    """Unclamped navigator height *pointer_y* is asking for (``nav`` splitter)."""
    return max(0, int(round(pointer_y - float(layout.navigator[1]))))


@dataclass(frozen=True)
class ShellLayout:
    menu: Rect
    transport: Rect
    navigator: Rect
    visualiser: Rect
    inspector: Rect
    help: Rect
    timeline: Rect
    navigator_side: ColumnSide = DEFAULT_NAVIGATOR_SIDE
    help_side: ColumnSide = DEFAULT_HELP_SIDE

    @staticmethod
    def compute(
        display_w: int,
        display_h: int,
        menu_h: int,
        transport_h: int,
        timeline_h: int,
        insp_width: int | None = None,
        help_width: int | None = None,
        nav_content_h: int | None = None,
        navigator_height: int | None = None,
        *,
        navigator_side: ColumnSide = DEFAULT_NAVIGATOR_SIDE,
        help_side: ColumnSide = DEFAULT_HELP_SIDE,
    ) -> ShellLayout:
        """Column rects for one frame.

        The navigator column is *insp_width* wide (nominal 495 when omitted).
        The navigator is the top of that column. A positive
        *navigator_height* sets it, clamped so each side keeps one row.
        Otherwise it is *nav_content_h* tall after the half-band clamp, and
        None or a non-positive height is one row. The inspector is the rest
        of the column. *help_width* None or 0 leaves
        the help column closed. Requests are clamped into this layout and
        are not written back.

        *navigator_side* and *help_side* place those columns. The default
        puts the navigator column on the left and help on the right. When
        they share a side, help is at the window edge.
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
        stack_w, viz_w, help_w = _column_widths(
            display_w, insp_width, help_width
        )
        nav_h, insp_h = _stack_heights(
            columns_h, nav_content_h, navigator_height
        )

        if timeline_h > 0:
            timeline = (0, display_h - timeline_h, display_w, timeline_h)
        else:
            timeline = (0, display_h, display_w, 0)

        left: list[tuple[str, int]] = []
        right: list[tuple[str, int]] = []
        if help_side == "left":
            left.append(("help", help_w))
        if navigator_side == "left":
            left.append(("stack", stack_w))
        else:
            right.append(("stack", stack_w))
        if help_side == "right":
            right.append(("help", help_w))

        placed: dict[str, tuple[int, int]] = {}
        x = 0
        for name, width in (*left, ("viz", viz_w), *right):
            placed[name] = (x, width)
            x += width
        stack_x, _stack_placed = placed["stack"]
        viz_x, _viz_placed = placed["viz"]
        help_x, _help_placed = placed["help"]
        navigator = (stack_x, columns_y, stack_w, nav_h)
        inspector = (stack_x, columns_y + nav_h, stack_w, insp_h)
        visualiser = (viz_x, columns_y, viz_w, columns_h)
        help_rect = (help_x, columns_y, help_w, columns_h)

        return ShellLayout(
            menu=(0, 0, display_w, menu_h),
            transport=(0, menu_h, display_w, transport_h),
            navigator=navigator,
            visualiser=visualiser,
            inspector=inspector,
            help=help_rect,
            timeline=timeline,
            navigator_side=navigator_side,
            help_side=help_side,
        )
