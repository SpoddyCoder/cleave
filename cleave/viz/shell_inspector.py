"""The shell's inspector page: value rows and command buttons."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from cleave.preset_library import marker_tooltip
from cleave.viz.choice_widgets import ChoiceTone
from cleave.viz.commands import command_by_id, command_context, CommandContext
from cleave.viz.drag_reorder import DRAG_PRESET
from cleave.viz.imgui_icon_button import glyph_drop
from cleave.viz.imgui_theme import padded_row_spacing_y, padded_rows, rgba
from cleave.viz.inspector import build_inspector_rows, InspectorRow
from cleave.viz.inspector_controls import (
    inspector_command_enabled,
    inspector_command_locked,
)
from cleave.viz.material_icons import (
    ARROW_BACK_GLYPH,
    ARROW_FORWARD_GLYPH,
    DRAG_INDICATOR_GLYPH,
    FILE_GLYPH,
    FOLDER_GLYPH,
)
from cleave.viz.navigator import (
    page_status,
    PageStatus,
    timeline_row_slot_of,
    timeline_row_title,
)
from cleave.viz.panel_notification import AttentionClock
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_present_renderers import inspector_field_colors
from cleave.viz.row_spec import (
    format_row_markers,
    format_row_position,
    format_row_value,
    row_available,
    row_inert,
    row_is_two_line,
    row_label,
    row_spec,
    RowPresentStyle,
    section_lock_blocks_mutation,
)
from cleave.viz.scroll_follow import ScrollFollow
from cleave.viz.shell_context import ShellContext, ShellFrame
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.shell_inspector_values import ValueControls
from cleave.viz.shell_inspector_title import (
    draw_inspector_title,
    inspector_title,
    page_history_tooltip,
    page_status_marks,
    page_title,
    TITLE_BACK,
    TITLE_FORWARD,
    TitleButton,
)
from cleave.viz.row_paint import RowState, row_band
from cleave.viz.shell_widgets import (
    PANEL_BORDER_PX,
    drag_handle_lead,
    draw_aligned_parts,
    draw_button,
    drawn_row_rect,
    ImguiTextSizer,
    InlineField,
    row_text_y,
    RowDrag,
    selectable_label_origin,
    stroke_h_rule,
)
from cleave.viz.text_fit import fit_path_or_name_to_width, fit_text_to_width
from cleave.viz.theme import (
    DISABLED,
    INSPECTOR_DIVIDER,
    LABEL,
    LOCKED,
    MUTED,
    OFF_CONTROL_TEXT,
    PRESET_FILE_ICON,
    PRESET_ICON,
    ui_chrome_px,
    VALUE,
)
from cleave.viz.tooltips import show_tooltip
from cleave.viz.value_nudge import nudge_cluster_origin_x, value_parts

if TYPE_CHECKING:
    from cleave.viz.inline_edit import InlineTextView
    from cleave.viz.row_spec import RowSpec
    from cleave.viz.shell_focus import ShellFocusState
    from cleave.viz.tuning_view_state import TuningViewState

# Indent per nesting level of an inspector row.
_INSPECTOR_INDENT = 16.0
_INSPECTOR_ROWS = "##inspector-rows"
# Height of an inspector divider, as a fraction of the text line.
_INSPECTOR_DIVIDER_LINES = 0.5


def choice_tone(value_color: tuple[int, int, int]) -> ChoiceTone:
    """Choice control tone that matches a row drawn in *value_color*."""
    if value_color == LOCKED:
        return ChoiceTone.LOCKED
    if value_color == DISABLED:
        return ChoiceTone.OFF
    return ChoiceTone.NORMAL


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


def _drag_lead() -> str:
    """Label prefix that reserves the leading drag-handle column."""
    count = drag_handle_lead(
        imgui.calc_text_size(DRAG_INDICATOR_GLYPH).x,
        imgui.calc_text_size(" ").x,
    )
    return " " * count


_INLINE_FIELD_WIDTH_FRACTION = 0.6


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
        fit_path_or_name_to_width(ImguiTextSizer(), value, int(right_x - x)),
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
    origin_x, origin_y = selectable_label_origin()
    lead_x = imgui.calc_text_size(lead).x if lead else 0.0
    right_x = imgui.get_item_rect_max().x
    pad = imgui.get_style().frame_padding.x
    sizer = ImguiTextSizer()
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


def _inspector_row_selected(focus: ShellFocusState, desc: RowDescriptor) -> bool:
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


def _divider_height() -> float:
    return imgui.get_text_line_height() * _INSPECTOR_DIVIDER_LINES


def _divider_rule_y(top_y: float) -> float:
    """Pixel row of the rule in a divider whose space starts at *top_y*."""
    return float(int(top_y + _divider_height() * 0.5))


def _draw_inspector_divider() -> None:
    """Thin rule across the inspector, shorter than a row; takes no input."""
    origin = imgui.get_cursor_screen_pos()
    x1 = origin.x + imgui.get_content_region_avail().x
    stroke_h_rule(origin.x, x1, _divider_rule_y(origin.y), INSPECTOR_DIVIDER)
    imgui.dummy(imgui.ImVec2(0.0, _divider_height()))


def _button_text_role(
    enabled: bool, locked: bool, *, page_off: bool
) -> tuple[int, int, int]:
    """Button label colour. A section lock reads as locked, not as disabled.

    A button on a switched-off page still runs, but dims like its rows, on the
    OFF tone (``_button_off``).
    """
    if locked:
        return LOCKED
    return VALUE if enabled and not page_off else OFF_CONTROL_TEXT


def _button_off(enabled: bool, locked: bool, *, page_off: bool) -> bool:
    """Whether a command button rests in the darker OFF tone."""
    return locked or page_off or not enabled


@dataclass(frozen=True)
class _RowLook:
    """What an inspector value row draws with this frame.

    ``lead`` is the label prefix that reserves the drag-handle column.
    ``stepped`` is true when the row has side arrows and takes a sideways drag.
    """

    row: InspectorRow
    desc: RowDescriptor
    spec: RowSpec
    label: str
    lead: str
    label_color: tuple[int, int, int]
    value_color: tuple[int, int, int]
    selected: bool
    band_left: float
    two_line: bool
    stepped: bool


@dataclass(frozen=True)
class _RowItem:
    """Item flags of a row's selectable, read while it was the current item.

    ``text_x`` is the label's left edge and ``span`` the row's top and bottom.
    """

    clicked: bool
    activated: bool
    active: bool
    released: bool
    text_x: float
    span: tuple[float, float]


def _begin_inspector_rows() -> None:
    """Open the scrolling child that holds the inspector rows.

    The child spans the panel inside its border and pads its sides by the
    rest of the panel's padding, so rows, their washes, and the scrollbar sit
    where they would in the panel itself. A selectable's rect reaches half the
    row spacing above and below its line, so the child starts that much
    higher and pads its top and bottom by it, and the first and last rows
    keep their whole wash.
    """
    half = 0.5 * padded_row_spacing_y()
    border = PANEL_BORDER_PX
    pad_x = max(0.0, imgui.get_style().window_padding.x - border)
    win_x = imgui.get_window_pos().x
    width = imgui.get_window_width() - 2.0 * border
    cursor = imgui.get_cursor_screen_pos()
    imgui.set_cursor_screen_pos(imgui.ImVec2(win_x + border, cursor.y - half))
    imgui.push_style_var(imgui.StyleVar_.window_padding, imgui.ImVec2(pad_x, half))
    try:
        imgui.begin_child(
            _INSPECTOR_ROWS,
            imgui.ImVec2(width, 0.0),
            imgui.ChildFlags_.always_use_window_padding,
        )
    finally:
        imgui.pop_style_var()


class InspectorPanel:
    """The inspector page: title line, value rows, and command buttons."""

    def __init__(
        self, context: ShellContext, row_drag: RowDrag, inline_field: InlineField
    ) -> None:
        self._ctx = context
        self._row_drag = row_drag
        self._inline = inline_field
        self.values = ValueControls(context)
        self._follow = ScrollFollow()
        # Swipes the toast's accent bar under the inspector title when the
        # selection changes.
        self._title_attention = AttentionClock()
        # The inspector page's off and locked owners, read each frame.
        self._page_status = PageStatus()
        # Rows with a descriptor from the last draw, for right-click and Shift+F10.
        self.row_rects: dict[
            RowDescriptor, tuple[tuple[int, int, int, int], InspectorRow]
        ] = {}

    def draw(self, frame: ShellFrame) -> None:
        focus = self._ctx.controls.shell_focus
        state = frame.view_state
        nodes = frame.nav_nodes
        row_slot = timeline_row_slot_of(focus.selected_id)
        title = (
            inspector_title(nodes, focus.selected_id)
            if row_slot is None
            else timeline_row_title(self._ctx.controls.session, row_slot)
        )
        self._page_status = page_status(
            self._ctx.controls.session, focus.selected_id, nodes
        )
        # A new clip on the same strip row is new content, so it swipes too.
        clip_serial = self._ctx.controls.session.timeline.selected_clip_serial
        attention_key = (
            focus.selected_id if row_slot is None else (focus.selected_id, clip_serial)
        )
        # With the highlight off, the title draws as if its swipe has ended.
        elapsed = (
            self._title_attention.elapsed(attention_key)
            if self._ctx.controls.cfg.editor.highlight_new_page
            else math.inf
        )
        # The title line takes one text line, then the divider's space starts.
        title_y = imgui.get_cursor_screen_pos().y
        pressed = draw_inspector_title(
            title,
            elapsed,
            _divider_rule_y(
                title_y + imgui.get_text_line_height() + imgui.get_style().item_spacing.y
            ),
            page_status_marks(self._page_status),
            self._page_history_buttons(frame.command_ctx),
        )
        if pressed == TITLE_BACK:
            self._ctx.controls.navigator.go_back()
        elif pressed == TITLE_FORWARD:
            self._ctx.controls.navigator.go_forward()
        _draw_inspector_divider()
        self.values.choice_rects = {}
        self.row_rects = {}
        # Only the rows scroll, so the title line stays in view and the
        # scrollbar spans the rows alone.
        _begin_inspector_rows()
        try:
            with padded_rows():
                for row in build_inspector_rows(state, focus.selected_id):
                    if row.divider:
                        _draw_inspector_divider()
                        continue
                    self.draw_row(state, row)
            self._row_drag.finish(DRAG_PRESET)
        finally:
            imgui.end_child()
        self.values.draw_colour_picker()
        self.values.draw_choice_list_window()

    def _page_history_buttons(
        self, ctx: CommandContext
    ) -> tuple[TitleButton, TitleButton]:
        """Back and Forward arrows for the inspector title line."""
        controls = self._ctx.controls
        back_id = ctx.page_back_id
        forward_id = ctx.page_forward_id
        session = controls.session
        expanded = controls.shell_focus.nav_expanded

        def tooltip(page_id: str | None, *, forward: bool) -> Callable[[], str]:
            def text() -> str:
                title = None if page_id is None else page_title(session, expanded, page_id)
                return page_history_tooltip(title, forward=forward)

            return text

        return (
            TitleButton(
                TITLE_BACK,
                ARROW_BACK_GLYPH,
                back_id is not None,
                tooltip(back_id, forward=False),
            ),
            TitleButton(
                TITLE_FORWARD,
                ARROW_FORWARD_GLYPH,
                forward_id is not None,
                tooltip(forward_id, forward=True),
            ),
        )

    def draw_row(self, state: TuningViewState, row: InspectorRow) -> None:
        """One inspector row: a button row, a heading, or a label with its value."""
        indent = row.depth * ui_chrome_px(_INSPECTOR_INDENT)
        # A focused row's band runs the full width, under its indent.
        band_left = imgui.get_cursor_screen_pos().x - math.floor(
            imgui.get_style().item_spacing.x * 0.5
        )
        if indent:
            imgui.indent(indent)
        try:
            if row.command_ids:
                self._draw_command_row(row)
                return
            desc = row.descriptor
            spec = row_spec(desc.kind)
            label = row_label(state, desc)
            if row.is_heading:
                value = format_row_value(state, desc) if spec.format_value else ""
                imgui.text_colored(rgba(MUTED), f"{label} {value}".rstrip())
                return
            selected = _inspector_row_selected(self._ctx.controls.shell_focus, desc)
            label_color, value_color = inspector_field_colors(state, desc)
            if selected and label_color == LABEL:
                label_color = VALUE
            look = _RowLook(
                row=row,
                desc=desc,
                spec=spec,
                label=label,
                lead=_drag_lead() if spec.drag_reorder else "",
                label_color=label_color,
                value_color=value_color,
                selected=selected,
                band_left=band_left,
                two_line=row_is_two_line(desc.kind),
                stepped=inspector_row_stepped(state, desc),
            )
            item = self._draw_row_selectable(look)
            if self._draw_row_value(state, look, item):
                return
            self._apply_row_click(look, item)
        finally:
            if indent:
                imgui.unindent(indent)

    def _draw_row_selectable(self, look: _RowLook) -> _RowItem:
        """The row's label as a selectable, with its wash and focus ring."""
        desc = look.desc
        row_height = 2.0 * imgui.get_text_line_height() if look.two_line else 0.0
        imgui.push_style_color(imgui.Col_.text, rgba(look.label_color))
        try:
            with row_band(RowState.FOCUSED if look.selected else None) as mark_band:
                text_x = imgui.get_cursor_screen_pos().x
                clicked, _selected = imgui.selectable(
                    f"{look.lead}{look.label}{inspector_selectable_id(desc)}",
                    look.selected,
                    imgui.SelectableFlags_.allow_overlap if look.lead else 0,
                    imgui.ImVec2(0.0, row_height),
                )
                mark_band(look.band_left)
                span = (
                    imgui.get_item_rect_min().y,
                    imgui.get_item_rect_max().y,
                )
                rect = drawn_row_rect(text_x)
                if rect is not None:
                    self.row_rects[desc] = (rect, look.row)
                # Item flags are only valid while this selectable is current.
                # Release clears the active id inside the widget, so the
                # frame the button comes up is deactivated, not active.
                item = _RowItem(
                    clicked=clicked,
                    activated=imgui.is_item_activated(),
                    active=imgui.is_item_active(),
                    released=imgui.is_item_deactivated(),
                    text_x=text_x,
                    span=span,
                )
                if look.selected:
                    selected_id = self._ctx.controls.shell_focus.selected_id
                    self._follow.follow((selected_id, desc))
        finally:
            imgui.pop_style_color()
        return item

    def _draw_row_value(
        self, state: TuningViewState, look: _RowLook, item: _RowItem
    ) -> bool:
        """Everything right of the label, and the presses it takes.

        True when the value owns the row this frame (an open text field, or a
        click on the colour swatch), so the row's own click does not run.
        """
        row, desc, spec = look.row, look.desc, look.spec
        two_line = look.two_line
        list_item = spec.present_style is RowPresentStyle.LIST_ITEM
        value = format_row_value(state, desc) if spec.format_value else ""
        if spec.shows_dirty_suffix and state.config_dirty:
            value = f"{value}*" if value else "*"
        cluster = format_row_position(state, desc) if two_line else value
        inline = self._ctx.controls.inline_edit
        if inline.text_target == desc:
            self.draw_inline_field(inline.text_view())
            return True
        labels = (
            spec.choice.labels() if spec.choice is not None and not two_line else ()
        )
        if labels:
            self.values.draw_choice_value(
                state,
                row,
                desc,
                labels,
                value,
                enabled=look.stepped,
                tone=choice_tone(look.value_color),
                activated=item.activated,
                after_label=look.label if list_item else None,
            )
            cluster = ""
        elif look.stepped and cluster and not two_line:
            cluster = self.values.fixed_width_value(desc.kind, cluster)
        icon = path_row_icon(desc.kind)
        if icon is not None and not two_line:
            origin_x, origin_y = selectable_label_origin()
            if look.label:
                origin_x += imgui.calc_text_size(f"{look.lead}{look.label} ").x
            _draw_path_value(
                origin_x,
                origin_y,
                imgui.get_item_rect_max().x - imgui.get_style().frame_padding.x,
                cluster,
                look.value_color,
                icon,
            )
            cluster = ""
        if cluster and self._draw_value_cluster(state, look, item, cluster, value, icon):
            return True
        if spec.nav_buttons and list_item:
            self.values.handle_nav_buttons(
                state,
                row,
                desc,
                None,
                spec.nav_buttons,
                rgba(look.value_color),
                stepped=look.stepped,
                activated=item.activated,
                two_line=two_line,
            )
        if look.lead:
            self._preset_row_drag(
                row,
                desc,
                item.text_x,
                item.span,
                blocked=section_lock_blocks_mutation(state, desc),
            )
        if look.stepped and not labels and not self.values.press_swallowed:
            self.values.track_value_drag(
                row,
                desc,
                activated=item.activated,
                active=item.active or item.released,
            )
        return False

    def _draw_value_cluster(
        self,
        state: TuningViewState,
        look: _RowLook,
        item: _RowItem,
        cluster: str,
        value: str,
        icon: tuple[str, tuple[int, int, int]] | None,
    ) -> bool:
        """The right-aligned value text with its arrows, buttons, and swatch.

        True when the colour swatch took the click.
        """
        row, desc, spec = look.row, look.desc, look.spec
        list_item = spec.present_style is RowPresentStyle.LIST_ITEM
        parts = value_parts(cluster, rgba(look.value_color), stepped=look.stepped)
        draw_aligned_parts(parts)
        if look.two_line:
            _draw_two_line_row_text(
                look.label,
                format_row_markers(state, desc),
                value,
                parts,
                rgba(look.label_color),
                look.value_color,
                lead=look.lead,
                icon=icon,
            )
        if spec.nav_buttons and not list_item:
            self.values.handle_nav_buttons(
                state,
                row,
                desc,
                look.label,
                spec.nav_buttons,
                rgba(look.value_color),
                stepped=look.stepped,
                activated=item.activated,
                two_line=look.two_line,
            )
        if self.values.handle_colour_swatch(state, row, desc, spec, parts, item.clicked):
            return True
        if look.stepped:
            self.values.handle_value_nudge(
                row,
                desc,
                parts,
                repeatable=spec.repeatable,
                activated=item.activated,
                two_line=look.two_line,
                hand=not row_inert(state, desc),
            )
        return False

    def _apply_row_click(self, look: _RowLook, item: _RowItem) -> None:
        """Focus the row, and run its action, from this frame's press.

        A release still over the row reports clicked. A gesture that already
        stepped is a drag, so it must not run the row action. An arrow press
        is neither a drag nor an activate.
        """
        if self.values.value_drag_crossed or self.values.press_swallowed:
            return
        focus, activate = inspector_row_click_outcome(
            double_click_row=look.spec.activate_on_double_click,
            clicked=item.clicked,
            activated=item.activated,
            double_clicked=imgui.is_mouse_double_clicked(0),
        )
        if focus:
            self._ctx.controls.inspector.focus_row(look.row)
        if activate:
            self._ctx.controls.inspector.activate(look.row)

    def _preset_row_drag(
        self,
        row: InspectorRow,
        desc: RowDescriptor,
        x: float,
        span: tuple[float, float],
        *,
        blocked: bool,
    ) -> None:
        slot, index = desc.slot, desc.preset_index
        if slot is None or index is None:
            return
        if self._row_drag.draw_handle(
            f"##drag-preset-{slot}-{index}",
            x,
            span,
            blocked=blocked,
            lead=_drag_lead(),
        ):
            self._row_drag.begin(DRAG_PRESET, slot, index)
            self._ctx.controls.inspector.focus_row(row)
        drag = self._row_drag.gesture
        if drag is not None and drag.kind == DRAG_PRESET and drag.slot == slot:
            drag.record_span(index, *span)

    def draw_inline_field(self, view: InlineTextView) -> None:
        """The value area of the row just drawn, as a text field with a caret."""
        rect_min = imgui.get_item_rect_min()
        rect_max = imgui.get_item_rect_max()
        pad = imgui.get_style().frame_padding.x
        width = (rect_max.x - rect_min.x) * _INLINE_FIELD_WIDTH_FRACTION
        self._inline.paint(
            imgui.ImVec2(rect_max.x - pad - width, rect_min.y),
            imgui.ImVec2(rect_max.x - pad, rect_max.y),
            view,
            text_y=row_text_y(rect_min.y),
        )

    def _draw_command_row(self, row: InspectorRow) -> None:
        """One row of buttons. A click focuses that button, then runs it."""
        focus = self._ctx.controls.shell_focus
        # One context for the frame; a row drawn outside a frame builds its own.
        ctx = self._ctx.command_ctx or command_context(self._ctx.controls)
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
            locked = (
                inspector_command_locked(ctx, command_id)
                or self._page_status.locked_by is not None
            )
            page_off = self._page_status.off_by is not None
            clicked = draw_button(
                f"{command.label}##cmd-{command_id}",
                text_role=_button_text_role(enabled, locked, page_off=page_off),
                selected=selected,
                enabled=enabled,
                off=_button_off(enabled, locked, page_off=page_off),
            )
            if selected:
                self._follow.follow((focus.selected_id, command_id))
            if clicked:
                self._ctx.controls.inspector.focus_command(row, command_id)
                if enabled:
                    self._ctx.controls.inspector.activate(row)
