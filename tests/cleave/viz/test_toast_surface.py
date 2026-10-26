"""Headless toast: rect, timed-line click, and modal z-order. No GL window."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pygame
from imgui_bundle import imgui

from cleave.viz.commands import CommandContext
from cleave.viz.menu_bar import MenuBarState
from cleave.viz.modal_surface import ImGuiTextMeasure
from cleave.viz.panel_notification import PanelNotificationActive
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.shell_layout import ShellLayout
from cleave.viz.toast_surface import (
    ToastPointerIntent,
    ToastPointerKind,
    ToastSurface,
    apply_toast_pointer,
)

_MODAL_RECT = (480, 260, 200, 120)


class _Overlay:
    def __init__(self) -> None:
        self.visibility = 1.0

    def notify_input(self) -> None:
        return None


class _Dismiss:
    def __init__(self) -> None:
        self.calls = 0

    def dismiss_notification(self) -> None:
        self.calls += 1


class _FixedSurface:
    def __init__(
        self, name: str, rect: tuple[int, int, int, int], *, modal: bool
    ) -> None:
        self.modal = modal
        self._name = name
        self._rect = rect

    def draw(self) -> tuple[int, int, int, int]:
        x, y, w, h = self._rect
        imgui.set_next_window_pos(imgui.ImVec2(float(x), float(y)), imgui.Cond_.always)
        imgui.set_next_window_size(imgui.ImVec2(float(w), float(h)), imgui.Cond_.always)
        flags = (
            int(imgui.WindowFlags_.no_title_bar)
            | int(imgui.WindowFlags_.no_resize)
            | int(imgui.WindowFlags_.no_move)
            | int(imgui.WindowFlags_.no_saved_settings)
            | int(imgui.WindowFlags_.no_focus_on_appearing)
            | int(imgui.WindowFlags_.no_nav)
            | int(imgui.WindowFlags_.no_bring_to_front_on_focus)
        )
        imgui.begin(self._name, None, flags)
        try:
            imgui.internal.bring_window_to_display_front(
                imgui.internal.find_window_by_name(self._name)
            )
            pos = imgui.get_window_pos()
            size = imgui.get_window_size()
            return (int(pos.x), int(pos.y), int(size.x), int(size.y))
        finally:
            imgui.end()


def _content_names() -> list[str]:
    lists = list(imgui.get_draw_data().cmd_lists)
    names = [
        str(draw_list._owner_name)
        for draw_list in lists
        if "Foreground" not in str(draw_list._owner_name)
    ]
    del lists
    return names


@contextmanager
def _host() -> Iterator[object]:
    from cleave.viz import imgui_host
    from cleave.viz.imgui_host import ImGuiHost
    from cleave.viz.shell_host import ShellHost, menu_bar_height_px

    controls = SimpleNamespace(
        session=SimpleNamespace(layer_z_order=()),
        shell_focus=SimpleNamespace(region=ShellRegion.NAVIGATOR),
        build_view_state=lambda **_kwargs: None,
        set_shell_region=MagicMock(),
    )
    overlay = _Overlay()
    menu = MenuBarState()
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = ShellHost(
            ImGuiHost.create(),
            overlay,
            menu,
            controls,
            menu_bar_height_px(),
        )
    host.imgui.display_size = (1280, 720)
    height = host.menu_bar_height_px
    host.set_layout(ShellLayout.compute(1280, 720, height, height, 0))
    host._draw_navigator = lambda: None
    host._draw_inspector = lambda _state: None
    try:
        yield host
    finally:
        host.imgui.destroy()


def _draw(host: object, *, visibility: float = 1.0) -> None:
    from cleave.viz.shell_host import draw_shell_frame

    draw_shell_frame(
        host, host._menu_state, CommandContext(), visibility, 1.0 / 60.0
    )


def _motion(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)
    )


def _button(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def _release(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)


def _center(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    x, y, width, height = rect
    return (x + width // 2, y + height // 2)


def _active() -> PanelNotificationActive:
    return PanelNotificationActive(
        persistent_message="Missing stem",
        persistent_elapsed_sec=10.0,
        message="Saved",
        remaining_sec=2.0,
        elapsed_sec=0.05,
    )


def _surface(host: object) -> ToastSurface:
    assert host.layout is not None
    return ToastSurface(_active(), host.layout, ImGuiTextMeasure())


def _pointer(
    host: object, surface: ToastSurface, pos: tuple[int, int], *, click: bool
) -> None:
    host.process_event(_motion(pos))
    if click:
        host.process_event(_button(pos))
    host.top_layer.push(surface)
    _draw(host)


def _assert_shell_before(names: list[str], later: str) -> None:
    later_at = names.index(later)
    for name in (
        "##MainMenuBar",
        "##shell-transport",
        "##shell-navigator",
        "##shell-inspector",
        "##shell-chrome",
    ):
        assert names.index(name) < later_at, names


def test_toast_records_rect_and_click_dismisses_only_the_timed_line() -> None:
    with _host() as host:
        surface = _surface(host)
        host.top_layer.push(surface)
        _draw(host)
        names = _content_names()
        _assert_shell_before(names, "##toast")
        assert "##top-scrim" not in names
        assert surface.rect is not None
        assert surface.persistent_line_rect is not None
        assert surface.timed_line_rect is not None
        assert surface.modal is False
        rect = surface.rect
        assert host.top_layer.captures_pointer(
            rect[0] + rect[2] // 2, rect[1] + rect[3] // 2
        )
        layout = host.layout
        assert layout is not None
        nav_x, nav_y, _nav_w, nav_h = layout.navigator
        navigator = (nav_x + 4, nav_y + nav_h // 2)
        assert not host.top_layer.captures_pointer(navigator[0], navigator[1])

        target = _Dismiss()
        persistent = _center(surface.persistent_line_rect)
        _pointer(host, surface, persistent, click=True)
        assert surface.intent is None
        apply_toast_pointer(target, surface.intent)
        assert target.calls == 0
        host.process_event(_release(persistent))
        host.top_layer.push(surface)
        _draw(host)

        timed = _center(surface.timed_line_rect)
        _pointer(host, surface, timed, click=True)
        assert surface.intent == ToastPointerIntent(ToastPointerKind.DISMISS_TIMED)
        apply_toast_pointer(target, surface.intent)
        assert target.calls == 1

        host.top_layer.push(surface)
        host.top_layer.push(_FixedSurface("##top-modal", _MODAL_RECT, modal=True))
        _draw(host)
        names = _content_names()
        _assert_shell_before(names, "##toast")
        assert names.index("##top-scrim") < names.index("##toast"), names
        assert names.index("##toast") < names.index("##top-modal"), names
        assert host.top_layer.modal_active
        assert host.top_layer.captures_pointer(navigator[0], navigator[1])
        assert host.top_layer.captures_pointer(
            _MODAL_RECT[0] + 8, _MODAL_RECT[1] + 8
        )
        del names
    assert not imgui.get_current_context()


def test_toast_draws_while_the_shell_is_hidden() -> None:
    with _host() as host:
        surface = _surface(host)
        host.top_layer.push(surface)
        _draw(host, visibility=0.0)
        names = _content_names()
        assert "##toast" in names
        assert surface.rect is not None
        rect = surface.rect
        assert host.top_layer.captures_pointer(
            rect[0] + rect[2] // 2, rect[1] + rect[3] // 2
        )
        del names
    assert not imgui.get_current_context()
