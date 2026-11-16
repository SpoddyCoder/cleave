"""The inspector's title line: breadcrumb, accent swipe, marks, and page history arrows."""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from cleave.viz.config_pages import config_page_title, is_config_page
from cleave.viz.icon_button import icon_box, icon_columns, icon_gap
from cleave.viz.imgui_icon_button import box_button, icon_button, paint_box
from cleave.viz.imgui_theme import row_band, row_band_side
from cleave.viz.material_icons import LOCK_GLYPH, POWER_GLYPH
from cleave.viz.navigator import (
    ancestor_ids,
    build_navigator,
    NavNode,
    PageStatus,
    timeline_row_slot_of,
    timeline_row_title,
)
from cleave.viz.panel_notification import (
    attention_scroll_hold_sec,
    attention_scroll_offset,
    attention_scroll_sec,
    notification_attention,
)
from cleave.viz.shell_widgets import packed_color, PANEL_BORDER_PX, swipe_fill
from cleave.viz.theme import DISABLED, HIGHLIGHT, LOCKED, NOTIFICATION_ON_FILL, VALUE

if TYPE_CHECKING:
    from cleave.viz.session import TuningSession

TITLE_BACK = "back"
TITLE_FORWARD = "forward"


def page_status_marks(
    status: PageStatus,
) -> tuple[tuple[str, tuple[int, int, int], str], ...]:
    """Icons after the inspector title, as ``(glyph, colour, tooltip)``."""
    marks: list[tuple[str, tuple[int, int, int], str]] = []
    if status.off_by is not None:
        marks.append(
            (
                POWER_GLYPH,
                DISABLED,
                f"Off: these settings have no effect until {status.off_by} is turned on",
            )
        )
    if status.locked_by is not None:
        marks.append(
            (
                LOCK_GLYPH,
                LOCKED,
                f"Locked: unlock {status.locked_by} to change these settings",
            )
        )
    return tuple(marks)


def inspector_title(nodes: Sequence[NavNode], selected_id: str) -> str:
    """Breadcrumb title for *selected_id*."""
    if is_config_page(selected_id):
        return config_page_title(selected_id)
    node = next((item for item in nodes if item.id == selected_id), None)
    if node is None:
        return selected_id
    by_id = {item.id: item for item in nodes}
    labels = [node.label]
    parent = by_id.get(node.parent_id)
    while parent is not None:
        labels.insert(0, parent.label)
        parent = by_id.get(parent.parent_id)
    return " > ".join(labels)


def page_title(session: TuningSession, expanded: Collection[str], page_id: str) -> str:
    """Breadcrumb for any inspector page, opening its ancestors to name them."""
    slot = timeline_row_slot_of(page_id)
    if slot is not None:
        return timeline_row_title(session, slot)
    nodes = build_navigator(session, set(expanded) | ancestor_ids(page_id))
    return inspector_title(nodes, page_id)


def page_history_tooltip(
    target_title: str | None, *, forward: bool
) -> str:
    """Tooltip for the inspector's Back or Forward arrow."""
    if target_title is None:
        return "No later page" if forward else "No earlier page"
    if forward:
        return f"Forward to {target_title} (Alt+Right)"
    return f"Back to {target_title} (Alt+Left)"


def inspector_title_cluster(
    avail: float, slot_count: int, side: float, gap: float, title_gap: float
) -> tuple[float, tuple[float, ...]]:
    """Title width and the x of each icon box at the title line's right.

    Boxes sit flush right, in order, *gap* apart. The title and its accent
    bar stop *title_gap* before the first box.
    """
    cluster_w = slot_count * side + max(0, slot_count - 1) * gap
    slots = icon_columns(max(avail, cluster_w), slot_count, side, gap)
    cluster_x = slots[0] if slots else avail
    return max(0.0, cluster_x - title_gap), slots


@dataclass(frozen=True)
class TitleButton:
    """An icon button on the inspector title line."""

    id: str
    glyph: str
    enabled: bool
    tooltip: Callable[[], str]


