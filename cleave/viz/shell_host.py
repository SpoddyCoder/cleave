"""ImGui menu bar on the live pygame OpenGL window.

``ImGuiHost`` owns the context, font atlas, renderer, and mouse queue.
Keyboard stays in ``input_dispatch``; the host only feeds mouse input.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Collection, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pygame
from imgui_bundle import imgui

from cleave.preset_library import marker_tooltip
from cleave.viz.commands import (
    Command,
    CommandContext,
    MenuSeparator,
    command_by_id,
    command_context,
)
from cleave.viz.drag_reorder import DRAG_LAYER, DRAG_PRESET, RowDragGesture
from cleave.viz.config_pages import config_page_title, is_config_page
from cleave.viz.frame_rate import format_fps_value
from cleave.viz.help_column import draw_help_column
from cleave.viz.help_content import (
    help_section_kwargs,
    help_sections_for_stop,
    modal_help_content,
)
from cleave.viz.imgui_host import ImGuiHost, PAUSE_GLYPH, PLAY_GLYPH, mouse_button
from cleave.viz.icon_button import (
    box_index_at,
    glyph_x,
    icon_box,
    icon_columns,
    icon_gap,
    icon_row,
    text_box,
)
from cleave.viz.imgui_icon_button import (
    box_button,
    glyph_drop,
    icon_button,
    paint_box,
    paint_wash,
    text_top,
)
from cleave.viz.imgui_theme import (
    padded_row_spacing_y,
    padded_rows,
    rgba,
    row_band,
    row_band_side,
)
from cleave.viz.inspector import InspectorRow, build_inspector_rows
from cleave.viz.inspector_controls import (
    inspector_command_enabled,
    inspector_command_locked,
)
from cleave.viz.menu_bar import MenuBarState, menus_for_session
from cleave.viz.menu_rows import (
    ContextMenuSurface,
    ContextSubmenuSurface,
    FittedWindow,
    MenuRowView,
    draw_menu_rows,
    opaque_highlight_fill,
)
from cleave.viz.pointer_cursor import PointerShape, request_pointer
from cleave.viz.overlay_profiler import OverlayProfiler
from cleave.viz.profiler_panel import draw_profiler_panel
from cleave.viz.context_menu import ContextMenuProvider
from cleave.viz.navigator_context_menu import navigator_node_menu
from cleave.viz.preset_context_menu import PRESET_MENU_KINDS, preset_row_menu
from cleave.viz.timeline_overlay import timeline_band_height_px
from cleave.viz.timeline_pointer import MIDDLE_BUTTON, RIGHT_BUTTON, TimelinePointer
from cleave.viz.material_icons import (
    ARROW_BACK_GLYPH,
    ARROW_FORWARD_GLYPH,
    LOCK_GLYPH,
    LOCK_OPEN_GLYPH,
    ADD_GLYPH,
    DRAG_INDICATOR_GLYPH,
    FILE_GLYPH,
    FOLDER_GLYPH,
    POWER_GLYPH,
    SOLO_GLYPH,
)
from cleave.viz.navigator import (
    TOGGLE_ENABLED,
    TOGGLE_ADD,
    TOGGLE_LOCK,
    TOGGLE_SOLO,
    TWISTY_COLLAPSED,
    TWISTY_EXPANDED,
    NavNode,
    NavToggle,
    ancestor_ids,
    build_navigator,
    navigator_row_text_color,
    navigator_tree_rails,
    PageStatus,
    page_status,
    timeline_row_slot_of,
    timeline_row_title,
)
from cleave.viz.panel_notification import (
    AttentionClock,
    PanelNotificationActive,
    attention_scroll_hold_sec,
    attention_scroll_offset,
    attention_scroll_sec,
    notification_attention,
)
from cleave.viz.playback import format_mmss
from cleave.viz.row_hotkeys import activate_header_toggle, node_control_descriptor
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_present_renderers import inspector_field_colors
from cleave.viz.row_spec import (
    RowNavButton,
    RowPresentStyle,
    apply_field_choice,
    apply_field_horizontal,
    apply_field_nav_button,
    format_row_markers,
    format_row_position,
    format_row_value,
    row_available,
    row_inert,
    row_is_two_line,
    row_label,
    row_spec,
    section_lock_blocks_mutation,
)
from cleave.viz.scroll_follow import ScrollFollow
from cleave.viz.shell_focus import (
    CycleStop,
    ShellRegion,
    cycle_stop_for_focus,
)
from cleave.viz.shell_layout import (
    ShellLayout,
    clamp_timeline_band_height,
    splitter_hit,
    splitter_request_height,
    splitter_request_timeline_height,
    splitter_request_width,
)
from cleave.viz.text_fit import fit_path_or_name_to_width, fit_text_to_width
from cleave.viz.theme import (
    BORDER_COLOR,
    BUTTON_BORDER,
    BACKGROUND,
    DISABLED,
    ERROR_NOTIFICATION,
    FOCUS_WASH_ALPHA,
    HIGHLIGHT,
    INSPECTOR_DIVIDER,
    LABEL,
    LOCK_ICON,
    LOCKED,
    MOVE_MODE,
    MUTED,
    NAV_LOCK_BG,
    NAV_LOCK_GLYPH,
    NAV_ON_BG,
    NAVIGATOR_BORDER,
    NAVIGATOR_TREE_LINE,
    NOTIFICATION_ON_FILL,
    NUDGE_HOVER_FG,
    PANEL_FOCUS_BORDER_ALPHA,
    PRESET_FILE_ICON,
    PRESET_ICON,
    ROW_FOCUS_BORDER,
    SOLO_BG,
    TRANSPORT_RULE,
    VALUE,
    tuning_ui_metrics,
    ui_chrome_px,
)
from cleave.viz.value_nudge import (
    NudgeRect,
    nudge_arrow_rects,
    nudge_cluster_origin_x,
    nudge_hit_at,
    nudge_press_skips_row,
    centre_pad,
    selectable_text_y,
    value_parts,
)
from cleave.viz.tooltips import show_tooltip
from cleave.viz.top_layer import TopLayer
from cleave.choice import ChoiceKind, choice_kind
from cleave.viz.choice_layout import (
    choice_width,
    combo_width,
    rect_contains,
    rect_index_at,
)
from cleave.viz.choice_widgets import (
    ChoiceTone,
    draw_choice_list,
    draw_combo,
    draw_segments,
    paint_stepper_hover,
)
from cleave.viz.transport_controls import TransportField

if TYPE_CHECKING:
    from cleave.viz.session import TuningSession

# Vertical padding for the menu bar and the transport bar, which shares its height.
# Dear ImGui's default FramePadding.y is 3, which leaves both rows cramped.
_MENU_BAR_FRAME_PADDING_Y = 8.0
# Extra space between the menu-bar rule and the first popup row.
_INSPECTOR_INDENT = 16.0
# Height of an inspector divider, as a fraction of the text line.
_INSPECTOR_DIVIDER_LINES = 0.5

_NAV_LOCK_MARK = "[lock]"
# pygame numbers the mouse back (X1) and forward (X2) side buttons 6 and 7.
_PAGE_HISTORY_BUTTONS = {6: -1, 7: 1}
_TITLE_BACK = "back"
_TITLE_FORWARD = "forward"
# Fixed columns, so a row without solo keeps its icons under the rows that have it.
_NAV_TOGGLE_COLUMNS = (TOGGLE_ENABLED, TOGGLE_SOLO, TOGGLE_LOCK)
_TRANSPORT_GAP = 16.0
# Border pushed onto navigator and inspector windows.
_PANEL_BORDER_PX = 2.0
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
class TransportPart:
    """One piece of transport bar text.

    ``field`` is set on a part the pointer can use. ``gap`` is false on a
    part that runs on from the one before it, such as the clock's duration.
    ``icon`` is drawn before the text, one space apart, centred on its capitals.
    """

    text: str
    color: tuple[int, int, int]
    field: TransportField | None = None
    gap: bool = True
    icon: str = ""

    @property
    def label(self) -> str:
        """Icon and text as laid out, for measuring."""
        return f"{self.icon} {self.text}" if self.icon else self.text


def transport_parts(readout: TransportReadout) -> list[TransportPart]:
    """Play state, clock, and bar for the transport bar, all in the value role.

    Play and pause, the current time, and the bar take the pointer. The bar
    has no field when there is no downbeat grid. Frame rate is
    ``transport_fps_text`` so the bar can pin it to the right.
    """
    icon = PAUSE_GLYPH if readout.paused else PLAY_GLYPH
    word = "PAUSED" if readout.paused else "PLAYING"
    has_bars = readout.bar_text != "—"
    return [
        TransportPart(word, VALUE, TransportField.PLAY, icon=icon),
        TransportPart(format_mmss(readout.position_sec), VALUE, TransportField.TIME),
        TransportPart(f"/ {format_mmss(readout.duration_sec)}", VALUE, gap=False),
        TransportPart(
            f"BAR {readout.bar_text}",
            VALUE,
            TransportField.BAR if has_bars else None,
        ),
    ]


def transport_fps_text(readout: TransportReadout) -> str:
    """Frame-rate label pinned to the right of the transport bar."""
    fps = format_fps_value(readout.fps) if readout.fps is not None else "—"
    return f"{fps} FPS"


# Widest text the transport time and bar fields are sized for.
_TRANSPORT_FIELD_TEMPLATE = {
    TransportField.TIME: "000:00.0",
    TransportField.BAR: "00000",
}


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


def navigator_toggle_glyph(toggle: NavToggle) -> str:
    """Material icon for a navigator toggle."""
    if toggle.id == TOGGLE_ADD:
        return ADD_GLYPH
    if toggle.id == TOGGLE_LOCK:
        return LOCK_GLYPH if toggle.active else LOCK_OPEN_GLYPH
    if toggle.id == TOGGLE_SOLO:
        return SOLO_GLYPH
    return POWER_GLYPH


def navigator_toggle_fill(toggle: NavToggle) -> tuple[int, int, int] | None:
    """Solid square behind a lit toggle: green on, red solo, amber lock."""
    if toggle.id == TOGGLE_ADD or not toggle.active:
        return None
    if toggle.id == TOGGLE_LOCK:
        return NAV_LOCK_BG
    if toggle.id == TOGGLE_SOLO:
        return SOLO_BG
    return NAV_ON_BG


def navigator_toggle_color(toggle: NavToggle) -> tuple[int, int, int]:
    """Resting icon color. Muted while inactive; a lit icon sits on its fill."""
    if toggle.id == TOGGLE_ADD:
        return DISABLED if toggle.blocked else VALUE
    if not toggle.active:
        return LOCKED if toggle.blocked else MUTED
    return NAV_LOCK_GLYPH if toggle.id == TOGGLE_LOCK else VALUE


def navigator_toggle_tooltip(toggle: NavToggle) -> str:
    """Hover text naming the state and what a click does."""
    if toggle.id == TOGGLE_ADD:
        return "Layer limit reached" if toggle.blocked else "Add layer"
    if toggle.blocked:
        return "Locked: unlock to change"
    if toggle.inert:
        return "Timeline controls layer visibility"
    if toggle.id == TOGGLE_LOCK:
        return "Locked: click to unlock" if toggle.active else "Unlocked: click to lock"
    if toggle.id == TOGGLE_SOLO:
        return "Solo: click to end solo" if toggle.active else "Click to solo"
    return "On: click to turn off" if toggle.active else "Off: click to turn on"


def strip_arm_tooltip(*, armed: bool, locked: bool) -> str:
    """Hover text for a strip row's arm button."""
    if locked:
        return "Locked: unlock the timeline to arm"
    return "Disarm" if armed else "Arm for recording"


def strip_solo_tooltip(*, solo: bool) -> str:
    """Hover text for a strip row's solo button."""
    return "End solo" if solo else "Solo this layer"


def strip_eye_tooltip(*, overridden: bool, recording: bool, armed: bool) -> str:
    """Hover text for a strip row's live visibility eye."""
    if recording:
        if armed:
            return "Click to record show / hide"
        return "Arm this row to record show / hide"
    if armed:
        return "Armed: press REC to record show / hide"
    if overridden:
        return "Override: click to show / hide"
    return "Show / hide, taking over from the timeline"


def strip_release_tooltip(*, recording: bool) -> str:
    """Hover text for a strip row's back-to-timeline button."""
    if recording:
        return "Stop recording to hand back to the timeline"
    return "Back to timeline"


def navigator_toggle_xs(right_x: float, side: float, gap: float) -> dict[str, float]:
    """Left edge of each toggle's column, ending flush at *right_x*.

    Columns are fixed, so a row without solo keeps its icons under the rows
    that have it. Add shares the lock column.
    """
    xs = dict(zip(_NAV_TOGGLE_COLUMNS, icon_columns(right_x, len(_NAV_TOGGLE_COLUMNS), side, gap)))
    xs[TOGGLE_ADD] = xs[TOGGLE_LOCK]
    return xs


