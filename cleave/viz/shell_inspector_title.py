"""The inspector's title line: breadcrumb, accent swipe, page toggles, and page history arrows."""

from __future__ import annotations

import math
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from cleave.viz.config_pages import config_page_title, is_config_page
from cleave.viz.icon_button import icon_columns, icon_gap
from cleave.viz.imgui_icon_button import icon_button
from cleave.viz.imgui_theme import row_band, row_band_side
from cleave.viz.navigator import (
    ancestor_ids,
    build_navigator,
    NavNode,
    PageStatus,
    PageToggle,
    TOGGLE_ENABLED,
    TOGGLE_PREVIEW,
    TOGGLE_SOLO,
    timeline_row_slot_of,
    timeline_row_title,
)
from cleave.viz.panel_notification import (
    attention_scroll_hold_sec,
    attention_scroll_offset,
    attention_scroll_sec,
    notification_attention,
)
from cleave.viz.progress_bar import accent_at
from cleave.viz.shell_navigator import (
    navigator_toggle_color,
    navigator_toggle_fill,
    navigator_toggle_glyph,
)
from cleave.viz.shell_widgets import packed_color, PANEL_BORDER_PX, swipe_fill
from cleave.viz.theme import palette

if TYPE_CHECKING:
    from cleave.viz.session import TuningSession

TITLE_BACK = "back"
TITLE_FORWARD = "forward"


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
    # None draws the glyph in value, or disabled while not enabled.
    color: tuple[int, int, int] | None = None
    fill: tuple[int, int, int] | None = None
    fill_alpha: float = 1.0
    # Refuses a press for a reason other than being disabled; draws as usual.
    inert: bool = False


def page_toggle_tooltip(item: PageToggle, status: PageStatus) -> str:
    """Hover text for a page's on/off, solo, preview, or lock button on the title line."""
    toggle = item.toggle
    name = item.owner_label
    if toggle.blocked:
        return f"Locked: unlock {status.locked_by or name} to change"
    if toggle.inert:
        return "Timeline controls layer visibility"
    if toggle.id == TOGGLE_ENABLED:
        if not toggle.active:
            return f"{name} is off: these settings have no effect. Click to turn on"
        if status.off_by is not None and status.off_by != name:
            return (
                f"{name} is on, but these settings have no effect until "
                f"{status.off_by} is turned on. Click to turn {name} off"
            )
        return f"{name} is on: click to turn off"
    if toggle.id == TOGGLE_SOLO:
        if toggle.active:
            return f"{name} is soloed: click to end solo"
        return f"Click to solo {name}"
    if toggle.id == TOGGLE_PREVIEW:
        if toggle.active:
            return "Previewing cards: click to end preview"
        return "Click to preview cards"
    if toggle.active:
        return f"{name} is locked: click to unlock"
    return f"{name} is unlocked: click to lock"


def page_toggle_buttons(
    toggles: Sequence[PageToggle], status: PageStatus
) -> tuple[TitleButton, ...]:
    """The page's on/off, solo or preview, and lock icons as title buttons, drawn like the
    navigator's. Each button's id is its toggle id.

    An on switch under a parent that is off draws its fill at half strength.
    """
    buttons: list[TitleButton] = []
    for item in toggles:
        toggle = item.toggle
        shadowed = (
            toggle.id == TOGGLE_ENABLED
            and toggle.active
            and status.off_by is not None
            and status.off_by != item.owner_label
        )
        buttons.append(
            TitleButton(
                toggle.id,
                navigator_toggle_glyph(toggle),
                not toggle.blocked,
                lambda item=item: page_toggle_tooltip(item, status),
                color=navigator_toggle_color(toggle),
                fill=navigator_toggle_fill(toggle),
                fill_alpha=0.5 if toggle.blocked or shadowed else 1.0,
                inert=toggle.inert,
            )
        )
    return tuple(buttons)


