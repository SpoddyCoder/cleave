"""ImGui menu bar on the live pygame OpenGL window.

``ImGuiHost`` owns the context, font atlas, renderer, and mouse queue.
Keyboard stays in ``input_dispatch``; the host only feeds mouse input.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Collection, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pygame
from imgui_bundle import imgui

from cleave.viz.commands import Command, CommandContext, MenuSeparator, command_by_id
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.frame_rate import format_fps_value
from cleave.viz.help_column import draw_help_column
from cleave.viz.help_content import help_section_kwargs, help_sections_for_stop
from cleave.viz.imgui_host import ImGuiHost, PAUSE_GLYPH, PLAY_GLYPH, mouse_button
from cleave.viz.imgui_theme import rgba
from cleave.viz.inspector import build_inspector_rows
from cleave.viz.inspector_controls import inspector_command_enabled
from cleave.viz.menu_bar import MenuBarState, menus_for_session
from cleave.viz.navigator import NavNode, build_navigator
from cleave.viz.panel_notification import (
    PanelNotificationActive,
    notification_attention,
)
from cleave.viz.playback import format_mmss
from cleave.viz.row_hotkeys import activate_inspector_chip, node_header_descriptor
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_present_renderers import inspector_field_colors
from cleave.viz.row_sections import inspector_group_glyph
from cleave.viz.row_spec import (
    apply_field_horizontal,
    format_row_value,
    row_lock_section,
    row_panel_label,
    row_spec,
    section_lock_blocks_mutation,
    section_locked,
)
from cleave.viz.session import TuningSession
from cleave.viz.ui_fade import UiFade
from cleave.viz.shell_focus import (
    CycleStop,
    InspectorGroupKey,
    ShellRegion,
    cycle_stop_for_focus,
    inspector_group_is_open,
)
from cleave.viz.shell_layout import (
    ShellLayout,
    splitter_hit,
    splitter_request_width,
)
from cleave.viz.theme import (
    ACTION,
    BACKGROUND,
    BORDER_COLOR,
    DISABLED,
    ERROR_NOTIFICATION,
    FOCUS_WASH_ALPHA,
    HIGHLIGHT,
    LABEL,
    LOCK_ICON,
    MUTED,
    NAVIGATOR_BORDER,
    NOTIFICATION_ON_FILL,
    SELECTED_WASH_ALPHA,
    TRANSPORT_RULE,
    VALUE,
    tuning_ui_metrics,
)
from cleave.viz.top_layer import TopLayer

_HIDDEN = 0.01
# Vertical padding for the menu bar and the transport bar, which shares its height.
# Dear ImGui's default FramePadding.y is 3, which leaves both rows cramped.
_MENU_BAR_FRAME_PADDING_Y = 8.0
_INSPECTOR_INDENT = 16.0
_NAV_LOCK_MARK = "[lock]"
_TRANSPORT_GAP = 16.0
# Border pushed onto navigator and inspector windows.
_PANEL_BORDER_PX = 1.0
# ImDrawList::AddRect insets the stroke path by half a pixel.
_BORDER_PATH_INSET_PX = 0.5
# Anti-aliased lines add this fringe beyond half the stroke thickness.
_AA_LINE_FRINGE_PX = 1.0
# One Left/Right step per this many pixels of sideways drag.
_VALUE_DRAG_THRESHOLD_PX = 10.0


@dataclass(frozen=True)
class TransportReadout:
    """Transport bar numbers. The shell host does not read the app."""

    paused: bool
    position_sec: float
    duration_sec: float
    bar_text: str
    fps: float | None


@dataclass(frozen=True)
class InspectorChip:
    """One inspector header toggle.

    ``id`` is ``enabled``, ``solo``, or ``lock``. ``active`` is on, soloed,
    or locked. The lock label is ``locked`` or ``lock``; solo stays ``solo``.
    """

    id: str
    label: str
    active: bool


@dataclass(frozen=True)
class InspectorHeader:
    """Inspector title line and the header chips for the selected node."""

    title: str
    chips: tuple[InspectorChip, ...] = ()
    descriptor: RowDescriptor | None = None


def transport_parts(readout: TransportReadout) -> list[tuple[str, tuple[int, int, int]]]:
    """Play state, clock, and bar for the transport bar.

    Play and pause use the action role. The clock uses the value role.
    The bar uses the muted role. Frame rate is ``transport_fps_text`` so the
    bar can pin it to the right.
    """
    icon = PAUSE_GLYPH if readout.paused else PLAY_GLYPH
    word = "pause" if readout.paused else "playing"
    clock = (
        f"{format_mmss(readout.position_sec)} / {format_mmss(readout.duration_sec)}"
    )
    return [
        (f"{icon} {word}", ACTION),
        (clock, VALUE),
        (f"bar {readout.bar_text}", MUTED),
    ]


def transport_fps_text(readout: TransportReadout) -> str:
    """Muted frame-rate label pinned to the right of the transport bar."""
    fps = format_fps_value(readout.fps) if readout.fps is not None else "—"
    return f"{fps} fps"


@dataclass(frozen=True)
class TransportNotice:
    """One warning or error line drawn across the transport bar.

    A timed warning uses ``HIGHLIGHT``. A persistent error uses
    ``ERROR_NOTIFICATION``. ``timed`` is true when a click should dismiss it.
    """

    text: str
    accent: tuple[int, int, int]
    elapsed_sec: float
    timed: bool


def transport_notice(active: PanelNotificationActive) -> TransportNotice | None:
    """The line the transport bar shows, or None when nothing is up.

    A timed warning wins when both lines are active, so a new toast is not
    hidden behind a pinned error. The error returns once the warning clears.
    """
    if active.message is not None:
        return TransportNotice(active.message, HIGHLIGHT, active.elapsed_sec, True)
    if active.persistent_message is not None:
        return TransportNotice(
            active.persistent_message,
            ERROR_NOTIFICATION,
            active.persistent_elapsed_sec,
            False,
        )
    return None


def navigator_twisty(node: NavNode, expanded: Collection[str]) -> str | None:
    """Disclosure glyph for an expandable navigator node."""
    if not node.expandable:
        return None
    return inspector_group_glyph(node.id in expanded)


def navigator_lock_mark(node: NavNode) -> str | None:
    """Lock mark for a locked navigator node."""
    if not node.locked:
        return None
    return _NAV_LOCK_MARK


def value_drag_steps(accum: float, threshold: float) -> tuple[int, float]:
    """Split a signed pixel accumulator into steps and a sub-threshold remainder.

    Positive *accum* steps forward. ``25`` at ``10`` is ``(2, 5.0)``;
    ``-25`` is ``(-2, -5.0)``; ``9`` is ``(0, 9.0)``.
    """
    steps = math.trunc(accum / threshold)
    if steps == 0:
        return 0, accum
    return steps, accum - steps * threshold


def apply_value_drag(
    controls: Any,
    desc: RowDescriptor,
    delta_x: float,
    accum: float,
    *,
    threshold: float = _VALUE_DRAG_THRESHOLD_PX,
) -> tuple[float, bool]:
    """Apply one Left/Right step per *threshold* pixels of horizontal motion.

    *delta_x* is this frame's mouse delta, added to *accum*. Rightward motion
    is ``forward=True``. ``large`` stays false. A refused mutation still
    consumes its steps so those pixels are not retried later.

    Returns the leftover accumulator and whether this call consumed a step.
    """
    steps, remaining = value_drag_steps(accum + delta_x, threshold)
    if steps == 0:
        return remaining, False
    forward = steps > 0
    for _ in range(abs(steps)):
        apply_field_horizontal(controls, desc, forward, False)
    return remaining, True


def selection_after_nav_toggle(
    visible_ids: Sequence[str],
    selected_id: str,
    toggled_id: str,
    *,
    expanded: bool,
) -> str:
    """Selection after a twisty click.

    Expanding keeps *selected_id*. Collapsing selects *toggled_id* when
    *selected_id* is not in *visible_ids*.
    """
    if expanded or selected_id in visible_ids:
        return selected_id
    return toggled_id


def inspector_header(
    nodes: Sequence[NavNode],
    selected_id: str,
    session: TuningSession,
    *,
    curation: bool,
) -> InspectorHeader:
    """Title for *selected_id*. A layer slot breadcrumbs to its parent.

    Chips follow the node's header ``RowSpec`` and are omitted in preset
    curation. Enabled, solo, then lock.
    """
    node = next((item for item in nodes if item.id == selected_id), None)
    if node is None:
        return InspectorHeader(selected_id)
    title = node.label
    if node.parent_id == "layers":
        parent = next((item for item in nodes if item.id == node.parent_id), None)
        if parent is not None:
            title = f"{parent.label} > {node.label}"
    if curation:
        return InspectorHeader(title)
    descriptor = node_header_descriptor(selected_id)
    if descriptor is None:
        return InspectorHeader(title)
    return InspectorHeader(
        title, _header_chips(session, descriptor), descriptor
    )


def _header_chips(
    session: TuningSession, desc: RowDescriptor
) -> tuple[InspectorChip, ...]:
    spec = row_spec(desc.kind)
    chips: list[InspectorChip] = []
    if spec.toggle_enabled is not None:
        enabled = _header_enabled(session, desc)
        chips.append(
            InspectorChip("enabled", "on" if enabled else "off", enabled)
        )
    if spec.toggle_solo is not None:
        chips.append(InspectorChip("solo", "solo", _header_solo_active(session, desc)))
    if row_lock_section(desc.kind) is not None:
        locked = section_locked(session, desc)
        chips.append(InspectorChip("lock", "locked" if locked else "lock", locked))
    return tuple(chips)


def _header_enabled(session: TuningSession, desc: RowDescriptor) -> bool:
    kind = desc.kind
    if kind == RowKind.TRACK_HEADER:
        slot = desc.slot
        if slot is None:
            return False
        return bool(session.layers[slot].enabled)
    if kind == RowKind.RENDER_OVERLAYS_HEADER:
        overlays = session.render_overlays
        return bool(
            overlays.opening_card.enabled or overlays.closing_card.enabled
        )
    if kind == RowKind.RENDER_OVERLAY_CARD_HEADER:
        if desc.card == "opening_card":
            return bool(session.render_overlays.opening_card.enabled)
        if desc.card == "closing_card":
            return bool(session.render_overlays.closing_card.enabled)
        return False
    if kind == RowKind.RENDER_POST_FX_HEADER:
        return bool(session.render_post_fx.enabled)
    if kind == RowKind.RENDER_PATTERN_MASK_HEADER:
        return bool(session.render_pattern_mask.enabled)
    if kind == RowKind.RENDER_TIMELINE_HEADER:
        return bool(session.timeline.enabled)
    return False


def _header_solo_active(session: TuningSession, desc: RowDescriptor) -> bool:
    if desc.kind == RowKind.TRACK_HEADER:
        return session.solo_slot == desc.slot
    if desc.kind == RowKind.RENDER_OVERLAYS_HEADER:
        return bool(session.render_overlay_solo)
    return False


def inspector_selectable_id(desc: RowDescriptor, *, group: bool) -> str:
    """ImGui id for an inspector group or row.

    Slot, card, effect, and preset index stay in the id so repeated effect
    rows and preset-list items do not collide. Group ids include the slot.
    """
    tag = "grp" if group else "row"
    return (
        f"##{tag}-{desc.kind.name}-{desc.slot}-{desc.card}-"
        f"{desc.effect_id}-{desc.driver_slug}-{desc.preset_index}"
    )


def _navigator_content_height_px() -> int:
    """Outer height of the navigator list just drawn in the current window.

    The cursor sits one item-spacing past the last row. Adding the bottom
    padding and border matches the window size that fits the rows. Scroll is
    already included in the cursor, so a clipped list still reports its full
    height for the next frame.
    """
    style = imgui.get_style()
    cursor_y = float(imgui.get_cursor_pos().y)
    spacing_y = float(style.item_spacing.y)
    content_bottom = cursor_y - spacing_y
    if content_bottom < 0.0:
        content_bottom = cursor_y
    outer = (
        content_bottom
        + float(style.window_padding.y)
        + float(style.window_border_size)
    )
    return max(1, int(round(outer)))


def menu_bar_height_px() -> int:
    """Pixels reserved for the menu bar before the first ImGui layout.

    Safe without a GL context or an ImGui context. ``ShellHost`` replaces
    this with the laid-out bar height after the first frame. The transport
    bar uses the same height.
    """
    font_size = float(tuning_ui_metrics().font_size)
    return max(1, int(round(font_size + _MENU_BAR_FRAME_PADDING_Y * 2.0)))


@contextmanager
def _menu_bar_frame_padding() -> Iterator[None]:
    """Extra vertical padding for the menu bar. Other rows keep the default."""
    style = imgui.get_style()
    imgui.push_style_var(
        imgui.StyleVar_.frame_padding,
        imgui.ImVec2(style.frame_padding.x, _MENU_BAR_FRAME_PADDING_Y),
    )
    try:
        yield
    finally:
        imgui.pop_style_var()


_POPUP_FLAGS = (
    int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.no_scrollbar)
    | int(imgui.WindowFlags_.always_auto_resize)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_nav)
)
_SHELL_FLAGS = (
    int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_bring_to_front_on_focus)
    | int(imgui.WindowFlags_.no_nav)
    | int(imgui.WindowFlags_.no_scrollbar)
    | int(imgui.WindowFlags_.no_scroll_with_mouse)
)
_CHROME_WINDOW = "##shell-chrome"
_CHROME_FLAGS = (
    int(imgui.WindowFlags_.no_background)
    | int(imgui.WindowFlags_.no_inputs)
    | int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_bring_to_front_on_focus)
    | int(imgui.WindowFlags_.no_nav)
)


def shell_window_flags(base: int, *, scrollable: bool) -> int:
    """Shell window flags. Scrollable panels keep the wheel and the scrollbar."""
    flags = int(base)
    if not scrollable:
        return flags
    hidden = (
        int(imgui.WindowFlags_.no_scrollbar)
        | int(imgui.WindowFlags_.no_scroll_with_mouse)
    )
    return flags & ~hidden


def _rect_contains(rect: tuple[int, int, int, int], x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rw > 0 and rh > 0 and rx <= x < rx + rw and ry <= y < ry + rh


def _draw_item_suffix(text: str, color: imgui.ImVec4) -> None:
    _draw_aligned_parts([(text, color)])


def _selectable_label_origin() -> tuple[float, float]:
    """Top-left of the current selectable's label.

    The item rect is the highlight, which Selectable grows by half of
    ItemSpacing. The label itself is drawn at the unpadded cursor.
    """
    rect_min = imgui.get_item_rect_min()
    spacing = imgui.get_style().item_spacing
    return (
        rect_min.x + float(math.trunc(spacing.x * 0.5)),
        rect_min.y + float(math.trunc(spacing.y * 0.5)),
    )


def _draw_mnemonic_underline(label: str, color: tuple[int, int, int]) -> None:
    """1px underline two pixels under the ink of a top menu's first letter."""
    letter = label[:1]
    if not letter:
        return
    origin_x, origin_y = _selectable_label_origin()
    glyph = imgui.get_font().find_glyph(ord(letter))
    letter_width = imgui.calc_text_size(letter).x
    # Two pixels under the glyph. The line box still has descent below that.
    y = origin_y + glyph.y1 + 2.0
    packed = imgui.get_color_u32(rgba(color))
    imgui.get_window_draw_list().add_rect_filled(
        imgui.ImVec2(origin_x, y),
        imgui.ImVec2(origin_x + letter_width, y + 1.0),
        packed,
    )