def navigator_tree_lines(
    rails: Sequence[bool],
    first_stem_x: float,
    indent: float,
    elbow_right_x: float,
    top_y: float,
    mid_y: float,
    bottom_y: float,
) -> list[tuple[float, float, float, float]]:
    """Connector segments ``(x1, y1, x2, y2)`` for one row's *rails*.

    Stems sit *indent* apart from *first_stem_x*. An outer rail passes through
    only while its branch continues. The last rail always reaches the row: it
    runs on to *bottom_y* for a tee and stops at *mid_y* for a closing elbow,
    and its arm runs to *elbow_right_x*.
    """
    if not rails:
        return []
    lines: list[tuple[float, float, float, float]] = []
    for level, continues in enumerate(rails[:-1]):
        if continues:
            x = first_stem_x + level * indent
            lines.append((x, top_y, x, bottom_y))
    stem_x = first_stem_x + (len(rails) - 1) * indent
    lines.append((stem_x, top_y, stem_x, bottom_y if rails[-1] else mid_y))
    lines.append((stem_x, mid_y, elbow_right_x, mid_y))
    return lines


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


@dataclass(frozen=True)
class NavLabelClick:
    """What a press or release on a navigator row's label does.

    ``toggle`` opens or closes the row. ``opened_by_click`` is the row a click
    just opened, so the double-click it starts does not close it again.
    ``swallow_release`` skips the release that ends a closing double-click,
    which would otherwise open the row again.
    """

    select: bool = False
    toggle: bool = False
    opened_by_click: str | None = None
    swallow_release: bool = False


def navigator_label_click(
    mode: str,
    node_id: str,
    *,
    expandable: bool,
    expanded: bool,
    clicked: bool,
    double_pressed: bool,
    opened_by_click: str | None,
    swallowing: bool,
) -> NavLabelClick:
    """Outcome of a label click under the ``navigator_expand_click`` *mode*.

    Selectable reports a click on release, but ImGui flags a double-click on
    the second press, so a closing double-click acts on that press.
    """
    if mode == "click-expand" and expandable and double_pressed:
        if expanded and opened_by_click != node_id:
            return NavLabelClick(select=True, toggle=True, swallow_release=True)
        return NavLabelClick(opened_by_click=opened_by_click)
    if not clicked:
        return NavLabelClick(opened_by_click=opened_by_click)
    if swallowing or not expandable or mode == "button-only":
        return NavLabelClick(select=True)
    if mode == "click-toggle":
        return NavLabelClick(select=True, toggle=True)
    if expanded:
        return NavLabelClick(select=True)
    return NavLabelClick(select=True, toggle=True, opened_by_click=node_id)


def selection_after_nav_collapse(
    visible_ids: Sequence[str],
    selected_id: str,
    toggled_id: str,
) -> str:
    """Selection after a twisty collapses *toggled_id*.

    *selected_id* stays unless the collapse hid it. A Settings or Project
    page and a timeline row page have no row, so a collapse never hides them.
    """
    if (
        selected_id in visible_ids
        or is_config_page(selected_id)
        or timeline_row_slot_of(selected_id) is not None
    ):
        return selected_id
    return toggled_id


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


def choice_tone(value_color: tuple[int, int, int]) -> ChoiceTone:
    """Choice control tone that matches a row drawn in *value_color*."""
    if value_color == LOCKED:
        return ChoiceTone.LOCKED
    if value_color == DISABLED:
        return ChoiceTone.OFF
    return ChoiceTone.NORMAL


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


def row_icon_boxes(
    start_x: float, band: tuple[float, float], count: int
) -> tuple[tuple[float, float, float, float], ...]:
    """Square boxes for a row's icon buttons, left to right from *start_x*."""
    side = band[1] - band[0]
    return tuple(icon_box(x, band) for x in icon_row(start_x, count, side, icon_gap()))


def inspector_selectable_id(desc: RowDescriptor) -> str:
    """ImGui id for an inspector row.

    Slot, card, effect, preset index, and marker index stay in the id so
    repeated effect rows, preset-list items, and song markers do not collide.
    """
    return (
        f"##row-{desc.kind.name}-{desc.slot}-{desc.card}-"
        f"{desc.effect_id}-{desc.driver_slug}-{desc.preset_index}-"
        f"{desc.marker_index}"
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


def _nav_indent() -> float:
    """Navigator indent per level: one icon column, on whole pixels."""
    return float(round(row_band_side()))


def _draw_nav_twisty(
    node: NavNode,
    twisty: str,
    selected: bool,
    x: float,
    label_min_x: float,
    band: tuple[float, float],
) -> bool:
    """Disclosure button in the column at *x*, drawn after the row's label.

    The label selectable allows overlap, so the press reaches this button. A
    selected row's wash is filled under the column from where a selectable's
    highlight would start up to *label_min_x*, so the row reads as one band.
    Returns whether it was pressed.
    """
    if selected:
        wash_left = x - math.floor(imgui.get_style().item_spacing.x * 0.5)
        imgui.get_window_draw_list().add_rect_filled(
            imgui.ImVec2(wash_left, band[0]),
            imgui.ImVec2(label_min_x, band[1]),
            imgui.get_color_u32(selectable_wash()[0]),
        )
    return icon_button(
        f"##nav-twisty-{node.id}",
        twisty,
        x,
        band,
        color=navigator_row_text_color(node, selected=selected, moving=False),
    ).pressed


def navigator_height_for_rows(
    measured_px: int,
    measured_rows: int,
    rows: int,
    *,
    chrome_px: float,
    spacing_px: float,
) -> int:
    """Navigator outer height for *rows* given one measured frame.

    The window is sized a frame after the rows change, so the tree is
    resized from the last measurement to avoid one frame of overflow, which
    draws a scrollbar. *chrome_px* is the window padding top and bottom plus border and
    *spacing_px* the gap between rows. Rows are uniform.
    """
    if measured_px <= 0 or measured_rows <= 0 or rows == measured_rows:
        return measured_px
    step = (measured_px - chrome_px + spacing_px) / measured_rows
    return max(1, int(math.ceil(measured_px + (rows - measured_rows) * step)))


def menu_bar_height_px() -> int:
    """Pixels reserved for the menu bar before the first ImGui layout.

    Safe without a GL context or an ImGui context. ``ShellHost`` replaces
    this with the laid-out bar height after the first frame. The transport
    bar uses the same height.
    """
    font_size = float(tuning_ui_metrics().font_size)
    return max(1, int(round(font_size + _menu_bar_pad_y() * 2.0)))


def menu_bar_project_label(project_slug: str, dirty: bool) -> tuple[str, str]:
    """Prefix and name at the right end of the menu bar; ``*`` marks unsaved changes."""
    return "Project: ", f"{project_slug}*" if dirty else project_slug


def _menu_bar_pad_y() -> float:
    """Menu bar frame padding in whole pixels, so its labels and underlines stay on the pixel grid."""
    return float(round(ui_chrome_px(_MENU_BAR_FRAME_PADDING_Y)))


@contextmanager
def _menu_bar_frame_padding() -> Iterator[None]:
    """Extra vertical padding for the menu bar. Other rows keep the default."""
    style = imgui.get_style()
    imgui.push_style_var(
        imgui.StyleVar_.frame_padding,
        imgui.ImVec2(style.frame_padding.x, _menu_bar_pad_y()),
    )
    try:
        yield
    finally:
        imgui.pop_style_var()


_HELP_WINDOW = "##shell-help"
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


def scroll_clip_span(window_y: float, window_h: float, pad_y: float) -> tuple[float, float]:
    """Top and bottom clip edges for a scrollable panel's content.

    Dear ImGui clips window content at the border, so rows that overflow run
    into it. Insetting by the window padding keeps the same gap at the top
    and bottom edges that an unscrolled list has.
    """
    top = window_y + pad_y
    bottom = max(top, window_y + window_h - pad_y)
    return top, bottom


def _draw_padded_scroll_body(body: Callable[[], None]) -> None:
    """Draw *body* clipped inside the window padding, top and bottom."""
    pos = imgui.get_window_pos()
    size = imgui.get_window_size()
    top, bottom = scroll_clip_span(
        float(pos.y), float(size.y), float(imgui.get_style().window_padding.y)
    )
    imgui.push_clip_rect(
        imgui.ImVec2(float(pos.x), top),
        imgui.ImVec2(float(pos.x + size.x), bottom),
        True,
    )
    try:
        body()
    finally:
        imgui.pop_clip_rect()


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


def drag_handle_lead(glyph_width: float, space_width: float) -> int:
    """Spaces to put before a row label so the drag handle fits in front of it."""
    if space_width <= 0:
        return 0
    return max(1, math.ceil((glyph_width + space_width) / space_width))


def _drag_lead() -> str:
    """Label prefix that reserves the leading drag-handle column."""
    count = drag_handle_lead(
        imgui.calc_text_size(DRAG_INDICATOR_GLYPH).x,
        imgui.calc_text_size(" ").x,
    )
    return " " * count


def _nav_drag_lead() -> str:
    """Label prefix for a navigator drag handle: the glyph, with no extra space."""
    space = imgui.calc_text_size(" ").x
    if space <= 0:
        return ""
    glyph = imgui.calc_text_size(DRAG_INDICATOR_GLYPH).x
    return " " * max(1, math.ceil(glyph / space))


def nav_handle_text(node: NavNode) -> str:
    """The part of a navigator label drawn inside its drag handle."""
    text = node.handle_text
    return text if text and node.label.startswith(text) else ""


def _space_lead(text: str) -> str:
    """Spaces at least as wide as *text*, to hold its place in a label."""
    if not text:
        return ""
    space = imgui.calc_text_size(" ").x
    if space <= 0:
        return ""
    return " " * math.ceil(imgui.calc_text_size(text).x / space)


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


def _draw_nav_tree_lines(
    rails: tuple[bool, ...], left_x: float, row_x: float
) -> None:
    """Connector lines in the gutter of the row just drawn.

    Selectable rects tile with no gap, so stems join up between rows. Each stem
    drops from the center of the parent's twisty, and the arm stops where the
    row's highlight starts. Coordinates land on pixel centers to stay one pixel wide.
    """
    if not rails:
        return
    rect_min = imgui.get_item_rect_min()
    rect_max = imgui.get_item_rect_max()
    line = imgui.get_text_line_height()
    first_stem_x = math.floor(left_x + _nav_indent() * 0.5)
    mid_y = math.floor(_selectable_text_y(rect_min.y) + line * 0.5) + 0.5
    elbow_right_x = row_x - math.floor(imgui.get_style().item_spacing.x * 0.5)
    color = imgui.get_color_u32(rgba(NAVIGATOR_TREE_LINE))
    draw = imgui.get_window_draw_list()
    for x1, y1, x2, y2 in navigator_tree_lines(
        rails,
        first_stem_x + 0.5,
        _nav_indent(),
        elbow_right_x,
        rect_min.y,
        mid_y,
        rect_max.y,
    ):
        draw.add_line(imgui.ImVec2(x1, y1), imgui.ImVec2(x2, y2), color)


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


# Space above and below a segment or combo box, around the row's text line.
_CHOICE_PAD_Y = 1.0
_INLINE_FIELD_WIDTH_FRACTION = 0.6
_SWATCH_ASPECT = 1.6
_SWATCH_GAP = 6.0
_PICKER_UNSET = VALUE
_PICKER_FLAGS = (
    int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.always_auto_resize)
)
_PICKER_COLOUR_FLAGS = (
    int(imgui.ColorEditFlags_.no_alpha)
    | int(imgui.ColorEditFlags_.no_side_preview)
    | int(imgui.ColorEditFlags_.display_hex)
)


class _ImguiTextSizer:
    """Measure text with the current ImGui font for the text fitters."""

    def size(self, text: str) -> tuple[int, int]:
        measured = imgui.calc_text_size(text)
        return math.ceil(measured.x), math.ceil(measured.y)


def path_row_icon(kind: RowKind) -> tuple[str, tuple[int, int, int]] | None:
    """Folder or file glyph, with its accent, in front of a path row's value."""
    spec = row_spec(kind)
    if spec.present_style is not RowPresentStyle.PATH_ICON:
        return None
    if spec.affordance is RowAffordance.PATH_DIR:
        return FOLDER_GLYPH, PRESET_ICON
    return FILE_GLYPH, PRESET_FILE_ICON


def path_icon_color(
    accent: tuple[int, int, int], value_color: tuple[int, int, int]
) -> tuple[int, int, int]:
    """Icon accent, or the value color when the row is dimmed or locked."""
    return value_color if value_color in (DISABLED, LOCKED) else accent


