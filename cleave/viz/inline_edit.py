"""Inline editing of a value in place: a text field, a colour picker, or the
open list of a combo.

The target is an inspector ``RowDescriptor`` or another hashable key, such as
a transport bar field.

One edit runs at a time. While one is active it owns the keyboard, so typing
never reaches a hotkey.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass

import pygame

from cleave.viz.choice_list import (
    ChoiceListKey,
    ChoiceListState,
    ChoiceListView,
    choice_list_view,
    handle_choice_list_key,
)
from cleave.viz.key_repeat import KeyRepeatController
from cleave.viz.row_kinds import RowDescriptor
from cleave.viz.text_edit import (
    TEXT_EDIT_REPEAT_KEYS,
    apply_text_edit_key,
    insert_text_at_caret,
    reset_caret_blink,
    text_caret_visible,
)

Rgb = tuple[int, int, int]


@dataclass
class InlineTextState:
    target: Hashable
    draft: str
    caret_index: int
    initial: str
    on_commit: Callable[[str], None]
    validate: Callable[[str], str | None] | None
    editing: bool = True
    error: str | None = None
    caret_blink_sec: float = 0.0


@dataclass(frozen=True)
class InlineTextView:
    draft: str
    caret_index: int
    caret_visible: bool
    error: str | None


@dataclass(frozen=True)
class ColourTarget:
    """A colour property. ``current`` is None when an optional colour is unset."""

    current: Rgb | None
    apply: Callable[[Rgb | None], None]
    optional: bool = False


@dataclass
class ColourEditState:
    descriptor: RowDescriptor
    target: ColourTarget
    value: Rgb | None


class InlineEditController:
    """The one inline edit in progress, if any."""

    def __init__(
        self,
        on_start_text_input: Callable[[], None] | None = None,
        on_stop_text_input: Callable[[], None] | None = None,
    ) -> None:
        self._on_start_text_input = on_start_text_input
        self._on_stop_text_input = on_stop_text_input
        self._text: InlineTextState | None = None
        self._colour: ColourEditState | None = None
        self._choice: ChoiceListState | None = None
        self._key_repeat = KeyRepeatController()

    @property
    def active(self) -> bool:
        return (
            self._text is not None
            or self._colour is not None
            or self._choice is not None
        )

    @property
    def choice_view(self) -> ChoiceListView | None:
        return choice_list_view(self._choice)

    @property
    def text_target(self) -> Hashable | None:
        return None if self._text is None else self._text.target

    @property
    def colour_edit(self) -> ColourEditState | None:
        return self._colour

    def text_view(self) -> InlineTextView | None:
        state = self._text
        if state is None:
            return None
        return InlineTextView(
            state.draft,
            state.caret_index,
            text_caret_visible(state),
            state.error,
        )

    def begin_text(
        self,
        target: Hashable,
        initial: str,
        on_commit: Callable[[str], None],
        *,
        validate: Callable[[str], str | None] | None = None,
    ) -> None:
        self.finish()
        self._text = InlineTextState(
            target=target,
            draft=initial,
            caret_index=len(initial),
            initial=initial,
            on_commit=on_commit,
            validate=validate,
        )
        if self._on_start_text_input is not None:
            self._on_start_text_input()

    def begin_colour(self, descriptor: RowDescriptor, target: ColourTarget) -> None:
        self.finish()
        self._colour = ColourEditState(descriptor, target, target.current)

    def begin_choice(self, state: ChoiceListState) -> None:
        """Open a combo's list. A pick applies at once; Esc keeps the value."""
        self.finish()
        self._choice = state

    def hover_choice(self, index: int) -> None:
        if self._choice is not None:
            self._choice.hover(index)

    def pick_choice(self, index: int) -> None:
        choice = self._choice
        if choice is None:
            return
        self._choice = None
        choice.pick(index)

    def set_colour(self, value: Rgb | None) -> None:
        """Apply a picked colour live. Esc restores the one from when it opened."""
        state = self._colour
        if state is None or value == state.value:
            return
        state.value = value
        state.target.apply(value)

    def finish(self) -> None:
        """Keep the edit: commit valid text, leave a colour as picked.

        Clicking away is not an error. Text that fails validation is dropped.
        An open list closes with its value unchanged.
        """
        self._colour = None
        self._choice = None
        state = self._text
        if state is None:
            return
        valid = state.validate is None or state.validate(state.draft) is None
        self._end_text()
        if valid and state.draft != state.initial:
            state.on_commit(state.draft)

    def cancel(self) -> None:
        self._choice = None
        colour = self._colour
        if colour is not None:
            self._colour = None
            if colour.value != colour.target.current:
                colour.target.apply(colour.target.current)
        if self._text is not None:
            self._end_text()

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Consume every key while an edit is active."""
        if not self.active:
            return False
        choice = self._choice
        if choice is not None:
            outcome = handle_choice_list_key(choice, event.key)
            if outcome in (ChoiceListKey.PICKED, ChoiceListKey.CLOSED):
                self._choice = None
            return True
        if event.key == pygame.K_ESCAPE:
            self.cancel()
            return True
        state = self._text
        if state is None:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                self.finish()
            return True
        if event.key == pygame.K_TAB:
            self.finish()
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._commit_from_enter(state)
        elif event.key in TEXT_EDIT_REPEAT_KEYS:
            apply_text_edit_key(state, event.key)
            self._key_repeat.on_keydown(
                event.key,
                event.mod,
                on_repeat=lambda key, _mod: self._repeat_key(key),
            )
        return True

    def handle_keyup(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False
        self._key_repeat.on_keyup(event.key)
        return True

    def handle_text_input(self, text: str) -> bool:
        state = self._text
        if state is None:
            return False
        insert_text_at_caret(state, text)
        return True

    def tick(self, dt_sec: float) -> None:
        state = self._text
        if state is None:
            return
        state.caret_blink_sec += dt_sec
        self._key_repeat.tick(dt_sec)

    def _commit_from_enter(self, state: InlineTextState) -> None:
        error = None if state.validate is None else state.validate(state.draft)
        if error is not None:
            state.error = error
            reset_caret_blink(state)
            return
        self.finish()

    def _repeat_key(self, key: int) -> None:
        if self._text is not None:
            apply_text_edit_key(self._text, key)

    def _end_text(self) -> None:
        self._text = None
        self._key_repeat.disarm()
        if self._on_stop_text_input is not None:
            self._on_stop_text_input()
