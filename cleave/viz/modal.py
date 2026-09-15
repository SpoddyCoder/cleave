"""Centered confirm modal host for live tuning UI."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

import pygame

from cleave.viz.key_repeat import KeyRepeatController, mod_shift


class ModalKind(Enum):
    YES_NO = "yes_no"
    UNSAVED_QUIT = "unsaved_quit"
    CHOICE = "choice"
    PROGRESS = "progress"
    TEXT = "text"


class TextFocusRegion(Enum):
    FIELD = "field"
    BUTTONS = "buttons"


def capital_case_modal_option(label: str) -> str:
    """Capital Case each whitespace-separated word; leave numeric tokens unchanged."""

    def _word(word: str) -> str:
        if not word:
            return word
        for index, char in enumerate(word):
            if char.isalpha():
                return word[:index] + char.upper() + word[index + 1 :].lower()
            if char.isdigit():
                return word
        return word

    return " ".join(_word(part) for part in label.split(" "))


def clamp_modal_focus_index(index: int, option_count: int) -> int:
    """Return ``index`` when in range, otherwise ``0`` (first option)."""
    if option_count <= 0 or index < 0 or index >= option_count:
        return 0
    return index


def _logical_line_start(text: str, index: int) -> int:
    newline = text.rfind("\n", 0, index)
    if newline < 0:
        return 0
    return newline + 1


def _next_logical_line_start(text: str, index: int) -> int:
    newline = text.find("\n", index)
    if newline < 0:
        return len(text)
    return newline + 1


@dataclass
class ModalOption:
    label: str
    action: Callable[[], None]


@dataclass(frozen=True)
class ModalLabeledLine:
    """Setting-style modal body line: LABEL prefix ``label: `` plus VALUE text."""

    label: str
    value: str

    def prefix(self) -> str:
        return f"{self.label}: "

    def display_text(self) -> str:
        return f"{self.label}: {self.value}"


@dataclass
class TextModalState:
    cta: str
    draft: str
    single_line: bool
    editing: bool
    caret_index: int
    focus_region: TextFocusRegion
    button_index: int
    on_confirm: Callable[[str], None]
    on_cancel: Callable[[], None] | None
    initial: str
    caret_blink_sec: float = 0.0


_TEXT_EDIT_REPEAT_KEYS = frozenset(
    {
        pygame.K_LEFT,
        pygame.K_RIGHT,
        pygame.K_UP,
        pygame.K_DOWN,
        pygame.K_BACKSPACE,
    }
)
_CARET_BLINK_CYCLE_SEC = 1.0
_CARET_BLINK_VISIBLE_SEC = 0.5


def _reset_caret_blink(state: TextModalState) -> None:
    state.caret_blink_sec = 0.0


def _text_caret_visible(state: TextModalState) -> bool:
    if not state.editing:
        return False
    return (state.caret_blink_sec % _CARET_BLINK_CYCLE_SEC) < _CARET_BLINK_VISIBLE_SEC


def _insert_text_at_caret(state: TextModalState, text: str) -> None:
    caret = state.caret_index
    state.draft = state.draft[:caret] + text + state.draft[caret:]
    state.caret_index = caret + len(text)
    _reset_caret_blink(state)


def _apply_text_edit_key(state: TextModalState, key: int) -> None:
    _reset_caret_blink(state)
    if key == pygame.K_BACKSPACE:
        if state.caret_index > 0:
            caret = state.caret_index
            state.draft = state.draft[:caret - 1] + state.draft[caret:]
            state.caret_index = caret - 1
        return
    if key == pygame.K_LEFT:
        state.caret_index = max(0, state.caret_index - 1)
        return
    if key == pygame.K_RIGHT:
        state.caret_index = min(len(state.draft), state.caret_index + 1)
        return
    if key == pygame.K_UP:
        if not state.single_line:
            state.caret_index = _logical_line_start(state.draft, state.caret_index)
        return
    if key == pygame.K_DOWN:
        if not state.single_line:
            state.caret_index = _next_logical_line_start(
                state.draft, state.caret_index
            )


@dataclass
class ModalRequest:
    kind: ModalKind
    message: str | None
    options: list[ModalOption]
    on_dismiss: Callable[[], None] | None = None
    initial_focus_index: int = 0
    labeled_lines: tuple[ModalLabeledLine, ...] = ()
    progress_fraction: float | None = None


@dataclass(frozen=True)
class ModalViewState:
    kind: ModalKind
    message: str | None
    options: tuple[str, ...]
    focus_index: int
    labeled_lines: tuple[ModalLabeledLine, ...] = ()
    progress_fraction: float | None = None
    cta: str | None = None
    draft: str | None = None
    single_line: bool = False
    editing: bool = False
    caret_index: int = 0
    focus_region: TextFocusRegion | None = None
    button_index: int = 0
    caret_visible: bool = True


_UNSAVED_QUIT_MESSAGE = "Unsaved changes - save changes before exit?"


class ModalHost:
    """Modal prompt host; consumes keys while active."""

    def __init__(
        self,
        on_start_text_input: Callable[[], None] | None = None,
        on_stop_text_input: Callable[[], None] | None = None,
    ) -> None:
        self._request: ModalRequest | None = None
        self._text_state: TextModalState | None = None
        self._focus_index = 0
        self._on_start_text_input = on_start_text_input
        self._on_stop_text_input = on_stop_text_input
        self._text_input_started = False
        self._text_key_repeat = KeyRepeatController()

    @property
    def active(self) -> bool:
        return self._request is not None

    @property
    def text_key_repeat_armed(self) -> bool:
        return self._text_key_repeat.is_armed

    def view_state(self) -> ModalViewState | None:
        if self._request is None:
            return None
        text = self._text_state
        if self._request.kind == ModalKind.TEXT and text is not None:
            return ModalViewState(
                kind=ModalKind.TEXT,
                message=None,
                options=(),
                focus_index=self._focus_index,
                cta=text.cta,
                draft=text.draft,
                single_line=text.single_line,
                editing=text.editing,
                caret_index=text.caret_index,
                focus_region=text.focus_region,
                button_index=text.button_index,
                caret_visible=_text_caret_visible(text),
            )
        return ModalViewState(
            kind=self._request.kind,
            message=self._request.message,
            options=tuple(
                capital_case_modal_option(option.label)
                for option in self._request.options
            ),
            focus_index=self._focus_index,
            labeled_lines=self._request.labeled_lines,
            progress_fraction=self._request.progress_fraction,
        )

    def prompt(self, request: ModalRequest) -> None:
        self._stop_text_input()
        self._request = request
        self._text_state = None
        self._focus_index = clamp_modal_focus_index(
            request.initial_focus_index,
            len(request.options),
        )

    def prompt_yes_no(
        self,
        message: str,
        on_confirm: Callable[[], None],
        on_cancel: Callable[[], None] | None = None,
        *,
        cancel_label: str = "No",
        labeled_lines: Sequence[ModalLabeledLine] = (),
    ) -> None:
        def on_cancel_action() -> None:
            if on_cancel is not None:
                on_cancel()

        self.prompt(
            ModalRequest(
                kind=ModalKind.YES_NO,
                message=message,
                options=[
                    ModalOption("Yes", on_confirm),
                    ModalOption(cancel_label, on_cancel_action),
                ],
                on_dismiss=on_cancel,
                labeled_lines=tuple(labeled_lines),
            )
        )

    def prompt_choice(
        self,
        message: str,
        options: list[ModalOption],
        on_dismiss: Callable[[], None] | None = None,
        *,
        initial_focus_index: int = 0,
        labeled_lines: Sequence[ModalLabeledLine] = (),
    ) -> None:
        self.prompt(
            ModalRequest(
                kind=ModalKind.CHOICE,
                message=message,
                options=options,
                on_dismiss=on_dismiss,
                initial_focus_index=initial_focus_index,
                labeled_lines=tuple(labeled_lines),
            )
        )

    def prompt_progress(
        self,
        message: str,
        *,
        labeled_lines: Sequence[ModalLabeledLine] = (),
        fraction: float = 0.0,
    ) -> None:
        self.prompt(
            ModalRequest(
                kind=ModalKind.PROGRESS,
                message=message,
                options=[],
                labeled_lines=tuple(labeled_lines),
                progress_fraction=max(0.0, min(1.0, float(fraction))),
            )
        )

    def update_progress(self, fraction: float) -> None:
        if self._request is None or self._request.kind != ModalKind.PROGRESS:
            return
        self._request.progress_fraction = max(0.0, min(1.0, float(fraction)))

    def prompt_text(
        self,
        cta: str,
        initial: str,
        on_confirm: Callable[[str], None],
        on_cancel: Callable[[], None] | None = None,
        *,
        single_line: bool = False,
    ) -> None:
        self.prompt(
            ModalRequest(
                kind=ModalKind.TEXT,
                message=None,
                options=[],
                on_dismiss=on_cancel,
            )
        )
        self._text_state = TextModalState(
            cta=cta,
            draft=initial,
            single_line=single_line,
            editing=True,
            caret_index=len(initial),
            focus_region=TextFocusRegion.FIELD,
            button_index=0,
            on_confirm=on_confirm,
            on_cancel=on_cancel,
            initial=initial,
        )
        self._start_text_input()

    def dismiss(self) -> None:
        self._dismiss()

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
                    ModalOption("Save", on_save),
                    ModalOption("Don't Save", on_discard),
                    ModalOption("Cancel", on_cancel_action),
                ],
                on_dismiss=on_cancel,
            )
        )

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Return True when the event is consumed (including while blocking)."""
        if not self.active or event.type != pygame.KEYDOWN:
            return False

        request = self._request
        assert request is not None
        if request.kind == ModalKind.PROGRESS:
            return True
        if request.kind == ModalKind.TEXT:
            return self._handle_text_keydown(event)

        if event.key == pygame.K_ESCAPE:
            self._dismiss()
            return True

        option_count = len(request.options)
        if option_count == 0:
            return True
        if event.key in (pygame.K_UP, pygame.K_LEFT):
            self._focus_index = (self._focus_index - 1) % option_count
            return True
        if event.key in (pygame.K_DOWN, pygame.K_RIGHT):
            self._focus_index = (self._focus_index + 1) % option_count
            return True

        if option_count == 2:
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

    def handle_keyup(self, event: pygame.event.Event) -> bool:
        """Return True when a TEXT modal consumed the event."""
        if event.type != pygame.KEYUP or self._request is None:
            return False
        if self._request.kind != ModalKind.TEXT:
            return False
        self._text_key_repeat.on_keyup(event.key)
        return True

    def tick(self, dt_sec: float) -> None:
        self._text_key_repeat.tick(dt_sec)
        state = self._text_state
        if state is None or not state.editing:
            return
        state.caret_blink_sec += dt_sec

    def handle_text_input(self, text: str) -> bool:
        if not self.active or self._request is None:
            return False
        if self._request.kind != ModalKind.TEXT:
            return False
        state = self._text_state
        if state is None or not state.editing:
            return False
        if not text or (state.single_line and "\n" in text):
            return True
        _insert_text_at_caret(state, text)
        return True

    def _handle_text_keydown(self, event: pygame.event.Event) -> bool:
        state = self._text_state
        if state is None:
            return True
        if state.editing:
            return self._handle_text_edit_keydown(event, state)
        return self._handle_text_navigate_keydown(event, state)

    def _handle_text_edit_keydown(
        self,
        event: pygame.event.Event,
        state: TextModalState,
    ) -> bool:
        if event.key == pygame.K_ESCAPE:
            self._leave_text_edit(state)
            return True
        if event.key == pygame.K_RETURN:
            if mod_shift(event.mod):
                if not state.single_line:
                    _insert_text_at_caret(state, "\n")
                return True
            self._leave_text_edit(state)
            return True
        if event.key in _TEXT_EDIT_REPEAT_KEYS:
            _apply_text_edit_key(state, event.key)
            self._text_key_repeat.on_keydown(
                event.key,
                event.mod,
                on_repeat=lambda key, _mod: self._repeat_text_edit_key(key),
            )
            return True
        return True

    def _repeat_text_edit_key(self, key: int) -> None:
        state = self._text_state
        if state is None or not state.editing:
            return
        _apply_text_edit_key(state, key)

    def _handle_text_navigate_keydown(
        self,
        event: pygame.event.Event,
        state: TextModalState,
    ) -> bool:
        if event.key == pygame.K_ESCAPE:
            self._dismiss_text(invoke_cancel=True)
            return True
        if event.key in (pygame.K_UP, pygame.K_DOWN):
            if state.focus_region == TextFocusRegion.FIELD:
                state.focus_region = TextFocusRegion.BUTTONS
                state.button_index = 0
            else:
                state.focus_region = TextFocusRegion.FIELD
            return True
        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            if state.focus_region == TextFocusRegion.BUTTONS:
                delta = -1 if event.key == pygame.K_LEFT else 1
                state.button_index = (state.button_index + delta) % 2
            return True
        if event.key == pygame.K_RETURN:
            if state.focus_region == TextFocusRegion.FIELD:
                state.editing = True
                _reset_caret_blink(state)
                self._start_text_input()
                return True
            if state.button_index == 0:
                on_confirm = state.on_confirm
                draft = state.draft
                self._dismiss_text(invoke_cancel=False)
                on_confirm(draft)
            else:
                self._dismiss_text(invoke_cancel=True)
            return True
        return True

    def _leave_text_edit(self, state: TextModalState) -> None:
        self._stop_text_input()
        state.editing = False
        state.focus_region = TextFocusRegion.FIELD

    def _start_text_input(self) -> None:
        if self._text_input_started:
            return
        self._text_input_started = True
        if self._on_start_text_input is not None:
            self._on_start_text_input()

    def _stop_text_input(self) -> None:
        self._text_key_repeat.disarm()
        if not self._text_input_started:
            return
        self._text_input_started = False
        if self._on_stop_text_input is not None:
            self._on_stop_text_input()

    def _dismiss_text(self, *, invoke_cancel: bool) -> None:
        self._stop_text_input()
        state = self._text_state
        self._text_state = None
        self._request = None
        self._focus_index = 0
        if invoke_cancel and state is not None and state.on_cancel is not None:
            state.on_cancel()

    def _dismiss(self) -> None:
        self._stop_text_input()
        request = self._request
        self._request = None
        self._text_state = None
        self._focus_index = 0
        if request is not None and request.on_dismiss is not None:
            request.on_dismiss()

    def _activate_focused(self) -> None:
        request = self._request
        if request is None:
            return
        self._stop_text_input()
        focus_index = self._focus_index
        self._request = None
        self._text_state = None
        self._focus_index = 0
        request.options[focus_index].action()