def _draw_nav_lock_mark(text_pos: imgui.ImVec2, label: str, mark: str) -> None:
    gap = imgui.get_style().item_spacing.x
    origin = imgui.ImVec2(
        text_pos.x + imgui.calc_text_size(label).x + gap,
        text_pos.y,
    )
    imgui.get_window_draw_list().add_text(
        origin,
        imgui.get_color_u32(rgba(LOCK_ICON)),
        mark,
    )


def _draw_aligned_parts(parts: list[tuple[str, imgui.ImVec4]]) -> None:
    if not parts:
        return
    widths = [imgui.calc_text_size(text).x for text, _color in parts]
    rect_min = imgui.get_item_rect_min()
    rect_max = imgui.get_item_rect_max()
    pad = imgui.get_style().frame_padding.x
    x = rect_max.x - sum(widths) - pad
    y = rect_min.y
    draw = imgui.get_window_draw_list()
    for (text, color), width in zip(parts, widths):
        draw.add_text(imgui.ImVec2(x, y), imgui.get_color_u32(color), text)
        x += width


def _inspector_row_selected(focus: Any, desc: Any) -> bool:
    return (
        focus.region is ShellRegion.INSPECTOR
        and focus.inspector_command_id is None
        and focus.inspector_cursor == desc
    )