def draw_inspector_title(
    title: str,
    elapsed_sec: float,
    marks: Sequence[tuple[str, tuple[int, int, int], str]] = (),
    buttons: Sequence[TitleButton] = (),
) -> str | None:
    """Inspector page title, with the toast's accent swipe behind it.

    *marks* (coloured icons with a tooltip) and then *buttons* sit flush
    right on the title line. The bar starts inset from the panel edge by the
    gap above it and is one text row tall. It and the title stop a space short
    of the icons. A title wider than its room waits, scrolls to its last
    words, pauses, then snaps back to its start, cut at its right edge, as
    the bar slides off. Returns the id of a pressed, enabled button.
    """
    start = imgui.get_cursor_screen_pos()
    avail = max(0.0, imgui.get_content_region_avail().x)
    line_h = imgui.get_text_line_height()
    style = imgui.get_style()
    space_w = imgui.calc_text_size(" ").x
    title_room, slot_xs = inspector_title_cluster(
        avail, len(marks) + len(buttons), row_band_side(), icon_gap(), space_w
    )
    title_w = imgui.calc_text_size(title).x
    imgui.dummy(imgui.ImVec2(title_room, line_h))
    win_pos = imgui.get_window_pos()
    win_size = imgui.get_window_size()
    border = PANEL_BORDER_PX
    # The bar is a row's highlight band, so the title's icons match the rows'.
    band = row_band(start.y)
    bar_y0, bar_y1 = band
    # The blank gap above the bar, inside the panel border, repeats at the
    # bar's left end.
    inset = border + max(0.0, style.window_padding.y - (start.y - bar_y0) - border)
    bar_x0 = win_pos.x + inset
    bar_x1 = start.x + title_room + space_w * 0.5
    overflow = title_w - title_room
    scroll_sec = attention_scroll_sec(overflow, space_w)
    attention = notification_attention(
        elapsed_sec, hold_sec=attention_scroll_hold_sec(scroll_sec)
    )
    draw = imgui.get_window_draw_list()
    color = packed_color(VALUE)
    fill = swipe_fill(
        bar_x1 - bar_x0, attention.fill_progress, from_left=attention.fill_from_left
    )
    if fill is not None:
        fill_x, fill_w = fill
        draw.push_clip_rect(
            imgui.ImVec2(win_pos.x, win_pos.y),
            imgui.ImVec2(win_pos.x + win_size.x, win_pos.y + win_size.y),
            False,
        )
        try:
            draw.add_rect_filled(
                imgui.ImVec2(bar_x0 + fill_x, bar_y0),
                imgui.ImVec2(bar_x0 + fill_x + fill_w, bar_y1),
                packed_color(HIGHLIGHT),
            )
        finally:
            draw.pop_clip_rect()
        mid = start.x + min(title_w, title_room) * 0.5
        if attention.text_on_fill and bar_x0 + fill_x <= mid < bar_x0 + fill_x + fill_w:
            color = packed_color(NOTIFICATION_ON_FILL)
    offset = attention_scroll_offset(elapsed_sec, overflow, scroll_sec)
    draw.push_clip_rect(
        imgui.ImVec2(start.x, bar_y0),
        imgui.ImVec2(start.x + title_room, bar_y1),
        True,
    )
    try:
        draw.add_text(imgui.ImVec2(start.x - offset, start.y), color, title)
    finally:
        draw.pop_clip_rect()
    for index, ((glyph, role, tooltip), slot_x) in enumerate(zip(marks, slot_xs)):
        box = icon_box(start.x + slot_x, band)
        # A mark only reports: it shows its tooltip and takes no press.
        box_button(f"##inspector-mark-{index}", box, enabled=False, tooltip=tooltip)
        paint_box(box, glyph, color=role)
    return _draw_title_buttons(buttons, start, slot_xs[len(marks) :], band)


def _draw_title_buttons(
    buttons: Sequence[TitleButton],
    start: imgui.ImVec2,
    slot_xs: Sequence[float],
    band: tuple[float, float],
) -> str | None:
    """Arrow buttons on the title line, like navigator toggles. A disabled
    button has no hover fill and keeps the arrow pointer."""
    pressed_id: str | None = None
    for button, slot_x in zip(buttons, slot_xs):
        pressed = icon_button(
            f"##inspector-title-{button.id}",
            button.glyph,
            start.x + slot_x,
            band,
            color=VALUE if button.enabled else DISABLED,
            enabled=button.enabled,
            tooltip=button.tooltip,
        ).pressed
        if pressed and button.enabled:
            pressed_id = button.id
    return pressed_id
