"""Transport-bar toasts: a click dismisses a timed warning. No GL window."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pygame
from imgui_bundle import imgui

from cleave.viz.commands import CommandContext
from cleave.viz.menu_bar import MenuBarState
from cleave.viz.panel_notification import PanelNotificationActive
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.shell_layout import ShellLayout


class _Overlay:
    def __init__(self) -> None:
        self.visibility = 1.0

    def notify_input(self) -> None:
        return None


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
        session=SimpleNamespace(
            layer_z_order=(),
            help_visible=False,
            timeline=SimpleNamespace(panel_open=False),
        ),
        shell_focus=SimpleNamespace(region=ShellRegion.NAVIGATOR),
        build_view_state=lambda **_kwargs: None,
        set_shell_region=MagicMock(),
    )
    menu = MenuBarState()
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = ShellHost(
            ImGuiHost.create(),
            _Overlay(),
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


def _notice(
    *,
    message: str | None,
    persistent: str | None = None,
) -> PanelNotificationActive:
    return PanelNotificationActive(
        persistent_message=persistent,
        persistent_elapsed_sec=10.0,
        message=message,
        remaining_sec=2.0 if message is not None else 0.0,
        elapsed_sec=0.05,
    )


def _draw(host: object, notice: PanelNotificationActive) -> None:
    from cleave.viz.shell_host import draw_shell_frame

    draw_shell_frame(
        host,
        host._menu_state,
        CommandContext(),
        1.0,
        1.0 / 60.0,
        notice=notice,
    )


def _click(host: object, pos: tuple[int, int], notice: PanelNotificationActive) -> None:
    host.process_event(
        pygame.event.Event(
            pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)
        )
    )
    host.process_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)
    )
    _draw(host, notice)


def _center(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    x, y, width, height = rect
    return (x + width // 2, y + height // 2)


def test_click_on_the_transport_bar_dismisses_a_timed_warning() -> None:
    with _host() as host:
        notice = _notice(message="Saved", persistent="Missing stem")
        _draw(host, notice)
        names = _content_names()
        assert "##shell-transport" in names
        assert "##toast" not in names
        layout = host.layout
        assert layout is not None
        _click(host, _center(layout.transport), notice)
        assert host.transport_notice_clicked is True
        host.process_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONUP,
                pos=_center(layout.transport),
                button=1,
            )
        )

        tx, ty, _tw, th = layout.transport
        _click(host, (tx + 4, ty + th // 2), notice)
        assert host.transport_notice_clicked is False

        nav_x, nav_y, _nav_w, nav_h = layout.navigator
        _click(host, (nav_x + 4, nav_y + nav_h // 2), notice)
        assert host.transport_notice_clicked is False
        del names
    assert not imgui.get_current_context()


def test_click_on_a_persistent_error_does_not_dismiss() -> None:
    with _host() as host:
        notice = _notice(message=None, persistent="Missing stem")
        _draw(host, notice)
        layout = host.layout
        assert layout is not None
        _click(host, _center(layout.transport), notice)
        assert host.transport_notice_clicked is False
    assert not imgui.get_current_context()
