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
from cleave.viz.navigator import (
    TWISTY_COLLAPSED,
    TWISTY_EXPANDED,
    NavNode,
    build_navigator,
)
from cleave.viz.panel_notification import (
    PanelNotificationActive,
    notification_attention,
)
from cleave.viz.playback import format_mmss
from cleave.viz.row_hotkeys import activate_inspector_chip, node_control_descriptor
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_present_renderers import inspector_field_colors
from cleave.viz.row_spec import (
    RowNavButton,
    apply_field_horizontal,
    apply_field_nav_button,
    format_row_markers,
    format_row_position,
    format_row_value,
    row_is_two_line,
    row_lock_section,
    row_panel_label,
    row_spec,
    section_lock_blocks_mutation,
    section_locked,
)
from cleave.viz.session import TuningSession
from cleave.viz.shell_focus import (
    CycleStop,
    ShellRegion,
    cycle_stop_for_focus,
)
from cleave.viz.shell_layout import (
    ShellLayout,
    splitter_hit,
    splitter_request_width,
)
from cleave.viz.text_fit import fit_path_or_name_to_width, fit_text_to_width
from cleave.viz.theme import (
    ACTION,
    BACKGROUND,
    BORDER_COLOR,
    DISABLED,
    ERROR_NOTIFICATION,
    FOCUS_BORDER_ALPHA,
    FOCUS_WASH_ALPHA,
    HIGHLIGHT,
    LABEL,
    LOCK_ICON,
    MUTED,
    NAVIGATOR_BORDER,
    NOTIFICATION_ON_FILL,
    NUDGE_HOVER_BG,
    NUDGE_HOVER_BG_ALPHA,
    NUDGE_HOVER_FG,
    SELECTED_WASH_ALPHA,
    TRANSPORT_RULE,
    VALUE,
    tuning_ui_metrics,
)
from cleave.viz.value_nudge import (
    NudgeRect,
    nav_button_hit_at,
    nav_button_rects,
    nudge_arrow_rects,
    nudge_cluster_origin_x,
    nudge_hit_at,
    nudge_hover_fill_rect,
    nudge_press_skips_row,
    selectable_text_y,
    value_parts,
)
from cleave.viz.top_layer import TopLayer

# Vertical padding for the menu bar and the transport bar, which shares its height.
# Dear ImGui's default FramePadding.y is 3, which leaves both rows cramped.
_MENU_BAR_FRAME_PADDING_Y = 8.0
# Extra space between the menu-bar rule and the first popup row.
_MENU_POPUP_TOP_PAD_PX = 4.0
_INSPECTOR_INDENT = 16.0
_NAV_LOCK_MARK = "[lock]"
_TRANSPORT_GAP = 16.0
# Border pushed onto navigator and inspector windows.
_PANEL_BORDER_PX = 1.0
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
    return TWISTY_EXPANDED if node.id in expanded else TWISTY_COLLAPSED


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


def selection_after_nav_collapse(
    visible_ids: Sequence[str],
    selected_id: str,
    toggled_id: str,
) -> str:
    """Selection after a twisty collapses *toggled_id*.

    *selected_id* stays unless the collapse hid it.
    """
    if selected_id in visible_ids:
        return selected_id
    return toggled_id


def inspector_header(
    nodes: Sequence[NavNode],
    selected_id: str,
    session: TuningSession,
    *,
    curation: bool,
) -> InspectorHeader:
    """Breadcrumb title for *selected_id*.

    Chips follow the ``RowSpec`` of the header that owns the page and are
    omitted in preset curation. Enabled, solo, then lock.
    """
    node = next((item for item in nodes if item.id == selected_id), None)
    if node is None:
        return InspectorHeader(selected_id)
    by_id = {item.id: item for item in nodes}
    labels = [node.label]
    parent = by_id.get(node.parent_id)
    while parent is not None:
        labels.insert(0, parent.label)
        parent = by_id.get(parent.parent_id)
    title = " > ".join(labels)
    if curation:
        return InspectorHeader(title)
    descriptor = node_control_descriptor(selected_id)
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


