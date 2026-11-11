"""Context menu state: items, highlight, keys, and activation."""

from __future__ import annotations

import pygame

from cleave.viz.context_menu import (
    CONTEXT_SEPARATOR,
    ContextMenuEntry,
    ContextMenuItem,
    ContextMenuState,
)
from cleave.viz.menu_rows import clamp_menu_origin, context_menu_row_views
from tests.support.viz import keydown


def _menu(ran: list[str], *, middle_enabled: bool = False) -> tuple[ContextMenuEntry, ...]:
    return (
        ContextMenuItem("a", "Alpha", lambda: ran.append("a")),
        CONTEXT_SEPARATOR,
        ContextMenuItem("b", "Beta", lambda: ran.append("b"), enabled=middle_enabled),
        ContextMenuItem("c", "Gamma", lambda: ran.append("c"), checked=True),
    )


def test_open_from_the_pointer_has_no_highlight() -> None:
    state = ContextMenuState()
    state.open(lambda: _menu([]), (12, 34))
    assert state.is_open
    assert state.anchor == (12.0, 34.0)
    assert state.highlight is None


def test_arrows_skip_separators_and_disabled_items_and_wrap() -> None:
    ran: list[str] = []
    state = ContextMenuState()
    state.open(lambda: _menu(ran), (0, 0), keyboard=True)
    assert state.highlight == 0
    state.handle_keydown(keydown(pygame.K_DOWN))
    assert state.highlight == 3
    state.handle_keydown(keydown(pygame.K_DOWN))
    assert state.highlight == 0
    state.handle_keydown(keydown(pygame.K_UP))
    assert state.highlight == 3
    state.handle_keydown(keydown(pygame.K_HOME))
    assert state.highlight == 0
    state.handle_keydown(keydown(pygame.K_END))
    assert state.highlight == 3


def test_enter_runs_the_highlighted_item_and_closes() -> None:
    ran: list[str] = []
    state = ContextMenuState()
    state.open(lambda: _menu(ran), (0, 0), keyboard=True)
    assert state.handle_keydown(keydown(pygame.K_RETURN)) is True
    assert ran == ["a"]
    assert not state.is_open


def test_disabled_items_neither_highlight_nor_run() -> None:
    ran: list[str] = []
    state = ContextMenuState()
    state.open(lambda: _menu(ran), (0, 0))
    state.hover(2)
    assert state.highlight is None
    assert state.activate(2) is False
    assert state.activate(1) is False
    assert ran == []
    assert state.is_open
    state.hover(3)
    assert state.highlight == 3
    assert state.activate(3) is True
    assert ran == ["c"]


def test_escape_closes_and_other_keys_are_swallowed() -> None:
    state = ContextMenuState()
    assert state.handle_keydown(keydown(pygame.K_a)) is False
    state.open(lambda: _menu([]), (0, 0))
    assert state.handle_keydown(keydown(pygame.K_a)) is True
    assert state.is_open
    assert state.handle_keydown(keydown(pygame.K_ESCAPE)) is True
    assert not state.is_open


def test_items_follow_the_provider_while_open() -> None:
    flags = {"enabled": False}
    state = ContextMenuState()
    state.open(lambda: _menu([], middle_enabled=flags["enabled"]), (0, 0))
    entry = state.items()[2]
    assert isinstance(entry, ContextMenuItem) and not entry.enabled
    flags["enabled"] = True
    entry = state.items()[2]
    assert isinstance(entry, ContextMenuItem) and entry.enabled


def test_a_provider_with_no_items_closes_the_menu() -> None:
    entries: list[tuple[ContextMenuEntry, ...]] = [()]
    state = ContextMenuState()
    state.open(lambda: entries[0], (0, 0))
    assert not state.is_open
    entries[0] = _menu([])
    state.open(lambda: entries[0], (0, 0))
    assert state.is_open
    entries[0] = (CONTEXT_SEPARATOR,)
    assert state.items() == ()
    assert not state.is_open


def test_row_views_map_items_and_separators() -> None:
    views = context_menu_row_views(_menu([]))
    assert views[1] is None
    assert [view.label for view in views if view is not None] == [
        "Alpha",
        "Beta",
        "Gamma",
    ]
    assert views[2] is not None and views[2].enabled is False
    assert views[3] is not None and views[3].checked is True


def test_clamp_menu_origin_flips_at_the_edges() -> None:
    display = (800.0, 600.0)
    assert clamp_menu_origin((100, 100), (200, 150), display) == (100, 100)
    assert clamp_menu_origin((700, 500), (200, 150), display) == (500, 350)
    assert clamp_menu_origin((100, 500), (200, 700), display) == (100, 0.0)
    assert clamp_menu_origin((150, 100), (900, 150), display) == (0.0, 100)
