"""Right-click context menus: items, open state, and keyboard.

No ImGui and no GL. The shell host draws what this records
(``menu_rows.ContextMenuSurface``) and routes the pointer and keys here.

A menu comes from a provider, a callable that returns the items for one
target (a timeline row, say). The provider runs again each time the items
are read, so labels, checks, and enabled state follow the session while the
menu is open. Items act through public controller methods; a disabled item
carries a ``hint`` saying why.

A ``ContextSubmenu`` row opens one level of child items beside it, on hover,
click, Right, or Enter. Left or Escape closes the child and keeps the menu.
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
ContextMenuLeaf = ContextMenuItem | ContextMenuSeparator


@dataclass(frozen=True)
class ContextSubmenu:
    """A row that opens *items* beside it. ``shortcut`` names the key that cycles them."""

    id: str
    label: str
    items: tuple[ContextMenuLeaf, ...]
    enabled: bool = True
    shortcut: str | None = None
    hint: str | None = None


ContextMenuEntry = ContextMenuItem | ContextSubmenu | ContextMenuSeparator
ContextMenuProvider = Callable[[], tuple[ContextMenuEntry, ...]]

_ACTIVATE_KEYS = frozenset({pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE})


def _is_row(entry: object) -> bool:
    return isinstance(entry, (ContextMenuItem, ContextSubmenu))


def _enabled_at(entries: tuple[object, ...], index: int | None) -> bool:
    if index is None or not 0 <= index < len(entries):
        return False
    entry = entries[index]
    return _is_row(entry) and bool(entry.enabled)  # type: ignore[attr-defined]


def _step_index(
    entries: tuple[object, ...], current: int | None, delta: int
) -> int | None:
    """Next enabled row from *current*, wrapping; the first or last from None."""
    enabled = [index for index in range(len(entries)) if _enabled_at(entries, index)]
    if not enabled:
        return None
    if current not in enabled:
        return enabled[0] if delta > 0 else enabled[-1]
    position = enabled.index(current)
    return enabled[(position + delta) % len(enabled)]


class ContextMenuState:
    """The open menu, if any, its anchor, the highlighted row, and an open submenu.

    ``submenu`` is the index of the row whose child items show. Keys drive
    the child while ``sub_highlight`` is set (it was opened from the keyboard
    or the pointer moved into it), and the menu otherwise.
    """

    def __init__(self) -> None:
        self._provider: ContextMenuProvider | None = None
        self._anchor: tuple[float, float] = (0.0, 0.0)
        self.highlight: int | None = None
        self.submenu: int | None = None
        self.sub_highlight: int | None = None

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
        self._close_submenu()
        if keyboard:
            self.highlight = _step_index(self.items(), None, 1)
        if not self.items():
            self.close()

    def close(self) -> None:
        self._provider = None
        self.highlight = None
        self._close_submenu()

    def items(self) -> tuple[ContextMenuEntry, ...]:
        """This moment's entries; closes the menu when it has no items."""
        provider = self._provider
        if provider is None:
            return ()
        entries = provider()
        if not any(_is_row(entry) for entry in entries):
            self.close()
            return ()
        return entries

    def submenu_items(self) -> tuple[ContextMenuLeaf, ...]:
        """The open submenu's entries, or () when none is open or it went away."""
        index = self.submenu
        if index is None:
            return ()
        entries = self.items()
        if not _enabled_at(entries, index) or not isinstance(
            entries[index], ContextSubmenu
        ):
            self._close_submenu()
            return ()
        return entries[index].items  # type: ignore[union-attr]

    def hover(self, index: int | None) -> None:
        """Highlight the enabled row at *index*; a submenu row opens its items.

        None or a dead row clears the highlight and leaves an open submenu
        alone, so the pointer can cross a gap into it.
        """
        entries = self.items()
        if not _enabled_at(entries, index):
            self.highlight = None
            return
        self.highlight = index
        if isinstance(entries[index], ContextSubmenu):  # type: ignore[index]
            if self.submenu != index:
                self.submenu = index
                self.sub_highlight = None
        else:
            self._close_submenu()

    def hover_submenu(self, index: int | None) -> None:
        """Highlight the enabled child row at *index*; None clears it."""
        sub = self.submenu_items()
        self.sub_highlight = index if _enabled_at(sub, index) else None
        if self.sub_highlight is not None:
            self.highlight = self.submenu

    def activate(self, index: int | None) -> bool:
        """Run the enabled item at *index* and close, or open a submenu row.

        False when nothing can run.
        """
        entries = self.items()
        if not _enabled_at(entries, index):
            return False
        assert index is not None
        entry = entries[index]
        if isinstance(entry, ContextSubmenu):
            self.highlight = index
            self._open_submenu(index)
            return True
        assert isinstance(entry, ContextMenuItem)
        self.close()
        entry.run()
        return True

    def activate_submenu(self, index: int | None) -> bool:
        """Run the enabled child item at *index* and close. False when it cannot run."""
        sub = self.submenu_items()
        if not _enabled_at(sub, index):
            return False
        assert index is not None
        item = sub[index]
        assert isinstance(item, ContextMenuItem)
        self.close()
        item.run()
        return True

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Drive the open menu. Every key is taken while it is open."""
        if not self.is_open:
            return False
        key = event.key
        if self.submenu is not None and self.sub_highlight is not None:
            self._submenu_key(key)
            return True
        if key == pygame.K_ESCAPE:
            self.close()
        elif key in (pygame.K_UP, pygame.K_DOWN):
            self._close_submenu()
            self.highlight = _step_index(
                self.items(), self.highlight, -1 if key == pygame.K_UP else 1
            )
        elif key in (pygame.K_HOME, pygame.K_END):
            self._close_submenu()
            self.highlight = _step_index(
                self.items(), None, 1 if key == pygame.K_HOME else -1
            )
        elif key == pygame.K_RIGHT:
            entries = self.items()
            index = self.highlight
            if _enabled_at(entries, index) and isinstance(
                entries[index], ContextSubmenu  # type: ignore[index]
            ):
                self._open_submenu(index)  # type: ignore[arg-type]
        elif key == pygame.K_LEFT:
            self._close_submenu()
        elif key in _ACTIVATE_KEYS:
            self.activate(self.highlight)
        return True

    def _submenu_key(self, key: int) -> None:
        sub = self.submenu_items()
        if key in (pygame.K_ESCAPE, pygame.K_LEFT):
            self._close_submenu()
        elif key in (pygame.K_UP, pygame.K_DOWN):
            self.sub_highlight = _step_index(
                sub, self.sub_highlight, -1 if key == pygame.K_UP else 1
            )
        elif key in (pygame.K_HOME, pygame.K_END):
            self.sub_highlight = _step_index(
                sub, None, 1 if key == pygame.K_HOME else -1
            )
        elif key in _ACTIVATE_KEYS or key == pygame.K_RIGHT:
            self.activate_submenu(self.sub_highlight)

    def _open_submenu(self, index: int) -> None:
        """Show *index*'s child items with the checked one (or the first) highlighted."""
        self.submenu = index
        sub = self.submenu_items()
        checked = next(
            (
                position
                for position, entry in enumerate(sub)
                if isinstance(entry, ContextMenuItem)
                and entry.checked
                and entry.enabled
            ),
            None,
        )
        self.sub_highlight = checked if checked is not None else _step_index(sub, None, 1)

    def _close_submenu(self) -> None:
        self.submenu = None
        self.sub_highlight = None
