"""Right-click context menus: items, open state, and keyboard.

No ImGui and no GL. The shell host draws what this records
(``menu_rows.ContextMenuSurface``) and routes the pointer and keys here.

A menu comes from a provider, a callable that returns the items for one
target (a timeline row, say). The provider runs again each time the items
are read, so labels, checks, and enabled state follow the session while the
menu is open. Items act through public controller methods; a disabled item
carries a ``hint`` saying why.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame


@dataclass(frozen=True)
class ContextMenuItem:
    """One row. ``checked`` None is a plain command; True or False is a check."""

    id: str
    label: str
    run: Callable[[], None]
    enabled: bool = True
    checked: bool | None = None
    shortcut: str | None = None
    hint: str | None = None


class ContextMenuSeparator:
    """Visual break between items."""


CONTEXT_SEPARATOR = ContextMenuSeparator()
ContextMenuEntry = ContextMenuItem | ContextMenuSeparator
ContextMenuProvider = Callable[[], tuple[ContextMenuEntry, ...]]

_ACTIVATE_KEYS = frozenset({pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE})


class ContextMenuState:
    """The open menu, if any, its anchor, and the highlighted row."""

    def __init__(self) -> None:
        self._provider: ContextMenuProvider | None = None
        self._anchor: tuple[float, float] = (0.0, 0.0)
        self.highlight: int | None = None

    @property
    def is_open(self) -> bool:
        return self._provider is not None

    @property
    def anchor(self) -> tuple[float, float]:
        """Screen point the menu's top-left corner hangs from."""
        return self._anchor

    def open(
        self,
        provider: ContextMenuProvider,
        anchor: tuple[float, float],
        *,
        keyboard: bool = False,
    ) -> None:
        """Show *provider*'s items at *anchor*.

        From the keyboard, the first enabled item starts highlighted.
        """
        self._provider = provider
        self._anchor = (float(anchor[0]), float(anchor[1]))
        self.highlight = None
        if keyboard:
            self._step(1)
        if not self.items():
            self.close()

    def close(self) -> None:
        self._provider = None
        self.highlight = None

    def items(self) -> tuple[ContextMenuEntry, ...]:
        """This moment's entries; closes the menu when it has no items."""
        provider = self._provider
        if provider is None:
            return ()
        entries = provider()
        if not any(isinstance(entry, ContextMenuItem) for entry in entries):
            self.close()
            return ()
        return entries

    def hover(self, index: int | None) -> None:
        """Highlight the enabled item at *index*; None or a dead row clears it."""
        self.highlight = index if self._enabled_at(self.items(), index) else None

    def activate(self, index: int | None) -> bool:
        """Run the enabled item at *index* and close. False when it cannot run."""
        entries = self.items()
        if not self._enabled_at(entries, index):
            return False
        assert index is not None
        item = entries[index]
        assert isinstance(item, ContextMenuItem)
        self.close()
        item.run()
        return True

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Drive the open menu. Every key is taken while it is open."""
        if not self.is_open:
            return False
        key = event.key
        if key == pygame.K_ESCAPE:
            self.close()
        elif key in (pygame.K_UP, pygame.K_DOWN):
            self._step(-1 if key == pygame.K_UP else 1)
        elif key in (pygame.K_HOME, pygame.K_END):
            self.highlight = None
            self._step(1 if key == pygame.K_HOME else -1)
        elif key in _ACTIVATE_KEYS:
            self.activate(self.highlight)
        return True

    def _step(self, delta: int) -> None:
        entries = self.items()
        enabled = [
            index
            for index in range(len(entries))
            if self._enabled_at(entries, index)
        ]
        if not enabled:
            self.highlight = None
            return
        current = self.highlight
        if current not in enabled:
            self.highlight = enabled[0] if delta > 0 else enabled[-1]
            return
        position = enabled.index(current)
        self.highlight = enabled[(position + delta) % len(enabled)]

    @staticmethod
    def _enabled_at(entries: tuple[ContextMenuEntry, ...], index: int | None) -> bool:
        if index is None or not 0 <= index < len(entries):
            return False
        entry = entries[index]
        return isinstance(entry, ContextMenuItem) and entry.enabled
