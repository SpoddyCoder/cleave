"""Drawing helpers the shell's region modules share, and two shared gestures."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from cleave.viz.button_paint import ButtonState, ButtonTone, button_text_role, paint_button
from cleave.viz.drag_reorder import DRAG_PRESET, RowDragGesture
from cleave.viz.icon_button import text_box
from cleave.viz.imgui_icon_button import box_button, paint_box
from cleave.viz.imgui_theme import rgba
from cleave.viz.material_icons import DRAG_INDICATOR_GLYPH
from cleave.viz.pointer_cursor import PointerShape, request_pointer
from cleave.viz.shell_context import ShellContext
from cleave.viz.theme import palette
from cleave.viz.tooltips import show_tooltip
from cleave.viz.value_nudge import nudge_cluster_origin_x, selectable_text_y

if TYPE_CHECKING:
    from cleave.viz.inline_edit import InlineTextView

# Border pushed onto navigator and inspector windows.
PANEL_BORDER_PX = 2.0
# One Left/Right step per this many pixels of sideways drag.
VALUE_DRAG_THRESHOLD_PX = 10.0


def value_drag_steps(accum: float, threshold: float) -> tuple[int, float]:
    """Split a signed pixel accumulator into steps and a sub-threshold remainder.

    Positive *accum* steps forward. ``25`` at ``10`` is ``(2, 5.0)``;
    ``-25`` is ``(-2, -5.0)``; ``9`` is ``(0, 9.0)``.
    """
    steps = math.trunc(accum / threshold)
    if steps == 0:
        return 0, accum
    return steps, accum - steps * threshold


def rect_has_point(rect: tuple[int, int, int, int], x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rw > 0 and rh > 0 and rx <= x < rx + rw and ry <= y < ry + rh


def row_text_y(item_min_y: float) -> float:
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


def selectable_label_origin() -> tuple[float, float]:
    """Top-left of the current selectable's label.

    The item rect is the highlight, which Selectable grows by half of
    ItemSpacing. The label itself is drawn at the unpadded cursor.
    """
    rect_min = imgui.get_item_rect_min()
    spacing_x = imgui.get_style().item_spacing.x
    return (
        rect_min.x + float(math.trunc(spacing_x * 0.5)),
        row_text_y(rect_min.y),
    )


def drag_handle_lead(glyph_width: float, space_width: float) -> int:
    """Spaces to put before a row label so the drag handle fits in front of it."""
    if space_width <= 0:
        return 0
    return max(1, math.ceil((glyph_width + space_width) / space_width))


def space_lead(text: str) -> str:
    """Spaces at least as wide as *text*, to hold its place in a label."""
    if not text:
        return ""
    space = imgui.calc_text_size(" ").x
    if space <= 0:
        return ""
    return " " * math.ceil(imgui.calc_text_size(text).x / space)


def draw_aligned_parts(parts: list[tuple[str, imgui.ImVec4]]) -> None:
    if not parts:
        return
    widths = [imgui.calc_text_size(text).x for text, _color in parts]
    rect_min = imgui.get_item_rect_min()
    rect_max = imgui.get_item_rect_max()
    pad = imgui.get_style().frame_padding.x
    x = nudge_cluster_origin_x(rect_max.x, widths, pad)
    # Same line as the selectable label. Navigator badges use this too.
    y = row_text_y(rect_min.y)
    draw = imgui.get_window_draw_list()
    for (text, color), width in zip(parts, widths):
        draw.add_text(imgui.ImVec2(x, y), imgui.get_color_u32(color), text)
        x += width


class ImguiTextSizer:
    """Measure text with the current ImGui font for the text fitters."""

    def size(self, text: str) -> tuple[int, int]:
        measured = imgui.calc_text_size(text)
        return math.ceil(measured.x), math.ceil(measured.y)


def packed_color(role: tuple[int, int, int]) -> int:
    return int(imgui.get_color_u32(rgba(role)))


def swipe_fill(
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


def stroke_h_rule(
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


def draw_item_focus_ring() -> None:
    """1px focus edge around the current item (a focused panel button) on its window.

    The window list is painted with that panel, so a later menu popup covers
    the outline where they overlap. The foreground list would sit above the
    popup.
    """
    rect_min = imgui.get_item_rect_min()
    rect_max = imgui.get_item_rect_max()
    if rect_max.x <= rect_min.x or rect_max.y <= rect_min.y:
        return
    color = imgui.get_color_u32(rgba(palette().row_focus_edge))
    imgui.get_window_draw_list().add_rect(
        rect_min,
        rect_max,
        color,
        0.0,
        0,
        1.0,
    )


def drawn_row_rect(left_x: float) -> tuple[int, int, int, int] | None:
    """The item just drawn, from *left_x*, clipped to its window. None when hidden."""
    rect_min = imgui.get_item_rect_min()
    rect_max = imgui.get_item_rect_max()
    window_y = imgui.get_window_pos().y
    top = max(rect_min.y, window_y)
    bottom = min(rect_max.y, window_y + imgui.get_window_height())
    if bottom <= top:
        return None
    return (int(left_x), int(top), int(rect_max.x - left_x), int(bottom - top))


def hand_on_hover() -> None:
    """Ask for the hand pointer while the item just drawn is hovered."""
    if imgui.is_item_hovered():
        request_pointer(PointerShape.HAND)


def draw_button(
    label: str,
    *,
    text_role: tuple[int, int, int] | None = None,
    selected: bool = False,
    enabled: bool = True,
    off: bool = False,
) -> bool:
    """A framed panel button at the cursor. Returns whether it was clicked.

    Painted by ``button_paint``: it lights violet under the pointer and sinks
    while held. A button that is not *enabled* stays at rest and keeps the
    arrow pointer. An *off* button (on a switched-off or locked page, or not
    enabled) rests in the darker OFF tone. Text after ``##`` is the id only.
    """
    text = label.split("##", 1)[0]
    pad = imgui.get_style().frame_padding
    text_size = imgui.calc_text_size(text)
    size = imgui.ImVec2(text_size.x + pad.x * 2.0, text_size.y + pad.y * 2.0)
    clicked = imgui.invisible_button(label, size)
    if enabled:
        hand_on_hover()
    rect_min = imgui.get_item_rect_min()
    state = ButtonState.REST
    if enabled and imgui.is_item_active():
        state = ButtonState.PRESSED
    elif enabled and imgui.is_item_hovered():
        state = ButtonState.HOVER
    draw = imgui.get_window_draw_list()
    tone = ButtonTone.OFF if off and state is ButtonState.REST else ButtonTone.PLAIN
    paint_button(draw, (rect_min.x, rect_min.y, size.x, size.y), tone, state)
    role = button_text_role(tone, state) or text_role or palette().value
    draw.add_text(
        imgui.ImVec2(rect_min.x + pad.x, rect_min.y + pad.y), packed_color(role), text
    )
    if selected:
        draw_item_focus_ring()
    return clicked


class InlineField:
    """Paints an open text field and remembers this frame's pointer use.

    ``hovered`` is true when the pointer was on a field this frame.
    ``began`` is true when a click this frame opened one.
    """

    def __init__(self) -> None:
        self.hovered = False
        self.began = False

    def reset(self) -> None:
        self.hovered = False
        self.began = False

    def paint(
        self,
        field_min: imgui.ImVec2,
        field_max: imgui.ImVec2,
        view: InlineTextView,
        *,
        text_y: float | None = None,
    ) -> None:
        """A text field with a caret. *text_y* defaults to the field's top."""
        if imgui.is_mouse_hovering_rect(field_min, field_max):
            self.hovered = True
            request_pointer(PointerShape.TEXT)
        pad = imgui.get_style().frame_padding.x
        width = field_max.x - field_min.x
        draw = imgui.get_window_draw_list()
        draw.add_rect_filled(field_min, field_max, imgui.get_color_u32(rgba(palette().background)))
        border = palette().error_notification if view.error is not None else palette().highlight
        draw.add_rect(field_min, field_max, imgui.get_color_u32(rgba(border)))
        inner = width - pad * 2
        caret_x = imgui.calc_text_size(view.draft[: view.caret_index]).x
        text_x = field_min.x + pad - max(0.0, caret_x - inner)
        y = field_min.y if text_y is None else text_y
        draw.push_clip_rect(field_min, field_max, True)
        text_u32 = imgui.get_color_u32(rgba(palette().value))
        draw.add_text(imgui.ImVec2(text_x, y), text_u32, view.draft)
        if view.caret_visible:
            line = imgui.get_text_line_height()
            draw.add_line(
                imgui.ImVec2(text_x + caret_x, y),
                imgui.ImVec2(text_x + caret_x, y + line),
                imgui.get_color_u32(rgba(palette().highlight)),
            )
        draw.pop_clip_rect()
        if view.error is not None:
            show_tooltip(view.error)