def _draw_path_value(
    x: float,
    y: float,
    right_x: float,
    value: str,
    value_color: tuple[int, int, int],
    icon: tuple[str, tuple[int, int, int]] | None,
) -> None:
    """*value* fitted between *x* and *right_x*, after the row's path icon."""
    draw = imgui.get_window_draw_list()
    if icon is not None:
        glyph, accent = icon
        draw.add_text(
            imgui.ImVec2(x, y + glyph_drop(glyph)),
            imgui.get_color_u32(rgba(path_icon_color(accent, value_color))),
            glyph,
        )
        x += imgui.calc_text_size(f"{glyph} ").x
    draw.add_text(
        imgui.ImVec2(x, y),
        imgui.get_color_u32(rgba(value_color)),
        fit_path_or_name_to_width(_ImguiTextSizer(), value, int(right_x - x)),
    )


def marker_token_spans(markers: str, fitted: str) -> list[tuple[int, int, str]]:
    """``(start, end, token)`` of each marker token visible in *fitted*.

    *fitted* is *markers* cut to width; a cut token keeps its full text so
    its tooltip still names it.
    """
    spans: list[tuple[int, int, str]] = []
    start = 0
    for token in markers.split(" "):
        if start >= len(fitted):
            break
        if token:
            spans.append((start, min(start + len(token), len(fitted)), token))
        start += len(token) + 1
    return spans


def _marker_tooltip_at(markers: str, fitted: str, x: float, y: float) -> None:
    """Tooltip for the marker token under the mouse, on a row the mouse is over."""
    height = imgui.get_text_line_height()
    for start, end, token in marker_token_spans(markers, fitted):
        token_x = x + imgui.calc_text_size(fitted[:start]).x
        token_end = x + imgui.calc_text_size(fitted[:end]).x
        if not imgui.is_mouse_hovering_rect(
            imgui.ImVec2(token_x, y), imgui.ImVec2(token_end, y + height)
        ):
            continue
        text = marker_tooltip(token)
        if text is not None:
            show_tooltip(text)
        return


