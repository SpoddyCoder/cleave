"""The shell's navigator tree."""

from __future__ import annotations

import math
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from imgui_bundle import imgui

from cleave.viz.commands import command_by_id
from cleave.viz.config_pages import is_config_page
from cleave.viz.drag_reorder import DRAG_LAYER
from cleave.viz.icon_button import icon_columns, icon_gap
from cleave.viz.imgui_icon_button import icon_button
from cleave.viz.imgui_theme import (
    padded_row_spacing_y,
    padded_rows,
    rgba,
    row_band_side,
)
from cleave.viz.material_icons import (
    ADD_GLYPH,
    DRAG_INDICATOR_GLYPH,
    LOCK_GLYPH,
    LOCK_OPEN_GLYPH,
    PAUSE_GLYPH,
    PROBLEM_GLYPH,
    POWER_GLYPH,
    PREVIEW_GLYPH,
    SOLO_GLYPH,
)
from cleave.viz.navigator import (
    build_navigator,
    navigator_row_text_color,
    navigator_tree_rails,
    NavNode,
    NavToggle,
    timeline_row_slot_of,
    TOGGLE_ADD,
    TOGGLE_ENABLED,
    TOGGLE_HOLD,
    TOGGLE_LOCK,
    TOGGLE_PREVIEW,
    TOGGLE_SOLO,
    TOGGLE_WARN,
    TWISTY_COLLAPSED,
    TWISTY_EXPANDED,
)
from cleave.viz.row_paint import RowState, row_band
from cleave.viz.row_hotkeys import activate_header_toggle, node_control_descriptor
from cleave.viz.scroll_follow import ScrollFollow
from cleave.viz.shell_context import ShellContext, ShellFrame
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.shell_widgets import (
    draw_aligned_parts,
    drawn_row_rect,
    rect_has_point,
    row_text_y,
    RowDrag,
    space_lead,
)
from cleave.viz.theme import palette

_NAV_LOCK_MARK = "[lock]"
# Fixed columns, so a row without solo keeps its icons under the rows that have it.
_NAV_TOGGLE_COLUMNS = (
    TOGGLE_WARN,
    TOGGLE_HOLD,
    TOGGLE_ENABLED,
    TOGGLE_SOLO,
    TOGGLE_LOCK,
)


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
    if toggle.id == TOGGLE_HOLD:
        return PAUSE_GLYPH
    if toggle.id == TOGGLE_WARN:
        return PROBLEM_GLYPH
    if toggle.id == TOGGLE_LOCK:
        return LOCK_GLYPH if toggle.active else LOCK_OPEN_GLYPH
    if toggle.id == TOGGLE_SOLO:
        return SOLO_GLYPH
    if toggle.id == TOGGLE_PREVIEW:
        return PREVIEW_GLYPH
    return POWER_GLYPH


def navigator_toggle_fill(toggle: NavToggle) -> tuple[int, int, int] | None:
    """Solid square behind a lit toggle: green on, red solo or preview, amber
    lock, yellow held switching (a manual override, as on the timeline strip),
    red warning."""
    if toggle.id == TOGGLE_ADD or not toggle.active:
        return None
    if toggle.id == TOGGLE_WARN:
        return palette().button_danger_bg
    if toggle.id == TOGGLE_HOLD:
        return palette().override_bg
    if toggle.id == TOGGLE_LOCK:
        return palette().nav_lock_bg
    if toggle.id in (TOGGLE_SOLO, TOGGLE_PREVIEW):
        return palette().solo_bg
    return palette().nav_on_bg


def navigator_toggle_color(toggle: NavToggle) -> tuple[int, int, int]:
    """Resting icon color. Muted while inactive; a lit icon sits on its fill."""
    if toggle.id == TOGGLE_ADD:
        return palette().disabled if toggle.blocked else palette().value
    if not toggle.active:
        return palette().locked if toggle.blocked else palette().muted
    if toggle.id == TOGGLE_HOLD:
        return palette().override_glyph
    if toggle.id == TOGGLE_WARN:
        return palette().on_danger
    return palette().nav_lock_glyph if toggle.id == TOGGLE_LOCK else palette().on_lit_icon


