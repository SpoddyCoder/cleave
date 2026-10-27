"""Top layer order, pointer capture, and the ImGui theme table. No GL window."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pygame
import pytest
from imgui_bundle import imgui

from cleave.viz.commands import CommandContext
from cleave.viz.imgui_theme import IMGUI_COLOR_ROLES, apply_imgui_theme, rgba
from cleave.viz.menu_bar import MenuBarState
from cleave.viz.info_panel import InfoPanelViewState
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.shell_layout import ShellLayout
from cleave.viz.top_layer import InfoPanelSurface

_MODAL_RECT = (480, 260, 200, 120)
_PANEL_RECT = (400, 200, 120, 80)


class _Overlay:
    def __init__(self) -> None:
        self.visibility = 1.0

    def notify_input(self) -> None:
        return None


class _FixedSurface:
    def __init__(self, name: str, rect: tuple[int, int, int, int], *, modal: bool) -> None:
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
        session=SimpleNamespace(
            layer_z_order=(),
            help_visible=False,
            timeline=SimpleNamespace(panel_open=False),
        ),
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


def _draw(host: object) -> None:
    from cleave.viz.shell_host import draw_shell_frame

    draw_shell_frame(host, host._menu_state, CommandContext(), 1.0, 1.0 / 60.0)


def _button(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


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


def test_info_panel_draws_after_chrome_and_scrim_only_when_modal() -> None:
    view = InfoPanelViewState(
        title_lines=("Listening",),
        body_lines=("120 BPM",),
        footer_line="tap",
    )
    with _host() as host:
        # Auto-resize hides the panel on the measuring frame. The next frame paints it.
        for _frame in range(2):
            host.top_layer.push(InfoPanelSurface(view))
            _draw(host)
        names = _content_names()
        _assert_shell_before(names, "##info-panel")
        assert "##top-scrim" not in names

        host.top_layer.push(_FixedSurface("##top-modal", _MODAL_RECT, modal=True))
        _draw(host)
        names = _content_names()
        _assert_shell_before(names, "##top-scrim")
        assert names.index("##top-scrim") < names.index("##top-modal"), names
        del names
    assert not imgui.get_current_context()


def test_modal_click_skips_region_and_splitter_and_reaches_imgui() -> None:
    with _host() as host:
        modal = _FixedSurface("##top-modal", _MODAL_RECT, modal=True)
        host.top_layer.push(modal)
        _draw(host)
        assert host.top_layer.modal_active
        layout = host.layout
        assert layout is not None
        nav_x, nav_y, nav_w, nav_h = layout.navigator
        navigator = (nav_x + nav_w - 1, nav_y + nav_h // 2)
        inside = (_MODAL_RECT[0] + 10, _MODAL_RECT[1] + 10)
        with patch("cleave.viz.shell_host.pygame.mouse.set_cursor") as set_cursor:
            host.process_event(_button(inside))
            assert host.imgui.queued_buttons == [(0, True)]
            assert host._splitter is None
            host.top_layer.push(modal)
            _draw(host)
            host.process_event(_button(navigator))
            assert host.imgui.queued_buttons == [(0, True)]
            assert host._splitter is None
            set_cursor.assert_not_called()
        host._controls.set_shell_region.assert_not_called()


def test_chrome_contains_recorded_top_layer_rect() -> None:
    with _host() as host:
        host.top_layer.push(_FixedSurface("##top-panel", _PANEL_RECT, modal=False))
        _draw(host)
        assert host._chrome_contains(450, 230)
        assert not host._chrome_contains(300, 400)


def test_apply_imgui_theme_uses_the_role_table() -> None:
    with _host():
        apply_imgui_theme()
        style = imgui.get_style()
        for slot in (imgui.Col_.text, imgui.Col_.header, imgui.Col_.modal_window_dim_bg):
            role, alpha = IMGUI_COLOR_ROLES[slot]
            got = style.color_(slot)
            expect = rgba(role, alpha)
            assert got.x == pytest.approx(expect.x)
            assert got.y == pytest.approx(expect.y)
            assert got.z == pytest.approx(expect.z)
            assert got.w == pytest.approx(expect.w)
