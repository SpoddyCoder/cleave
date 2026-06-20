"""Centered confirm modal host for live tuning UI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import pygame


class ModalKind(Enum):
    YES_NO = "yes_no"
    SAVE_CHOICE = "save_choice"
    UNSAVED_QUIT = "unsaved_quit"


@dataclass
class ModalOption:
    label: str
    action: Callable[[], None]


@dataclass
class ModalRequest:
    kind: ModalKind
    message: str | None
    options: list[ModalOption]
    on_dismiss: Callable[[], None] | None = None


@dataclass(frozen=True)
class ModalViewState:
    kind: ModalKind
    message: str | None
    options: tuple[str, ...]
    focus_index: int


_UNSAVED_QUIT_MESSAGE = "Unsaved changes - save changes before exit?"
_SAVE_CHOICE_MESSAGE = "Save configuration?"


class ModalHost:
    """Modal prompt host; consumes keys while active."""

    def __init__(self) -> None:
        self._request: ModalRequest | None = None
        self._focus_index = 0

    @property
    def active(self) -> bool:
        return self._request is not None

    def view_state(self) -> ModalViewState | None:
        if self._request is None:
            return None
        return ModalViewState(
            kind=self._request.kind,
            message=self._request.message,
            options=tuple(option.label for option in self._request.options),
            focus_index=self._focus_index,
        )

    def prompt(self, request: ModalRequest) -> None:
        self._request = request
        self._focus_index = 0

    def prompt_yes_no(
        self,
        message: str,
        on_confirm: Callable[[], None],
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        def on_no() -> None:
            if on_cancel is not None:
                on_cancel()

        self.prompt(
            ModalRequest(
                kind=ModalKind.YES_NO,
                message=message,
                options=[
                    ModalOption("Yes", on_confirm),
                    ModalOption("No", on_no),
                ],
                on_dismiss=on_cancel,
            )
        )

    def prompt_save_choice(
        self,
        on_overwrite: Callable[[], None],
        on_save_as_new: Callable[[], None],
        on_dismiss: Callable[[], None] | None = None,
    ) -> None:
        self.prompt(
            ModalRequest(
                kind=ModalKind.SAVE_CHOICE,
                message=_SAVE_CHOICE_MESSAGE,
                options=[
                    ModalOption("OVERWRITE", on_overwrite),
                    ModalOption("SAVE AS NEW", on_save_as_new),
                ],
                on_dismiss=on_dismiss,
            )
        )

    def prompt_save_as_new(
        self,
        on_save_as_new: Callable[[], None],
        on_dismiss: Callable[[], None] | None = None,
    ) -> None:
        def on_cancel() -> None:
            if on_dismiss is not None:
                on_dismiss()

        self.prompt(
            ModalRequest(
                kind=ModalKind.SAVE_CHOICE,
                message=_SAVE_CHOICE_MESSAGE,
                options=[
                    ModalOption("SAVE AS NEW", on_save_as_new),
                    ModalOption("CANCEL", on_cancel),
                ],
                on_dismiss=on_dismiss,
            )
        )

    def prompt_unsaved_quit(
        self,
        on_save: Callable[[], None],
        on_discard: Callable[[], None],
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        def on_cancel_action() -> None:
            if on_cancel is not None:
                on_cancel()

        self.prompt(
            ModalRequest(
                kind=ModalKind.UNSAVED_QUIT,
                message=_UNSAVED_QUIT_MESSAGE,
                options=[
                    ModalOption("SAVE", on_save),
                    ModalOption("DON'T SAVE", on_discard),
                    ModalOption("CANCEL", on_cancel_action),
                ],
                on_dismiss=on_cancel,
            )
        )

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Return True when the event is consumed (including while blocking)."""
        if not self.active or event.type != pygame.KEYDOWN:
            return False

        if event.key == pygame.K_ESCAPE:
            self._dismiss()
            return True

        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            option_count = len(self._request.options)  # type: ignore[union-attr]
            delta = -1 if event.key == pygame.K_LEFT else 1
            self._focus_index = (self._focus_index + delta) % option_count
            return True

        if len(self._request.options) == 2:  # type: ignore[union-attr]
            if event.key == pygame.K_y:
                self._focus_index = 0
                return True
            if event.key == pygame.K_n:
                self._focus_index = 1
                return True

        if event.key == pygame.K_RETURN:
            self._activate_focused()
            return True

        return True

    def _dismiss(self) -> None:
        request = self._request
        self._request = None
        self._focus_index = 0
        if request is not None and request.on_dismiss is not None:
            request.on_dismiss()

    def _activate_focused(self) -> None:
        request = self._request
        if request is None:
            return
        focus_index = self._focus_index
        self._request = None
        self._focus_index = 0
        request.options[focus_index].action()