def inspector_selectable_id(desc: RowDescriptor) -> str:
    """ImGui id for an inspector row.

    Slot, card, effect, and preset index stay in the id so repeated effect
    rows and preset-list items do not collide.
    """
    return (
        f"##row-{desc.kind.name}-{desc.slot}-{desc.card}-"
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


def _selectable_text_y(item_min_y: float) -> float:
    """Y of a shell selectable's label, given that item's rect top.

    Rows call Selectable with no explicit size. The theme leaves
    SelectableTextAlign at (0, 0) and FramePadding at Dear ImGui's default
    (y = 3), which this widget does not add. The text box is one line, so
    the align term is zero and the label sits trunc(ItemSpacing.y / 2)
    below the item rect.
    """
    style = imgui.get_style()
    line = imgui.get_text_line_height()
    return selectable_text_y(
        item_min_y,
        style.item_spacing.y,
        selectable_text_align_y=style.selectable_text_align.y,
        text_box_height=line,
        text_height=line,
    )


def _selectable_label_origin() -> tuple[float, float]:
    """Top-left of the current selectable's label.

    The item rect is the highlight, which Selectable grows by half of
    ItemSpacing. The label itself is drawn at the unpadded cursor.
    """
    rect_min = imgui.get_item_rect_min()
    spacing_x = imgui.get_style().item_spacing.x
    return (
        rect_min.x + float(math.trunc(spacing_x * 0.5)),
        _selectable_text_y(rect_min.y),
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
    x = nudge_cluster_origin_x(rect_max.x, widths, pad)
    # Same line as the selectable label. Navigator badges use this too.
    y = _selectable_text_y(rect_min.y)
    draw = imgui.get_window_draw_list()
    for (text, color), width in zip(parts, widths):
        draw.add_text(imgui.ImVec2(x, y), imgui.get_color_u32(color), text)
        x += width


class _ImguiTextSizer:
    """Measure text with the current ImGui font for the text fitters."""

    def size(self, text: str) -> tuple[int, int]:
        measured = imgui.calc_text_size(text)
        return math.ceil(measured.x), math.ceil(measured.y)


def _icon_drop_to_text(glyph: str) -> float:
    """Pixels to lower a merged icon so it centers on the capitals beside it."""
    font = imgui.get_font()
    icon = font.find_glyph(ord(glyph))
    cap = font.find_glyph(ord("A"))
    return float(round(((cap.y0 + cap.y1) - (icon.y0 + icon.y1)) * 0.5))


def _draw_two_line_row_text(
    label: str,
    markers: str,
    value: str,
    parts: list[tuple[str, imgui.ImVec4]],
    label_color: imgui.ImVec4,
    value_color: imgui.ImVec4,
) -> None:
    """Markers after the label, stopping short of the arrows, and the value below.

    Markers are painted, not part of the selectable label: ImGui hashes the
    visible label into the id, and a press must survive the markers changing.
    """
    origin_x, origin_y = _selectable_label_origin()
    right_x = imgui.get_item_rect_max().x
    pad = imgui.get_style().frame_padding.x
    sizer = _ImguiTextSizer()
    draw = imgui.get_window_draw_list()
    if markers:
        marker_x = origin_x + imgui.calc_text_size(f"{label} ").x
        cluster_x = nudge_cluster_origin_x(
            right_x,
            [imgui.calc_text_size(text).x for text, _color in parts],
            pad,
        )
        fitted = fit_text_to_width(
            sizer, markers, int(cluster_x - marker_x - imgui.calc_text_size(" ").x)
        )
        draw.add_text(
            imgui.ImVec2(marker_x, origin_y),
            imgui.get_color_u32(label_color),
            fitted,
        )
    draw.add_text(
        imgui.ImVec2(origin_x, origin_y + imgui.get_text_line_height()),
        imgui.get_color_u32(value_color),
        fit_path_or_name_to_width(sizer, value, int(right_x - pad - origin_x)),
    )


def inspector_row_click_outcome(
    *,
    double_click_row: bool,
    clicked: bool,
    activated: bool,
    double_clicked: bool,
) -> tuple[bool, bool]:
    """Whether a row gesture focuses the row, and whether it runs the row action.

    Selectable reports a click on release, but ImGui only flags a double-click
    on the second press. A double-click row therefore activates on that press.
    """
    if not double_click_row:
        return clicked, clicked
    activate = activated and double_clicked
    return clicked or activate, activate


def _inspector_row_selected(focus: Any, desc: Any) -> bool:
    return (
        focus.region is ShellRegion.INSPECTOR
        and focus.inspector_command_id is None
        and focus.inspector_cursor == desc
    )


def inspector_row_stepped(state: object, desc: RowDescriptor) -> bool:
    """Whether this inspector row paints side arrows and accepts a sideways drag.

    The section-lock rule matches Left/Right.
    """
    return (
        row_spec(desc.kind).apply_horizontal is not None
        and not section_lock_blocks_mutation(state, desc)
    )


def panel_border_overlap_px(border_size: float) -> int:
    """Pixels to pull a panel up so its top border shares the rule above.

    ``AddRect`` centers a window border half a pixel inside the rect. The
    transport rule fills the bar's last pixel, and a panel stacked below
    starts on that shared edge, so the two strokes sit one pixel apart.
    One pixel of overlap puts them on the same row.
    """
    if border_size <= 0.0:
        return 0
    return 1


def transport_content_pad_y(window_height: float, line_height: float) -> float:
    """Vertical padding that centers one text line inside the transport bar."""
    return max(0.0, (float(window_height) - float(line_height)) * 0.5)


def _overlap_panel(
    rect: tuple[int, int, int, int], overlap: int
) -> tuple[int, int, int, int]:
    """Pull a panel up so its top border sits on the rule above it.

    The bottom edge stays put. The extra pixel covers the line already drawn
    by the window above, so the two strokes share one row.
    """
    x, y, width, height = rect
    if overlap <= 0 or height <= 0 or y < overlap:
        return rect
    return (x, y - overlap, width, height + overlap)


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


def _focus_border_rgba() -> imgui.ImVec4:
    """Highlight colour at the quieter focus-outline alpha."""
    return rgba(HIGHLIGHT, FOCUS_BORDER_ALPHA / 255.0)


def _draw_rect_border(rect: tuple[int, int, int, int]) -> None:
    """1px highlight around *rect* on the current window."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    color = imgui.get_color_u32(_focus_border_rgba())
    imgui.get_window_draw_list().add_rect(
        imgui.ImVec2(float(x), float(y)),
        imgui.ImVec2(float(x + w), float(y + h)),
        color,
        0.0,
        0,
        1.0,
    )


def _fill_rect_border(rect: tuple[int, int, int, int]) -> None:
    """1px highlight around *rect* on the current window.

    A stroked border is anti-aliased, so the solid rule underneath shows
    through it. Filled edges cover that rule. The fill uses the quieter
    focus-outline alpha, so the rule tints the shared edge.
    """
    x, y, w, h = rect
    if w <= 1 or h <= 1:
        return
    color = imgui.get_color_u32(_focus_border_rgba())
    draw = imgui.get_window_draw_list()
    x0, y0 = float(x), float(y)
    x1, y1 = x0 + float(w), y0 + float(h)
    draw.add_rect_filled(imgui.ImVec2(x0, y0), imgui.ImVec2(x1, y0 + 1.0), color)
    draw.add_rect_filled(imgui.ImVec2(x0, y1 - 1.0), imgui.ImVec2(x1, y1), color)
    draw.add_rect_filled(imgui.ImVec2(x0, y0), imgui.ImVec2(x0 + 1.0, y1), color)
    draw.add_rect_filled(imgui.ImVec2(x1 - 1.0, y0), imgui.ImVec2(x1, y1), color)


def _draw_panel_focus_border(rect: tuple[int, int, int, int]) -> None:
    """Highlight outline above the shell windows that share its edges.

    Shell windows stay in an earlier display slot, so a border drawn with
    its panel sits under the rule it overlaps. This window is moved in front
    of those panels and left behind the menu popup, which begins afterwards.
    """
    display = imgui.get_io().display_size
    imgui.set_next_window_pos(imgui.ImVec2(0.0, 0.0), imgui.Cond_.always)
    imgui.set_next_window_size(
        imgui.ImVec2(display.x, display.y), imgui.Cond_.always
    )
    imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
    try:
        _visible, _opened = imgui.begin(
            "##shell-focus-border", None, _CHROME_FLAGS
        )
        try:
            imgui.internal.bring_window_to_display_front(
                imgui.internal.find_window_by_name("##shell-focus-border")
            )
            draw = imgui.get_window_draw_list()
            draw.push_clip_rect(imgui.ImVec2(0.0, 0.0), display, False)
            try:
                _fill_rect_border(rect)
            finally:
                draw.pop_clip_rect()
        finally:
            imgui.end()
    finally:
        imgui.pop_style_var()


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
    color = imgui.get_color_u32(_focus_border_rgba())
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
        menu_state: MenuBarState,
        controls: Any,
        bar_height: int,
    ) -> None:
        self.imgui = imgui_host
        self._menu_state = menu_state
        self._controls = controls
        self._menu_bar_height_px = bar_height
        # Drawn navigator list height, applied on the next frame. 0 until measured.
        self._nav_content_height_px = 0
        self._nav_scrolled_id: str | None = None
        self._layout: ShellLayout | None = None
        self._value_drag_accum = 0.0
        self._value_drag_crossed = False
        self._nudge_swallow = False
        # Live drag requests. A drag that moves at least 1px persists the stack
        # and help, then clears these.
        self._insp_width: int | None = None
        self._help_width: int | None = None
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

    def process_event(self, event: pygame.event.Event) -> None:
        """Mouse motion, buttons, and wheel only. Keys stay out of ImGui."""
        # Host active covers the click before the top layer has drawn the modal.
        if self._modal_has_pointer():
            self._process_modal_event(event)
            return
        imgui_host = self.imgui
        if event.type == pygame.MOUSEMOTION:
            imgui_host.process_mouse_event(event)
            x = float(event.pos[0])
            y = float(event.pos[1])
            self._track_splitter_motion(x, y)
            return
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            button = mouse_button(event)
            if button is None:
                return
            down = event.type == pygame.MOUSEBUTTONDOWN
            if down:
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
                self._end_splitter_drag(event.pos)
                return
            elif not imgui_host.button_held(button):
                return
            else:
                imgui_host.release_button(button)
            imgui_host.process_mouse_event(event)
            return
        if event.type == pygame.MOUSEWHEEL:
            imgui_host.process_mouse_event(event)

    def _process_modal_event(self, event: pygame.event.Event) -> None:
        """Forward the pointer to ImGui. The shell takes no region or splitter."""
        self._cancel_splitter_drag()
        self._controls.disarm_value_nudge()
        imgui_host = self.imgui
        if event.type == pygame.MOUSEMOTION:
            imgui_host.process_mouse_event(event)
            modal_host = getattr(self._controls, "modal_host", None)
            if modal_host is not None and modal_host.active:
                modal_host.note_pointer_motion(event)
            project_switch = getattr(self._controls, "project_switch", None)
            if project_switch is not None:
                project_switch.note_pointer_motion(event)
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
        """Left click chooses navigator, inspector, or the open strip.

        Menu, transport, help, and the visualiser leave the region alone. A
        miss when no layout is stored does nothing. The strip stays open.
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
        if self._nudge_input_blocked():
            self._controls.disarm_value_nudge()
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
        self._release_nudge_swallow()
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
        overlap = panel_border_overlap_px(_PANEL_BORDER_PX)
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
            navigator = _overlap_panel(layout.navigator, overlap)
            inspector = _overlap_panel(layout.inspector, overlap)
            self._draw_fixed_window(
                "##shell-navigator",
                navigator,
                active=stop is CycleStop.NAVIGATOR,
                idle_border=NAVIGATOR_BORDER,
                body=lambda: self._draw_navigator(),
                scrollable=True,
            )
            self._draw_fixed_window(
                "##shell-inspector",
                inspector,
                active=stop is CycleStop.INSPECTOR,
                idle_border=NAVIGATOR_BORDER,
                body=lambda: self._draw_inspector(state),
                scrollable=True,
            )
            self._draw_help(
                layout.help,
                overlap,
                state=state,
                menu_state=menu_state,
            )
            if stop is CycleStop.NAVIGATOR:
                _draw_panel_focus_border(navigator)
            elif stop is CycleStop.INSPECTOR:
                _draw_panel_focus_border(inspector)
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
            alpha = FOCUS_BORDER_ALPHA / 255.0 if active else 1.0
            imgui.push_style_color(imgui.Col_.border, rgba(border, alpha))
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
        overlap: int,
        *,
        state: object | None,
        menu_state: MenuBarState,
    ) -> None:
        if rect[2] <= 0 or rect[3] <= 0:
            return

        def body() -> None:
            if state is None:
                return
            stop = self._cycle_stop(menu_state)
            shell_focus = self._controls.shell_focus
            draw_help_column(
                help_sections_for_stop(
                    stop,
                    **help_section_kwargs(state, shell_focus, stop=stop),
                )
            )

        self._draw_fixed_window(
            "##shell-help",
            _overlap_panel(rect, overlap),
            active=False,
            idle_border=NAVIGATOR_BORDER,
            body=body,
            scrollable=True,
        )

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
                    if selected and self._nav_scrolled_id != node.id:
                        imgui.set_scroll_here_y()
                        self._nav_scrolled_id = node.id
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
        if node_id not in focus.nav_expanded:
            self._controls.navigator.select(node_id)
            return
        focus.nav_expanded.discard(node_id)
        visible = tuple(
            node.id
            for node in build_navigator(
                self._controls.session, focus.nav_expanded
            )
        )
        focus.selected_id = selection_after_nav_collapse(
            visible,
            focus.selected_id,
            node_id,
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
        for row in build_inspector_rows(state, focus.selected_id):
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
            if row.is_heading:
                value = format_row_value(state, desc) if spec.format_value else ""
                imgui.text_colored(rgba(MUTED), f"{label} {value}".rstrip())
                return
            label_color, value_color = inspector_field_colors(state, desc)
            if selected and label_color == LABEL:
                label_color = HIGHLIGHT
            two_line = row_is_two_line(kind)
            row_height = 2.0 * imgui.get_text_line_height() if two_line else 0.0
            imgui.push_style_color(imgui.Col_.text, rgba(label_color))
            try:
                with _selected_header_wash(selected, inspector=True):
                    clicked, _selected = imgui.selectable(
                        f"{label}{inspector_selectable_id(desc)}",
                        selected,
                        0,
                        imgui.ImVec2(0.0, row_height),
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
            cluster = format_row_position(state, desc) if two_line else value
            if cluster:
                parts = value_parts(
                    cluster,
                    rgba(value_color),
                    stepped=stepped,
                )
                _draw_aligned_parts(parts)
                if two_line:
                    _draw_two_line_row_text(
                        label,
                        format_row_markers(state, desc),
                        value,
                        parts,
                        rgba(label_color),
                        rgba(value_color),
                    )
                if spec.nav_buttons:
                    self._handle_nav_buttons(
                        state,
                        row,
                        desc,
                        label,
                        spec.nav_buttons,
                        rgba(value_color),
                        stepped=stepped,
                        activated=activated,
                    )
                if stepped:
                    self._handle_value_nudge(
                        row,
                        desc,
                        parts,
                        repeatable=spec.repeatable,
                        activated=activated,
                        two_line=two_line,
                    )
            if stepped and not self._nudge_swallow:
                self._track_value_drag(
                    row,
                    desc,
                    activated=activated,
                    active=active or released,
                )
            # A release still over the row reports clicked. A gesture that
            # already stepped is a drag, so it must not run the row action.
            # An arrow press is neither a drag nor an activate.
            if not self._value_drag_crossed and not self._nudge_swallow:
                focus, activate = inspector_row_click_outcome(
                    double_click_row=spec.activate_on_double_click,
                    clicked=clicked,
                    activated=activated,
                    double_clicked=imgui.is_mouse_double_clicked(0),
                )
                if focus:
                    self._controls.inspector.focus_row(row)
                if activate:
                    self._controls.inspector.activate(row)
        finally:
            if indent:
                imgui.unindent(indent)

    def _handle_nav_buttons(
        self,
        state: Any,
        row: Any,
        desc: RowDescriptor,
        label: str,
        buttons: tuple[RowNavButton, ...],
        value_color: imgui.ImVec4,
        *,
        stepped: bool,
        activated: bool,
    ) -> None:
        """Paint the icon buttons after the label, and take hover and press.

        A press on a dimmed button is swallowed. Otherwise a double-click on
        it would reach the row and open a child directory.
        """
        origin_x, text_y = _selectable_label_origin()
        rect_min = imgui.get_item_rect_min()
        line = imgui.get_text_line_height()
        space = imgui.calc_text_size(" ").x
        rects = nav_button_rects(
            origin_x + imgui.calc_text_size(f"{label} ").x,
            rect_min.y,
            imgui.get_item_rect_max().y - line,
            [imgui.calc_text_size(button.glyph).x for button in buttons],
            gap=space,
        )
        blocked = not stepped or self._nudge_input_blocked()
        mouse = imgui.get_mouse_pos()
        hit = None if blocked else nav_button_hit_at(mouse.x, mouse.y, rects)
        hold_armed = self._controls.value_nudge.armed
        available = [button.available(state, desc) for button in buttons]
        draw = imgui.get_window_draw_list()
        for index, (button, rect) in enumerate(zip(buttons, rects)):
            color = value_color if available[index] else rgba(DISABLED)
            if index == hit and available[index] and not hold_armed:
                draw.add_rect_filled(
                    imgui.ImVec2(rect.min_x, rect.min_y),
                    imgui.ImVec2(rect.max_x, rect.max_y),
                    imgui.get_color_u32(
                        rgba(NUDGE_HOVER_BG, NUDGE_HOVER_BG_ALPHA / 255.0)
                    ),
                )
                color = rgba(NUDGE_HOVER_FG)
            draw.add_text(
                imgui.ImVec2(
                    rect.min_x + space * 0.5,
                    text_y + _icon_drop_to_text(button.glyph),
                ),
                imgui.get_color_u32(color),
                button.glyph,
            )
        if not activated or hit is None:
            return
        self._controls.inspector.focus_row(row)
        if available[hit]:
            apply_field_nav_button(self._controls, desc, hit)
        self._clear_value_drag()
        self._nudge_swallow = True

    def _handle_value_nudge(
        self,
        row: Any,
        desc: RowDescriptor,
        parts: list[tuple[str, imgui.ImVec4]],
        *,
        repeatable: bool,
        activated: bool,
        two_line: bool,
    ) -> None:
        """Hover and press the painted side arrows. The value string is not a hit.

        On a two-line row the arrows cover the first line only.
        """
        if len(parts) != 3:
            return
        rect_min = imgui.get_item_rect_min()
        rect_max = imgui.get_item_rect_max()
        widths = [imgui.calc_text_size(text).x for text, _color in parts]
        pad = imgui.get_style().frame_padding.x
        arrows_max_y = rect_max.y
        if two_line:
            arrows_max_y -= imgui.get_text_line_height()
        back_rect, forward_rect = nudge_arrow_rects(
            rect_min.x,
            rect_min.y,
            rect_max.x,
            arrows_max_y,
            widths,
            frame_pad_x=pad,
        )
        blocked = self._nudge_input_blocked()
        mouse = imgui.get_mouse_pos()
        hit = (
            None
            if blocked
            else nudge_hit_at(mouse.x, mouse.y, back_rect, forward_rect)
        )
        hold = self._controls.value_nudge
        held_here = hold.armed and hold.desc == desc
        hover_forward: bool | None = None
        if held_here:
            hover_forward = hold.forward
        elif hit is not None and not hold.armed:
            hover_forward = hit.forward
        if hover_forward is not None:
            self._paint_nudge_hover(
                forward_rect if hover_forward else back_rect,
                parts,
                hover_forward,
            )
        if (
            not activated
            or blocked
            or not nudge_press_skips_row(hit)
            or hit is None
        ):
            return
        self._controls.inspector.focus_row(row)
        apply_field_horizontal(self._controls, desc, hit.forward, False)
        self._controls.begin_value_nudge(desc, hit.forward, repeatable)
        self._clear_value_drag()
        self._nudge_swallow = True

    def _paint_nudge_hover(
        self,
        rect: NudgeRect,
        parts: list[tuple[str, imgui.ImVec4]],
        forward: bool,
    ) -> None:
        glyph = parts[2][0] if forward else parts[0][0]
        arrow = ">" if forward else "<"
        arrow_width = imgui.calc_text_size(arrow).x
        space_width = imgui.calc_text_size(" ").x
        fill_rect = nudge_hover_fill_rect(
            rect,
            forward=forward,
            arrow_width=arrow_width,
            space_width=space_width,
        )
        draw = imgui.get_window_draw_list()
        fill = imgui.get_color_u32(
            rgba(NUDGE_HOVER_BG, NUDGE_HOVER_BG_ALPHA / 255.0)
        )
        draw.add_rect_filled(
            imgui.ImVec2(fill_rect.min_x, fill_rect.min_y),
            imgui.ImVec2(fill_rect.max_x, fill_rect.max_y),
            fill,
        )
        draw.add_text(
            imgui.ImVec2(rect.min_x, _selectable_text_y(rect.min_y)),
            imgui.get_color_u32(rgba(NUDGE_HOVER_FG)),
            glyph,
        )

    def _nudge_input_blocked(self) -> bool:
        return self._modal_has_pointer()

    def _modal_has_pointer(self) -> bool:
        modal_host = getattr(self._controls, "modal_host", None)
        return bool(self.top_layer.modal_active) or (
            modal_host is not None and bool(modal_host.active)
        )

    def _release_nudge_swallow(self) -> None:
        if not imgui.is_mouse_down(0):
            self._nudge_swallow = False

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
        imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() + _MENU_POPUP_TOP_PAD_PX)
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
    dt: float,
    readout: TransportReadout | None = None,
    notice: PanelNotificationActive | None = None,
) -> None:
    """One ImGui frame: shell windows, chrome, then the top layer.

    The menu, navigator, and inspector stay visible.
    """
    shell.transport_notice_clicked = False
    shell.imgui.begin_frame(dt)
    try:
        rule_y = shell.draw_windows(
            menu_state, command_ctx, readout, notice
        )
        shell.draw_chrome(menu_state, rule_y)
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