def navigator_toggle_tooltip(toggle: NavToggle) -> str:
    """Hover text naming the state and what a click does."""
    if toggle.id == TOGGLE_ADD:
        return "Layer limit reached" if toggle.blocked else "Add layer"
    if toggle.id == TOGGLE_WARN:
        return toggle.detail
    if toggle.blocked:
        return "Locked: unlock to change"
    if toggle.inert:
        return "Timeline controls layer visibility"
    if toggle.id == TOGGLE_HOLD:
        return toggle.detail
    if toggle.id == TOGGLE_LOCK:
        return "Locked: click to unlock" if toggle.active else "Unlocked: click to lock"
    if toggle.id == TOGGLE_SOLO:
        return "Solo: click to end solo" if toggle.active else "Click to solo"
    if toggle.id == TOGGLE_PREVIEW:
        return (
            "Previewing cards: click to end preview"
            if toggle.active
            else "Click to preview cards"
        )
    return "On: click to turn off" if toggle.active else "Off: click to turn on"


def navigator_toggle_xs(right_x: float, side: float, gap: float) -> dict[str, float]:
    """Left edge of each toggle's column, ending flush at *right_x*.

    Columns are fixed, so a row without solo keeps its icons under the rows
    that have it, a held layer's pause icon sits left of its on/off, and a
    layer's warning icon left of that. Add shares the lock column, and Overlay's preview the solo
    column.
    """
    xs = dict(zip(_NAV_TOGGLE_COLUMNS, icon_columns(right_x, len(_NAV_TOGGLE_COLUMNS), side, gap)))
    xs[TOGGLE_ADD] = xs[TOGGLE_LOCK]
    xs[TOGGLE_PREVIEW] = xs[TOGGLE_SOLO]
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


@dataclass(frozen=True)
class NavLabelClick:
    """What a press or release on a navigator row's label does.

    ``toggle`` opens or closes the row. ``opened_by_click`` is the row a click
    just opened, so the double-click it starts does not close it again.
    ``swallow_release`` skips the release that ends a toggling double-click,
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
    the second press, so a double-click acts on that press.
    """
    if mode == "dbl-click" and expandable and double_pressed:
        return NavLabelClick(select=True, toggle=True, swallow_release=True)
    if mode == "click-expand" and expandable and double_pressed:
        if expanded and opened_by_click != node_id:
            return NavLabelClick(select=True, toggle=True, swallow_release=True)
        return NavLabelClick(opened_by_click=opened_by_click)
    if not clicked:
        return NavLabelClick(opened_by_click=opened_by_click)
    if swallowing or not expandable or mode in ("dbl-click", "button-only"):
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


def _navigator_content_height_px() -> int:
    """Outer height of the navigator list just drawn in the current window.

    The cursor sits one item-spacing past the last row. Adding the bottom
    padding matches the window size that fits the rows. The top border sits
    inside the top padding, so the bottom border sits inside the bottom
    padding too and the rows centre between the two. Scroll is
    already included in the cursor, so a clipped list still reports its full
    height for the next frame.
    """
    style = imgui.get_style()
    cursor_y = float(imgui.get_cursor_pos().y)
    spacing_y = float(style.item_spacing.y)
    content_bottom = cursor_y - spacing_y
    if content_bottom < 0.0:
        content_bottom = cursor_y
    outer = content_bottom + float(style.window_padding.y)
    return max(1, int(round(outer)))


def _nav_indent() -> float:
    """Navigator indent per level: one icon column, on whole pixels."""
    return float(round(row_band_side()))