class RowDrag:
    """A held reorder handle on a preset list item or a layer row."""

    def __init__(self, context: ShellContext) -> None:
        self._ctx = context
        self.gesture: RowDragGesture | None = None

    def draw_handle(
        self,
        item_id: str,
        x: float,
        band: tuple[float, float],
        *,
        blocked: bool,
        lead: str,
        text: str = "",
        text_color: tuple[int, int, int] | None = None,
    ) -> bool:
        """Leading reorder handle on the row just drawn, with its left edge at *x*.

        The glyph fills the *lead* column. *text*, the start of the row's label,
        follows it inside the handle, so it washes and takes the press too; it
        keeps *text_color* until hovered. The row selectable allows overlap, so
        the press reaches this button. True on the press that starts a drag; a
        blocked handle never starts one.
        """
        glyph_column = imgui.calc_text_size(lead).x
        text_w = imgui.calc_text_size(space_lead(text)).x
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
            color=palette().locked if blocked else palette().muted,
            hovered=lit,
        )
        if text:
            label_box = (box[0] + glyph_column, box[1], text_w, box[3])
            paint_box(
                label_box,
                text,
                color=palette().label if text_color is None else text_color,
                hovered=lit,
                icon=False,
            )
        if state.hovered and not state.held:
            show_tooltip("Locked: unlock to reorder" if blocked else "Drag to reorder")
        return state.activated and not blocked

    def begin(self, kind: str, slot: str, index: int) -> None:
        """Start a mouse reorder as move mode, so Esc restores and release keeps it."""
        controls = self._ctx.controls
        controls.layer_lifecycle.confirm_move_mode()
        controls.preset_list.confirm_move_mode()
        if kind == DRAG_PRESET:
            controls.preset_list.enter_move_mode(slot, index)
        else:
            controls.layer_lifecycle.enter_move_mode(slot)
        self.gesture = RowDragGesture(kind, slot, index)

    def _row_drag_in_move_mode(self, drag: RowDragGesture) -> bool:
        controls = self._ctx.controls
        if drag.kind == DRAG_PRESET:
            return controls.preset_list.move_mode_preset == (drag.slot, drag.index)
        return controls.layer_lifecycle.move_mode_slot == drag.slot

    def finish(self, kind: str) -> None:
        """Move the dragged row under the pointer, or confirm it on release.

        Esc (or a view rebuild) ends move mode while the button is still down;
        the gesture then drops without moving anything further.
        """
        drag = self.gesture
        if drag is None or drag.kind != kind:
            return
        if not self._row_drag_in_move_mode(drag):
            self.gesture = None
            return
        controls = self._ctx.controls
        if not imgui.is_mouse_down(0):
            if kind == DRAG_PRESET:
                controls.preset_list.confirm_move_mode()
            else:
                controls.layer_lifecycle.confirm_move_mode()
            self.gesture = None
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