def _draw_two_line_row_text(
    label: str,
    markers: str,
    value: str,
    parts: list[tuple[str, imgui.ImVec4]],
    label_color: imgui.ImVec4,
    value_color: tuple[int, int, int],
    *,
    lead: str = "",
    icon: tuple[str, tuple[int, int, int]] | None = None,
) -> None:
    """Markers after the label, stopping short of the arrows, and the value below.

    Markers are painted, not part of the selectable label: ImGui hashes the
    visible label into the id, and a press must survive the markers changing.
    *lead* is the drag-handle prefix of the label; the value lines up after it.
    """
    origin_x, origin_y = _selectable_label_origin()
    lead_x = imgui.calc_text_size(lead).x if lead else 0.0
    right_x = imgui.get_item_rect_max().x
    pad = imgui.get_style().frame_padding.x
    sizer = _ImguiTextSizer()
    draw = imgui.get_window_draw_list()
    if markers:
        marker_x = origin_x + imgui.calc_text_size(f"{lead}{label} ").x
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
        if imgui.is_item_hovered():
            _marker_tooltip_at(markers, fitted, marker_x, origin_y)
    _draw_path_value(
        origin_x + lead_x,
        origin_y + imgui.get_text_line_height(),
        right_x - pad,
        value,
        value_color,
        icon,
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

    The section-lock rule matches Left/Right. A row with nothing to edit
    (``RowSpec.available``) has no arrows.
    """
    return (
        row_spec(desc.kind).apply_horizontal is not None
        and not section_lock_blocks_mutation(state, desc)
        and row_available(state, desc)
    )


def panel_border_overlap_px(border_size: float) -> int:
    """Pixels to pull a panel up so its top border shares the rule above.

    The transport rule fills the bar's last *border_size* rows, and a panel
    border fills its first *border_size* rows, so overlapping by the border
    width puts the two strokes on the same rows.
    """
    if border_size <= 0.0:
        return 0
    return max(1, int(round(border_size)))


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


@dataclass(frozen=True)
class TitleButton:
    """An icon button on the inspector title line."""

    id: str
    glyph: str
    enabled: bool
    tooltip: Callable[[], str]


def _draw_inspector_title(
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
    border = _PANEL_BORDER_PX
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
    color = _packed(VALUE)
    fill = _notice_fill(
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
                _packed(HIGHLIGHT),
            )
        finally:
            draw.pop_clip_rect()
        mid = start.x + min(title_w, title_room) * 0.5
        if attention.text_on_fill and bar_x0 + fill_x <= mid < bar_x0 + fill_x + fill_w:
            color = _packed(NOTIFICATION_ON_FILL)
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


def _transport_notice_hovered(chip: tuple[float, float, float, float]) -> bool:
    """True when the pointer is on the toast chip."""
    if not bool(imgui.is_window_hovered()):
        return False
    x, y, width, height = chip
    pos = imgui.get_io().mouse_pos
    return x <= pos.x < x + width and y <= pos.y < y + height


def _transport_notice_clicked(chip: tuple[float, float, float, float]) -> bool:
    """True when this frame's left click landed on the toast chip."""
    if not bool(imgui.get_io().mouse_clicked[0]):
        return False
    return _transport_notice_hovered(chip)


def _stroke_h_rule(
    x0: float,
    x1: float,
    y: float,
    rgb: tuple[int, int, int],
    thickness: float = 1.0,
) -> None:
    """Opaque rule ending on pixel row *y* of the current window.

    *thickness* rows are filled, from ``y - thickness + 1`` down to *y*.

    A stroked line is anti-aliased, so an opaque fill shows through it. A
    filled rectangle is not. The menu rule is drawn on the chrome window,
    above the menu buttons. The transport rule stays on the transport window
    so a later menu popup covers it.
    """
    if x1 <= x0:
        return
    color = imgui.get_color_u32(rgba(rgb))
    imgui.get_window_draw_list().add_rect_filled(
        imgui.ImVec2(x0, y + 1.0 - thickness),
        imgui.ImVec2(x1, y + 1.0),
        color,
    )


def _draw_inspector_divider() -> None:
    """Thin rule across the inspector, shorter than a row; takes no input."""
    height = imgui.get_text_line_height() * _INSPECTOR_DIVIDER_LINES
    origin = imgui.get_cursor_screen_pos()
    x1 = origin.x + imgui.get_content_region_avail().x
    _stroke_h_rule(origin.x, x1, float(int(origin.y + height * 0.5)), INSPECTOR_DIVIDER)
    imgui.dummy(imgui.ImVec2(0.0, height))


def _panel_focus_border_rgba() -> imgui.ImVec4:
    """Highlight colour at the quieter panel focus-outline alpha."""
    return rgba(HIGHLIGHT, PANEL_FOCUS_BORDER_ALPHA / 255.0)


def _fill_rect_border(rect: tuple[int, int, int, int], color_rgba: imgui.ImVec4) -> None:
    """Outline of the panel border width around *rect* on the current window.

    A stroked border is anti-aliased, so the solid rule underneath shows
    through it. Filled edges cover that rule. The focus outline uses the
    quieter focus alpha, so the rule tints the shared edge.
    """
    x, y, w, h = rect
    if w <= 2 * _PANEL_BORDER_PX or h <= 2 * _PANEL_BORDER_PX:
        return
    color = imgui.get_color_u32(color_rgba)
    draw = imgui.get_window_draw_list()
    x0, y0 = float(x), float(y)
    x1, y1 = x0 + float(w), y0 + float(h)
    t = _PANEL_BORDER_PX
    draw.add_rect_filled(imgui.ImVec2(x0, y0), imgui.ImVec2(x1, y0 + t), color)
    draw.add_rect_filled(imgui.ImVec2(x0, y1 - t), imgui.ImVec2(x1, y1), color)
    draw.add_rect_filled(imgui.ImVec2(x0, y0), imgui.ImVec2(x0 + t, y1), color)
    draw.add_rect_filled(imgui.ImVec2(x1 - t, y0), imgui.ImVec2(x1, y1), color)


def _draw_panel_border(
    rect: tuple[int, int, int, int], color_rgba: imgui.ImVec4
) -> None:
    """Outline above the shell windows that share its edges.

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
                _fill_rect_border(rect, color_rgba)
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
    color = imgui.get_color_u32(rgba(ROW_FOCUS_BORDER))
    imgui.get_window_draw_list().add_rect(
        rect_min,
        rect_max,
        color,
        0.0,
        0,
        1.0,
    )


def _drawn_row_rect(left_x: float) -> tuple[int, int, int, int] | None:
    """The item just drawn, from *left_x*, clipped to its window. None when hidden."""
    rect_min = imgui.get_item_rect_min()
    rect_max = imgui.get_item_rect_max()
    window_y = imgui.get_window_pos().y
    top = max(rect_min.y, window_y)
    bottom = min(rect_max.y, window_y + imgui.get_window_height())
    if bottom <= top:
        return None
    return (int(left_x), int(top), int(rect_max.x - left_x), int(bottom - top))


def selectable_wash() -> tuple[imgui.ImVec4, imgui.ImVec4]:
    """Header fill for a selected navigator row or a focused inspector row.

    Both values are that fill, pushed on the header slots so the row keeps it
    under the pointer. Unselected hover stays the theme table.
    """
    fill = rgba(HIGHLIGHT, FOCUS_WASH_ALPHA / 255.0)
    return fill, fill


def _button_text_role(
    enabled: bool, locked: bool, *, page_off: bool
) -> tuple[int, int, int]:
    """Button label colour. A section lock reads as locked, not as disabled.

    A button on a switched-off page still runs, but greys like its rows.
    """
    if locked:
        return LOCKED
    return VALUE if enabled and not page_off else DISABLED


def _hand_on_hover() -> None:
    """Ask for the hand pointer while the item just drawn is hovered."""
    if imgui.is_item_hovered():
        request_pointer(PointerShape.HAND)


def _draw_button(
    label: str, *, text_role: tuple[int, int, int], selected: bool, enabled: bool
) -> bool:
    """A bordered panel button. Returns whether it was clicked.

    A button that is not *enabled* keeps the arrow pointer.
    """
    imgui.push_style_color(imgui.Col_.border, rgba(BUTTON_BORDER))
    imgui.push_style_color(imgui.Col_.text, rgba(text_role))
    imgui.push_style_var(imgui.StyleVar_.frame_border_size, 1.0)
    try:
        clicked = imgui.button(label)
        if enabled:
            _hand_on_hover()
    finally:
        imgui.pop_style_var()
        imgui.pop_style_color(2)
    if selected:
        _draw_item_focus_ring()
    return clicked


@contextmanager
def _selected_header_wash(selected: bool) -> Iterator[None]:
    """Push the focus wash on a selected navigator or inspector row, then pop.

    Hover on an unselected row is the theme table, not a second push.
    """
    if selected:
        hovered, active = selectable_wash()
        imgui.push_style_color(imgui.Col_.header, hovered)
        imgui.push_style_color(imgui.Col_.header_hovered, hovered)
        imgui.push_style_color(imgui.Col_.header_active, active)
    try:
        yield
    finally:
        if selected:
            imgui.pop_style_color(3)


class ShellHost:
    """ImGui shell drawn through an ``ImGuiHost`` on the current GL context."""

    def __init__(
        self,
        imgui_host: ImGuiHost,
        menu_state: MenuBarState,
        controls: Any,
        bar_height: int,
        *,
        strip_pointer: TimelinePointer | None = None,
        preview_menu: ContextMenuProvider | None = None,
        play_menu: ContextMenuProvider | None = None,
        profiler: OverlayProfiler | None = None,
    ) -> None:
        self.imgui = imgui_host
        self._profiler = (
            profiler if profiler is not None else OverlayProfiler(enabled=False)
        )
        self._menu_state = menu_state
        self._controls = controls
        self._strip_pointer = strip_pointer
        self._preview_menu = preview_menu
        self._play_menu = play_menu
        self._menu_bar_height_px = bar_height
        self._dropdown_span: tuple[float, float] | None = None
        # One fitted window per top menu, so a hover onto the next title
        # shows its dropdown at its own size, not the last menu's for a frame.
        self._dropdown_window = FittedWindow("##cleave-menu", remember_keys=True)
        # Top label under the pointer last frame. Hover opens on entry only, so
        # a click that closes a menu is not undone while the pointer stays put.
        self._bar_hover_index: int | None = None
        # Dropdown row under the pointer last frame. Only a move onto a new
        # row takes the highlight, so a resting pointer does not fight the
        # arrow keys.
        self._dropdown_hover_index: int | None = None
        # Drawn navigator list height, applied on the next frame. 0 until measured.
        self._nav_content_height_px = 0
        self._nav_measured_rows = 0
        self._nav_follow = ScrollFollow()
        self._insp_follow = ScrollFollow()
        # Swipes the toast's accent bar under the inspector title when the
        # selection changes.
        self._title_attention = AttentionClock()
        self._layout: ShellLayout | None = None
        self._value_drag_accum = 0.0
        self._value_drag_crossed = False
        self._nudge_swallow = False
        # Held row drag handle (preset list item or layer), or None.
        self._row_drag: RowDragGesture | None = None
        self._inline_field_hovered = False
        self._inline_began = False
        self._transport_drag_accum = 0.0
        self._picker_pos = imgui.ImVec2(0.0, 0.0)
        # This frame's segment or combo rect for each choice row; an open list
        # hangs from its row's rect.
        self._choice_rects: dict[RowDescriptor, tuple[int, int, int, int]] = {}
        # The inspector page's off and locked owners, read each frame.
        self._page_status = PageStatus()
        self._frame_command_ctx: CommandContext | None = None
        self._choice_list_rows: tuple[tuple[int, int, int, int], ...] = ()
        # Widest value each stepped row has shown, in characters, so its arrows
        # hold still as the number changes. The shell font is monospace.
        self._stepper_chars: dict[tuple[RowKind, int], int] = {}
        # Live drag requests. A drag that moves at least 1px persists the stack,
        # help, navigator, or timeline height, then clears these.
        self._insp_width: int | None = None
        self._help_width: int | None = None
        self._navigator_height: int | None = None
        self._timeline_height: int | None = None
        self._splitter: str | None = None
        self._splitter_down = (0.0, 0.0)
        # Pointer distance below the timeline's top edge at the press, so the
        # edge does not jump to the pointer when the drag starts.
        self._timeline_grab_dy = 0.0
        self.transport_notice_clicked = False
        self.top_layer = TopLayer()
        self._context_surface = ContextMenuSurface(lambda: self._controls.context_menu)
        # Navigator row rects from the last draw, for right-click and Shift+F10.
        self._nav_row_rects: dict[str, tuple[int, int, int, int]] = {}
        # Label-click state for ``navigator_label_click``.
        self._nav_opened_by_click: str | None = None
        self._nav_swallow_release: str | None = None
        # Inspector rows with a descriptor from the last draw, the same way.
        self._insp_row_rects: dict[
            RowDescriptor, tuple[tuple[int, int, int, int], InspectorRow]
        ] = {}
        self._context_submenu_surface = ContextSubmenuSurface(self._context_surface)

    @property
    def menu_bar_height_px(self) -> int:
        return self._menu_bar_height_px

    @property
    def nav_content_height_px(self) -> int:
        """Navigator list height for the rows now visible. 0 until measured.

        Rows opened or closed since the last draw are included, so the window
        never lags the tree by a frame.
        """
        if self._nav_content_height_px <= 0:
            return 0
        style = imgui.get_style()
        return navigator_height_for_rows(
            self._nav_content_height_px,
            self._nav_measured_rows,
            len(self._visible_nav_nodes()),
            chrome_px=2.0 * float(style.window_padding.y)
            + float(style.window_border_size),
            spacing_px=padded_row_spacing_y(),
        )

    def _visible_nav_nodes(self) -> tuple[NavNode, ...]:
        return build_navigator(
            self._controls.session, self._controls.shell_focus.nav_expanded
        )

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
    def navigator_height(self) -> int | None:
        """Navigator height requested by an in-progress splitter drag."""
        return self._navigator_height

    @property
    def timeline_height(self) -> int | None:
        """Timeline band height requested by an in-progress splitter drag."""
        return self._timeline_height

    def process_event(self, event: pygame.event.Event) -> None:
        """Mouse motion, buttons, and wheel only. Keys stay out of ImGui."""
        # Host active covers the click before the top layer has drawn the modal.
        if event.type == pygame.WINDOWFOCUSLOST:
            self._cancel_strip_pointer()
            self._clear_strip_hover()
            self._controls.context_menu.close()
            return
        if event.type == pygame.WINDOWLEAVE:
            self._clear_strip_hover()
            return
        if self._modal_has_pointer():
            self._process_modal_event(event)
            return
        imgui_host = self.imgui
        if event.type == pygame.MOUSEMOTION:
            imgui_host.process_mouse_event(event)
            x = float(event.pos[0])
            y = float(event.pos[1])
            self._track_splitter_motion(x, y)
            if self._strip_pointer is not None:
                self._strip_pointer.motion(x, y)
            return
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            if self._page_history_button(event):
                return
            button = mouse_button(event)
            if button is None:
                return
            down = event.type == pygame.MOUSEBUTTONDOWN
            if down:
                x = float(event.pos[0])
                y = float(event.pos[1])
                captured = self.top_layer.captures_pointer(x, y)
                context_menu = self._controls.context_menu
                if context_menu.is_open and not captured:
                    # A press outside an open menu only closes it. A
                    # right-click goes on to open the menu under it.
                    context_menu.close()
                    if button != RIGHT_BUTTON:
                        return
                if button == RIGHT_BUTTON:
                    if not captured:
                        self._assign_shell_region(x, y)
                        self._open_context_menu(x, y)
                    return
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
                    self._press_strip(x, y)
                elif button == MIDDLE_BUTTON and not captured:
                    self._press_strip(x, y, button)
                imgui_host.press_button(button)
            elif button == 0 and self._splitter is not None:
                self._end_splitter_drag(event.pos)
                return
            elif not imgui_host.button_held(button):
                return
            else:
                if button in (0, MIDDLE_BUTTON) and self._strip_pointer is not None:
                    self._strip_pointer.release()
                imgui_host.release_button(button)
            imgui_host.process_mouse_event(event)
            return
        if event.type == pygame.MOUSEWHEEL:
            if not self._wheel_strip(event):
                imgui_host.process_mouse_event(event)

    def _page_history_button(self, event: pygame.event.Event) -> bool:
        """Mouse back and forward buttons step the page history on press.

        A press while a context menu is open only closes the menu.
        """
        step = _PAGE_HISTORY_BUTTONS.get(getattr(event, "button", 0))
        if step is None:
            return False
        if event.type != pygame.MOUSEBUTTONDOWN:
            return True
        context_menu = self._controls.context_menu
        if context_menu.is_open:
            context_menu.close()
            return True
        navigator = self._controls.navigator
        if step < 0:
            navigator.go_back()
        else:
            navigator.go_forward()
        return True

    def process_play_event(self, event: pygame.event.Event) -> None:
        """Mouse while Play Full Screen shows only the visualiser.

        A right-click opens the play menu; a press outside an open menu
        closes it. Nothing else under the pointer acts.
        """
        context_menu = self._controls.context_menu
        if event.type == pygame.WINDOWFOCUSLOST:
            context_menu.close()
            return
        imgui_host = self.imgui
        if event.type == pygame.MOUSEMOTION:
            imgui_host.process_mouse_event(event)
            return
        if event.type not in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            return
        button = mouse_button(event)
        if button is None:
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            x = float(event.pos[0])
            y = float(event.pos[1])
            if self.top_layer.captures_pointer(x, y):
                imgui_host.press_button(button)
                imgui_host.process_mouse_event(event)
                return
            context_menu.close()
            if button == RIGHT_BUTTON and self._play_menu is not None:
                context_menu.open(self._play_menu, (x, y))
            return
        if imgui_host.button_held(button):
            imgui_host.release_button(button)
            imgui_host.process_mouse_event(event)

    def draw_play_frame(self, dt: float) -> None:
        """One ImGui frame for Play Full Screen: only an open context menu."""
        self.imgui.begin_frame(dt)
        try:
            if self._controls.context_menu.is_open:
                self.top_layer.push(self._context_surface)
                self.top_layer.push(self._context_submenu_surface)
            self.top_layer.draw()
            self.draw_profiler_panel((0, 0))
        finally:
            self.end_imgui_frame()

    def draw_profiler_panel(self, origin: tuple[int, int] | None = None) -> None:
        """Draw the frame timer while it is on, at *origin* or the visualiser."""
        if not self._profiler.enabled:
            return
        if origin is None:
            layout = self._layout
            origin = (0, 0) if layout is None else layout.visualiser[:2]
        draw_profiler_panel(self._profiler.report, origin)

    def end_imgui_frame(self) -> None:
        with self._profiler.time_section("ui_render"):
            self.imgui.end_frame()

    def _open_context_menu(self, x: float, y: float) -> None:
        """Open the menu for whatever sits under (*x*, *y*), if it has one."""
        provider = self._context_menu_at(x, y)
        if provider is None:
            return
        self._menu_state.blur()
        self._controls.context_menu.open(provider, (x, y))

    def _context_menu_at(self, x: float, y: float) -> ContextMenuProvider | None:
        pointer = self._strip_under(x, y)
        if pointer is not None:
            provider = pointer.context_menu_at(x, y)
            if provider is not None:
                self._cancel_strip_pointer()
            return provider
        layout = self._layout
        if layout is not None and _rect_contains(layout.inspector, x, y):
            return self._inspector_menu_at(x, y)
        if layout is not None and _rect_contains(layout.visualiser, x, y):
            return self._preview_menu
        if layout is None or not _rect_contains(layout.navigator, x, y):
            return None
        node_id = self._nav_row_at(x, y)
        if node_id is None:
            return None
        self._controls.navigator.select(node_id)
        return self._nav_menu(node_id)

    def open_focus_context_menu(self) -> bool:
        """Open the focused item's menu (Shift+F10, Menu key). False when it has none."""
        found = self._focus_context_menu()
        if found is None:
            return False
        provider, anchor = found
        self._menu_state.blur()
        self._controls.context_menu.open(provider, anchor, keyboard=True)
        return self._controls.context_menu.is_open

    def _focus_context_menu(
        self,
    ) -> tuple[ContextMenuProvider, tuple[float, float]] | None:
        region = self._controls.shell_focus.region
        if region is ShellRegion.TIMELINE:
            pointer = self._strip_pointer
            if pointer is None or not self._strip_has_scope():
                return None
            row = self._controls.session.timeline.focus_row
            anchor = pointer.row_menu_anchor(row)
            if anchor is None:
                return None
            return pointer.row_menu(row), anchor
        if region is ShellRegion.NAVIGATOR:
            node_id = self._controls.shell_focus.selected_id
            rect = self._nav_row_rects.get(node_id)
            if rect is None:
                return None
            x, y, _w, h = rect
            return self._nav_menu(node_id), (float(x), float(y + h))
        if region is ShellRegion.INSPECTOR:
            desc = self._controls.shell_focus.inspector_cursor
            found = self._insp_row_rects.get(desc) if desc is not None else None
            provider = self._inspector_menu(desc) if desc is not None else None
            if found is None or provider is None:
                return None
            (x, y, _w, h), _row = found
            return provider, (float(x), float(y + h))
        if region is ShellRegion.PREVIEW:
            layout = self._layout
            if layout is None or self._preview_menu is None:
                return None
            x, y, _w, _h = layout.visualiser
            return self._preview_menu, (float(x), float(y))
        return None

    def _inspector_menu_at(self, x: float, y: float) -> ContextMenuProvider | None:
        """The menu for the inspector row under (*x*, *y*); the row takes focus."""
        for desc, (rect, row) in self._insp_row_rects.items():
            if not _rect_contains(rect, x, y):
                continue
            provider = self._inspector_menu(desc)
            if provider is not None:
                self._controls.inspector.focus_row(row)
            return provider
        return None

    def _inspector_menu(self, desc: RowDescriptor) -> ContextMenuProvider | None:
        if desc.kind in PRESET_MENU_KINDS:
            return preset_row_menu(self._controls, desc)
        return None

    def _nav_menu(self, node_id: str) -> ContextMenuProvider:
        return navigator_node_menu(self._controls, node_id, self._toggle_nav_expanded)

    def _nav_row_at(self, x: float, y: float) -> str | None:
        """Navigator row under a screen point, from the last draw."""
        for node_id, rect in self._nav_row_rects.items():
            if _rect_contains(rect, x, y):
                return node_id
        return None

    def _strip_under(self, x: float, y: float) -> TimelinePointer | None:
        """The strip pointer when (*x*, *y*) is on the open strip."""
        pointer = self._strip_pointer
        layout = self._layout
        if pointer is None or layout is None:
            return None
        if not self._controls.session.timeline.panel_open:
            return None
        if layout.timeline[3] > 0 and _rect_contains(layout.timeline, x, y):
            return pointer
        return None

    def _press_strip(self, x: float, y: float, button: int = 0) -> None:
        """Press on the open strip: focus a row, select a cue, seek, or pan."""
        pointer = self._strip_under(x, y)
        if pointer is not None:
            pointer.press(x, y, button)

    def _wheel_strip(self, event: pygame.event.Event) -> bool:
        """Wheel over the open strip zooms or pans it. False leaves it to ImGui."""
        pos = self.imgui.mouse_pos
        if pos is None:
            return False
        x, y = pos
        if self.top_layer.captures_pointer(x, y):
            return False
        pointer = self._strip_under(x, y)
        if pointer is None:
            return False
        shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        pointer.wheel(x, float(event.x), float(event.y), shift=shift)
        return True

    def _cancel_strip_pointer(self) -> None:
        if self._strip_pointer is not None:
            self._strip_pointer.cancel()

    def _clear_strip_hover(self) -> None:
        if self._strip_pointer is not None:
            self._strip_pointer.clear_hover()

    def _process_modal_event(self, event: pygame.event.Event) -> None:
        """Forward the pointer to ImGui. The shell takes no region or splitter."""
        self._cancel_splitter_drag()
        self._cancel_strip_pointer()
        self._clear_strip_hover()
        self._controls.disarm_value_nudge()
        imgui_host = self.imgui
        if event.type == pygame.MOUSEMOTION:
            imgui_host.process_mouse_event(event)
            modal_host = getattr(self._controls, "modal_host", None)
            if modal_host is not None and modal_host.active:
                modal_host.note_pointer_motion(event)
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
        """A click chooses navigator, inspector, the preview, or the open strip.

        Menu, transport, and help leave the region alone. A miss when no
        layout is stored does nothing. The strip stays open.
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
        if _rect_contains(layout.visualiser, x, y):
            self._controls.set_shell_region(ShellRegion.PREVIEW)

    def _splitter_at(self, x: float, y: float) -> str | None:
        layout = self._layout
        if layout is None:
            return None
        return splitter_hit(layout, x, y)

    def _assign_splitter_request(
        self, which: str, pointer: tuple[float, float]
    ) -> None:
        layout = self._layout
        if layout is None:
            return
        if which == "nav":
            self._navigator_height = splitter_request_height(layout, pointer[1])
            return
        if which == "timeline":
            self._timeline_height = splitter_request_timeline_height(
                layout, pointer[1] - self._timeline_grab_dy
            )
            return
        width = splitter_request_width(layout, which, pointer[0])
        if which == "help":
            self._help_width = width
        elif which == "insp":
            self._insp_width = width

    def _begin_splitter_drag(self, pos: tuple[float, float]) -> bool:
        which = self._splitter_at(float(pos[0]), float(pos[1]))
        if which is None:
            return False
        self._splitter = which
        self._splitter_down = (float(pos[0]), float(pos[1]))
        layout = self._layout
        self._timeline_grab_dy = (
            float(pos[1]) - float(layout.timeline[1])
            if which == "timeline" and layout is not None
            else 0.0
        )
        return True

    def _end_splitter_drag(self, pos: tuple[float, float]) -> None:
        which = self._splitter
        pointer = (float(pos[0]), float(pos[1]))
        axis = 1 if which in ("nav", "timeline") else 0
        moved = abs(pointer[axis] - self._splitter_down[axis]) >= 1.0
        if which == "timeline" and moved:
            self._assign_splitter_request(which, pointer)
            if self._timeline_height is not None:
                self._controls.settings.set_timeline_height(
                    self._drawn_timeline_height(self._timeline_height)
                )
            self._timeline_height = None
        elif which == "nav" and moved:
            self._assign_splitter_request(which, pointer)
            if self._navigator_height is not None:
                self._controls.settings.set_navigator_height(
                    self._navigator_height
                )
            self._navigator_height = None
        elif which is not None and moved:
            self._assign_splitter_request(which, pointer)
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

    def _drawn_timeline_height(self, requested: int) -> int:
        """Saved timeline height for *requested*: 0 at the fit, else the clamp."""
        layout = self._layout
        if layout is None:
            return requested
        rows = len(self._controls.session.layer_z_order)
        fit_h = timeline_band_height_px(rows)
        top_h = layout.menu[3] + layout.transport[3]
        display_h = layout.timeline[1] + layout.timeline[3]
        height = clamp_timeline_band_height(
            requested, fit_h, display_h=display_h, top_h=top_h
        )
        return 0 if height <= fit_h else height

    def _cancel_splitter_drag(self) -> None:
        self._splitter = None
        self._navigator_height = None
        self._timeline_height = None

    def _track_splitter_motion(self, x: float, y: float) -> None:
        if self._splitter is not None:
            self._assign_splitter_request(self._splitter, (x, y))

    def _request_gesture_pointer(self) -> None:
        """Pointer for the strip, a live drag, and the splitters.

        Called after the shell windows, so these win over a widget's request.
        A modal or top-layer surface under the pointer keeps its own.
        """
        mouse = imgui.get_mouse_pos()
        if self._modal_has_pointer() or self.top_layer.captures_pointer(
            float(mouse.x), float(mouse.y)
        ):
            return
        if self._controls.context_menu.is_open:
            # A press outside the open menu only closes it.
            return
        shape = self._strip_pointer_shape()
        if self._row_drag is not None:
            shape = PointerShape.MOVE
        elif self._value_drag_crossed and imgui.is_mouse_down(0):
            shape = PointerShape.RESIZE_EW
        splitter = self._splitter
        if splitter is None and not imgui.is_mouse_down(0):
            splitter = self._splitter_at(float(mouse.x), float(mouse.y))
        if splitter is not None:
            shape = (
                PointerShape.RESIZE_NS
                if splitter in ("nav", "timeline")
                else PointerShape.RESIZE_EW
            )
        if shape is not None:
            request_pointer(shape)
        if splitter is None and self._row_drag is None:
            self._show_strip_tooltip()

    def _show_strip_tooltip(self) -> None:
        """Say what a row header button does on click."""
        pointer = self._strip_pointer
        if pointer is None or pointer.scrubbing or pointer.panning:
            return
        if imgui.is_any_mouse_down():
            return
        session = self._controls.session
        timeline = session.timeline
        hover = timeline.strip_hover
        if not timeline.panel_open or hover is None:
            return
        target, row = hover
        if target not in ("arm", "solo", "eye", "release") or row is None:
            return
        z_order = session.layer_z_order
        if not 0 <= row < len(z_order):
            return
        slot = z_order[row]
        if target == "arm":
            text = strip_arm_tooltip(
                armed=slot in timeline.armed_slots,
                locked=timeline.locked,
            )
        elif target == "solo":
            text = strip_solo_tooltip(solo=session.solo_slot == slot)
        elif target == "release":
            if slot not in timeline.override_slots:
                return
            text = strip_release_tooltip(recording=bool(timeline.recording))
        elif target == "eye":
            text = strip_eye_tooltip(
                overridden=slot in timeline.override_slots,
                recording=bool(timeline.recording),
                armed=slot in timeline.armed_slots,
            )
        else:
            return
        show_tooltip(text)

    def _strip_pointer_shape(self) -> PointerShape | None:
        """Hand over a strip button, left-right over the ruler, a scrub, or a clip edge, move over a clip."""
        pointer = self._strip_pointer
        if pointer is None:
            return None
        timeline = self._controls.session.timeline
        if not timeline.panel_open:
            return None
        if pointer.panning:
            return PointerShape.MOVE
        if pointer.scrubbing or pointer.over_ruler or pointer.scrollbar_active:
            return PointerShape.RESIZE_EW
        # A clip body moves and a clip edge trims, where clips can be edited.
        clip_gesture = pointer.clip_gesture
        if clip_gesture == "trim":
            return PointerShape.RESIZE_EW
        if clip_gesture == "move":
            return PointerShape.MOVE
        if pointer.hover_pressable:
            return PointerShape.HAND
        return None

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
        self._frame_command_ctx = command_ctx
        if self._nudge_input_blocked():
            self._controls.disarm_value_nudge()
        with _menu_bar_frame_padding():
            self._menu_bar_height_px = max(
                1, int(round(imgui.get_frame_height()))
            )
            rule_y, anchors, menus = self._draw_bar(menu_state)
        if menu_state.dropdown_open:
            # Opening a context menu blurs the bar, so both open together
            # only when the bar just opened. The dropdown wins.
            self._controls.context_menu.close()
        if self._layout is not None:
            self._draw_shell(menu_state, readout, notice)
        popup_hovered = False
        self._dropdown_span = None
        if menu_state.dropdown_open and menus:
            popup_hovered = self._draw_dropdown(
                menu_state, command_ctx, menus, anchors
            )
        if imgui.is_mouse_clicked(0) and not popup_hovered:
            mouse = imgui.get_mouse_pos()
            in_bar = 0.0 <= mouse.y < float(self._menu_bar_height_px)
            if not in_bar:
                menu_state.blur()
        if self._controls.context_menu.is_open:
            self.top_layer.push(self._context_surface)
            self.top_layer.push(self._context_submenu_surface)
        self._request_gesture_pointer()
        self._release_value_drag()
        self._release_nudge_swallow()
        return rule_y

    def draw_chrome(self, menu_state: MenuBarState, rule_y: float | None) -> None:
        """Menu rule, above the shell windows.

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
                        _stroke_h_rule(
                            0.0, display.x, rule_y, TRANSPORT_RULE, _PANEL_BORDER_PX
                        )
                        span = self._dropdown_span
                        if span is not None:
                            # The popup's top border sits on this row.
                            _stroke_h_rule(
                                span[0], span[1], rule_y, BORDER_COLOR, _PANEL_BORDER_PX
                            )
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
        self._inline_field_hovered = False
        self._inline_began = False
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
            if layout.timeline[3] > 0:
                # The strip has no ImGui window, so its container outline is
                # drawn here, sharing the rule under the columns above it.
                _draw_panel_border(
                    _overlap_panel(layout.timeline, overlap),
                    _panel_focus_border_rgba()
                    if stop is CycleStop.TIMELINE
                    else rgba(NAVIGATOR_BORDER),
                )
            if stop is CycleStop.NAVIGATOR:
                _draw_panel_border(navigator, _panel_focus_border_rgba())
            elif stop is CycleStop.INSPECTOR:
                _draw_panel_border(inspector, _panel_focus_border_rgba())
            elif stop is CycleStop.PREVIEW:
                _draw_panel_border(
                    _overlap_panel(layout.visualiser, overlap),
                    _panel_focus_border_rgba(),
                )
        finally:
            style.window_min_size = imgui.ImVec2(saved_min_x, saved_min_y)
        inline = self._controls.inline_edit
        # A click outside the open text field keeps the edit. The click that
        # opened a transport field this frame is not one.
        if (
            inline.text_target is not None
            and imgui.is_mouse_clicked(0)
            and not self._inline_field_hovered
            and not self._inline_began
        ):
            inline.finish()

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
            # ImGui centres a thick window border on a half pixel, which
            # blurs it; hide that stroke and fill the edges instead.
            alpha = PANEL_FOCUS_BORDER_ALPHA / 255.0 if active else 1.0
            imgui.push_style_color(imgui.Col_.border, rgba(border, 0.0))
        try:
            _visible, _opened = imgui.begin(
                title,
                None,
                shell_window_flags(_SHELL_FLAGS, scrollable=scrollable),
            )
            try:
                if scrollable:
                    _draw_padded_scroll_body(body)
                else:
                    body()
                if border is not None:
                    draw = imgui.get_window_draw_list()
                    draw.push_clip_rect(
                        imgui.ImVec2(float(x), float(y)),
                        imgui.ImVec2(float(x + w), float(y + h)),
                        False,
                    )
                    try:
                        _fill_rect_border(rect, rgba(border, alpha))
                    finally:
                        draw.pop_clip_rect()
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
        modal_host = getattr(self._controls, "modal_host", None)
        modal_help = () if modal_host is None else modal_host.help_sections()

        def body() -> None:
            if modal_help:
                draw_help_column(modal_help_content(modal_help))
                return
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

        panel = _overlap_panel(rect, overlap)
        self._draw_fixed_window(
            _HELP_WINDOW,
            panel,
            active=False,
            idle_border=NAVIGATOR_BORDER,
            body=body,
            scrollable=True,
        )
        if modal_help:
            # A form's help stays bright above the scrim, under the modal.
            self.top_layer.lift(_HELP_WINDOW, panel)

    def _draw_transport(
        self,
        readout: TransportReadout,
        notice: PanelNotificationActive | None,
    ) -> None:
        for index, part in enumerate(transport_parts(readout)):
            if index:
                gap = ui_chrome_px(_TRANSPORT_GAP) if part.gap else 0.0
                imgui.same_line(0.0, gap)
            self._draw_transport_part(part)
        fps = transport_fps_text(readout)
        width = imgui.calc_text_size(fps).x
        avail = imgui.get_window_width()
        pad = imgui.get_style().window_padding.x
        imgui.same_line(max(imgui.get_cursor_pos_x(), avail - width - pad))
        imgui.text_colored(rgba(VALUE), fps)
        line = None if notice is None else transport_notice(notice)
        if line is not None:
            chip = _draw_transport_notice(line)
            if line.timed and chip is not None:
                if _transport_notice_hovered(chip):
                    request_pointer(PointerShape.HAND)
                if _transport_notice_clicked(chip):
                    self.transport_notice_clicked = True
        origin = imgui.get_window_pos()
        size = imgui.get_window_size()
        _stroke_h_rule(
            origin.x,
            origin.x + size.x,
            origin.y + size.y - 1.0,
            TRANSPORT_RULE,
            _PANEL_BORDER_PX,
        )

    def _draw_transport_part(self, part: TransportPart) -> None:
        """One transport part, a space wider than its text for the hover fill.

        Play and pause toggle on click. The time and the bar step while
        dragged sideways and open a text field on double-click.
        """
        space = imgui.calc_text_size(" ").x
        line = imgui.get_text_line_height()
        text_w = imgui.calc_text_size(part.label).x
        field = part.field
        inline = self._controls.inline_edit
        if field is not None and inline.text_target is field:
            template = _TRANSPORT_FIELD_TEMPLATE[field]
            width = max(text_w, imgui.calc_text_size(template).x) + space
            imgui.dummy(imgui.ImVec2(width, line))
            view = inline.text_view()
            if view is not None:
                self._paint_inline_field(
                    imgui.get_item_rect_min(), imgui.get_item_rect_max(), view
                )
            return
        imgui.dummy(imgui.ImVec2(text_w + space, line))
        origin = imgui.get_item_rect_min()
        box = text_box(origin.x, text_w, space, row_band(origin.y))
        if field is None or self._nudge_input_blocked():
            self._paint_transport_text(part, box, hovered=False)
            return
        pointer = (
            PointerShape.HAND if field is TransportField.PLAY else PointerShape.RESIZE_EW
        )
        state = box_button(f"##transport-{field.value}", box, pointer=pointer)
        self._paint_transport_text(part, box, hovered=state.hovered or state.held)
        if state.held:
            request_pointer(pointer)
        transport = self._controls.transport
        if field is TransportField.PLAY:
            if state.pressed:
                transport.toggle_pause()
            return
        if state.activated:
            self._transport_drag_accum = 0.0
            transport.begin_drag(field)
        if state.held:
            steps, self._transport_drag_accum = value_drag_steps(
                self._transport_drag_accum + float(imgui.get_io().mouse_delta.x),
                _VALUE_DRAG_THRESHOLD_PX,
            )
            transport.drag_step(field, steps)
        if state.released:
            transport.end_drag()
        if state.hovered and imgui.is_mouse_double_clicked(0):
            transport.end_drag()
            transport.begin_entry(field)
            self._inline_began = True

    def _paint_transport_text(
        self,
        part: TransportPart,
        box: tuple[float, float, float, float],
        *,
        hovered: bool,
    ) -> None:
        """The part's icon and text, centred in *box*, on the wash when hovered."""
        color = part.color
        if hovered:
            paint_wash(box)
            color = NUDGE_HOVER_FG
        draw = imgui.get_window_draw_list()
        u32 = imgui.get_color_u32(rgba(color))
        x = glyph_x(box, imgui.calc_text_size(part.label).x)
        y = text_top(box)
        if part.icon:
            draw.add_text(imgui.ImVec2(x, y + glyph_drop(part.icon[0])), u32, part.icon)
            x += imgui.calc_text_size(f"{part.icon} ").x
        draw.add_text(imgui.ImVec2(x, y), u32, part.text)

    def _draw_navigator(self) -> None:
        imgui.push_style_color(imgui.Col_.text, rgba(LABEL))
        try:
            with padded_rows():
                nodes = self._visible_nav_nodes()
                self._nav_row_rects = {}
                for node, rails in zip(nodes, navigator_tree_rails(nodes)):
                    self._draw_nav_node(node, rails)
                self._nav_content_height_px = _navigator_content_height_px()
        finally:
            imgui.pop_style_color()
        self._finish_row_drag(DRAG_LAYER)
        self._nav_measured_rows = len(nodes)

    def _draw_nav_node(self, node: NavNode, rails: tuple[bool, ...]) -> None:
        focus = self._controls.shell_focus
        # One icon column per level, so a child's twisty sits under its
        # parent's label and the stem from the parent's twisty has an arm.
        indent = node.depth * _nav_indent()
        left_x = imgui.get_cursor_screen_pos().x
        if indent:
            imgui.indent(indent)
        try:
            selected = node.id == focus.selected_id
            ring = (
                selected
                and focus.region is ShellRegion.NAVIGATOR
                and not self._menu_state.focused
            )
            twisty = navigator_twisty(node, focus.nav_expanded)
            row_x = imgui.get_cursor_screen_pos().x
            if twisty is not None:
                # The label starts right after the twisty's column, with no
                # item gap. The twisty draws over that column once the row is done.
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + _nav_indent())
            with _selected_header_wash(selected):
                moving = (
                    node.draggable
                    and node.slot is not None
                    and node.slot == self._controls.layer_lifecycle.move_mode_slot
                )
                text_color = navigator_row_text_color(
                    node, selected=selected, moving=moving
                )
                bright = text_color != LABEL
                if bright:
                    imgui.push_style_color(imgui.Col_.text, rgba(text_color))
                try:
                    text_pos = imgui.get_cursor_screen_pos()
                    label = node.label
                    lead = ""
                    if node.draggable:
                        handle_text = nav_handle_text(node)
                        # The handle draws its part of the label itself.
                        lead = _nav_drag_lead() + _space_lead(handle_text)
                        label = label[len(handle_text):]
                    overlap = (
                        bool(node.toggles) or node.draggable or twisty is not None
                    )
                    clicked, _selected = imgui.selectable(
                        f"{lead}{label}##nav-{node.id}",
                        selected,
                        imgui.SelectableFlags_.allow_overlap if overlap else 0,
                    )
                    double_pressed = (
                        imgui.is_item_activated() and imgui.is_mouse_double_clicked(0)
                    )
                    label_min_x = imgui.get_item_rect_min().x
                    span = (imgui.get_item_rect_min().y, imgui.get_item_rect_max().y)
                    row_right_x = imgui.get_item_rect_max().x
                    self._record_nav_row_rect(node.id, left_x)
                    if ring:
                        _draw_item_focus_ring()
                    if selected:
                        self._nav_follow.follow(node.id)
                finally:
                    if bright:
                        imgui.pop_style_color()
            _draw_nav_tree_lines(rails, left_x, left_x + indent)
            mark = navigator_lock_mark(node)
            if mark is not None:
                _draw_nav_lock_mark(text_pos, node.label, mark)
            if node.badge:
                _draw_item_suffix(node.badge, rgba(LABEL))
            if node.toggles:
                self._draw_nav_toggles(node, row_right_x, span)
            if node.draggable:
                self._layer_row_drag(node, text_pos.x, span, text_color)
            twisty_clicked = twisty is not None and _draw_nav_twisty(
                node, twisty, selected, row_x, label_min_x, span
            )
            if twisty_clicked:
                self._nav_opened_by_click = None
                self._toggle_nav_expanded(node.id)
            elif clicked or double_pressed:
                self._nav_label_click(node, clicked, double_pressed)
        finally:
            if indent:
                imgui.unindent(indent)

    def _nav_label_click(
        self, node: NavNode, clicked: bool, double_pressed: bool
    ) -> None:
        outcome = navigator_label_click(
            self._controls.cfg.editor.navigator_expand_click,
            node.id,
            expandable=node.expandable,
            expanded=node.id in self._controls.shell_focus.nav_expanded,
            clicked=clicked,
            double_pressed=double_pressed,
            opened_by_click=self._nav_opened_by_click,
            swallowing=self._nav_swallow_release == node.id,
        )
        self._nav_opened_by_click = outcome.opened_by_click
        if clicked:
            self._nav_swallow_release = None
        if outcome.swallow_release:
            self._nav_swallow_release = node.id
        if outcome.select:
            self._controls.navigator.select(node.id)
        if outcome.toggle:
            self._toggle_nav_expanded(node.id)

    def _record_nav_row_rect(self, node_id: str, left_x: float) -> None:
        """Remember the row just drawn, for right-click and Shift+F10."""
        rect = _drawn_row_rect(left_x)
        if rect is not None:
            self._nav_row_rects[node_id] = rect

    def _draw_nav_toggles(
        self, node: NavNode, row_right_x: float, band: tuple[float, float]
    ) -> None:
        """Icon buttons at the right of the row just drawn.

        The row selectable allows overlap, so a press here reaches the button
        and not the label. It selects the row but never opens or closes it. A
        blocked toggle has no hover fill, and a press on it only selects.
        """
        descriptor = node_control_descriptor(node.id)
        if descriptor is None and not node.toggles:
            return
        xs = navigator_toggle_xs(
            row_right_x - imgui.get_style().frame_padding.x,
            row_band_side(),
            icon_gap(),
        )
        for toggle in node.toggles:
            pressed = icon_button(
                f"##nav-toggle-{node.id}-{toggle.id}",
                navigator_toggle_glyph(toggle),
                xs[toggle.id],
                band,
                color=navigator_toggle_color(toggle),
                fill=navigator_toggle_fill(toggle),
                # A blocked toggle keeps its state readable at half strength.
                fill_alpha=0.5 if toggle.blocked else 1.0,
                enabled=not toggle.blocked,
                inert=toggle.inert,
                tooltip=lambda toggle=toggle: navigator_toggle_tooltip(toggle),
            ).pressed
            if pressed:
                self._controls.navigator.select(node.id)
                if toggle.blocked:
                    continue
                if toggle.id == TOGGLE_ADD:
                    command_by_id("layers.add").run(self._controls)
                else:
                    activate_header_toggle(self._controls, toggle.id, descriptor)

    def _toggle_nav_expanded(self, node_id: str) -> None:
        focus = self._controls.shell_focus
        if node_id not in focus.nav_expanded:
            focus.nav_expanded.add(node_id)
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
        row_slot = timeline_row_slot_of(focus.selected_id)
        title = (
            inspector_title(nodes, focus.selected_id)
            if row_slot is None
            else timeline_row_title(self._controls.session, row_slot)
        )
        self._page_status = page_status(self._controls.session, focus.selected_id)
        # A new clip on the same strip row is new content, so it swipes too.
        clip_serial = self._controls.session.timeline.selected_clip_serial
        attention_key = (
            focus.selected_id if row_slot is None else (focus.selected_id, clip_serial)
        )
        # With the highlight off, the title draws as if its swipe has ended.
        elapsed = (
            self._title_attention.elapsed(attention_key)
            if self._controls.cfg.editor.highlight_new_page
            else math.inf
        )
        pressed = _draw_inspector_title(
            title,
            elapsed,
            page_status_marks(self._page_status),
            self._page_history_buttons(),
        )
        if pressed == _TITLE_BACK:
            self._controls.navigator.go_back()
        elif pressed == _TITLE_FORWARD:
            self._controls.navigator.go_forward()
        _draw_inspector_divider()
        self._choice_rects = {}
        self._insp_row_rects = {}
        with padded_rows():
            for row in build_inspector_rows(state, focus.selected_id):
                if row.divider:
                    _draw_inspector_divider()
                    continue
                self._draw_inspector_row(state, row)
        self._finish_row_drag(DRAG_PRESET)
        self._draw_colour_picker()
        self._draw_choice_list()

    def _page_history_buttons(self) -> tuple[TitleButton, TitleButton]:
        """Back and Forward arrows for the inspector title line."""
        controls = self._controls
        can_show = controls.navigator.page_filter()
        history = controls.page_history
        back_id = history.peek_back(can_show)
        forward_id = history.peek_forward(can_show)
        session = controls.session
        expanded = controls.shell_focus.nav_expanded

        def tooltip(page_id: str | None, *, forward: bool) -> Callable[[], str]:
            def text() -> str:
                title = None if page_id is None else page_title(session, expanded, page_id)
                return page_history_tooltip(title, forward=forward)

            return text

        return (
            TitleButton(
                _TITLE_BACK,
                ARROW_BACK_GLYPH,
                back_id is not None,
                tooltip(back_id, forward=False),
            ),
            TitleButton(
                _TITLE_FORWARD,
                ARROW_FORWARD_GLYPH,
                forward_id is not None,
                tooltip(forward_id, forward=True),
            ),
        )

    def _draw_inspector_row(self, state: Any, row: Any) -> None:
        focus = self._controls.shell_focus
        indent = row.depth * ui_chrome_px(_INSPECTOR_INDENT)
        if indent:
            imgui.indent(indent)
        try:
            if row.command_ids:
                self._draw_command_row(row)
                return
            desc = row.descriptor
            kind = desc.kind
            spec = row_spec(kind)
            label = row_label(state, desc)
            list_item = spec.present_style is RowPresentStyle.LIST_ITEM
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
            lead = _drag_lead() if spec.drag_reorder else ""
            imgui.push_style_color(imgui.Col_.text, rgba(label_color))
            try:
                with _selected_header_wash(selected):
                    text_x = imgui.get_cursor_screen_pos().x
                    clicked, _selected = imgui.selectable(
                        f"{lead}{label}{inspector_selectable_id(desc)}",
                        selected,
                        imgui.SelectableFlags_.allow_overlap if lead else 0,
                        imgui.ImVec2(0.0, row_height),
                    )
                    span = (
                        imgui.get_item_rect_min().y,
                        imgui.get_item_rect_max().y,
                    )
                    rect = _drawn_row_rect(text_x)
                    if rect is not None:
                        self._insp_row_rects[desc] = (rect, row)
                    # Item flags are only valid while this selectable is current.
                    # Release clears the active id inside the widget, so the
                    # frame the button comes up is deactivated, not active.
                    activated = imgui.is_item_activated()
                    active = imgui.is_item_active()
                    released = imgui.is_item_deactivated()
                    if selected:
                        _draw_item_focus_ring()
                        self._insp_follow.follow((focus.selected_id, desc))
            finally:
                imgui.pop_style_color()
            value = format_row_value(state, desc) if spec.format_value else ""
            stepped = inspector_row_stepped(state, desc)
            if spec.shows_dirty_suffix and state.config_dirty:
                value = f"{value}*" if value else "*"
            cluster = format_row_position(state, desc) if two_line else value
            inline = self._controls.inline_edit
            if inline.text_target == desc:
                self._draw_inline_field(inline.text_view())
                return
            labels = (
                spec.choice.labels()
                if spec.choice is not None and not two_line
                else ()
            )
            if labels:
                self._draw_choice_value(
                    state,
                    row,
                    desc,
                    labels,
                    value,
                    enabled=stepped,
                    tone=choice_tone(value_color),
                    activated=activated,
                    after_label=label if list_item else None,
                )
                cluster = ""
            elif stepped and cluster and not two_line:
                cluster = self._fixed_width_value(kind, cluster)
            icon = path_row_icon(kind)
            if icon is not None and not two_line:
                origin_x, origin_y = _selectable_label_origin()
                if label:
                    origin_x += imgui.calc_text_size(f"{lead}{label} ").x
                _draw_path_value(
                    origin_x,
                    origin_y,
                    imgui.get_item_rect_max().x - imgui.get_style().frame_padding.x,
                    cluster,
                    value_color,
                    icon,
                )
                cluster = ""
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
                        value_color,
                        lead=lead,
                        icon=icon,
                    )
                if spec.nav_buttons and not list_item:
                    self._handle_nav_buttons(
                        state,
                        row,
                        desc,
                        label,
                        spec.nav_buttons,
                        rgba(value_color),
                        stepped=stepped,
                        activated=activated,
                        two_line=two_line,
                    )
                if self._handle_colour_swatch(state, row, desc, spec, parts, clicked):
                    return
                if stepped:
                    self._handle_value_nudge(
                        row,
                        desc,
                        parts,
                        repeatable=spec.repeatable,
                        activated=activated,
                        two_line=two_line,
                        hand=not row_inert(state, desc),
                    )
            if spec.nav_buttons and list_item:
                self._handle_nav_buttons(
                    state,
                    row,
                    desc,
                    None,
                    spec.nav_buttons,
                    rgba(value_color),
                    stepped=stepped,
                    activated=activated,
                    two_line=two_line,
                )
            if lead:
                self._preset_row_drag(
                    row,
                    desc,
                    text_x,
                    span,
                    blocked=section_lock_blocks_mutation(state, desc),
                )
            if stepped and not labels and not self._nudge_swallow:
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

    def _draw_drag_handle(
        self,
        item_id: str,
        x: float,
        band: tuple[float, float],
        *,
        blocked: bool,
        lead: str,
        text: str = "",
        text_color: tuple[int, int, int] = LABEL,
    ) -> bool:
        """Leading reorder handle on the row just drawn, with its left edge at *x*.

        The glyph fills the *lead* column. *text*, the start of the row's label,
        follows it inside the handle, so it washes and takes the press too; it
        keeps *text_color* until hovered. The row selectable allows overlap, so
        the press reaches this button. True on the press that starts a drag; a
        blocked handle never starts one.
        """
        glyph_column = imgui.calc_text_size(lead).x
        text_w = imgui.calc_text_size(_space_lead(text)).x
        box = text_box(x, glyph_column + text_w, 0.0, band)
        state = box_button(
            item_id,
            box,
            pointer=PointerShape.NOT_ALLOWED if blocked else PointerShape.MOVE,
        )
        lit = not blocked and (state.hovered or state.held)
        glyph_box = (box[0], box[1], glyph_column, box[3])
        paint_box(
            glyph_box,
            DRAG_INDICATOR_GLYPH,
            color=LOCKED if blocked else MUTED,
            hovered=lit,
        )
        if text:
            label_box = (box[0] + glyph_column, box[1], text_w, box[3])
            paint_box(label_box, text, color=text_color, hovered=lit, icon=False)
        if state.hovered and not state.held:
            show_tooltip("Locked: unlock to reorder" if blocked else "Drag to reorder")
        return state.activated and not blocked

    def _preset_row_drag(
        self,
        row: Any,
        desc: RowDescriptor,
        x: float,
        span: tuple[float, float],
        *,
        blocked: bool,
    ) -> None:
        slot, index = desc.slot, desc.preset_index
        if slot is None or index is None:
            return
        if self._draw_drag_handle(
            f"##drag-preset-{slot}-{index}",
            x,
            span,
            blocked=blocked,
            lead=_drag_lead(),
        ):
            self._begin_row_drag(DRAG_PRESET, slot, index)
            self._controls.inspector.focus_row(row)
        drag = self._row_drag
        if drag is not None and drag.kind == DRAG_PRESET and drag.slot == slot:
            drag.record_span(index, *span)

    def _layer_row_drag(
        self,
        node: NavNode,
        x: float,
        span: tuple[float, float],
        text_color: tuple[int, int, int],
    ) -> None:
        slot = node.slot
        order = self._controls.session.layer_z_order
        if slot is None or slot not in order:
            return
        index = order.index(slot)
        if self._draw_drag_handle(
            f"##drag-layer-{slot}",
            x,
            span,
            blocked=node.drag_blocked,
            lead=_nav_drag_lead(),
            text=nav_handle_text(node),
            text_color=text_color,
        ):
            self._begin_row_drag(DRAG_LAYER, slot, index)
            self._controls.navigator.select(node.id)
        drag = self._row_drag
        if drag is not None and drag.kind == DRAG_LAYER:
            drag.record_span(index, *span)

    def _begin_row_drag(self, kind: str, slot: str, index: int) -> None:
        """Start a mouse reorder as move mode, so Esc restores and release keeps it."""
        controls = self._controls
        controls.layer_lifecycle.confirm_move_mode()
        controls.preset_list.confirm_move_mode()
        if kind == DRAG_PRESET:
            controls.preset_list.enter_move_mode(slot, index)
        else:
            controls.layer_lifecycle.enter_move_mode(slot)
        self._row_drag = RowDragGesture(kind, slot, index)

    def _row_drag_in_move_mode(self, drag: RowDragGesture) -> bool:
        controls = self._controls
        if drag.kind == DRAG_PRESET:
            return controls.preset_list.move_mode_preset == (drag.slot, drag.index)
        return controls.layer_lifecycle.move_mode_slot == drag.slot

    def _finish_row_drag(self, kind: str) -> None:
        """Move the dragged row under the pointer, or confirm it on release.

        Esc (or a view rebuild) ends move mode while the button is still down;
        the gesture then drops without moving anything further.
        """
        drag = self._row_drag
        if drag is None or drag.kind != kind:
            return
        if not self._row_drag_in_move_mode(drag):
            self._row_drag = None
            return
        controls = self._controls
        if not imgui.is_mouse_down(0):
            if kind == DRAG_PRESET:
                controls.preset_list.confirm_move_mode()
            else:
                controls.layer_lifecycle.confirm_move_mode()
            self._row_drag = None
            return
        target = drag.target(imgui.get_mouse_pos().y)
        drag.clear_spans()
        if target is None or target == drag.index:
            return
        if kind == DRAG_PRESET:
            controls.preset_list.move_item_to(target)
            moved = controls.preset_list.move_mode_preset
            drag.index = drag.index if moved is None else moved[1]
        else:
            controls.layer_lifecycle.move_slot_to(drag.slot, target)
            drag.index = controls.session.layer_z_order.index(drag.slot)

    def _draw_inline_field(self, view: Any) -> None:
        """The value area of the row just drawn, as a text field with a caret."""
        rect_min = imgui.get_item_rect_min()
        rect_max = imgui.get_item_rect_max()
        pad = imgui.get_style().frame_padding.x
        width = (rect_max.x - rect_min.x) * _INLINE_FIELD_WIDTH_FRACTION
        self._paint_inline_field(
            imgui.ImVec2(rect_max.x - pad - width, rect_min.y),
            imgui.ImVec2(rect_max.x - pad, rect_max.y),
            view,
            text_y=_selectable_text_y(rect_min.y),
        )

    def _paint_inline_field(
        self,
        field_min: imgui.ImVec2,
        field_max: imgui.ImVec2,
        view: Any,
        *,
        text_y: float | None = None,
    ) -> None:
        """A text field with a caret. *text_y* defaults to the field's top."""
        if imgui.is_mouse_hovering_rect(field_min, field_max):
            self._inline_field_hovered = True
            request_pointer(PointerShape.TEXT)
        pad = imgui.get_style().frame_padding.x
        width = field_max.x - field_min.x
        draw = imgui.get_window_draw_list()
        draw.add_rect_filled(field_min, field_max, imgui.get_color_u32(rgba(BACKGROUND)))
        border = ERROR_NOTIFICATION if view.error is not None else HIGHLIGHT
        draw.add_rect(field_min, field_max, imgui.get_color_u32(rgba(border)))
        inner = width - pad * 2
        caret_x = imgui.calc_text_size(view.draft[: view.caret_index]).x
        text_x = field_min.x + pad - max(0.0, caret_x - inner)
        y = field_min.y if text_y is None else text_y
        draw.push_clip_rect(field_min, field_max, True)
        draw.add_text(imgui.ImVec2(text_x, y), imgui.get_color_u32(rgba(VALUE)), view.draft)
        if view.caret_visible:
            line = imgui.get_text_line_height()
            draw.add_line(
                imgui.ImVec2(text_x + caret_x, y),
                imgui.ImVec2(text_x + caret_x, y + line),
                imgui.get_color_u32(rgba(HIGHLIGHT)),
            )
        draw.pop_clip_rect()
        if view.error is not None:
            show_tooltip(view.error)

    def _handle_colour_swatch(
        self,
        state: Any,
        row: Any,
        desc: RowDescriptor,
        spec: Any,
        parts: list[tuple[str, imgui.ImVec4]],
        clicked: bool,
    ) -> bool:
        """Paint the swatch left of the hex value. True when it took the click."""
        if spec.colour_target is None:
            return False
        target = spec.colour_target(self._controls, desc)
        line = imgui.get_text_line_height()
        rect_min = imgui.get_item_rect_min()
        rect_max = imgui.get_item_rect_max()
        pad = imgui.get_style().frame_padding.x
        text_w = sum(imgui.calc_text_size(text).x for text, _color in parts)
        right = rect_max.x - pad - text_w - ui_chrome_px(_SWATCH_GAP)
        y = _selectable_text_y(rect_min.y)
        swatch_min = imgui.ImVec2(right - line * _SWATCH_ASPECT, y)
        swatch_max = imgui.ImVec2(right, y + line)
        draw = imgui.get_window_draw_list()
        if target.current is not None:
            draw.add_rect_filled(
                swatch_min, swatch_max, imgui.get_color_u32(rgba(target.current))
            )
        draw.add_rect(swatch_min, swatch_max, imgui.get_color_u32(rgba(BUTTON_BORDER)))
        if not imgui.is_mouse_hovering_rect(swatch_min, swatch_max):
            return False
        locked = section_lock_blocks_mutation(state, desc)
        if not locked and imgui.is_window_hovered():
            request_pointer(PointerShape.HAND)
        if clicked and not locked:
            self._controls.inspector.focus_row(row)
            self._controls.inline_edit.begin_colour(desc, target)
            self._picker_pos = imgui.ImVec2(swatch_min.x, swatch_max.y)
        return True

    def _draw_colour_picker(self) -> None:
        """The picker window for the colour being edited, updating it live."""
        inline = self._controls.inline_edit
        edit = inline.colour_edit
        if edit is None:
            return
        imgui.set_next_window_pos(self._picker_pos, imgui.Cond_.always)
        imgui.begin("##colour-picker", None, _PICKER_FLAGS)
        try:
            value = edit.value if edit.value is not None else _PICKER_UNSET
            changed, picked = imgui.color_picker3(
                "##colour",
                [channel / 255.0 for channel in value],
                _PICKER_COLOUR_FLAGS,
            )
            if changed:
                inline.set_colour(
                    tuple(int(round(channel * 255.0)) for channel in picked)
                )
            done = imgui.button("Done")
            _hand_on_hover()
            if edit.target.optional:
                imgui.same_line()
                cleared = imgui.button("None")
                _hand_on_hover()
                if cleared:
                    inline.set_colour(None)
                    done = True
            hovered = imgui.is_window_hovered(
                imgui.HoveredFlags_.root_and_child_windows
            )
            if done or (imgui.is_mouse_clicked(0) and not hovered):
                inline.finish()
        finally:
            imgui.end()

    def _handle_nav_buttons(
        self,
        state: Any,
        row: Any,
        desc: RowDescriptor,
        label: str | None,
        buttons: tuple[RowNavButton, ...],
        value_color: imgui.ImVec4,
        *,
        stepped: bool,
        activated: bool,
        two_line: bool,
    ) -> None:
        """Paint the icon buttons, and take hover and press.

        The buttons follow *label*, or sit at the row's right edge when
        *label* is None. On a two-line row they cover the first line only.
        A press on a dimmed button is swallowed. Otherwise a double-click on
        it would reach the row and open a child directory.
        """
        origin_x, _text_y = _selectable_label_origin()
        rect_min = imgui.get_item_rect_min()
        rect_max = imgui.get_item_rect_max()
        line = imgui.get_text_line_height()
        band = (rect_min.y, rect_max.y - line if two_line else rect_max.y)
        side = band[1] - band[0]
        gap = icon_gap()
        if label is None:
            start_x = (
                rect_max.x
                - imgui.get_style().frame_padding.x
                - len(buttons) * (side + gap)
                + gap
            )
        else:
            start_x = origin_x + imgui.calc_text_size(f"{label} ").x
        boxes = row_icon_boxes(start_x, band, len(buttons))
        blocked = not stepped or self._nudge_input_blocked()
        mouse = imgui.get_mouse_pos()
        hit = None if blocked else box_index_at(boxes, mouse.x, mouse.y)
        hold_armed = self._controls.value_nudge.armed
        available = [button.available(state, desc) for button in buttons]
        for index, (button, box) in enumerate(zip(buttons, boxes)):
            lit = index == hit and available[index] and not hold_armed
            if lit:
                request_pointer(PointerShape.HAND)
            paint_box(
                box,
                button.glyph,
                color=value_color if available[index] else DISABLED,
                hovered=lit,
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
        hand: bool,
    ) -> None:
        """Hover and press the painted side arrows. The value string is not a hit.

        On a two-line row the arrows cover the first line only. *hand* is
        False while a step would be refused, so the pointer stays an arrow.
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
            if hand:
                request_pointer(PointerShape.HAND)
            self._paint_nudge_hover(
                forward_rect if hover_forward else back_rect,
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
        forward: bool,
    ) -> None:
        paint_stepper_hover(
            (rect.min_x, rect.min_y, rect.max_x - rect.min_x, rect.max_y - rect.min_y),
            forward=forward,
        )

    def _nudge_input_blocked(self) -> bool:
        return (
            self._modal_has_pointer()
            or self._choice_list_open()
            or self._controls.context_menu.is_open
        )

    def _choice_list_open(self) -> bool:
        inline = getattr(self._controls, "inline_edit", None)
        return inline is not None and inline.choice_view is not None

    def _fixed_width_value(self, kind: RowKind, text: str) -> str:
        """``text`` centred in the widest value this row has shown."""
        key = (kind, tuning_ui_metrics().font_size)
        width = max(len(text), self._stepper_chars.get(key, 0))
        self._stepper_chars[key] = width
        return centre_pad(text, width)

    def _draw_choice_value(
        self,
        state: Any,
        row: Any,
        desc: RowDescriptor,
        labels: tuple[str, ...],
        value: str,
        *,
        enabled: bool,
        tone: ChoiceTone,
        activated: bool,
        after_label: str | None = None,
    ) -> None:
        """Segments or a combo at the row's right edge, and their clicks.

        With *after_label*, the control sits just after that label instead.
        A segment click chooses that option; a combo click opens its list. Either
        press skips the row's own click.
        """
        spec = row_spec(desc.kind)
        assert spec.choice is not None
        measure = _ImguiTextSizer()
        rect_min = imgui.get_item_rect_min()
        rect_max = imgui.get_item_rect_max()
        line = imgui.get_text_line_height()
        pad_y = max(1, int(round(ui_chrome_px(_CHOICE_PAD_Y))))
        # A combo shows the row's value, which can add to the label (a font's
        # place in the list), so it fits that too.
        kind = choice_kind(len(labels), combo=spec.choice.combo)
        width = choice_width(measure, labels, combo=spec.choice.combo)
        if kind is ChoiceKind.COMBO:
            width = max(width, combo_width(measure, (value,)))
        if after_label is None:
            left = int(rect_max.x - imgui.get_style().frame_padding.x) - width
        else:
            origin_x, _origin_y = _selectable_label_origin()
            left = int(origin_x + imgui.calc_text_size(f"{after_label}  ").x)
        top = int(_selectable_text_y(rect_min.y)) - pad_y
        rect = (left, top, width, int(line) + pad_y * 2)
        index = spec.choice.index(state, desc)
        draw = imgui.get_window_draw_list()
        inline = self._controls.inline_edit
        list_view = inline.choice_view
        open_here = list_view is not None and list_view.target == desc
        hover = list_view is None and not self._nudge_input_blocked()
        hand = not row_inert(state, desc)
        self._choice_rects[desc] = rect
        if open_here and activated:
            # A press anywhere on the open row closes its list. Swallow it so
            # the release does not activate the row and open the list again.
            inline.finish()
            self._clear_value_drag()
            self._nudge_swallow = True
            return
        if kind is ChoiceKind.SEGMENT:
            rects = draw_segments(
                draw,
                measure,
                labels,
                index,
                x=rect[0],
                y=rect[1],
                height=rect[3],
                enabled=enabled,
                tone=tone,
                hover=hover,
                hand=hand,
            )
            mouse = imgui.get_mouse_pos()
            hit = rect_index_at(rects, mouse.x, mouse.y)
            if not activated or not enabled or not hover or hit is None:
                return
            self._controls.inspector.focus_row(row)
            apply_field_choice(self._controls, desc, hit - index)
        else:
            draw_combo(
                draw,
                measure,
                value,
                rect=rect,
                open_=open_here,
                enabled=enabled,
                tone=tone,
                hover=hover,
                hand=hand,
            )
            mouse = imgui.get_mouse_pos()
            if not activated or not enabled or not hover:
                return
            if not rect_contains(rect, mouse.x, mouse.y):
                return
            self._controls.inspector.open_choice(row)
        self._clear_value_drag()
        self._nudge_swallow = True

    def _draw_choice_list(self) -> None:
        """The open combo list of an inspector row, over every other window."""
        inline = self._controls.inline_edit
        view = inline.choice_view
        if view is None:
            return
        anchor = self._choice_rects.get(view.target)
        if anchor is None:
            # The row scrolled away or left the page.
            inline.finish()
            return
        pointer = draw_choice_list(
            "inspector-choice-list", view, _ImguiTextSizer(), anchor=anchor
        )
        self._choice_list_rows = pointer.rows
        if pointer.picked is not None:
            inline.pick_choice(pointer.picked)
        elif pointer.outside:
            inline.finish()
        elif pointer.hovered is not None:
            inline.hover_choice(pointer.hovered)

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
        """One row of buttons. A click focuses that button, then runs it."""
        focus = self._controls.shell_focus
        # One context for the frame; a row drawn outside a frame builds its own.
        ctx = self._frame_command_ctx or command_context(self._controls)
        if row.status is not None:
            imgui.align_text_to_frame_padding()
            imgui.text(row.status)
            imgui.same_line()
        for index, command_id in enumerate(row.command_ids):
            if index:
                imgui.same_line()
            command = command_by_id(command_id)
            enabled = inspector_command_enabled(ctx, command_id)
            selected = (
                focus.region is ShellRegion.INSPECTOR
                and focus.inspector_command_id == command_id
            )
            clicked = _draw_button(
                f"{command.label}##cmd-{command_id}",
                text_role=_button_text_role(
                    enabled,
                    inspector_command_locked(ctx, command_id)
                    or self._page_status.locked_by is not None,
                    page_off=self._page_status.off_by is not None,
                ),
                selected=selected,
                enabled=enabled,
            )
            if selected:
                self._insp_follow.follow((focus.selected_id, command_id))
            if clicked:
                self._controls.inspector.focus_command(row, command_id)
                if enabled:
                    self._controls.inspector.activate(row)

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
        hovered_index = self._bar_hover_index
        hovered_now: int | None = None
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
                    with opaque_highlight_fill(active):
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
                    label_y = _selectable_label_origin()[1]
                    _draw_mnemonic_underline(
                        menu.label, BACKGROUND if active else LABEL
                    )
                    # The dropdown's top border sits on the rule row. The
                    # title's item rect ends a few pixels above the bar
                    # bottom, so anchoring there doubled the top border
                    # whenever the popup drew in front of the bar.
                    anchors[index] = (imgui.get_item_rect_min().x, rule_y)
                    if clicked:
                        menu_state.click_top(index, menus)
                    elif imgui.is_item_hovered() and hovered_index != index:
                        menu_state.hover_top(index, menus)
                    if imgui.is_item_hovered():
                        hovered_now = index
                if menus:
                    self._draw_bar_project_label(label_y)
        finally:
            if bar_open:
                imgui.end_main_menu_bar()
            self._bar_hover_index = hovered_now
            imgui.pop_style_var()
            imgui.pop_style_color()
        return rule_y, anchors, menus

    def _draw_bar_project_label(self, label_y: float) -> None:
        """Right-aligned project name on the menu titles' text line.

        Painted on the bar's draw list, not laid out as an item, so the menu
        bar's horizontal layout cannot shift or wrap it. Dropped when it would
        overlap the last menu title.
        """
        prefix, name = menu_bar_project_label(
            self._controls.cfg.project_slug, self._controls.config_dirty
        )
        style = imgui.get_style()
        left = imgui.get_item_rect_max().x + style.frame_padding.x
        # Same inset as the transport bar's FPS readout below it.
        right = (
            imgui.get_window_pos().x
            + imgui.get_window_width()
            - style.window_padding.x
        )
        prefix_w = imgui.calc_text_size(prefix).x
        x = right - prefix_w - imgui.calc_text_size(name).x
        if x < left:
            return
        draw = imgui.get_window_draw_list()
        draw.add_text(
            imgui.ImVec2(x, label_y), imgui.get_color_u32(rgba(LABEL)), prefix
        )
        draw.add_text(
            imgui.ImVec2(x + prefix_w, label_y),
            imgui.get_color_u32(rgba(VALUE)),
            name,
        )

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
            origin_y = float(self._menu_bar_height_px) - 1.0
        else:
            origin_x, origin_y = anchor
        # Begun after the shell panels and raised over them; chrome is raised
        # after this window. Do not focus it: FocusWindow clears the menu-bar
        # button's ActiveId, and a later click on another top label never
        # completes. A menu's first open measures off-screen for one frame.
        with self._dropdown_window.begin(
            (index, menu.label),
            lambda _size, _display: (origin_x, origin_y),
        ) as (visible, measuring, rect):
            if not visible:
                return False
            hit = self._draw_rows(
                menu_state, command_ctx, menus, index, menu, measuring=measuring
            )
            if measuring:
                return False
            x, _y, width, _height = rect
            self._dropdown_span = (float(x), float(x + width))
            return hit or _mouse_in_current_window()

    def _draw_rows(
        self,
        menu_state: MenuBarState,
        command_ctx: CommandContext,
        menus: tuple[Any, ...],
        menu_index: int,
        menu: Any,
        *,
        measuring: bool,
    ) -> bool:
        rows = tuple(
            None
            if isinstance(item, MenuSeparator)
            else command_row_view(item, command_ctx)
            for item in menu.items
        )
        result = draw_menu_rows(rows, menu_state.item_index)
        if measuring:
            self._dropdown_hover_index = None
        elif result.hovered != self._dropdown_hover_index:
            self._dropdown_hover_index = result.hovered
            if result.hovered is not None:
                row = rows[result.hovered]
                menu_state.hover_item(
                    result.hovered if row is not None and row.enabled else None
                )
        if result.clicked is None:
            return False
        menu_state.click_item(
            menu_index,
            result.clicked,
            menus,
            command_ctx,
            self._controls,
        )
        return True


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
        shell.draw_profiler_panel()
    finally:
        shell.end_imgui_frame()


def _mouse_in_current_window() -> bool:
    origin = imgui.get_window_pos()
    size = imgui.get_window_size()
    mouse = imgui.get_mouse_pos()
    return (
        origin.x <= mouse.x < origin.x + size.x
        and origin.y <= mouse.y < origin.y + size.y
    )


def command_row_view(command: Command, ctx: CommandContext) -> MenuRowView:
    """A menu-bar command as a drawn menu row."""
    return MenuRowView(
        id=command.id,
        label=command.label,
        enabled=bool(command.enabled(ctx)),
        checked=(
            command.kind == "check"
            and command.checked is not None
            and bool(command.checked(ctx))
        ),
        shortcut=command.shortcut,
        color=command.label_role(ctx) if command.label_role is not None else VALUE,
    )