def inspector_row_stepped(state: object, desc: RowDescriptor) -> bool:
    """Whether this inspector row paints side arrows and accepts sideways drag.

    Arrows stay paint-only. Drag uses the row selectable. The section-lock
    rule matches Left/Right.
    """
    return (
        row_spec(desc.kind).apply_horizontal is not None
        and not section_lock_blocks_mutation(state, desc)
    )


def _value_parts(
    value: str, color: imgui.ImVec4, *, stepped: bool
) -> list[tuple[str, imgui.ImVec4]]:
    if not stepped:
        return [(value, color)]
    bracket = rgba(DISABLED)
    return [("< ", bracket), (value, color), (" >", bracket)]


def border_stroke_outset_px(border_size: float, *, anti_aliased_lines: bool) -> float:
    """How far an ImGui window border extends outside the window rect.

    ``AddRect`` centers the stroke on a path half a pixel inside the edge.
    Anti-aliased lines add a one-pixel fringe beyond half the thickness.
    Window padding is inside the rect and does not move this stroke.
    """
    if border_size <= 0.0:
        return 0.0
    half = float(border_size) * 0.5
    if anti_aliased_lines:
        return half + _AA_LINE_FRINGE_PX - _BORDER_PATH_INSET_PX
    return max(0.0, half - _BORDER_PATH_INSET_PX)


def side_panel_seat_px(border_size: float, *, anti_aliased_lines: bool) -> int:
    """Pixels to drop a side panel so its border clears the transport rule."""
    outset = border_stroke_outset_px(
        border_size, anti_aliased_lines=anti_aliased_lines
    )
    if outset <= 0.0:
        return 0
    return math.ceil(outset - 1e-6)


def transport_content_pad_y(window_height: float, line_height: float) -> float:
    """Vertical padding that centers one text line inside the transport bar."""
    return max(0.0, (float(window_height) - float(line_height)) * 0.5)


def _seat_panel(
    rect: tuple[int, int, int, int], inset: int
) -> tuple[int, int, int, int]:
    """Drop a side panel so its border stroke clears the transport rule."""
    x, y, width, height = rect
    if inset <= 0 or height <= inset:
        return rect
    return (x, y + inset, width, height - inset)


def _packed(role: tuple[int, int, int]) -> int:
    return int(imgui.get_color_u32(rgba(role)))


def _notice_fill(
    width: float, attention_progress: float, *, from_left: bool
) -> tuple[float, float] | None:
    """Fill origin and width for a swipe across a bar of *width* pixels.

    The origin is relative to the bar's left edge. ``None`` when the accent
    bar is gone.
    """
    if attention_progress <= 0.001 or width <= 0:
        return None
    if attention_progress >= 0.999:
        fill_w = width
    else:
        fill_w = float(max(1, int(round(width * attention_progress))))
    fill_x = 0.0 if from_left else max(0.0, width - fill_w)
    return fill_x, fill_w


def _draw_transport_notice(
    notice: TransportNotice,
) -> tuple[float, float, float, float] | None:
    """Centered accent chip, as wide as the message plus one space each side.

    The play, clock, bar, and frame-rate labels stay in place. Black text is
    used only while the accent bar covers the message. Before the swipe
    reaches it, and after the bar slides off, the text stays in the accent
    colour. Returns the chip rect, or None when there is no message.
    """
    if not notice.text:
        return None
    origin = imgui.get_window_pos()
    size = imgui.get_window_size()
    text_size = imgui.calc_text_size(notice.text)
    space = imgui.calc_text_size(" ").x
    chip_w = min(size.x, text_size.x + space * 2.0)
    chip_x = origin.x + (size.x - chip_w) * 0.5
    chip = (chip_x, origin.y, chip_w, size.y)
    draw = imgui.get_window_draw_list()
    draw.push_clip_rect(
        imgui.ImVec2(origin.x, origin.y),
        imgui.ImVec2(origin.x + size.x, origin.y + size.y),
        False,
    )
    try:
        attention = notification_attention(notice.elapsed_sec)
        fill = _notice_fill(
            chip_w,
            attention.fill_progress,
            from_left=attention.fill_from_left,
        )
        if fill is not None:
            fill_x, fill_w = fill
            draw.add_rect_filled(
                imgui.ImVec2(chip_x + fill_x, origin.y),
                imgui.ImVec2(chip_x + fill_x + fill_w, origin.y + size.y),
                _packed(notice.accent),
            )
        text_x = origin.x + (size.x - text_size.x) * 0.5
        text_y = origin.y + (size.y - text_size.y) * 0.5
        role = notice.accent
        if attention.text_on_fill and fill is not None:
            fill_x, fill_w = fill
            mid = text_x + text_size.x * 0.5
            if chip_x + fill_x <= mid < chip_x + fill_x + fill_w:
                role = NOTIFICATION_ON_FILL
        draw.add_text(imgui.ImVec2(text_x, text_y), _packed(role), notice.text)
    finally:
        draw.pop_clip_rect()
    return chip


def _transport_notice_clicked(chip: tuple[float, float, float, float]) -> bool:
    """True when this frame's left click landed on the toast chip."""
    if not bool(imgui.get_io().mouse_clicked[0]):
        return False
    if not bool(imgui.is_window_hovered()):
        return False
    x, y, width, height = chip
    pos = imgui.get_io().mouse_pos
    return x <= pos.x < x + width and y <= pos.y < y + height


