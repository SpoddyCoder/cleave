"""Menu bar focus and highlight. Keyboard and mouse both go through this state.

No ImGui and no GL. The shell host only draws what this records.
"""

from __future__ import annotations

from typing import Any

import pygame

from cleave.stems import stem_overlay_header
from cleave.viz.commands import (
    MENUS,
    Command,
    CommandContext,
    Menu,
    MenuSeparator,
    build_menus,
)

_NAV_KEYS = frozenset(
    {
        pygame.K_LEFT,
        pygame.K_RIGHT,
        pygame.K_UP,
        pygame.K_DOWN,
        pygame.K_RETURN,
        pygame.K_KP_ENTER,
        pygame.K_ESCAPE,
    }
)


def menu_mnemonic(label: str) -> str:
    """Lowercased first character of a top-menu label."""
    if not label:
        return ""
    return label[0].lower()


def menu_index_for_mnemonic(
    menus: tuple[Menu, ...] | list[Menu],
    letter: str,
) -> int | None:
    """Index of the menu whose mnemonic matches ``letter``, or None."""
    needle = letter.lower()
    for index, menu in enumerate(menus):
        if menu_mnemonic(menu.label) == needle:
            return index
    return None


def menus_for_session(session: Any) -> tuple[Menu, ...]:
    """Menus for the live session.

    Layer number shortcuts use this session's z-order. Those commands are
    not menu rows.
    """
    slots = tuple(
        (slot, stem_overlay_header(session.layers[slot].stem))
        for slot in session.layer_z_order
    )
    if not slots:
        return MENUS
    return build_menus(slots)


def _command_indices(menu: Menu) -> list[int]:
    return [
        index
        for index, item in enumerate(menu.items)
        if not isinstance(item, MenuSeparator)
    ]