def _draw_nav_twisty(
    node: NavNode,
    twisty: str,
    selected: bool,
    x: float,
    band: tuple[float, float],
) -> bool:
    """Disclosure button in the column at *x*, drawn after the row's label.

    The label selectable allows overlap, so the press reaches this button.
    Returns whether it was pressed.
    """
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
    draws a scrollbar. *chrome_px* is the window padding top and bottom and
    *spacing_px* the gap between rows. Rows are uniform.
    """
    if measured_px <= 0 or measured_rows <= 0 or rows == measured_rows:
        return measured_px
    step = (measured_px - chrome_px + spacing_px) / measured_rows
    return max(1, int(math.ceil(measured_px + (rows - measured_rows) * step)))


def _draw_item_suffix(text: str, color: imgui.ImVec4) -> None:
    draw_aligned_parts([(text, color)])


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
    mid_y = math.floor(row_text_y(rect_min.y) + line * 0.5) + 0.5
    elbow_right_x = row_x - math.floor(imgui.get_style().item_spacing.x * 0.5)
    color = imgui.get_color_u32(rgba(palette().navigator_tree_line))
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
        imgui.get_color_u32(rgba(palette().lock_icon)),
        mark,
    )


class NavigatorPanel:
    """The navigator tree: rows, twisties, toggles, and the layer drag."""

    def __init__(self, context: ShellContext, row_drag: RowDrag) -> None:
        self._ctx = context
        self._row_drag = row_drag
        # Drawn navigator list height, applied on the next frame. 0 until measured.
        self._content_height_px = 0
        self._measured_rows = 0
        self._follow = ScrollFollow()
        # Navigator row rects from the last draw, for right-click and Shift+F10.
        self.row_rects: dict[str, tuple[int, int, int, int]] = {}
        # Label-click state for ``navigator_label_click``.
        self._opened_by_click: str | None = None
        self._swallow_release: str | None = None

    @property
    def content_height_px(self) -> int:
        """Navigator list height for the rows now visible. 0 until measured.

        Rows opened or closed since the last draw are included, so the window
        never lags the tree by a frame.
        """
        if self._content_height_px <= 0:
            return 0
        style = imgui.get_style()
        return navigator_height_for_rows(
            self._content_height_px,
            self._measured_rows,
            len(self.visible_nodes()),
            chrome_px=2.0 * float(style.window_padding.y),
            spacing_px=padded_row_spacing_y(),
        )

    def visible_nodes(self) -> tuple[NavNode, ...]:
        return build_navigator(
            self._ctx.controls.session, self._ctx.controls.shell_focus.nav_expanded
        )

    def row_at(self, x: float, y: float) -> str | None:
        """Navigator row under a screen point, from the last draw."""
        for node_id, rect in self.row_rects.items():
            if rect_has_point(rect, x, y):
                return node_id
        return None

    def draw(self, frame: ShellFrame) -> None:
        nodes = frame.nav_nodes
        imgui.push_style_color(imgui.Col_.text, rgba(palette().label))
        try:
            with padded_rows():
                self.row_rects = {}
                for node, rails in zip(nodes, navigator_tree_rails(nodes)):
                    self._draw_node(node, rails)
                self._content_height_px = _navigator_content_height_px()
        finally:
            imgui.pop_style_color()
        self._row_drag.finish(DRAG_LAYER)
        self._measured_rows = len(nodes)

    def _draw_node(self, node: NavNode, rails: tuple[bool, ...]) -> None:
        focus = self._ctx.controls.shell_focus
        # One icon column per level, so a child's twisty sits under its
        # parent's label and the stem from the parent's twisty has an arm.
        indent = node.depth * _nav_indent()
        left_x = imgui.get_cursor_screen_pos().x
        if indent:
            imgui.indent(indent)
        try:
            selected = node.id == focus.selected_id
            focused = (
                selected
                and focus.region is ShellRegion.NAVIGATOR
                and not self._ctx.menu_state.focused
            )
            band_state = (
                RowState.FOCUSED
                if focused
                else RowState.SELECTED if selected else None
            )
            twisty = navigator_twisty(node, focus.nav_expanded)
            row_x = imgui.get_cursor_screen_pos().x
            if twisty is not None:
                # The label starts right after the twisty's column, with no
                # item gap. The twisty draws over that column once the row is done.
                imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + _nav_indent())
            with row_band(band_state) as mark_band:
                moving = (
                    node.draggable
                    and node.slot is not None
                    and node.slot == self._ctx.controls.layer_lifecycle.move_mode_slot
                )
                text_color = navigator_row_text_color(
                    node, selected=selected, moving=moving
                )
                bright = text_color != palette().label
                if bright:
                    imgui.push_style_color(imgui.Col_.text, rgba(text_color))
                try:
                    text_pos = imgui.get_cursor_screen_pos()
                    label = node.label
                    lead = ""
                    if node.draggable:
                        handle_text = nav_handle_text(node)
                        # The handle draws its part of the label itself.
                        lead = _nav_drag_lead() + space_lead(handle_text)
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
                    # The band spans the whole row, under the tree gutter and
                    # twisty, from where an unindented row's highlight starts.
                    mark_band(left_x - math.floor(imgui.get_style().item_spacing.x * 0.5))
                    span = (imgui.get_item_rect_min().y, imgui.get_item_rect_max().y)
                    row_right_x = imgui.get_item_rect_max().x
                    self._record_row_rect(node.id, left_x)
                    if selected:
                        self._follow.follow(node.id)
                finally:
                    if bright:
                        imgui.pop_style_color()
            _draw_nav_tree_lines(rails, left_x, left_x + indent)
            mark = navigator_lock_mark(node)
            if mark is not None:
                _draw_nav_lock_mark(text_pos, node.label, mark)
            if node.badge:
                _draw_item_suffix(node.badge, rgba(palette().label))
            if node.toggles:
                self._draw_toggles(node, row_right_x, span)
            if node.draggable:
                self._layer_row_drag(node, text_pos.x, span, text_color)
            twisty_clicked = twisty is not None and _draw_nav_twisty(
                node, twisty, selected, row_x, span
            )
            if twisty_clicked:
                self._opened_by_click = None
                self.toggle_expanded(node.id)
            elif clicked or double_pressed:
                self._label_click(node, clicked, double_pressed)
        finally:
            if indent:
                imgui.unindent(indent)

    def _label_click(
        self, node: NavNode, clicked: bool, double_pressed: bool
    ) -> None:
        outcome = navigator_label_click(
            self._ctx.controls.cfg.editor.navigator_expand_click,
            node.id,
            expandable=node.expandable,
            expanded=node.id in self._ctx.controls.shell_focus.nav_expanded,
            clicked=clicked,
            double_pressed=double_pressed,
            opened_by_click=self._opened_by_click,
            swallowing=self._swallow_release == node.id,
        )
        self._opened_by_click = outcome.opened_by_click
        if clicked:
            self._swallow_release = None
        if outcome.swallow_release:
            self._swallow_release = node.id
        if outcome.select:
            self._ctx.controls.navigator.select(node.id)
        if outcome.toggle:
            self.toggle_expanded(node.id)

    def _record_row_rect(self, node_id: str, left_x: float) -> None:
        """Remember the row just drawn, for right-click and Shift+F10."""
        rect = drawn_row_rect(left_x)
        if rect is not None:
            self.row_rects[node_id] = rect

    def _draw_toggles(
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
                self._ctx.controls.navigator.select(node.id)
                if toggle.blocked:
                    continue
                if toggle.id == TOGGLE_ADD:
                    command_by_id("layers.add").run(self._ctx.controls)
                else:
                    activate_header_toggle(self._ctx.controls, toggle.id, descriptor)

    def toggle_expanded(self, node_id: str) -> None:
        focus = self._ctx.controls.shell_focus
        if node_id not in focus.nav_expanded:
            focus.nav_expanded.add(node_id)
            return
        focus.nav_expanded.discard(node_id)
        visible = tuple(
            node.id
            for node in build_navigator(
                self._ctx.controls.session, focus.nav_expanded
            )
        )
        focus.selected_id = selection_after_nav_collapse(
            visible,
            focus.selected_id,
            node_id,
        )

    def _layer_row_drag(
        self,
        node: NavNode,
        x: float,
        span: tuple[float, float],
        text_color: tuple[int, int, int],
    ) -> None:
        slot = node.slot
        order = self._ctx.controls.session.layer_z_order
        if slot is None or slot not in order:
            return
        index = order.index(slot)
        if self._row_drag.draw_handle(
            f"##drag-layer-{slot}",
            x,
            span,
            blocked=node.drag_blocked,
            lead=_nav_drag_lead(),
            text=nav_handle_text(node),
            text_color=text_color,
        ):
            self._row_drag.begin(DRAG_LAYER, slot, index)
            self._ctx.controls.navigator.select(node.id)
        drag = self._row_drag.gesture
        if drag is not None and drag.kind == DRAG_LAYER:
            drag.record_span(index, *span)
