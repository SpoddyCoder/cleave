"""Scroll follow: least-move reveal helpers and the shell panels in headless ImGui."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pygame
from imgui_bundle import imgui

from cleave.viz import imgui_host, row_paint, shell_widgets
from cleave.viz.commands import CommandContext
from cleave.viz.imgui_host import ImGuiHost
from cleave.viz.menu_bar import MenuBarState
from cleave.viz.navigator import (
    LAYER_PAGE_PRESET_LIST,
    TOP_LEVEL_IDS,
    layer_node_id,
    layer_page_node_id,
)
from cleave.viz.row_paint import RowState
from cleave.viz.scroll_follow import clamp_scroll, reveal_span, scroll_to_reveal
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.shell_host import ShellHost, draw_shell_frame
from cleave.viz.shell_menu_bar import menu_bar_height_px
from cleave.viz.shell_layout import ShellLayout
from tests.support.viz import (
    keydown,
    make_controls,
)
from tests.support.preset_list import entries


_SLOTS = tuple(f"layer_{i}" for i in range(1, 9))


def test_clamp_scroll_fits_the_list_when_it_is_short() -> None:
    assert clamp_scroll(40, row_stride=10, view_height=50, row_count=3) == 0


def test_scroll_to_reveal_keeps_a_visible_row() -> None:
    assert (
        scroll_to_reveal(0, 1, row_stride=10, view_height=50, row_count=20) == 0
    )


def test_scroll_to_reveal_brings_a_row_below_into_view() -> None:
    assert (
        scroll_to_reveal(0, 9, row_stride=10, view_height=50, row_count=20) == 50
    )


def test_scroll_to_reveal_brings_a_row_above_into_view() -> None:
    assert (
        scroll_to_reveal(50, 1, row_stride=10, view_height=50, row_count=20) == 10
    )


def test_reveal_span_keeps_a_visible_span() -> None:
    assert reveal_span(20, 30, 40, view_height=50) == 20


def test_reveal_span_scrolls_down_to_a_span_below() -> None:
    assert reveal_span(0, 60, 75, view_height=50) == 25


def test_reveal_span_scrolls_up_to_a_span_above() -> None:
    assert reveal_span(40, 10, 20, view_height=50) == 10


def test_reveal_span_keeps_the_top_of_a_tall_span() -> None:
    assert reveal_span(0, 30, 200, view_height=50) == 30


def test_reveal_span_never_goes_negative() -> None:
    assert reveal_span(10, -5, 5, view_height=50) == 0


@contextmanager
def _shell(controls) -> Iterator[ShellHost]:
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = ShellHost(
            ImGuiHost.create(), MenuBarState(), controls, menu_bar_height_px()
        )
    host.imgui.display_size = (1280, 480)
    host.imgui._mouse_xy = lambda: (-1.0, -1.0)
    try:
        yield host
    finally:
        host.imgui.destroy()


def _focused_rows(host: ShellHost, frames: int = 2) -> list[tuple[float, float, float, float]]:
    """Draw *frames* shell frames.

    Each focused row band or focused button ring drawn is (top, bottom,
    window top, window bottom).
    """
    rings: list[tuple[float, float, float, float]] = []
    real_paint = row_paint.paint_row
    real_ring = shell_widgets.draw_item_focus_ring

    def record(top: float, bottom: float) -> None:
        window_y = float(imgui.get_window_pos().y)
        rings.append((top, bottom, window_y, window_y + float(imgui.get_window_height())))

    def paint(draw, rect, state, *, bar=True) -> None:
        real_paint(draw, rect, state, bar=bar)
        if state is RowState.FOCUSED:
            record(float(rect[1]), float(rect[1] + rect[3]))

    def ring() -> None:
        real_ring()
        record(float(imgui.get_item_rect_min().y), float(imgui.get_item_rect_max().y))

    with (
        patch.object(row_paint, "paint_row", paint),
        patch.object(shell_widgets, "draw_item_focus_ring", ring),
    ):
        for _ in range(frames):
            rings.clear()
            height = host.menu_bar_height_px
            host.set_layout(
                ShellLayout.compute(
                    1280,
                    480,
                    height,
                    height,
                    0,
                    nav_content_h=host.nav_content_height_px or None,
                )
            )
            draw_shell_frame(host, host.context.menu_state, CommandContext(), 1.0 / 60.0)
    return list(rings)


def _assert_in_view(rings: list[tuple[float, float, float, float]]) -> None:
    assert len(rings) == 1
    top, bottom, window_top, window_bottom = rings[0]
    assert window_top <= top and bottom <= window_bottom


def _window_scroll(host: ShellHost, panel_name: str) -> list[float]:
    """Record the scroll of the window *panel_name* draws its rows into.

    The navigator's rows scroll its own window; the inspector's scroll a child
    under the title, so the scroll is read from inside a row draw.
    """
    seen: list[float] = []
    panel = getattr(host, panel_name)
    method = "draw_row" if panel_name == "inspector" else "draw"
    real = getattr(panel, method)

    def spy(*args) -> None:
        real(*args)
        seen.append(float(imgui.get_scroll_y()))

    setattr(panel, method, spy)
    return seen


def _long_preset_page():
    controls = make_controls(_SLOTS)
    block = controls.session.layers["layer_1"]
    block.preset_switching_trigger = "timer"
    block.preset_list = entries(
        *(f"/tmp/presets/layer_1/preset-{i}.milk" for i in range(60))
    )
    controls.navigator.select(
        layer_page_node_id("layer_1", LAYER_PAGE_PRESET_LIST)
    )
    controls.navigator.activate()
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    return controls


def test_navigator_scrolls_to_keep_the_selected_row_in_view() -> None:
    controls = make_controls(_SLOTS)
    controls.shell_focus.nav_expanded |= set(TOP_LEVEL_IDS) | {
        layer_node_id(slot) for slot in _SLOTS
    }
    controls.set_shell_region(ShellRegion.NAVIGATOR)
    with _shell(controls) as host:
        scroll = _window_scroll(host, "navigator")
        _focused_rows(host)
        for _ in range(60):
            controls.navigator.handle_keydown(keydown(pygame.K_DOWN))
            _assert_in_view(_focused_rows(host))
        assert scroll[-1] > 0.0


def test_inspector_scrolls_to_keep_the_focused_row_in_view() -> None:
    controls = _long_preset_page()
    with _shell(controls) as host:
        scroll = _window_scroll(host, "inspector")
        _focused_rows(host)
        for _ in range(70):
            controls.inspector.handle_keydown(keydown(pygame.K_DOWN))
            _assert_in_view(_focused_rows(host))
        assert scroll[-1] > 0.0


def test_inspector_title_stays_put_while_its_rows_scroll() -> None:
    controls = _long_preset_page()
    with _shell(controls) as host:
        rows = _window_scroll(host, "inspector")
        title: list[float] = []
        real = host.inspector.draw

        def spy(*args) -> None:
            real(*args)
            title.append(float(imgui.get_scroll_y()))

        host.inspector.draw = spy
        _focused_rows(host)
        controls.inspector.handle_keydown(keydown(pygame.K_UP))
        _focused_rows(host)
        assert rows[-1] > 0.0
        assert set(title) == {0.0}


def test_inspector_wraps_back_to_the_top_row() -> None:
    controls = _long_preset_page()
    with _shell(controls) as host:
        scroll = _window_scroll(host, "inspector")
        _focused_rows(host)
        controls.inspector.handle_keydown(keydown(pygame.K_UP))
        _focused_rows(host)
        assert scroll[-1] > 0.0
        controls.inspector.handle_keydown(keydown(pygame.K_DOWN))
        _assert_in_view(_focused_rows(host))
        assert scroll[-1] == 0.0


def test_wheel_scroll_is_not_pulled_back_while_focus_stays() -> None:
    controls = _long_preset_page()
    with _shell(controls) as host:
        _focused_rows(host)
        scroll: list[float] = []
        real = host.inspector.draw_row

        def wheel_then_draw(*args) -> None:
            if not scroll:
                imgui.set_scroll_y(300.0)
            real(*args)
            scroll.append(float(imgui.get_scroll_y()))

        host.inspector.draw_row = wheel_then_draw
        _focused_rows(host, frames=3)
        assert scroll[-1] == 300.0