class MenuBarState:
    """Which top menu is current, whether its dropdown is open, and the highlight."""

    def __init__(self) -> None:
        self.focused = False
        self.menu_index = 0
        self.dropdown_open = False
        self.item_index = 0
        self._alt_tap_pending = False

    def focus(self) -> bool:
        """Focus the bar without opening a dropdown. True when focus was gained."""
        if self.focused:
            return False
        self.focused = True
        self.menu_index = 0
        self.dropdown_open = False
        self.item_index = 0
        return True

    def blur(self) -> None:
        """Drop bar focus and close the dropdown. Clears a pending Alt tap."""
        self.focused = False
        self.dropdown_open = False
        self._alt_tap_pending = False

    def toggle_focus(self) -> bool:
        """F10. Return True when the bar is focused after the toggle."""
        if self.focused:
            self.blur()
            return False
        self.focus()
        return True

    def note_alt_keydown(self) -> None:
        self._alt_tap_pending = True

    def cancel_alt_tap(self) -> None:
        self._alt_tap_pending = False

    def complete_alt_tap(self) -> bool:
        """Alt KEYUP. Focus the bar only when no other key arrived since KEYDOWN."""
        if not self._alt_tap_pending:
            return False
        self._alt_tap_pending = False
        return self.focus()

    def highlighted_command(self, menus: tuple[Menu, ...] | list[Menu]) -> Command | None:
        if not self.dropdown_open or not menus:
            return None
        menu = menus[self._clamped_menu_index(menus)]
        if self.item_index < 0 or self.item_index >= len(menu.items):
            return None
        item = menu.items[self.item_index]
        if isinstance(item, MenuSeparator):
            return None
        return item

    def handle_keydown(
        self,
        key: int,
        menus: tuple[Menu, ...] | list[Menu],
        ctx: CommandContext,
        controls: Any,
    ) -> bool:
        """Consume arrows, Enter, and Esc while the bar is focused.

        Any other key drops focus and returns False so the existing handlers
        still see it. Enter closes the dropdown before ``run``.
        """
        if not self.focused:
            return False
        if key not in _NAV_KEYS:
            self.blur()
            return False
        if not menus:
            if key == pygame.K_ESCAPE:
                self.blur()
            return True
        self.menu_index = self._clamped_menu_index(menus)
        if key == pygame.K_LEFT:
            self._move_menu(-1, menus)
        elif key == pygame.K_RIGHT:
            self._move_menu(1, menus)
        elif key == pygame.K_UP:
            self._move_item(-1, menus)
        elif key == pygame.K_DOWN:
            self._move_item(1, menus)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if not self.dropdown_open:
                self._open_dropdown(menus, last=False)
            else:
                self._activate(menus, ctx, controls)
        elif key == pygame.K_ESCAPE:
            if self.dropdown_open:
                self.dropdown_open = False
            else:
                self.blur()
        return True

    def open_menu(self, index: int, menus: tuple[Menu, ...] | list[Menu]) -> None:
        """Focus the bar and open this menu on its first command.

        A second call leaves the dropdown open. Cancels a pending Alt tap so
        Alt keyup does not treat the chord as a bare Alt tap.
        """
        self.cancel_alt_tap()
        if not menus:
            return
        self.focused = True
        self.menu_index = index % len(menus)
        self._open_dropdown(menus, last=False)

    def click_top(self, index: int, menus: tuple[Menu, ...] | list[Menu]) -> None:
        """Toggle the dropdown under a top label.

        A mouse open focuses the bar and leaves no keyboard row. Arrow keys
        seed the highlight afterwards. A second click on the open label closes
        the dropdown.
        """
        if not menus:
            return
        index = index % len(menus)
        self.focused = True
        if self.dropdown_open and self.menu_index == index:
            self.dropdown_open = False
            return
        self.menu_index = index
        self.dropdown_open = True
        self.item_index = -1

    def click_item(
        self,
        menu_index: int,
        item_index: int,
        menus: tuple[Menu, ...] | list[Menu],
        ctx: CommandContext,
        controls: Any,
    ) -> None:
        """Highlight the row. Enabled rows use the same close-then-run path as Enter."""
        if not menus:
            return
        self.focused = True
        self.menu_index = menu_index % len(menus)
        self.dropdown_open = True
        self.item_index = item_index
        self._activate(menus, ctx, controls)

    def _clamped_menu_index(self, menus: tuple[Menu, ...] | list[Menu]) -> int:
        if not menus:
            return 0
        return self.menu_index % len(menus)

    def _move_menu(self, delta: int, menus: tuple[Menu, ...] | list[Menu]) -> None:
        count = len(menus)
        self.menu_index = (self.menu_index + delta) % count
        if self.dropdown_open:
            self._open_dropdown(menus, last=False)

    def _move_item(self, delta: int, menus: tuple[Menu, ...] | list[Menu]) -> None:
        menu = menus[self.menu_index]
        indices = _command_indices(menu)
        if not indices:
            self.dropdown_open = True
            return
        if not self.dropdown_open:
            self._open_dropdown(menus, last=delta < 0)
            return
        if self.item_index not in indices:
            self.item_index = indices[-1] if delta < 0 else indices[0]
            return
        position = indices.index(self.item_index)
        self.item_index = indices[(position + delta) % len(indices)]

    def _open_dropdown(self, menus: tuple[Menu, ...] | list[Menu], *, last: bool) -> None:
        self.dropdown_open = True
        indices = _command_indices(menus[self.menu_index])
        if not indices:
            self.item_index = 0
            return
        self.item_index = indices[-1] if last else indices[0]

    def _activate(
        self,
        menus: tuple[Menu, ...] | list[Menu],
        ctx: CommandContext,
        controls: Any,
    ) -> None:
        command = self.highlighted_command(menus)
        if command is None or not command.enabled(ctx):
            return
        self.dropdown_open = False
        self.focused = False
        self._alt_tap_pending = False
        command.run(controls)
