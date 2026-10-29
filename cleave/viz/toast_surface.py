"""ImGui toast. Draw records a pointer intent and does not dismiss it."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from imgui_bundle import imgui

from cleave.viz.imgui_theme import rgba
from cleave.viz.modal_layout import TextMeasure
from cleave.viz.panel_notification import (
    PanelNotificationActive,
    notification_attention,
)
from cleave.viz.shell_layout import ShellLayout
from cleave.viz.theme import (
    ERROR_NOTIFICATION,
    HIGHLIGHT,
    NOTIFICATION_ON_FILL,
    tuning_ui_metrics,
)
from cleave.viz.toast_layout import Rect, ToastGeometry, toast_geometry

_TOAST_WINDOW = "##toast"
_TOAST_FLAGS = (
    int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_nav)
    | int(imgui.WindowFlags_.no_inputs)
    | int(imgui.WindowFlags_.no_bring_to_front_on_focus)
    | int(imgui.WindowFlags_.no_scrollbar)
    | int(imgui.WindowFlags_.no_scroll_with_mouse)
)
_Role = tuple[int, int, int]


class ToastPointerKind(Enum):
    DISMISS_TIMED = "dismiss_timed"


@dataclass(frozen=True)
class ToastPointerIntent:
    """Click on the timed line. The persistent line has no intent."""

    kind: ToastPointerKind


class NotificationDismiss(Protocol):
    def dismiss_notification(self) -> None: ...


def apply_toast_pointer(
    target: NotificationDismiss, intent: ToastPointerIntent | None
) -> None:
    """Map one recorded intent onto ``dismiss_notification``. ``None`` does nothing."""
    if intent is None:
        return
    if intent.kind is ToastPointerKind.DISMISS_TIMED:
        target.dismiss_notification()


def _contains(rect: Rect, x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rw > 0 and rh > 0 and rx <= x < rx + rw and ry <= y < ry + rh


def _shift(rect: Rect | None, dx: int, dy: int) -> Rect | None:
    if rect is None:
        return None
    x, y, width, height = rect
    return (x + dx, y + dy, width, height)


def _packed(role: _Role) -> int:
    return int(imgui.get_color_u32(rgba(role)))


def _raise_toast() -> None:
    imgui.internal.bring_window_to_display_front(
        imgui.internal.find_window_by_name(_TOAST_WINDOW)
    )


def _current_rect() -> Rect:
    pos = imgui.get_window_pos()
    size = imgui.get_window_size()
    return (int(pos.x), int(pos.y), max(0, int(size.x)), max(0, int(size.y)))


def _draw_line(
    draw: imgui.ImDrawList,
    rect: Rect,
    text: str,
    accent: _Role,
    elapsed_sec: float,
) -> None:
    attention = notification_attention(elapsed_sec)
    x, y, width, height = rect
    if attention.fill_progress > 0.001 and width > 0 and height > 0:
        if attention.fill_progress >= 0.999:
            fill_w = width
        else:
            fill_w = max(1, int(round(width * attention.fill_progress)))
        fill_x = x if attention.fill_from_left else x + max(0, width - fill_w)
        draw.add_rect_filled(
            imgui.ImVec2(float(fill_x), float(y)),
            imgui.ImVec2(float(fill_x + fill_w), float(y + height)),
            _packed(accent),
        )
    if not text:
        return
    role = NOTIFICATION_ON_FILL if attention.text_on_fill else accent
    pad_x = tuning_ui_metrics().padding
    draw.add_text(
        imgui.ImVec2(float(x + pad_x), float(y)),
        _packed(role),
        text,
    )


class ToastSurface:
    """Visualiser-corner toast. ``modal`` is false, so it draws without a scrim.

    ``intent`` is the pointer result of the last ``draw`` (one, or None).
    """

    modal = False

    def __init__(
        self,
        active: PanelNotificationActive,
        layout: ShellLayout,
        measure: TextMeasure,
    ) -> None:
        self.active = active
        self.layout = layout
        self.measure = measure
        self.intent: ToastPointerIntent | None = None
        self.rect: Rect | None = None
        self.persistent_line_rect: Rect | None = None
        self.timed_line_rect: Rect | None = None

    def draw(self) -> Rect:
        self.intent = None
        geometry = toast_geometry(
            self.layout,
            self.measure,
            persistent=self.active.persistent_message,
            timed=self.active.message,
        )
        self.rect = geometry.rect
        self.persistent_line_rect = geometry.persistent_line
        self.timed_line_rect = geometry.timed_line
        if geometry.rect[2] <= 0 or geometry.rect[3] <= 0:
            return geometry.rect

        x, y, width, height = geometry.rect
        imgui.set_next_window_pos(
            imgui.ImVec2(float(x), float(y)), imgui.Cond_.always
        )
        imgui.set_next_window_size(
            imgui.ImVec2(float(width), float(height)), imgui.Cond_.always
        )
        pushed_vars = 0
        begun = False
        try:
            imgui.push_style_var(
                imgui.StyleVar_.window_padding, imgui.ImVec2(0.0, 0.0)
            )
            pushed_vars += 1
            imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
            pushed_vars += 1
            imgui.begin(_TOAST_WINDOW, None, _TOAST_FLAGS)
            begun = True
            _raise_toast()
            self._place(geometry)
            self._record_pointer()
            rect = _current_rect()
            self.rect = rect
            return rect
        finally:
            try:
                if begun:
                    imgui.end()
            finally:
                if pushed_vars:
                    imgui.pop_style_var(pushed_vars)

    def _place(self, geometry: ToastGeometry) -> None:
        pos = imgui.get_window_pos()
        dx = int(pos.x) - geometry.rect[0]
        dy = int(pos.y) - geometry.rect[1]
        self.persistent_line_rect = _shift(geometry.persistent_line, dx, dy)
        self.timed_line_rect = _shift(geometry.timed_line, dx, dy)
        draw = imgui.get_window_draw_list()
        window = _current_rect()
        draw.push_clip_rect(
            imgui.ImVec2(float(window[0]), float(window[1])),
            imgui.ImVec2(
                float(window[0] + window[2]), float(window[1] + window[3])
            ),
            True,
        )
        try:
            active = self.active
            persistent = self.persistent_line_rect
            if persistent is not None and active.persistent_message is not None:
                _draw_line(
                    draw,
                    persistent,
                    active.persistent_message,
                    ERROR_NOTIFICATION,
                    active.persistent_elapsed_sec,
                )
            timed = self.timed_line_rect
            if timed is not None and active.message is not None:
                _draw_line(
                    draw,
                    timed,
                    active.message,
                    HIGHLIGHT,
                    active.elapsed_sec,
                )
        finally:
            draw.pop_clip_rect()

    def _record_pointer(self) -> None:
        timed = self.timed_line_rect
        if timed is None:
            return
        io = imgui.get_io()
        if not bool(io.mouse_clicked[0]):
            return
        pos = io.mouse_pos
        if _contains(timed, float(pos.x), float(pos.y)):
            self.intent = ToastPointerIntent(ToastPointerKind.DISMISS_TIMED)
