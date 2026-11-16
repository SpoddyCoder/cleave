"""The shell's transport bar: play state, clock, bar, frame rate, and toasts."""

from __future__ import annotations

import math
from dataclasses import dataclass

from imgui_bundle import imgui

from cleave.viz.frame_rate import format_fps_value
from cleave.viz.icon_button import glyph_x, text_box
from cleave.viz.imgui_host import PAUSE_GLYPH, PLAY_GLYPH
from cleave.viz.imgui_icon_button import box_button, glyph_drop, paint_hover, text_top
from cleave.viz.imgui_theme import rgba, row_band
from cleave.viz.panel_notification import (
    notification_attention,
    PanelNotificationActive,
)
from cleave.viz.playback import format_mmss
from cleave.viz.pointer_cursor import PointerShape, request_pointer
from cleave.viz.shell_context import ShellContext
from cleave.viz.shell_widgets import (
    InlineField,
    packed_color,
    PANEL_BORDER_PX,
    stroke_h_rule,
    swipe_fill,
    value_drag_steps,
    VALUE_DRAG_THRESHOLD_PX,
)
from cleave.viz.theme import (
    ERROR_NOTIFICATION,
    HIGHLIGHT,
    NOTIFICATION_ON_FILL,
    ICON_HOVER_FG,
    TRANSPORT_RULE,
    ui_chrome_px,
    VALUE,
)
from cleave.viz.transport_controls import TransportField

_TRANSPORT_GAP = 16.0


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


def transport_content_pad_y(
    window_height: float, line_height: float, rule_px: float
) -> float:
    """Top padding that centres one text line between the bar's top and its rule.

    The bottom rule fills the bar's last *rule_px* rows, so the line centres
    in the rows above it, on a whole pixel.
    """
    spare = float(window_height) - float(rule_px) - float(line_height)
    return float(max(0, math.floor(spare * 0.5)))


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
        fill = swipe_fill(
            chip_w,
            attention.fill_progress,
            from_left=attention.fill_from_left,
        )
        if fill is not None:
            fill_x, fill_w = fill
            draw.add_rect_filled(
                imgui.ImVec2(chip_x + fill_x, origin.y),
                imgui.ImVec2(chip_x + fill_x + fill_w, origin.y + size.y),
                packed_color(notice.accent),
            )
        text_x = origin.x + (size.x - text_size.x) * 0.5
        text_y = origin.y + (size.y - text_size.y) * 0.5
        role = notice.accent
        if attention.text_on_fill and fill is not None:
            fill_x, fill_w = fill
            mid = text_x + text_size.x * 0.5
            if chip_x + fill_x <= mid < chip_x + fill_x + fill_w:
                role = NOTIFICATION_ON_FILL
        draw.add_text(imgui.ImVec2(text_x, text_y), packed_color(role), notice.text)
    finally:
        draw.pop_clip_rect()
    return chip


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


class TransportBar:
    """Play state, clock, bar, frame rate, and the toast chip."""

    def __init__(self, context: ShellContext, inline_field: InlineField) -> None:
        self._ctx = context
        self._inline = inline_field
        self._drag_accum = 0.0
        # True on the frame a click landed on a timed toast.
        self.notice_clicked = False

    def draw(
        self,
        readout: TransportReadout,
        notice: PanelNotificationActive | None,
    ) -> None:
        for index, part in enumerate(transport_parts(readout)):
            if index:
                gap = ui_chrome_px(_TRANSPORT_GAP) if part.gap else 0.0
                imgui.same_line(0.0, gap)
            self._draw_part(part)
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
                    self.notice_clicked = True
        origin = imgui.get_window_pos()
        size = imgui.get_window_size()
        stroke_h_rule(
            origin.x,
            origin.x + size.x,
            origin.y + size.y - 1.0,
            TRANSPORT_RULE,
            PANEL_BORDER_PX,
        )

    def _draw_part(self, part: TransportPart) -> None:
        """One transport part, a space wider than its text for the hover fill.

        Play and pause toggle on click. The time and the bar step while
        dragged sideways and open a text field on double-click.
        """
        space = imgui.calc_text_size(" ").x
        line = imgui.get_text_line_height()
        text_w = imgui.calc_text_size(part.label).x
        field = part.field
        inline = self._ctx.controls.inline_edit
        if field is not None and inline.text_target is field:
            template = _TRANSPORT_FIELD_TEMPLATE[field]
            width = max(text_w, imgui.calc_text_size(template).x) + space
            imgui.dummy(imgui.ImVec2(width, line))
            view = inline.text_view()
            if view is not None:
                self._inline.paint(
                    imgui.get_item_rect_min(), imgui.get_item_rect_max(), view
                )
            return
        imgui.dummy(imgui.ImVec2(text_w + space, line))
        origin = imgui.get_item_rect_min()
        box = text_box(origin.x, text_w, space, row_band(origin.y))
        if field is None or self._ctx.input_blocked():
            self._paint_text(part, box, hovered=False)
            return
        pointer = (
            PointerShape.HAND if field is TransportField.PLAY else PointerShape.RESIZE_EW
        )
        state = box_button(f"##transport-{field.value}", box, pointer=pointer)
        self._paint_text(part, box, hovered=state.hovered or state.held)
        if state.held:
            request_pointer(pointer)
        transport = self._ctx.controls.transport
        if field is TransportField.PLAY:
            if state.pressed:
                transport.toggle_pause()
            return
        if state.activated:
            self._drag_accum = 0.0
            transport.begin_drag(field)
        if state.held:
            steps, self._drag_accum = value_drag_steps(
                self._drag_accum + float(imgui.get_io().mouse_delta.x),
                VALUE_DRAG_THRESHOLD_PX,
            )
            transport.drag_step(field, steps)
        if state.released:
            transport.end_drag()
        if state.hovered and imgui.is_mouse_double_clicked(0):
            transport.end_drag()
            transport.begin_entry(field)
            self._inline.began = True

    def _paint_text(
        self,
        part: TransportPart,
        box: tuple[float, float, float, float],
        *,
        hovered: bool,
    ) -> None:
        """The part's icon and text, centred in *box*, on the wash when hovered."""
        color = part.color
        if hovered:
            paint_hover(box)
            color = ICON_HOVER_FG
        draw = imgui.get_window_draw_list()
        u32 = imgui.get_color_u32(rgba(color))
        x = glyph_x(box, imgui.calc_text_size(part.label).x)
        y = text_top(box)
        if part.icon:
            draw.add_text(imgui.ImVec2(x, y + glyph_drop(part.icon[0])), u32, part.icon)
            x += imgui.calc_text_size(f"{part.icon} ").x
        draw.add_text(imgui.ImVec2(x, y), u32, part.text)
