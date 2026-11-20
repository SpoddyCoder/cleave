"""Inspector value controls: steppers, choices, icon buttons, and the colour picker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from imgui_bundle import imgui

from cleave.choice import choice_kind, ChoiceKind
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
from cleave.viz.breadcrumbs import CRUMB_ELLIPSIS, CRUMB_SEPARATOR, fit_crumbs
from cleave.viz.icon_button import (
    box_contains,
    box_index_at,
    icon_box,
    icon_gap,
    icon_row,
    text_box,
)
from cleave.viz.imgui_icon_button import glyph_drop, paint_box, paint_hover
from cleave.viz.imgui_theme import rgba
from cleave.viz.inspector import InspectorRow
from cleave.viz.pointer_cursor import PointerShape, request_pointer
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import (
    apply_field_choice,
    apply_field_horizontal,
    apply_field_nav_button,
    row_inert,
    row_spec,
    RowNavButton,
    section_lock_blocks_mutation,
)
from cleave.viz.shell_context import ShellContext
from cleave.viz.shell_widgets import (
    draw_button,
    ImguiTextSizer,
    row_text_y,
    selectable_label_origin,
    value_drag_steps,
    VALUE_DRAG_THRESHOLD_PX,
)
from cleave.viz.text_fit import fit_text_to_width
from cleave.viz.theme import palette, tuning_ui_metrics, ui_chrome_px
from cleave.viz.tooltips import show_tooltip
from cleave.viz.value_nudge import (
    centre_pad,
    nudge_arrow_rects,
    nudge_hit_at,
    nudge_press_skips_row,
    NudgeRect,
)

if TYPE_CHECKING:
    from cleave.viz.preset_browser import BrowserCrumb
    from cleave.viz.controls import TuningControls
    from cleave.viz.row_spec import RowSpec
    from cleave.viz.tuning_view_state import TuningViewState

# Extra space between the menu-bar rule and the first popup row.
# Space above and below a segment or combo box, around the row's text line.
_CHOICE_PAD_Y = 1.0
_SWATCH_ASPECT = 1.6
_SWATCH_GAP = 6.0
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


def apply_value_drag(
    controls: TuningControls,
    desc: RowDescriptor,
    delta_x: float,
    accum: float,
    *,
    threshold: float = VALUE_DRAG_THRESHOLD_PX,
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


def row_icon_boxes(
    start_x: float, band: tuple[float, float], count: int
) -> tuple[tuple[float, float, float, float], ...]:
    """Square boxes for a row's icon buttons, left to right from *start_x*."""
    side = band[1] - band[0]
    return tuple(icon_box(x, band) for x in icon_row(start_x, count, side, icon_gap()))


