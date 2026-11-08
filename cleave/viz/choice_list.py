"""The open list of a combo: which option is highlighted, and its keys.

The inspector and form dialogs each hold at most one. Drawing lives in
``choice_widgets``; this module has no ImGui.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass

import pygame

from cleave.choice import step_index

# Rows shown before the list scrolls.
CHOICE_LIST_MAX_VISIBLE = 12
_PAGE_STEP = CHOICE_LIST_MAX_VISIBLE - 1


@dataclass
class ChoiceListState:
    """An open combo list.

    ``start`` is the option chosen when the list opened. ``on_pick`` gets the
    picked index and runs only when it differs from ``start``.
    """

    target: Hashable
    options: tuple[str, ...]
    start: int
    on_pick: Callable[[int], None]
    highlighted: int = -1

    def __post_init__(self) -> None:
        if self.highlighted < 0:
            self.highlighted = self.start

    def move(self, delta: int) -> None:
        self.highlighted = step_index(self.highlighted, len(self.options), delta)

    def hover(self, index: int) -> None:
        if 0 <= index < len(self.options):
            self.highlighted = index

    def pick(self, index: int | None = None) -> None:
        chosen = self.highlighted if index is None else index
        if chosen != self.start and 0 <= chosen < len(self.options):
            self.on_pick(chosen)


@dataclass(frozen=True)
class ChoiceListView:
    target: Hashable
    options: tuple[str, ...]
    highlighted: int
    chosen: int


def choice_list_view(state: ChoiceListState | None) -> ChoiceListView | None:
    if state is None:
        return None
    return ChoiceListView(state.target, state.options, state.highlighted, state.start)


class ChoiceListKey:
    """What a key did to an open list."""

    NONE = "none"
    MOVED = "moved"
    PICKED = "picked"
    CLOSED = "closed"


def handle_choice_list_key(state: ChoiceListState, key: int) -> str:
    """Up/Down, Page Up/Down and Home/End move. Enter or Space picks. Esc and Tab close.

    The caller closes the list after ``PICKED`` or ``CLOSED``.
    """
    if key in (pygame.K_UP, pygame.K_DOWN):
        state.move(-1 if key == pygame.K_UP else 1)
        return ChoiceListKey.MOVED
    if key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
        state.move(-_PAGE_STEP if key == pygame.K_PAGEUP else _PAGE_STEP)
        return ChoiceListKey.MOVED
    if key == pygame.K_HOME:
        state.highlighted = 0
        return ChoiceListKey.MOVED
    if key == pygame.K_END:
        state.highlighted = max(0, len(state.options) - 1)
        return ChoiceListKey.MOVED
    if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
        state.pick()
        return ChoiceListKey.PICKED
    if key in (pygame.K_ESCAPE, pygame.K_TAB):
        return ChoiceListKey.CLOSED
    return ChoiceListKey.NONE
