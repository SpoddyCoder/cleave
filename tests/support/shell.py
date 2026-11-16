"""Headless ``ShellHost`` and pointer event builders for shell unit tests. No GL window."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pygame

from cleave.viz.commands import CommandContext
from cleave.viz.context_menu import ContextMenuState
from cleave.viz.inline_edit import InlineEditController
from cleave.viz.menu_bar import MenuBarState
from cleave.viz.modal import ModalHost
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.shell_layout import ShellLayout


Rect = tuple[int, int, int, int]


@contextmanager
def headless_shell_host() -> Iterator[object]:
    from cleave.viz import imgui_host
    from cleave.viz.imgui_host import ImGuiHost
    from cleave.viz.shell_host import ShellHost
    from cleave.viz.shell_menu_bar import menu_bar_height_px

    controls = SimpleNamespace(
        session=SimpleNamespace(
            layer_z_order=(),
            help_visible=False,
            timeline=SimpleNamespace(panel_open=False),
        ),
        shell_focus=SimpleNamespace(region=ShellRegion.NAVIGATOR),
        cfg=SimpleNamespace(project_slug="song"),
        config_dirty=False,
        build_view_state=lambda **_kwargs: None,
        set_shell_region=MagicMock(),
        modal_host=ModalHost(),
        disarm_value_nudge=MagicMock(),
        inline_edit=InlineEditController(),
        context_menu=ContextMenuState(),
        transport=MagicMock(),
    )
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = ShellHost(
            ImGuiHost.create(),
            MenuBarState(),
            controls,
            menu_bar_height_px(),
        )
    host.imgui.display_size = (1280, 720)
    height = host.menu_bar_height_px
    host.set_layout(ShellLayout.compute(1280, 720, height, height, 0))
    host.navigator.draw = lambda _frame: None
    host.navigator.visible_nodes = lambda: ()
    host.inspector.draw = lambda _state: None
    try:
        yield host
    finally:
        try:
            # Destroying a context after a single frame breaks the next one.
            draw_shell(host)
            draw_shell(host)
        finally:
            host.imgui.destroy()


def draw_shell(host: object) -> None:
    from cleave.viz.shell_host import draw_shell_frame

    draw_shell_frame(host, host.context.menu_state, CommandContext(), 1.0 / 60.0)


def mouse_motion(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)
    )


def mouse_down(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def rect_center(rect: Rect) -> tuple[int, int]:
    x, y, width, height = rect
    return (x + width // 2, y + height // 2)