def _stroke_h_rule(
    x0: float,
    x1: float,
    y: float,
    rgb: tuple[int, int, int],
) -> None:
    """Opaque 1px rule on pixel row *y* of the current window.

    A stroked line is anti-aliased, so an opaque fill shows through it. A
    filled rectangle is not. The menu rule is drawn on the chrome window,
    above the menu buttons. The transport rule stays on the transport window
    so a later menu popup covers it.
    """
    if x1 <= x0:
        return
    color = imgui.get_color_u32(rgba(rgb))
    imgui.get_window_draw_list().add_rect_filled(
        imgui.ImVec2(x0, y),
        imgui.ImVec2(x1, y + 1.0),
        color,
    )


def _draw_rect_border(rect: tuple[int, int, int, int]) -> None:
    """1px highlight around the timeline strip on the current window.

    Drawn on the chrome window while the strip has focus. An open menu takes
    that focus, so this outline and the popup are never in the same frame.
    Chrome sits above the side panels that meet the strip.
    """
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    color = imgui.get_color_u32(rgba(HIGHLIGHT))
    imgui.get_window_draw_list().add_rect(
        imgui.ImVec2(float(x), float(y)),
        imgui.ImVec2(float(x + w), float(y + h)),
        color,
        0.0,
        0,
        1.0,
    )


def _draw_item_focus_ring() -> None:
    """1px highlight outline of the current item on its window.

    The window list is painted with that panel, so a later menu popup covers
    the outline where they overlap. The foreground list would sit above the
    popup.
    """
    rect_min = imgui.get_item_rect_min()
    rect_max = imgui.get_item_rect_max()
    if rect_max.x <= rect_min.x or rect_max.y <= rect_min.y:
        return
    color = imgui.get_color_u32(rgba(HIGHLIGHT))
    imgui.get_window_draw_list().add_rect(
        rect_min,
        rect_max,
        color,
        0.0,
        0,
        1.0,
    )


def selectable_wash(*, inspector: bool) -> tuple[imgui.ImVec4, imgui.ImVec4]:
    """Header fill for a selected navigator row or a focused inspector row.

    Both values are that fill, pushed on the header slots so the row keeps it
    under the pointer. Unselected hover stays the theme table.
    """
    alpha = (FOCUS_WASH_ALPHA if inspector else SELECTED_WASH_ALPHA) / 255.0
    fill = rgba(HIGHLIGHT, alpha)
    return fill, fill


@contextmanager
def _selected_header_wash(selected: bool, *, inspector: bool = False) -> Iterator[None]:
    """Push a selected-row header fill, then pop.

    Navigator selection uses the selected wash. Inspector focus uses the focus
    wash. Hover on an unselected row is the theme table, not a second push.
    """
    if selected:
        hovered, active = selectable_wash(inspector=inspector)
        imgui.push_style_color(imgui.Col_.header, hovered)
        imgui.push_style_color(imgui.Col_.header_hovered, hovered)
        imgui.push_style_color(imgui.Col_.header_active, active)
    try:
        yield
    finally:
        if selected:
            imgui.pop_style_color(3)


@contextmanager
def _opaque_highlight_fill(active: bool) -> Iterator[None]:
    """Push an opaque highlight header fill for an open menu title or row."""
    if active:
        fill = rgba(HIGHLIGHT, 1.0)
        imgui.push_style_color(imgui.Col_.header, fill)
        imgui.push_style_color(imgui.Col_.header_hovered, fill)
        imgui.push_style_color(imgui.Col_.header_active, fill)
    try:
        yield
    finally:
        if active:
            imgui.pop_style_color(3)