def draw_inspector_title(
    title: str,
    elapsed_sec: float,
    rule_y: float,
    buttons: Sequence[TitleButton] = (),
) -> str | None:
    """Inspector page title, with the toast's accent swipe behind it.

    *buttons* sit flush right on the title line. The bar is one padded row tall and centres
    between the panel's top border and the divider rule on pixel row
    *rule_y*, so the title and its icons do too. It starts inset from the
    panel edge by the gap above it. It and the title stop a space short
    of the icons. A title wider than its room waits, scrolls to its last
    words, pauses, then snaps back to its start, cut at its right edge, as
    the bar slides off. Returns the id of a pressed, enabled button.
    """
    start = imgui.get_cursor_screen_pos()
    avail = max(0.0, imgui.get_content_region_avail().x)
    line_h = imgui.get_text_line_height()
    space_w = imgui.calc_text_size(" ").x
    title_room, slot_xs = inspector_title_cluster(
        avail, len(buttons), row_band_side(), icon_gap(), space_w
    )
    title_w = imgui.calc_text_size(title).x
    imgui.dummy(imgui.ImVec2(title_room, line_h))
    win_pos = imgui.get_window_pos()
    win_size = imgui.get_window_size()
    # The bar is a row's highlight band, so the title's icons match the rows'.
    # An odd spare pixel goes below it.
    free_y = win_pos.y + PANEL_BORDER_PX
    side = row_band_side()
    bar_top = free_y + max(0.0, math.floor((rule_y - free_y - side) * 0.5))
    text_y = bar_top + (side - line_h) * 0.5
    band = row_band(text_y)
    bar_y0, bar_y1 = band
    # The blank gap above the bar, inside the panel border, repeats at the
    # bar's left end.
    bar_x0 = win_pos.x + (bar_y0 - win_pos.y)
    bar_x1 = start.x + title_room + space_w * 0.5
    overflow = title_w - title_room
    scroll_sec = attention_scroll_sec(overflow, space_w)
    attention = notification_attention(
        elapsed_sec, hold_sec=attention_scroll_hold_sec(scroll_sec)
    )
    draw = imgui.get_window_draw_list()
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
            # The accent gradient spans the whole bar, so the swipe reveals
            # it rather than stretching it.
            span_w = max(1.0, bar_x1 - bar_x0)
            left = packed_color(accent_at(fill_x / span_w))
            right = packed_color(accent_at((fill_x + fill_w) / span_w))
            draw.add_rect_filled_multi_color(
                imgui.ImVec2(bar_x0 + fill_x, bar_y0),
                imgui.ImVec2(bar_x0 + fill_x + fill_w, bar_y1),
                left,
                right,
                right,
                left,
            )
        finally:
            draw.pop_clip_rect()
    offset = attention_scroll_offset(elapsed_sec, overflow, scroll_sec)
    draw.push_clip_rect(
        imgui.ImVec2(start.x, bar_y0),
        imgui.ImVec2(start.x + title_room, bar_y1),
        True,
    )
    title_xy = imgui.ImVec2(start.x - offset, text_y)
    try:
        draw.add_text(title_xy, packed_color(palette().value), title)
        if fill is not None:
            # The part of the title over the swipe is in on_accent.
            fill_x, fill_w = fill
            draw.push_clip_rect(
                imgui.ImVec2(bar_x0 + fill_x, bar_y0),
                imgui.ImVec2(bar_x0 + fill_x + fill_w, bar_y1),
                True,
            )
            try:
                draw.add_text(title_xy, packed_color(palette().on_accent), title)
            finally:
                draw.pop_clip_rect()
    finally:
        draw.pop_clip_rect()
    return _draw_title_buttons(buttons, start, slot_xs, band)


def _draw_title_buttons(
    buttons: Sequence[TitleButton],
    start: imgui.ImVec2,
    slot_xs: Sequence[float],
    band: tuple[float, float],
) -> str | None:
    """Icon buttons on the title line, like navigator toggles. A disabled
    button has no hover fill and keeps the arrow pointer."""
    pressed_id: str | None = None
    for button, slot_x in zip(buttons, slot_xs):
        pressed = icon_button(
            f"##inspector-title-{button.id}",
            button.glyph,
            start.x + slot_x,
            band,
            color=button.color or (palette().value if button.enabled else palette().disabled),
            fill=button.fill,
            fill_alpha=button.fill_alpha,
            enabled=button.enabled,
            inert=button.inert,
            tooltip=button.tooltip,
        ).pressed
        if pressed and button.enabled and not button.inert:
            pressed_id = button.id
    return pressed_id
