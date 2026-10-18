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


def _column_widths(display_w: int) -> tuple[int, int, int]:
    """Navigator, visualiser, and inspector widths that sum to *display_w*.

    The visualiser stays at least 1px when the display is at least 1px wide.
    Side columns shrink in proportion to their nominal widths when the window
    is too narrow for both columns plus that pixel.
    """
    if display_w <= 0:
        return (0, 0, 0)
    nav = NAVIGATOR_WIDTH
    insp = INSPECTOR_WIDTH
    if display_w > nav + insp:
        return (nav, display_w - nav - insp, insp)
    remaining = display_w - 1
    total = nav + insp
    nav_w = remaining * nav // total
    insp_w = remaining - nav_w
    return (nav_w, display_w - nav_w - insp_w, insp_w)


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
    ) -> ShellLayout:
        display_w = max(0, int(display_w))
        display_h = max(0, int(display_h))
        menu_h = max(0, int(menu_h))
        transport_h = max(0, int(transport_h))
        timeline_h = max(0, int(timeline_h))
        if timeline_h > display_h:
            timeline_h = display_h

        columns_y = menu_h + transport_h
        columns_h = max(0, display_h - columns_y - timeline_h)
        nav_w, viz_w, insp_w = _column_widths(display_w)

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