class ShellHost:
    """ImGui shell drawn through an ``ImGuiHost`` on the current GL context."""

    def __init__(
        self,
        imgui_host: ImGuiHost,
        ui_fade: UiFade,
        menu_state: MenuBarState,
        controls: Any,
        bar_height: int,
    ) -> None:
        self.imgui = imgui_host
        self._ui_fade = ui_fade
        self._menu_state = menu_state
        self._controls = controls
        self._menu_bar_height_px = bar_height
        # Drawn navigator list height, applied on the next frame. 0 until measured.
        self._nav_content_height_px = 0
        self._layout: ShellLayout | None = None
        self._value_drag_accum = 0.0
        self._value_drag_crossed = False
        # Live drag requests. A drag that moves at least 1px persists the stack
        # and help, then clears these.
        self._insp_width: int | None = None
        self._help_width: int | None = None
        self._help_scroll_px = 0.0
        self._splitter: str | None = None
        self._splitter_down_x = 0.0
        self._resize_cursor = False
        self.transport_notice_clicked = False
        self.top_layer = TopLayer()

    @property
    def menu_bar_height_px(self) -> int:
        return self._menu_bar_height_px

    @property
    def nav_content_height_px(self) -> int:
        """Navigator list height measured last frame. 0 until the list is drawn."""
        return self._nav_content_height_px

    @property
    def layout(self) -> ShellLayout | None:
        return self._layout

    def set_layout(self, layout: ShellLayout) -> None:
        """Remember the frame's shell rects for the transport, navigator, and inspector."""
        self._layout = layout

    @property
    def insp_width(self) -> int | None:
        """Inspector width requested by an in-progress splitter drag."""
        return self._insp_width

    @property
    def help_width(self) -> int | None:
        """Help width requested by an in-progress splitter drag."""
        return self._help_width

    @property
    def help_scroll_px(self) -> float:
        """Pending help-column scroll, applied the next time the window draws."""
        return self._help_scroll_px

    def scroll_help(self, delta_px: float) -> None:
        """Queue a vertical scroll for the help column."""
        self._help_scroll_px += float(delta_px)

    def process_event(self, event: pygame.event.Event) -> None:
        """Mouse motion, buttons, and wheel only. Keys stay out of ImGui."""
        # Host active covers the click before the top layer has drawn the modal.
        modal_host = getattr(self._controls, "modal_host", None)
        if self.top_layer.modal_active or (
            modal_host is not None and modal_host.active
        ):
            self._process_modal_event(event)
            return
        imgui_host = self.imgui
        if event.type == pygame.MOUSEMOTION:
            imgui_host.process_mouse_event(event)
            x = float(event.pos[0])
            y = float(event.pos[1])
            self._track_splitter_motion(x, y)
            if (
                self._chrome_contains(x, y)
                or self._splitter is not None
                or self._resize_cursor
            ):
                self._ui_fade.notify_input()
            return
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            button = mouse_button(event)
            if button is None:
                return
            down = event.type == pygame.MOUSEBUTTONDOWN
            if down:
                if self._clicks_ignored():
                    self._cancel_splitter_drag()
                    return
                x = float(event.pos[0])
                y = float(event.pos[1])
                captured = self.top_layer.captures_pointer(x, y)
                # Swallow the left button so ImGui does not activate a row
                # or start a value drag. A top-layer hit keeps the click.
                if (
                    button == 0
                    and not captured
                    and self._begin_splitter_drag(event.pos)
                ):
                    return
                if button == 0 and not captured:
                    self._assign_shell_region(x, y)
                imgui_host.press_button(button)
            elif button == 0 and self._splitter is not None:
                if self._clicks_ignored():
                    self._cancel_splitter_drag()
                else:
                    self._end_splitter_drag(event.pos)
                return
            elif not imgui_host.button_held(button):
                return
            else:
                imgui_host.release_button(button)
            imgui_host.process_mouse_event(event)
            return
        if event.type == pygame.MOUSEWHEEL:
            if self._clicks_ignored():
                return
            imgui_host.process_mouse_event(event)

    def _process_modal_event(self, event: pygame.event.Event) -> None:
        """Forward the pointer to ImGui. The shell takes no region or splitter."""
        self._cancel_splitter_drag()
        imgui_host = self.imgui
        if event.type == pygame.MOUSEMOTION:
            imgui_host.process_mouse_event(event)
            x = float(event.pos[0])
            y = float(event.pos[1])
            if self._chrome_contains(x, y):
                self._ui_fade.notify_input()
            return
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            button = mouse_button(event)
            if button is None:
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                imgui_host.press_button(button)
            else:
                imgui_host.release_button(button)
            imgui_host.process_mouse_event(event)
            return
        if event.type == pygame.MOUSEWHEEL:
            imgui_host.process_mouse_event(event)

    def _assign_shell_region(self, x: float, y: float) -> None:
        """Left click chooses navigator, inspector, help, or the open strip.

        Menu, transport, and the visualiser leave the region alone. A miss
        when no layout is stored does nothing. The strip stays open.
        """
        layout = self._layout
        if layout is None:
            return
        if _rect_contains(layout.navigator, x, y):
            self._controls.set_shell_region(ShellRegion.NAVIGATOR)
            return
        if _rect_contains(layout.inspector, x, y):
            self._controls.set_shell_region(ShellRegion.INSPECTOR)
            return
        if layout.timeline[3] > 0 and _rect_contains(layout.timeline, x, y):
            self._controls.set_shell_region(ShellRegion.TIMELINE)
            return
        if (
            layout.help[2] > 0
            and layout.help[3] > 0
            and _rect_contains(layout.help, x, y)
        ):
            self._controls.set_shell_region(
                ShellRegion.HELP,
                menu_focused=self._menu_state.focused,
            )

    def _splitter_at(self, x: float, y: float) -> str | None:
        layout = self._layout
        if layout is None:
            return None
        return splitter_hit(layout, x, y)

    def _assign_splitter_width(self, which: str, pointer_x: float) -> None:
        layout = self._layout
        if layout is None:
            return
        width = splitter_request_width(layout, which, pointer_x)
        if which == "help":
            self._help_width = width
        elif which == "insp":
            self._insp_width = width

    def _begin_splitter_drag(self, pos: tuple[float, float]) -> bool:
        which = self._splitter_at(float(pos[0]), float(pos[1]))
        if which is None:
            return False
        self._splitter = which
        self._splitter_down_x = float(pos[0])
        self._set_resize_cursor(True)
        return True

    def _end_splitter_drag(self, pos: tuple[float, float]) -> None:
        which = self._splitter
        x = float(pos[0])
        if which is not None and abs(x - self._splitter_down_x) >= 1.0:
            self._assign_splitter_width(which, x)
            editor = self._controls.cfg.editor
            insp = (
                self._insp_width
                if self._insp_width is not None
                else editor.inspector_width
            )
            help_w = (
                self._help_width
                if self._help_width is not None
                else editor.help_width
            )
            self._controls.settings.set_shell_column_widths(insp, help_w)
            self._insp_width = None
            self._help_width = None
        self._splitter = None
        # Layout catches up after this event. Keep the resize cursor until
        # the next motion, which tests the updated boundaries.
        self._set_resize_cursor(True)

    def _cancel_splitter_drag(self) -> None:
        self._splitter = None
        self._set_resize_cursor(False)

    def _track_splitter_motion(self, x: float, y: float) -> None:
        if self._clicks_ignored():
            self._cancel_splitter_drag()
            return
        if self._splitter is not None:
            self._assign_splitter_width(self._splitter, x)
            self._set_resize_cursor(True)
            return
        self._set_resize_cursor(self._splitter_at(x, y) is not None)

    def _set_resize_cursor(self, resize: bool) -> None:
        if resize == self._resize_cursor:
            return
        cursor = (
            pygame.SYSTEM_CURSOR_SIZEWE
            if resize
            else pygame.SYSTEM_CURSOR_ARROW
        )
        pygame.mouse.set_cursor(cursor)
        self._resize_cursor = resize

    def draw_windows(
        self,
        menu_state: MenuBarState,
        command_ctx: CommandContext,
        readout: TransportReadout | None = None,
        notice: PanelNotificationActive | None = None,
    ) -> float | None:
        """Menu bar, transport, navigator, inspector, and the open dropdown.

        The caller owns the ImGui frame and the fade. Returns the menu-rule
        row, or None when the bar did not open.
        """
        with _menu_bar_frame_padding():
            self._menu_bar_height_px = max(
                1, int(round(imgui.get_frame_height()))
            )
            rule_y, anchors, menus = self._draw_bar(menu_state)
        if self._layout is not None:
            self._draw_shell(menu_state, readout, notice)
        popup_hovered = False
        if menu_state.dropdown_open and menus:
            popup_hovered = self._draw_dropdown(
                menu_state, command_ctx, menus, anchors
            )
        if imgui.is_mouse_clicked(0) and not popup_hovered:
            mouse = imgui.get_mouse_pos()
            in_bar = 0.0 <= mouse.y < float(self._menu_bar_height_px)
            if not in_bar:
                menu_state.blur()
        self._release_value_drag()
        return rule_y

    def draw_chrome(self, menu_state: MenuBarState, rule_y: float | None) -> None:
        """Menu rule and timeline focus border, above the shell windows.

        Full-display, no background, and no inputs. Raised after Begin so the
        order stays shell windows, dropdown, then this window.
        """
        display = imgui.get_io().display_size
        imgui.set_next_window_pos(imgui.ImVec2(0.0, 0.0), imgui.Cond_.always)
        imgui.set_next_window_size(
            imgui.ImVec2(display.x, display.y), imgui.Cond_.always
        )
        # A non-zero border insets the window clip and would eat the edge rule.
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
        try:
            _visible, _opened = imgui.begin(_CHROME_WINDOW, None, _CHROME_FLAGS)
            try:
                imgui.internal.bring_window_to_display_front(
                    imgui.internal.find_window_by_name(_CHROME_WINDOW)
                )
                draw = imgui.get_window_draw_list()
                draw.push_clip_rect(imgui.ImVec2(0.0, 0.0), display, False)
                try:
                    if rule_y is not None:
                        _stroke_h_rule(0.0, display.x, rule_y, BORDER_COLOR)
                    layout = self._layout
                    if (
                        layout is not None
                        and self._cycle_stop(menu_state) is CycleStop.TIMELINE
                    ):
                        _draw_rect_border(layout.timeline)
                finally:
                    draw.pop_clip_rect()
            finally:
                imgui.end()
        finally:
            imgui.pop_style_var()

    def _chrome_contains(self, x: float, y: float) -> bool:
        if self.top_layer.captures_pointer(x, y):
            return True
        if y < self._menu_bar_height_px:
            return True
        layout = self._layout
        if layout is None:
            return False
        rects = [layout.transport, layout.navigator, layout.inspector]
        if layout.help[2] > 0 and layout.help[3] > 0:
            rects.append(layout.help)
        return any(_rect_contains(rect, x, y) for rect in rects)

    def _strip_has_scope(self) -> bool:
        return (
            self._controls.shell_focus.region is ShellRegion.TIMELINE
            and self._controls.session.timeline.panel_open
        )

    def _cycle_stop(self, menu_state: MenuBarState) -> CycleStop:
        session = self._controls.session
        return cycle_stop_for_focus(
            menu_focused=menu_state.focused,
            region=self._controls.shell_focus.region,
            help_open=bool(session.help_visible),
            strip_open=bool(session.timeline.panel_open),
        )

    def _draw_shell(
        self,
        menu_state: MenuBarState,
        readout: TransportReadout | None,
        notice: PanelNotificationActive | None,
    ) -> None:
        layout = self._layout
        if layout is None:
            return
        if readout is None:
            readout = TransportReadout(False, 0.0, 0.0, "—", None)
        state = self._controls.build_view_state(
            paused=readout.paused,
            position_sec=readout.position_sec,
            fps=readout.fps,
        )
        stop = self._cycle_stop(menu_state)
        style = imgui.get_style()
        # Default WindowMinSize is 32px, taller than this one-line bar, so the
        # transport was painted through its own text and over the side panels.
        saved_min_x = float(style.window_min_size.x)
        saved_min_y = float(style.window_min_size.y)
        style.window_min_size = imgui.ImVec2(1.0, 1.0)
        seat = side_panel_seat_px(
            _PANEL_BORDER_PX,
            anti_aliased_lines=bool(style.anti_aliased_lines),
        )
        try:
            pad_y = transport_content_pad_y(
                layout.transport[3], imgui.get_text_line_height()
            )
            imgui.push_style_var(
                imgui.StyleVar_.window_padding,
                imgui.ImVec2(style.window_padding.x, pad_y),
            )
            try:
                self._draw_fixed_window(
                    "##shell-transport",
                    layout.transport,
                    active=False,
                    body=lambda: self._draw_transport(readout, notice),
                )
            finally:
                imgui.pop_style_var()
            self._draw_fixed_window(
                "##shell-navigator",
                _seat_panel(layout.navigator, seat),
                active=stop is CycleStop.NAVIGATOR,
                idle_border=NAVIGATOR_BORDER,
                body=lambda: self._draw_navigator(),
                scrollable=True,
            )
            self._draw_fixed_window(
                "##shell-inspector",
                _seat_panel(layout.inspector, seat),
                active=stop is CycleStop.INSPECTOR,
                idle_border=NAVIGATOR_BORDER,
                body=lambda: self._draw_inspector(state),
                scrollable=True,
            )
            self._draw_help(
                layout.help,
                seat,
                active=stop is CycleStop.HELP,
                state=state,
                menu_state=menu_state,
            )
        finally:
            style.window_min_size = imgui.ImVec2(saved_min_x, saved_min_y)

    def _draw_fixed_window(
        self,
        title: str,
        rect: tuple[int, int, int, int],
        *,
        active: bool,
        body: Callable[[], None],
        idle_border: tuple[int, int, int] | None = None,
        scrollable: bool = False,
    ) -> None:
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return
        border = HIGHLIGHT if active else idle_border
        imgui.set_next_window_pos(
            imgui.ImVec2(float(x), float(y)), imgui.Cond_.always
        )
        imgui.set_next_window_size(
            imgui.ImVec2(float(w), float(h)), imgui.Cond_.always
        )
        imgui.push_style_var(
            imgui.StyleVar_.window_border_size,
            _PANEL_BORDER_PX if border is not None else 0.0,
        )
        if border is not None:
            imgui.push_style_color(imgui.Col_.border, rgba(border))
        try:
            _visible, _opened = imgui.begin(
                title,
                None,
                shell_window_flags(_SHELL_FLAGS, scrollable=scrollable),
            )
            try:
                body()
            finally:
                imgui.end()
        finally:
            if border is not None:
                imgui.pop_style_color()
            imgui.pop_style_var()

    def _draw_help(
        self,
        rect: tuple[int, int, int, int],
        seat: int,
        *,
        active: bool,
        state: object | None,
        menu_state: MenuBarState,
    ) -> None:
        if rect[2] <= 0 or rect[3] <= 0:
            self._help_scroll_px = 0.0
            return

        def body() -> None:
            pending = self._help_scroll_px
            self._help_scroll_px = 0.0
            if pending != 0.0:
                imgui.set_scroll_y(imgui.get_scroll_y() + pending)
            if state is None:
                return
            stop = self._help_content_stop(menu_state)
            shell_focus = self._controls.shell_focus
            draw_help_column(
                help_sections_for_stop(
                    stop,
                    **help_section_kwargs(state, shell_focus, stop=stop),
                )
            )

        self._draw_fixed_window(
            "##shell-help",
            _seat_panel(rect, seat),
            active=active,
            idle_border=NAVIGATOR_BORDER,
            body=body,
            scrollable=True,
        )

    def _help_content_stop(self, menu_state: MenuBarState) -> CycleStop:
        stop = self._cycle_stop(menu_state)
        if stop is not CycleStop.HELP:
            return stop
        subject = self._controls.shell_focus.help_subject
        if subject is CycleStop.HELP:
            return CycleStop.NAVIGATOR
        return subject

    def _draw_transport(
        self,
        readout: TransportReadout,
        notice: PanelNotificationActive | None,
    ) -> None:
        for index, (text, color) in enumerate(transport_parts(readout)):
            if index:
                imgui.same_line(0.0, _TRANSPORT_GAP)
            imgui.text_colored(rgba(color), text)
        fps = transport_fps_text(readout)
        width = imgui.calc_text_size(fps).x
        avail = imgui.get_window_width()
        pad = imgui.get_style().window_padding.x
        imgui.same_line(max(imgui.get_cursor_pos_x(), avail - width - pad))
        imgui.text_colored(rgba(MUTED), fps)
        line = None if notice is None else transport_notice(notice)
        if line is not None:
            chip = _draw_transport_notice(line)
            if line.timed and chip is not None and _transport_notice_clicked(chip):
                self.transport_notice_clicked = True
        origin = imgui.get_window_pos()
        size = imgui.get_window_size()
        _stroke_h_rule(
            origin.x,
            origin.x + size.x,
            origin.y + size.y - 1.0,
            TRANSPORT_RULE,
        )

    def _draw_navigator(self) -> None:
        focus = self._controls.shell_focus
        imgui.push_style_color(imgui.Col_.text, rgba(LABEL))
        try:
            for node in build_navigator(
                self._controls.session,
                focus.nav_expanded,
            ):
                self._draw_nav_node(node)
        finally:
            imgui.pop_style_color()
        self._nav_content_height_px = _navigator_content_height_px()

    def _draw_nav_node(self, node: NavNode) -> None:
        focus = self._controls.shell_focus
        indent = node.depth * _INSPECTOR_INDENT
        if indent:
            imgui.indent(indent)
        try:
            selected = node.id == focus.selected_id
            ring = (
                selected
                and focus.region is ShellRegion.NAVIGATOR
                and not self._menu_state.focused
            )
            twisty_clicked = False
            with _selected_header_wash(selected):
                twisty = navigator_twisty(node, focus.nav_expanded)
                if twisty is not None:
                    width = imgui.calc_text_size(twisty).x
                    twisty_clicked, _selected = imgui.selectable(
                        f"{twisty}##nav-twisty-{node.id}",
                        selected,
                        0,
                        imgui.ImVec2(width, 0.0),
                    )
                    imgui.same_line()
                if selected:
                    imgui.push_style_color(imgui.Col_.text, rgba(VALUE))
                try:
                    text_pos = imgui.get_cursor_screen_pos()
                    clicked, _selected = imgui.selectable(
                        f"{node.label}##nav-{node.id}",
                        selected,
                    )
                    if ring:
                        _draw_item_focus_ring()
                finally:
                    if selected:
                        imgui.pop_style_color()
            mark = navigator_lock_mark(node)
            if mark is not None:
                _draw_nav_lock_mark(text_pos, node.label, mark)
            if node.badge:
                _draw_item_suffix(node.badge, rgba(LABEL))
            if twisty_clicked:
                self._toggle_nav_expanded(node.id)
            elif clicked:
                self._controls.navigator.select(node.id)
        finally:
            if indent:
                imgui.unindent(indent)

    def _toggle_nav_expanded(self, node_id: str) -> None:
        focus = self._controls.shell_focus
        expanded = node_id not in focus.nav_expanded
        if expanded:
            focus.nav_expanded.add(node_id)
        else:
            focus.nav_expanded.discard(node_id)
        visible = tuple(
            node.id
            for node in build_navigator(
                self._controls.session, focus.nav_expanded
            )
        )
        focus.selected_id = selection_after_nav_toggle(
            visible,
            focus.selected_id,
            node_id,
            expanded=expanded,
        )

    def _draw_inspector(self, state: Any) -> None:
        focus = self._controls.shell_focus
        nodes = build_navigator(
            self._controls.session,
            focus.nav_expanded,
        )
        header = inspector_header(
            nodes,
            focus.selected_id,
            self._controls.session,
            curation=is_preset_curation_mode(
                self._controls.session.settings.editor_mode
            ),
        )
        if header.chips:
            imgui.align_text_to_frame_padding()
        imgui.text(header.title)
        if header.chips:
            self._draw_inspector_chips(header)
        rows = build_inspector_rows(
            state, focus.selected_id, focus.collapsed, focus.opened
        )
        if not rows:
            imgui.text_colored(rgba(DISABLED), "Edited on the panel")
            return
        for row in rows:
            self._draw_inspector_row(state, row)

    def _draw_inspector_row(self, state: Any, row: Any) -> None:
        focus = self._controls.shell_focus
        indent = row.depth * _INSPECTOR_INDENT
        if indent:
            imgui.indent(indent)
        try:
            if row.command_id is not None:
                self._draw_command_row(row)
                return
            desc = row.descriptor
            kind = desc.kind
            spec = row_spec(kind)
            label = row_panel_label(kind, desc)
            selected = _inspector_row_selected(focus, desc)
            if row.is_group:
                key = InspectorGroupKey(kind, desc.slot, desc.card)
                glyph = inspector_group_glyph(
                    inspector_group_is_open(key, focus.collapsed, focus.opened)
                )
                with _selected_header_wash(selected, inspector=True):
                    clicked, _selected = imgui.selectable(
                        f"{glyph} {label}{inspector_selectable_id(desc, group=True)}",
                        selected,
                    )
                    if selected:
                        _draw_item_focus_ring()
                if clicked:
                    self._controls.inspector.focus_row(row)
                    self._controls.inspector.activate(row)
                return
            label_color, value_color = inspector_field_colors(state, desc)
            if selected and label_color == LABEL:
                label_color = HIGHLIGHT
            imgui.push_style_color(imgui.Col_.text, rgba(label_color))
            try:
                with _selected_header_wash(selected, inspector=True):
                    clicked, _selected = imgui.selectable(
                        f"{label}{inspector_selectable_id(desc, group=False)}",
                        selected,
                    )
                    # Item flags are only valid while this selectable is current.
                    # Release clears the active id inside the widget, so the
                    # frame the button comes up is deactivated, not active.
                    activated = imgui.is_item_activated()
                    active = imgui.is_item_active()
                    released = imgui.is_item_deactivated()
                    if selected:
                        _draw_item_focus_ring()
            finally:
                imgui.pop_style_color()
            value = format_row_value(state, desc) if spec.format_value else ""
            stepped = inspector_row_stepped(state, desc)
            if spec.shows_dirty_suffix and state.config_dirty:
                value = f"{value}*" if value else "*"
            if value:
                _draw_aligned_parts(
                    _value_parts(
                        value,
                        rgba(value_color),
                        stepped=stepped,
                    )
                )
            if stepped:
                self._track_value_drag(
                    row,
                    desc,
                    activated=activated,
                    active=active or released,
                )
            # A release still over the row reports clicked. A gesture that
            # already stepped is a drag, so it must not run the row action.
            if clicked and not self._value_drag_crossed:
                self._controls.inspector.focus_row(row)
                self._controls.inspector.activate(row)
        finally:
            if indent:
                imgui.unindent(indent)

    def _track_value_drag(
        self,
        row: Any,
        desc: RowDescriptor,
        *,
        activated: bool,
        active: bool,
    ) -> None:
        """Step a held inspector value from this frame's horizontal mouse delta."""
        if not active:
            return
        if activated:
            self._value_drag_accum = 0.0
            self._value_drag_crossed = False
        delta_x = float(imgui.get_io().mouse_delta.x)
        remaining, crossed = apply_value_drag(
            self._controls,
            desc,
            delta_x,
            self._value_drag_accum,
        )
        self._value_drag_accum = remaining
        if not crossed:
            return
        self._value_drag_crossed = True
        self._controls.inspector.focus_row(row)

    def _clear_value_drag(self) -> None:
        self._value_drag_accum = 0.0
        self._value_drag_crossed = False

    def _release_value_drag(self) -> None:
        if not imgui.is_mouse_down(0):
            self._clear_value_drag()

    def _draw_command_row(self, row: Any) -> None:
        command = command_by_id(row.command_id)
        enabled = inspector_command_enabled(self._controls, row.command_id)
        focus = self._controls.shell_focus
        selected = (
            focus.region is ShellRegion.INSPECTOR
            and focus.inspector_command_id == row.command_id
        )
        color = ACTION if enabled else DISABLED
        imgui.push_style_color(imgui.Col_.text, rgba(color))
        try:
            with _selected_header_wash(selected, inspector=True):
                clicked, _selected = imgui.selectable(
                    f"{command.label}##cmd-{row.command_id}",
                    selected,
                )
                if selected:
                    _draw_item_focus_ring()
        finally:
            imgui.pop_style_color()
        if clicked:
            self._controls.inspector.focus_row(row)
            if enabled:
                self._controls.inspector.activate(row)

    def _draw_inspector_chips(self, header: InspectorHeader) -> None:
        chips = header.chips
        descriptor = header.descriptor
        if descriptor is None or not chips:
            return
        style = imgui.get_style()
        gap = style.item_spacing.x
        pad = style.frame_padding.x
        widths = [
            imgui.calc_text_size(chip.label).x + pad * 2.0 for chip in chips
        ]
        total = sum(widths) + gap * (len(chips) - 1)
        avail = imgui.get_window_width()
        imgui.same_line(
            max(
                imgui.get_cursor_pos_x(),
                avail - total - style.window_padding.x,
            )
        )
        for index, chip in enumerate(chips):
            if index:
                imgui.same_line(0.0, gap)
            color = LOCK_ICON if chip.id == "lock" else (
                ACTION if chip.active else LABEL
            )
            imgui.push_style_color(imgui.Col_.text, rgba(color))
            try:
                clicked, _selected = imgui.selectable(
                    f"{chip.label}##insp-chip-{chip.id}",
                    False,
                    0,
                    imgui.ImVec2(widths[index], 0.0),
                )
            finally:
                imgui.pop_style_color()
            if clicked:
                activate_inspector_chip(self._controls, chip.id, descriptor)

    def _clicks_ignored(self) -> bool:
        return (
            self._ui_fade.visibility <= _HIDDEN
            and not self._menu_state.dropdown_open
        )

    def _draw_bar(
        self, menu_state: MenuBarState
    ) -> tuple[float | None, dict[int, tuple[float, float]], tuple[Any, ...]]:
        menus = menus_for_session(self._controls.session)
        anchors: dict[int, tuple[float, float]] = {}
        imgui.push_style_color(imgui.Col_.text, rgba(LABEL))
        # The bar's own border is covered by the menu titles. The white rule
        # is drawn later, on top.
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
        bar_open = imgui.begin_main_menu_bar()
        rule_y: float | None = None
        try:
            if bar_open:
                bar_bottom = imgui.get_window_pos().y + imgui.get_window_height()
                self._menu_bar_height_px = max(1, int(round(bar_bottom)))
                rule_y = bar_bottom - 1.0
                pad_x = imgui.get_style().frame_padding.x
                for index, menu in enumerate(menus):
                    active = menu_state.focused and menu_state.menu_index == index
                    width = imgui.calc_text_size(menu.label).x + pad_x * 2.0
                    # Open title stays opaque highlight, including under the
                    # pointer. Idle hover is the theme header wash.
                    with _opaque_highlight_fill(active):
                        if active:
                            imgui.push_style_color(
                                imgui.Col_.text, rgba(BACKGROUND)
                            )
                        clicked, _selected = imgui.selectable(
                            menu.label,
                            active,
                            0,
                            imgui.ImVec2(width, 0.0),
                        )
                        if active:
                            imgui.pop_style_color()
                    _draw_mnemonic_underline(
                        menu.label, BACKGROUND if active else LABEL
                    )
                    rect_min = imgui.get_item_rect_min()
                    rect_max = imgui.get_item_rect_max()
                    anchors[index] = (rect_min.x, rect_max.y)
                    if clicked:
                        menu_state.click_top(index, menus)
        finally:
            if bar_open:
                imgui.end_main_menu_bar()
            imgui.pop_style_var()
            imgui.pop_style_color()
        return rule_y, anchors, menus

    def _draw_dropdown(
        self,
        menu_state: MenuBarState,
        command_ctx: CommandContext,
        menus: tuple[Any, ...],
        anchors: dict[int, tuple[float, float]],
    ) -> bool:
        index = menu_state.menu_index % len(menus)
        menu = menus[index]
        anchor = anchors.get(index)
        if anchor is None:
            origin_x = 0.0
            origin_y = float(self._menu_bar_height_px)
        else:
            origin_x, origin_y = anchor
        imgui.set_next_window_pos(
            imgui.ImVec2(origin_x, origin_y), imgui.Cond_.always
        )
        # Begun after the shell panels, and those panels do not raise themselves,
        # so the popup covers them. Chrome is raised after this window. Do not
        # focus it: FocusWindow clears the menu-bar button's ActiveId, and a
        # later click on another top label never completes.
        visible, _open = imgui.begin("##cleave-menu", None, _POPUP_FLAGS)
        try:
            if not visible:
                return False
            hit = self._draw_rows(menu_state, command_ctx, menus, index, menu)
            return hit or _mouse_in_current_window()
        finally:
            imgui.end()

    def _draw_rows(
        self,
        menu_state: MenuBarState,
        command_ctx: CommandContext,
        menus: tuple[Any, ...],
        menu_index: int,
        menu: Any,
    ) -> bool:
        hit = False
        style = imgui.get_style()
        pad_x = style.frame_padding.x
        check_w = imgui.calc_text_size("✓").x
        gap = max(imgui.calc_text_size("  ").x, 16.0)
        label_w = 0.0
        shortcut_w = 0.0
        for item in menu.items:
            if isinstance(item, MenuSeparator):
                continue
            label_w = max(label_w, imgui.calc_text_size(item.label).x)
            if item.shortcut:
                shortcut_w = max(shortcut_w, imgui.calc_text_size(item.shortcut).x)
        row_w = pad_x * 2.0 + check_w + gap + label_w + gap + shortcut_w + pad_x
        draw_list = imgui.get_window_draw_list()
        for item_index, item in enumerate(menu.items):
            if isinstance(item, MenuSeparator):
                imgui.separator()
                continue
            enabled = bool(item.enabled(command_ctx))
            highlighted = menu_state.item_index == item_index
            pos = imgui.get_cursor_screen_pos()
            # Disabled skips the hover wash. The keyboard row stays selectable
            # so its opaque fill still paints.
            flags = int(
                imgui.SelectableFlags_.disabled
                if not enabled and not highlighted
                else imgui.SelectableFlags_.none
            )
            with _opaque_highlight_fill(highlighted):
                clicked, _selected = imgui.selectable(
                    f"##{item.id}",
                    highlighted,
                    flags,
                    imgui.ImVec2(row_w, 0.0),
                )
            if highlighted:
                ink = rgba(BACKGROUND)
                label_color = check_color = shortcut_color = ink
            else:
                label_color = _row_color(item, command_ctx, enabled)
                check_color = rgba(ACTION)
                shortcut_color = rgba(MUTED)
            # Selectable anchors the label at the cursor and pads the highlight
            # with half of ItemSpacing on each side. Frame padding would push
            # the label down so the fill sits high, flush with the next row.
            text_y = pos.y
            text_x = pos.x + pad_x
            if (
                item.kind == "check"
                and item.checked is not None
                and item.checked(command_ctx)
            ):
                draw_list.add_text(
                    imgui.ImVec2(text_x, text_y),
                    imgui.get_color_u32(check_color),
                    "✓",
                )
            draw_list.add_text(
                imgui.ImVec2(text_x + check_w + gap, text_y),
                imgui.get_color_u32(label_color),
                item.label,
            )
            if item.shortcut:
                shortcut_width = imgui.calc_text_size(item.shortcut).x
                draw_list.add_text(
                    imgui.ImVec2(pos.x + row_w - pad_x - shortcut_width, text_y),
                    imgui.get_color_u32(shortcut_color),
                    item.shortcut,
                )
            if clicked:
                hit = True
                menu_state.click_item(
                    menu_index,
                    item_index,
                    menus,
                    command_ctx,
                    self._controls,
                )
        return hit