class ValueControls:
    """The controls right of an inspector row's label, and their gestures.

    ``choice_rects`` is this frame's segment or combo rect for each choice
    row; an open list hangs from its row's rect. ``press_swallowed`` is true
    from a press one of these controls took until the button comes up, so
    the row under it does not also act. ``value_drag_crossed`` is true once
    a held value has stepped.
    """

    def __init__(self, context: ShellContext) -> None:
        self._ctx = context
        self.choice_rects: dict[RowDescriptor, tuple[int, int, int, int]] = {}
        self.choice_list_rows: tuple[tuple[int, int, int, int], ...] = ()
        self.value_drag_accum = 0.0
        self.value_drag_crossed = False
        self.press_swallowed = False
        # True once a control on the row being drawn has the pointer, so the
        # row's own tooltip stays out of the way.
        self.control_hovered = False
        self._picker_pos = imgui.ImVec2(0.0, 0.0)
        # Widest value each stepped row has shown, in characters, so its arrows
        # hold still as the number changes. The shell font is monospace.
        self._stepper_chars: dict[tuple[RowKind, int], int] = {}

    def handle_colour_swatch(
        self,
        state: TuningViewState,
        row: InspectorRow,
        desc: RowDescriptor,
        spec: RowSpec,
        parts: list[tuple[str, imgui.ImVec4]],
        clicked: bool,
    ) -> bool:
        """Paint the swatch left of the hex value. True when it took the click."""
        if spec.colour_target is None:
            return False
        target = spec.colour_target(self._ctx.controls, desc)
        line = imgui.get_text_line_height()
        rect_min = imgui.get_item_rect_min()
        rect_max = imgui.get_item_rect_max()
        pad = imgui.get_style().frame_padding.x
        text_w = sum(imgui.calc_text_size(text).x for text, _color in parts)
        right = rect_max.x - pad - text_w - ui_chrome_px(_SWATCH_GAP)
        y = row_text_y(rect_min.y)
        swatch_min = imgui.ImVec2(right - line * _SWATCH_ASPECT, y)
        swatch_max = imgui.ImVec2(right, y + line)
        draw = imgui.get_window_draw_list()
        if target.current is not None:
            draw.add_rect_filled(
                swatch_min, swatch_max, imgui.get_color_u32(rgba(target.current))
            )
        draw.add_rect(swatch_min, swatch_max, imgui.get_color_u32(rgba(palette().button_border)))
        if not imgui.is_mouse_hovering_rect(swatch_min, swatch_max):
            return False
        locked = section_lock_blocks_mutation(state, desc)
        if not locked and imgui.is_window_hovered():
            request_pointer(PointerShape.HAND)
        if clicked and not locked:
            self._ctx.controls.inspector.focus_row(row)
            self._ctx.controls.inline_edit.begin_colour(desc, target)
            self._picker_pos = imgui.ImVec2(swatch_min.x, swatch_max.y)
        return True

    def draw_colour_picker(self) -> None:
        """The picker window for the colour being edited, updating it live."""
        inline = self._ctx.controls.inline_edit
        edit = inline.colour_edit
        if edit is None:
            return
        imgui.set_next_window_pos(self._picker_pos, imgui.Cond_.always)
        imgui.begin("##colour-picker", None, _PICKER_FLAGS)
        try:
            value = edit.value if edit.value is not None else palette().value
            changed, picked = imgui.color_picker3(
                "##colour",
                [channel / 255.0 for channel in value],
                _PICKER_COLOUR_FLAGS,
            )
            if changed:
                inline.set_colour(
                    tuple(int(round(channel * 255.0)) for channel in picked)
                )
            done = draw_button("Done")
            if edit.target.optional:
                imgui.same_line()
                cleared = draw_button("None")
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

    def handle_nav_buttons(
        self,
        state: TuningViewState,
        row: InspectorRow,
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
        origin_x, _text_y = selectable_label_origin()
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
        blocked = not stepped or self._ctx.input_blocked()
        mouse = imgui.get_mouse_pos()
        hit = None if blocked else box_index_at(boxes, mouse.x, mouse.y)
        hold_armed = self._ctx.controls.value_nudge.armed
        available = [button.available(state, desc) for button in buttons]
        if hit is not None:
            self.control_hovered = True
            if buttons[hit].tooltip is not None:
                show_tooltip(buttons[hit].tooltip(state, desc))
        for index, (button, box) in enumerate(zip(buttons, boxes)):
            lit = index == hit and available[index] and not hold_armed
            if lit:
                request_pointer(PointerShape.HAND)
            paint_box(
                box,
                button.glyph,
                color=value_color if available[index] else palette().disabled,
                hovered=lit,
            )
        if not activated or hit is None:
            return
        self._ctx.controls.inspector.focus_row(row)
        if available[hit]:
            apply_field_nav_button(self._ctx.controls, desc, hit)
        self.clear_value_drag()
        self.press_swallowed = True

    def handle_path_crumbs(
        self,
        row: InspectorRow,
        desc: RowDescriptor,
        crumbs: tuple[BrowserCrumb, ...],
        value_color: tuple[int, int, int],
        icon: tuple[str, tuple[int, int, int]] | None,
        *,
        lead_x: float,
        enabled: bool,
        activated: bool,
    ) -> None:
        """The second line of a path row as folders a press jumps to.

        Coloured as in the preset browser: parent folders in the label colour,
        separators muted, the folder shown in the value colour. Parents that
        do not fit fold into an ellipsis that goes to the nearest of them. A
        press on a folder is swallowed, so it never opens a subfolder too.
        """
        origin_x, origin_y = selectable_label_origin()
        line = imgui.get_text_line_height()
        y = origin_y + line
        x = origin_x + lead_x
        right_x = imgui.get_item_rect_max().x - imgui.get_style().frame_padding.x
        draw = imgui.get_window_draw_list()
        dimmed = value_color in (palette().disabled, palette().locked)
        if icon is not None:
            glyph, accent = icon
            draw.add_text(
                imgui.ImVec2(x, y + glyph_drop(glyph)),
                imgui.get_color_u32(rgba(value_color if dimmed else accent)),
                glyph,
            )
            x += imgui.calc_text_size(f"{glyph} ").x
        sizer = ImguiTextSizer()
        labels = tuple(crumb.label for crumb in crumbs)
        slots = fit_crumbs(
            labels,
            max(1, int(right_x - x)),
            lambda text: int(imgui.calc_text_size(text).x),
            lambda text, px: fit_text_to_width(sizer, text, px),
        )
        last = len(labels) - 1
        separator_w = imgui.calc_text_size(CRUMB_SEPARATOR).x
        space_w = imgui.calc_text_size(" ").x
        band = (y, y + line)
        blocked = not enabled or self._ctx.input_blocked()
        mouse = imgui.get_mouse_pos()
        hit: int | None = None
        for position, slot in enumerate(slots):
            slot_x = x + slot.x
            if position:
                draw.add_text(
                    imgui.ImVec2(slot_x - separator_w, y),
                    imgui.get_color_u32(rgba(value_color if dimmed else palette().muted)),
                    CRUMB_SEPARATOR,
                )
            current = slot.index == last and slot.text != CRUMB_ELLIPSIS
            target = crumbs[slot.index].path
            if not current and target is not None and not blocked:
                box = text_box(slot_x - space_w / 2, slot.width, space_w, band)
                if box_contains(box, mouse.x, mouse.y):
                    self.control_hovered = True
                    paint_hover(box)
                    request_pointer(PointerShape.HAND)
                    show_tooltip(f"Go to {crumbs[slot.index].label}")
                    hit = slot.index
            color = value_color if current or dimmed else palette().label
            draw.add_text(imgui.ImVec2(slot_x, y), imgui.get_color_u32(rgba(color)), slot.text)
        if not activated or hit is None or desc.slot is None:
            return
        self._ctx.controls.inspector.focus_row(row)
        target = crumbs[hit].path
        if target is not None:
            self._ctx.controls.layer_mutations.browse_directory(desc.slot, target)
        self.clear_value_drag()
        self.press_swallowed = True

    def handle_value_nudge(
        self,
        row: InspectorRow,
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
        blocked = self._ctx.input_blocked()
        mouse = imgui.get_mouse_pos()
        hit = (
            None
            if blocked
            else nudge_hit_at(mouse.x, mouse.y, back_rect, forward_rect)
        )
        hold = self._ctx.controls.value_nudge
        held_here = hold.armed and hold.desc == desc
        hover_forward: bool | None = None
        if held_here:
            hover_forward = hold.forward
        elif hit is not None and not hold.armed:
            hover_forward = hit.forward
        if hover_forward is not None:
            self.control_hovered = True
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
        self._ctx.controls.inspector.focus_row(row)
        apply_field_horizontal(self._ctx.controls, desc, hit.forward, False)
        self._ctx.controls.begin_value_nudge(desc, hit.forward, repeatable)
        self.clear_value_drag()
        self.press_swallowed = True

    def _paint_nudge_hover(
        self,
        rect: NudgeRect,
        forward: bool,
    ) -> None:
        paint_stepper_hover(
            (rect.min_x, rect.min_y, rect.max_x - rect.min_x, rect.max_y - rect.min_y),
            forward=forward,
        )

    def fixed_width_value(self, kind: RowKind, text: str) -> str:
        """``text`` centred in the widest value this row has shown."""
        key = (kind, tuning_ui_metrics().font_size)
        width = max(len(text), self._stepper_chars.get(key, 0))
        self._stepper_chars[key] = width
        return centre_pad(text, width)

    def draw_choice_value(
        self,
        state: TuningViewState,
        row: InspectorRow,
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
        measure = ImguiTextSizer()
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
            origin_x, _origin_y = selectable_label_origin()
            left = int(origin_x + imgui.calc_text_size(f"{after_label}  ").x)
        top = int(row_text_y(rect_min.y)) - pad_y
        rect = (left, top, width, int(line) + pad_y * 2)
        index = spec.choice.index(state, desc)
        draw = imgui.get_window_draw_list()
        inline = self._ctx.controls.inline_edit
        list_view = inline.choice_view
        open_here = list_view is not None and list_view.target == desc
        hover = list_view is None and not self._ctx.input_blocked()
        hand = not row_inert(state, desc)
        self.choice_rects[desc] = rect
        if open_here and activated:
            # A press anywhere on the open row closes its list. Swallow it so
            # the release does not activate the row and open the list again.
            inline.finish()
            self.clear_value_drag()
            self.press_swallowed = True
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
            self._ctx.controls.inspector.focus_row(row)
            apply_field_choice(self._ctx.controls, desc, hit - index)
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
            self._ctx.controls.inspector.open_choice(row)
        self.clear_value_drag()
        self.press_swallowed = True

    def draw_choice_list_window(self) -> None:
        """The open combo list of an inspector row, over every other window."""
        inline = self._ctx.controls.inline_edit
        view = inline.choice_view
        if view is None:
            return
        anchor = self.choice_rects.get(view.target)
        if anchor is None:
            # The row scrolled away or left the page.
            inline.finish()
            return
        pointer = draw_choice_list(
            "inspector-choice-list", view, ImguiTextSizer(), anchor=anchor
        )
        self.choice_list_rows = pointer.rows
        if pointer.rect is not None:
            self._ctx.top_layer.claim(pointer.rect)
        if pointer.picked is not None:
            inline.pick_choice(pointer.picked)
        elif pointer.outside:
            inline.finish()
        elif pointer.hovered is not None:
            inline.hover_choice(pointer.hovered)

    def track_value_drag(
        self,
        row: InspectorRow,
        desc: RowDescriptor,
        *,
        activated: bool,
        active: bool,
    ) -> None:
        """Step a held inspector value from this frame's horizontal mouse delta."""
        if not active:
            return
        if activated:
            self.value_drag_accum = 0.0
            self.value_drag_crossed = False
        delta_x = float(imgui.get_io().mouse_delta.x)
        remaining, crossed = apply_value_drag(
            self._ctx.controls,
            desc,
            delta_x,
            self.value_drag_accum,
        )
        self.value_drag_accum = remaining
        if not crossed:
            return
        self.value_drag_crossed = True
        self._ctx.controls.inspector.focus_row(row)

    def clear_value_drag(self) -> None:
        self.value_drag_accum = 0.0
        self.value_drag_crossed = False

    def release_gestures(self) -> None:
        """Drop the value drag and the swallowed press once the button is up."""
        if not imgui.is_mouse_down(0):
            self.clear_value_drag()
            self.press_swallowed = False
