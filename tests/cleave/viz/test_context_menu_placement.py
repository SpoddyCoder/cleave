"""Context menu windows open at their final size and spot, with no jump.

Drives real ImGui frames (no GL) through the surfaces in ``menu_rows``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

from cleave.viz.context_menu import (
    CONTEXT_SEPARATOR,
    ContextMenuEntry,
    ContextMenuItem,
    ContextMenuState,
    ContextSubmenu,
)
from cleave.viz.menu_rows import ContextMenuSurface, ContextSubmenuSurface

_DISPLAY = (800, 600)

Rect = tuple[int, int, int, int]


def _items(prefix: str, count: int) -> tuple[ContextMenuItem, ...]:
    return tuple(
        ContextMenuItem(f"{prefix}{n}", f"{prefix} item {n}", lambda: None)
        for n in range(count)
    )


_SMALL: tuple[ContextMenuEntry, ...] = _items("s", 2)
_BIG: tuple[ContextMenuEntry, ...] = (*_items("b", 6), CONTEXT_SEPARATOR, *_items("c", 6))


@contextmanager
def _frames() -> Iterator[tuple[ContextMenuState, object]]:
    from cleave.viz import imgui_host
    from cleave.viz.imgui_host import ImGuiHost

    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = ImGuiHost.create()
    host.display_size = _DISPLAY
    state = ContextMenuState()
    menu = ContextMenuSurface(lambda: state)
    sub = ContextSubmenuSurface(menu)

    def run(count: int) -> list[tuple[Rect, Rect]]:
        rects = []
        for _ in range(count):
            host.begin_frame(1.0 / 60.0)
            rects.append((menu.draw(), sub.draw()))
            host.end_frame()
        return rects

    try:
        yield state, run
    finally:
        host.destroy()


def _on_screen(rect: Rect) -> bool:
    x, y, w, h = rect
    return x >= 0 and y >= 0 and x + w <= _DISPLAY[0] and y + h <= _DISPLAY[1]


def test_first_shown_frame_is_final_after_a_smaller_menu() -> None:
    with _frames() as (state, run):
        state.open(lambda: _SMALL, (100, 20))
        run(3)
        state.close()
        run(5)
        state.open(lambda: _BIG, (100, 580))
        shown = [menu for menu, _sub in run(4) if menu[0] >= 0]
        assert len(shown) == 3
        assert shown[0] == shown[-1]
        x, y, _w, h = shown[0]
        assert (x, y + h) == (100, 580)
        assert _on_screen(shown[0])

        state.close()
        run(2)
        state.open(lambda: _SMALL, (100, 20))
        shown = [menu for menu, _sub in run(3) if menu[0] >= 0]
        assert shown[0] == shown[-1]
        assert shown[0][:2] == (100, 20)


def test_submenu_opens_on_screen_without_moving() -> None:
    picks = ContextSubmenu("p", "Pick", _items("p", 10))
    with _frames() as (state, run):
        state.open(lambda: (*_SMALL, picks), (100, 560))
        run(2)
        state.hover(2)
        subs = [sub for _menu, sub in run(4) if sub[0] >= 0 and sub[2] > 0]
        assert len(subs) == 3
        assert subs[0] == subs[-1]
        assert _on_screen(subs[0])