def draw_shell_frame(
    shell: ShellHost,
    menu_state: MenuBarState,
    command_ctx: CommandContext,
    visibility: float,
    dt: float,
    readout: TransportReadout | None = None,
    notice: PanelNotificationActive | None = None,
) -> None:
    """One ImGui frame: shell windows, chrome, then the top layer.

    Skips ``new_frame`` when the shell is hidden, no menu is open, and the
    top layer is empty. The fade covers the shell and chrome only.
    """
    shell.transport_notice_clicked = False
    if (
        visibility <= _HIDDEN
        and not menu_state.dropdown_open
        and shell.top_layer.empty
    ):
        shell.imgui.discard_input()
        shell._clear_value_drag()
        shell._cancel_splitter_drag()
        shell.top_layer.draw()
        return
    shell.imgui.begin_frame(dt)
    try:
        alpha = 1.0 if menu_state.dropdown_open else max(0.0, min(1.0, visibility))
        imgui.push_style_var(imgui.StyleVar_.alpha, alpha)
        try:
            rule_y = shell.draw_windows(
                menu_state, command_ctx, readout, notice
            )
            shell.draw_chrome(menu_state, rule_y)
        finally:
            imgui.pop_style_var()
        shell.top_layer.draw()
    finally:
        shell.imgui.end_frame()


def _mouse_in_current_window() -> bool:
    origin = imgui.get_window_pos()
    size = imgui.get_window_size()
    mouse = imgui.get_mouse_pos()
    return (
        origin.x <= mouse.x < origin.x + size.x
        and origin.y <= mouse.y < origin.y + size.y
    )


def _row_color(command: Command, ctx: CommandContext, enabled: bool) -> imgui.ImVec4:
    if not enabled:
        return rgba(DISABLED)
    if command.label_role is not None:
        return rgba(command.label_role(ctx))
    return rgba(VALUE)
