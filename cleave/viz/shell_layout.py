"""Shell column geometry for the live editor window.

Rects are ``(x, y, w, h)`` in top-left origin pixels. One layout is computed
per frame and shared by the shell host, overlay placement, and the compositor.
"""

from __future__ import annotations

from dataclasses import dataclass

Rect = tuple[int, int, int, int]

NAVIGATOR_WIDTH = 230
# Half again the design mock's 330px column, so labels and stepped values fit.
INSPECTOR_WIDTH = 495
# Side columns stay at least this wide once the display can hold both of them
# and a 1px visualiser. A narrower window skips the floor.
MIN_COLUMN_WIDTH = 60
# Hit-rects ``splitter`` role. Centered on each column boundary.
SPLITTER_HIT_PX = 6


def clamp_column_widths(
    display_w: int,
    nav: int,
    insp: int,
    *,
    min_column: int,
    min_visualiser: int = 1,
) -> tuple[int, int, int]:
    """Navigator, visualiser, and inspector widths that sum to *display_w*.

    *nav* and *insp* are requested side widths. The visualiser stays at least
    *min_visualiser* when the display is that wide. Each side stays at least
    *min_column* when both minimums and the visualiser fit. A narrower display
    keeps every width non-negative and shrinks the requested sides in proportion.
    """
    display_w = max(0, int(display_w))
    if display_w <= 0:
        return (0, 0, 0)
    nav = max(0, int(nav))
    insp = max(0, int(insp))
    min_column = max(0, int(min_column))
    min_visualiser = max(0, int(min_visualiser))
    if display_w <= min_visualiser:
        return (0, display_w, 0)

    if display_w < min_column * 2 + min_visualiser:
        return _proportional_columns(display_w, nav, insp, min_visualiser)

    nav_w = max(nav, min_column)
    insp_w = max(insp, min_column)
    if nav_w + insp_w + min_visualiser <= display_w:
        return (nav_w, display_w - nav_w - insp_w, insp_w)

    budget = display_w - min_visualiser
    extra = budget - min_column * 2
    nav_extra = nav_w - min_column
    insp_extra = insp_w - min_column
    extra_total = nav_extra + insp_extra
    nav_share = extra * nav_extra // extra_total
    nav_out = min_column + nav_share
    insp_out = budget - nav_out
    return (nav_out, display_w - nav_out - insp_out, insp_out)


def _proportional_columns(
    display_w: int,
    nav: int,
    insp: int,
    min_visualiser: int,
) -> tuple[int, int, int]:
    remaining = display_w - min_visualiser
    total = nav + insp
    if total <= 0:
        nav_w = remaining // 2
        return (nav_w, min_visualiser, remaining - nav_w)
    nav_w = remaining * nav // total
    insp_w = remaining - nav_w
    return (nav_w, display_w - nav_w - insp_w, insp_w)


def _column_widths(
    display_w: int,
    nav: int | None = None,
    insp: int | None = None,
) -> tuple[int, int, int]:
    """Resolve nominal or requested widths, then clamp them into *display_w*.

    Missing requests use the nominal widths and no column floor, so callers
    that omit overrides keep the proportional narrow-window split.
    """
    overridden = nav is not None or insp is not None
    nav_w = NAVIGATOR_WIDTH if nav is None else nav
    insp_w = INSPECTOR_WIDTH if insp is None else insp
    floor = MIN_COLUMN_WIDTH if overridden else 0
    return clamp_column_widths(
        display_w,
        nav_w,
        insp_w,
        min_column=floor,
    )


def splitter_hit(
    layout: ShellLayout,
    x: float,
    y: float,
    *,
    hit_px: float = SPLITTER_HIT_PX,
) -> str | None:
    """``nav`` or ``insp`` when (*x*, *y*) is in that splitter's hit zone.

    Each zone is *hit_px* wide, centered on the boundary, and only as tall as
    the columns. The hit-rects role is ``splitter``.
    """
    _origin_x, top, _width, height = layout.navigator
    if height <= 0 or hit_px <= 0 or y < top or y >= top + height:
        return None
    half = hit_px / 2.0
    left = float(layout.navigator[0] + layout.navigator[2])
    right = float(layout.inspector[0])
    in_left = (left - half) <= x < (left + half)
    in_right = (right - half) <= x < (right + half)
    if in_left and in_right:
        if abs(x - left) <= abs(x - right):
            return "nav"
        return "insp"
    if in_left:
        return "nav"
    if in_right:
        return "insp"
    return None


def splitter_request_width(layout: ShellLayout, which: str, pointer_x: float) -> int:
    """Unclamped column width *pointer_x* is asking for.

    ``nav`` grows as the pointer moves right. ``insp`` grows as it moves left.
    """
    if which == "nav":
        width = pointer_x - float(layout.navigator[0])
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
    timeline: Rect

    @staticmethod
    def compute(
        display_w: int,
        display_h: int,
        menu_h: int,
        transport_h: int,
        timeline_h: int,
        nav_width: int | None = None,
        insp_width: int | None = None,
    ) -> ShellLayout:
        """Column rects for one frame.

        *nav_width* and *insp_width* replace the nominal 230 and 495. None
        keeps that nominal width. Requests are clamped into this layout and
        are not written back.
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
        nav_w, viz_w, insp_w = _column_widths(display_w, nav_width, insp_width)

        if timeline_h > 0:
            timeline = (0, display_h - timeline_h, display_w, timeline_h)
        else:
            timeline = (0, display_h, display_w, 0)

        return ShellLayout(
            menu=(0, 0, display_w, menu_h),
            transport=(0, menu_h, display_w, transport_h),
            navigator=(0, columns_y, nav_w, columns_h),
            visualiser=(nav_w, columns_y, viz_w, columns_h),
            inspector=(nav_w + viz_w, columns_y, insp_w, columns_h),
            timeline=timeline,
        )
