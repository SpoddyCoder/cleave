"""Shell column geometry for the live editor window.

Rects are ``(x, y, w, h)`` in top-left origin pixels. One layout is computed
per frame and shared by the shell host, overlay placement, and the compositor.

The navigator and the inspector share one side stack. The navigator is the
top of that stack, only as tall as its rows. The inspector is the remainder.
Help is a full-height column beside the stack.
"""

from __future__ import annotations

from dataclasses import dataclass

from cleave.config_schema.editor import (
    DEFAULT_INSPECTOR_WIDTH,
    MIN_COLUMN_WIDTH,
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
    split. Help stays closed unless a positive width is requested.
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


def _stack_heights(columns_h: int, nav_content_h: int | None) -> tuple[int, int]:
    """Navigator and inspector heights that sum to the column band.

    A missing or non-positive content height is one row, so the first frame
    can be measured. The inspector keeps at least half the band. A band
    shorter than two rows gives the navigator one row and the inspector the
    rest. A taller tree scrolls inside the navigator window.
    """
    columns_h = max(0, int(columns_h))
    if columns_h <= 0:
        return (0, 0)
    row = navigator_row_px()
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
    """``insp`` or ``help`` when (*x*, *y*) is in that hit zone.

    Each zone is *hit_px* wide, centered on the boundary, and only as tall as
    the column band. ``insp`` resizes the shared stack. Help's zone exists
    only when that column has positive width. The stack zone exists only when
    the stack has positive width. The navigator/inspector boundary is not a
    splitter. The hit-rects role is ``splitter``.
    """
    top = layout.visualiser[1]
    height = layout.visualiser[3]
    if height <= 0 or hit_px <= 0 or y < top or y >= top + height:
        return None
    half = hit_px / 2.0
    zones: list[tuple[str, float]] = []
    stack_w = layout.navigator[2]
    if stack_w > 0:
        if layout.docked:
            zones.append(("insp", float(layout.navigator[0] + stack_w)))
        else:
            zones.append(("insp", float(layout.navigator[0])))
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

    In split mode ``insp`` and ``help`` grow as the pointer moves left; in
    docked mode both grow rightward. ``insp`` is the shared stack.
    ``help`` changes only the help column.
    """
    if which == "help":
        if layout.docked:
            width = pointer_x - float(layout.help[0])
        else:
            right = layout.help[0] + layout.help[2]
            width = float(right) - pointer_x
    elif which == "insp":
        if layout.docked:
            width = pointer_x - float(layout.inspector[0])
        else:
            right = layout.inspector[0] + layout.inspector[2]
            width = float(right) - pointer_x
    else:
        return 0
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
        insp_width: int | None = None,
        help_width: int | None = None,
        nav_content_h: int | None = None,
        *,
        docked: bool = False,
    ) -> ShellLayout:
        """Column rects for one frame.

        The stack is *insp_width* wide (nominal 495 when omitted). The
        navigator is the top of that stack, *nav_content_h* tall after the
        half-band clamp. None or a non-positive height is one row. The
        inspector is the rest of the stack. *help_width* None or 0 leaves
        the help column closed. Requests are clamped into this layout and
        are not written back.

        Split places the visualiser, then the stack, then help. Docked
        places the stack, then help, then the visualiser.
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
        nav_h, insp_h = _stack_heights(columns_h, nav_content_h)

        if timeline_h > 0:
            timeline = (0, display_h - timeline_h, display_w, timeline_h)
        else:
            timeline = (0, display_h, display_w, 0)

        if docked:
            navigator = (0, columns_y, stack_w, nav_h)
            inspector = (0, columns_y + nav_h, stack_w, insp_h)
            help_rect = (stack_w, columns_y, help_w, columns_h)
            visualiser = (stack_w + help_w, columns_y, viz_w, columns_h)
        else:
            visualiser = (0, columns_y, viz_w, columns_h)
            stack_x = viz_w
            navigator = (stack_x, columns_y, stack_w, nav_h)
            inspector = (stack_x, columns_y + nav_h, stack_w, insp_h)
            help_rect = (stack_x + stack_w, columns_y, help_w, columns_h)

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
