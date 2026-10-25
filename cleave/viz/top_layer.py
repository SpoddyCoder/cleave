"""Windows drawn above the shell: a modal scrim, then each pushed surface.

``draw`` records the rects it submitted. Hit testing reads that record on
the next frame. ``empty`` is this frame's push list, not the record.
"""

from __future__ import annotations

from typing import Protocol

from imgui_bundle import imgui

from cleave.viz.imgui_theme import rgba
from cleave.viz.info_panel import InfoPanelViewState
from cleave.viz.theme import ACTION, LABEL, VALUE

Rect = tuple[int, int, int, int]

_SCRIM_WINDOW = "##top-scrim"
_INFO_WINDOW = "##info-panel"
_SCRIM_FLAGS = (
    int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_nav)
    | int(imgui.WindowFlags_.no_bring_to_front_on_focus)
    | int(imgui.WindowFlags_.no_scrollbar)
    | int(imgui.WindowFlags_.no_scroll_with_mouse)
)
_INFO_FLAGS = (
    int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.always_auto_resize)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_nav)
    | int(imgui.WindowFlags_.no_bring_to_front_on_focus)
)


class TopLayerSurface(Protocol):
    modal: bool

    def draw(self) -> Rect:
        """Open one window and return its rect in pixels."""


def _raise(name: str) -> None:
    imgui.internal.bring_window_to_display_front(
        imgui.internal.find_window_by_name(name)
    )


def _current_rect() -> Rect:
    pos = imgui.get_window_pos()
    size = imgui.get_window_size()
    return (int(pos.x), int(pos.y), max(0, int(size.x)), max(0, int(size.y)))


def _contains(rect: Rect, x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rw > 0 and rh > 0 and rx <= x < rx + rw and ry <= y < ry + rh


def _style_color(slot: imgui.Col_) -> imgui.ImVec4:
    color = imgui.get_style().color_(slot)
    return imgui.ImVec4(color.x, color.y, color.z, color.w)


def _draw_scrim() -> Rect:
    display = imgui.get_io().display_size
    imgui.set_next_window_pos(imgui.ImVec2(0.0, 0.0), imgui.Cond_.always)
    imgui.set_next_window_size(
        imgui.ImVec2(display.x, display.y), imgui.Cond_.always
    )
    imgui.push_style_color(
        imgui.Col_.window_bg,
        _style_color(imgui.Col_.modal_window_dim_bg),
    )
    imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
    try:
        imgui.begin(_SCRIM_WINDOW, None, _SCRIM_FLAGS)
        try:
            _raise(_SCRIM_WINDOW)
            return _current_rect()
        finally:
            imgui.end()
    finally:
        imgui.pop_style_var()
        imgui.pop_style_color()


def _draw_lines(lines: tuple[str, ...], color: tuple[int, int, int]) -> None:
    packed = rgba(color)
    for line in lines:
        imgui.text_colored(packed, line)


class InfoPanelSurface:
    """Centred, auto-sized, non-modal panel. Phase 8 reuses it."""

    modal = False

    def __init__(self, view: InfoPanelViewState) -> None:
        self.view = view

    def draw(self) -> Rect:
        display = imgui.get_io().display_size
        imgui.set_next_window_pos(
            imgui.ImVec2(display.x * 0.5, display.y * 0.5),
            imgui.Cond_.always,
            imgui.ImVec2(0.5, 0.5),
        )
        imgui.begin(_INFO_WINDOW, None, _INFO_FLAGS)
        try:
            _raise(_INFO_WINDOW)
            view = self.view
            if view.title_lines:
                _draw_lines(view.title_lines, LABEL)
            if view.title_lines and view.body_lines:
                imgui.spacing()
            if view.body_lines:
                _draw_lines(view.body_lines, VALUE)
            if view.footer_line is not None:
                if view.title_lines or view.body_lines:
                    imgui.spacing()
                imgui.text_colored(rgba(ACTION), view.footer_line)
            return _current_rect()
        finally:
            imgui.end()


class TopLayer:
    """Surfaces pushed for this frame, drawn above the shell chrome."""

    def __init__(self) -> None:
        self._pending: list[TopLayerSurface] = []
        self._rects: list[Rect] = []
        self._modal = False

    def push(self, surface: TopLayerSurface) -> None:
        self._pending.append(surface)

    @property
    def empty(self) -> bool:
        """True when nothing has been pushed since the last ``draw``."""
        return not self._pending

    @property
    def modal_active(self) -> bool:
        """True when the last ``draw`` included a modal surface."""
        return self._modal

    def captures_pointer(self, x: float, y: float) -> bool:
        """True when a modal was up, or the point is inside a recorded rect."""
        if self._modal:
            return True
        return any(_contains(rect, x, y) for rect in self._rects)

    def draw(self) -> None:
        """Submit the scrim and each surface, then clear the push list.

        An empty call records no rects and does not open a window, so it is
        safe when no ImGui frame is current.
        """
        pending = self._pending
        modal = any(surface.modal for surface in pending)
        rects: list[Rect] = []
        try:
            if modal:
                rects.append(_draw_scrim())
            for surface in pending:
                rects.append(surface.draw())
        finally:
            self._rects = rects
            self._modal = modal
            self._pending.clear()
