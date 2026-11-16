"""Centered confirm modal host for live tuning UI."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

import pygame

from cleave.choice import ChoiceKind, choice_kind, step_index
from cleave.viz.choice_list import (
    ChoiceListKey,
    ChoiceListState,
    ChoiceListView,
    choice_list_view,
    handle_choice_list_key,
)
from cleave.viz.text_edit import (
    TEXT_EDIT_REPEAT_KEYS,
    apply_text_edit_key,
    insert_text_at_caret,
    reset_caret_blink,
    text_caret_visible,
)
from cleave.viz.input_modality import InputModality, PointerMotionTracker
from cleave.viz.key_repeat import KeyRepeatController, RepeatClock, mod_shift


class ModalKind(Enum):
    CONFIRM = "confirm"
    FORM = "form"
    UNSAVED_QUIT = "unsaved_quit"
    PROGRESS = "progress"
    TEXT = "text"


class ButtonRole(Enum):
    """Fill of a modal button. One primary or danger button per dialog."""

    PLAIN = "plain"
    PRIMARY = "primary"
    DANGER = "danger"


FormValues = dict[str, int]


@dataclass(frozen=True)
class FormField:
    """One parameter of a form. ``value`` is an index into ``options``.

    Up to three options show as segments, more as a combo (``choice_kind``).
    A ``stepper`` field is a number shown as ``< value >`` instead; its options
    run low to high, and PageUp/PageDown move ``large_step`` options at once.
    ``help`` and ``option_help`` (one line per option, or empty) fill the help
    column while the field is focused. ``section`` groups the field under a
    heading; consecutive fields with the same section share one heading.
    """

    id: str
    label: str
    options: tuple[str, ...]
    value: int = 0
    visible: Callable[[FormValues], bool] | None = None
    help: tuple[str, ...] = ()
    option_help: tuple[str, ...] = ()
    section: str | None = None
    stepper: bool = False
    large_step: int = 1


@dataclass(frozen=True)
class FormSpec:
    """A dialog of parameters. Nothing is applied until confirm.

    ``info`` is a line of feedback on the draft values, such as a count of the
    cues a command would change. It runs when a value changes, not every frame.
    It draws in brackets under the title, in lower case.
    ``on_change`` runs after a field changes, with its id, and may adjust
    other draft values in place, such as keeping a start before an end.
    ``help`` describes the whole dialog in the help column.
    """

    title: str
    fields: tuple[FormField, ...]
    confirm_label: str
    on_confirm: Callable[[FormValues], None]
    on_cancel: Callable[[], None] | None = None
    cancel_label: str = "Cancel"
    body: str | None = None
    info: Callable[[FormValues], str | None] | None = None
    destructive: bool = False
    help: tuple[str, ...] = ()
    on_change: Callable[[str, FormValues], None] | None = None


@dataclass(frozen=True)
class ModalHelpSection:
    """One help column section for an open form: a title, lines, and entries."""

    title: str
    lines: tuple[str, ...] = ()
    entries: tuple[tuple[str, str], ...] = ()


def _help_title(label: str) -> str:
    return " ".join(word[:1].upper() + word[1:] for word in label.split())


@dataclass(frozen=True)
class FormRowView:
    """One field row. ``heading`` is a section heading drawn above the row;
    ``indented`` rows sit under a heading.
    """

    label: str
    kind: ChoiceKind
    options: tuple[str, ...]
    value: int
    focused: bool
    heading: str | None = None
    indented: bool = False
    stepper: bool = False


@dataclass
class FormState:
    spec: FormSpec
    values: FormValues
    field_index: int | None
    info: str | None = None

    def visible_fields(self) -> tuple[FormField, ...]:
        return tuple(
            field
            for field in self.spec.fields
            if field.visible is None or field.visible(self.values)
        )

    def refresh_info(self) -> None:
        info = self.spec.info
        self.info = None if info is None else info(self.values)


def _form_row_views(form: FormState) -> tuple[FormRowView, ...]:
    rows: list[FormRowView] = []
    previous: str | None = None
    for index, field in enumerate(form.visible_fields()):
        section = field.section
        rows.append(
            FormRowView(
                field.label,
                choice_kind(len(field.options)),
                field.options,
                form.values[field.id],
                index == form.field_index,
                heading=section if section is not None and section != previous else None,
                indented=section is not None,
                stepper=field.stepper,
            )
        )
        previous = section
    return tuple(rows)


class TextFocusRegion(Enum):
    FIELD = "field"
    BUTTONS = "buttons"


def clamp_modal_focus_index(index: int, option_count: int) -> int:
    """Return ``index`` when in range, otherwise ``0`` (first option)."""
    if option_count <= 0 or index < 0 or index >= option_count:
        return 0
    return index


@dataclass
class ModalOption:
    label: str
    action: Callable[[], None]
    role: ButtonRole = ButtonRole.PLAIN


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
    validate: Callable[[str], str | None] | None = None
    error: str | None = None
    caret_blink_sec: float = 0.0


@dataclass
class ModalRequest:
    kind: ModalKind
    message: str | None
    options: list[ModalOption]
    on_dismiss: Callable[[], None] | None = None
    initial_focus_index: int = 0
    labeled_lines: tuple[ModalLabeledLine, ...] = ()
    progress_fraction: float | None = None
    body: str | None = None
    # PROGRESS only: draw the text in the larger progress-label font.
    large_text: bool = False


@dataclass(frozen=True)
class ModalViewState:
    kind: ModalKind
    message: str | None
    options: tuple[str, ...]
    focus_index: int
    labeled_lines: tuple[ModalLabeledLine, ...] = ()
    progress_fraction: float | None = None
    large_text: bool = False
    cta: str | None = None
    draft: str | None = None
    single_line: bool = False
    editing: bool = False
    caret_index: int = 0
    focus_region: TextFocusRegion | None = None
    button_index: int = 0
    caret_visible: bool = True
    error: str | None = None
    body: str | None = None
    option_roles: tuple[ButtonRole, ...] = ()
    form_rows: tuple[FormRowView, ...] = ()
    form_info: str | None = None
    form_buttons_focused: bool = False
    # The open combo list of a form row; ``target`` is the row index.
    form_choice: ChoiceListView | None = None
    # A stepper arrow held down with the pointer: (row, step), step -1 or 1.
    form_step_held: tuple[int, int] | None = None


@dataclass
class _FormStepHold:
    """A stepper arrow held with the pointer. ``tick`` repeats its step."""

    row: int
    delta: int
    clock: RepeatClock


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
        self._form_state: FormState | None = None
        self._form_choice: ChoiceListState | None = None
        self._form_key_repeat = KeyRepeatController()
        self._form_hold: _FormStepHold | None = None
        self._focus_index = 0
        self._on_start_text_input = on_start_text_input
        self._on_stop_text_input = on_stop_text_input
        self._text_input_started = False
        self._text_key_repeat = KeyRepeatController()
        self._text_field_wrap: Callable[[str], list[str]] | None = None
        self._input_modality = InputModality.POINTER
        self._pointer_motion = PointerMotionTracker()

    def set_text_field_wrap(
        self, wrap: Callable[[str], list[str]] | None
    ) -> None:
        """Use the same wrap as field draw; None falls back to logical lines."""
        self._text_field_wrap = wrap

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
                caret_visible=text_caret_visible(text),
                error=text.error,
            )
        form = self._form_state
        form_rows: tuple[FormRowView, ...] = ()
        if form is not None:
            form_rows = _form_row_views(form)
        return ModalViewState(
            kind=self._request.kind,
            message=self._request.message,
            options=tuple(option.label for option in self._request.options),
            focus_index=self._focus_index,
            labeled_lines=self._request.labeled_lines,
            progress_fraction=self._request.progress_fraction,
            large_text=self._request.large_text,
            body=self._request.body,
            option_roles=tuple(option.role for option in self._request.options),
            form_rows=form_rows,
            form_info=None if form is None else form.info,
            form_buttons_focused=form is not None and form.field_index is None,
            form_choice=choice_list_view(self._form_choice),
            form_step_held=(
                None
                if self._form_hold is None
                else (self._form_hold.row, self._form_hold.delta)
            ),
        )

    def prompt(self, request: ModalRequest) -> None:
        self.stop_text_input()
        self._request = request
        self._text_state = None
        self._form_state = None
        self._form_choice = None
        self._stop_form_repeat()
        self._input_modality = InputModality.POINTER
        self._pointer_motion.reset()
        self._focus_index = clamp_modal_focus_index(
            request.initial_focus_index,
            len(request.options),
        )

    def enter_keyboard_modality(self) -> None:
        self._input_modality = InputModality.KEYBOARD

    def enter_pointer_modality(self) -> None:
        self._input_modality = InputModality.POINTER

    def note_pointer_motion(self, event: pygame.event.Event) -> None:
        if self._pointer_motion.moved(event):
            self.enter_pointer_modality()

    def prompt_confirm(
        self,
        message: str,
        confirm_label: str,
        on_confirm: Callable[[], None],
        on_cancel: Callable[[], None] | None = None,
        *,
        body: str | None = None,
        destructive: bool = False,
        labeled_lines: Sequence[ModalLabeledLine] = (),
    ) -> None:
        """Ask once, with a verb button and Cancel.

        A destructive prompt fills the button red and starts on Cancel, so a
        stray Enter does nothing.
        """

        def on_cancel_action() -> None:
            if on_cancel is not None:
                on_cancel()

        self.prompt_buttons(
            message,
            [
                ModalOption(
                    confirm_label,
                    on_confirm,
                    ButtonRole.DANGER if destructive else ButtonRole.PRIMARY,
                ),
                ModalOption("Cancel", on_cancel_action),
            ],
            on_dismiss=on_cancel,
            initial_focus_index=1 if destructive else 0,
            labeled_lines=labeled_lines,
            body=body,
        )

    def prompt_buttons(
        self,
        message: str,
        options: list[ModalOption],
        on_dismiss: Callable[[], None] | None = None,
        *,
        initial_focus_index: int = 0,
        labeled_lines: Sequence[ModalLabeledLine] = (),
        body: str | None = None,
    ) -> None:
        """Ask with a right-aligned row of buttons, one per option.

        Give at most one option a PRIMARY or DANGER role. Esc runs
        ``on_dismiss``.
        """
        self.prompt(
            ModalRequest(
                kind=ModalKind.CONFIRM,
                message=message,
                options=options,
                on_dismiss=on_dismiss,
                initial_focus_index=initial_focus_index,
                labeled_lines=tuple(labeled_lines),
                body=body,
            )
        )

    def prompt_notice(
        self,
        message: str,
        on_close: Callable[[], None] | None = None,
        *,
        labeled_lines: Sequence[ModalLabeledLine] = (),
        body: str | None = None,
    ) -> None:
        """Tell the user something, with one OK button. Esc also closes it."""

        def close() -> None:
            if on_close is not None:
                on_close()

        self.prompt_buttons(
            message,
            [ModalOption("OK", close, ButtonRole.PRIMARY)],
            on_dismiss=on_close,
            labeled_lines=labeled_lines,
            body=body,
        )

    def prompt_progress(
        self,
        message: str,
        *,
        labeled_lines: Sequence[ModalLabeledLine] = (),
        fraction: float = 0.0,
        on_cancel: Callable[[], None] | None = None,
        large_text: bool = True,
    ) -> None:
        """Show a progress bar. With *on_cancel*, a Cancel button (and Esc) runs it.

        *large_text* draws the message and lines in the larger progress-label
        font; a dialog with several status lines passes False for body text.
        """
        options = [] if on_cancel is None else [ModalOption("Cancel", on_cancel)]
        self.prompt(
            ModalRequest(
                kind=ModalKind.PROGRESS,
                message=message,
                options=options,
                on_dismiss=on_cancel,
                labeled_lines=tuple(labeled_lines),
                progress_fraction=max(0.0, min(1.0, float(fraction))),
                large_text=large_text,
            )
        )

    def update_progress(
        self,
        fraction: float,
        *,
        message: str | None = None,
        labeled_lines: Sequence[ModalLabeledLine] | None = None,
    ) -> None:
        """Move the bar. *message* and *labeled_lines* replace the text when given."""
        request = self._request
        if request is None or request.kind != ModalKind.PROGRESS:
            return
        request.progress_fraction = max(0.0, min(1.0, float(fraction)))
        if message is not None:
            request.message = message
        if labeled_lines is not None:
            request.labeled_lines = tuple(labeled_lines)

    def prompt_text(
        self,
        cta: str,
        initial: str,
        on_confirm: Callable[[str], None],
        on_cancel: Callable[[], None] | None = None,
        *,
        single_line: bool = False,
        validate: Callable[[str], str | None] | None = None,
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
            validate=validate,
        )
        self.start_text_input()

    def dismiss(self) -> None:
        self._dismiss()

    def prompt_form(self, spec: FormSpec) -> None:
        """Open a dialog of parameters. Cancel leaves everything untouched.

        Focus starts on the first field. A destructive form starts on Cancel.
        """
        fields_first = bool(spec.fields) and not spec.destructive
        state = FormState(
            spec=spec,
            values={field.id: field.value for field in spec.fields},
            field_index=0 if fields_first else None,
        )
        state.refresh_info()

        def confirm() -> None:
            spec.on_confirm(dict(state.values))

        def cancel() -> None:
            if spec.on_cancel is not None:
                spec.on_cancel()

        role = ButtonRole.DANGER if spec.destructive else ButtonRole.PRIMARY
        self.prompt(
            ModalRequest(
                kind=ModalKind.FORM,
                message=spec.title,
                options=[
                    ModalOption(spec.confirm_label, confirm, role),
                    ModalOption(spec.cancel_label, cancel),
                ],
                on_dismiss=spec.on_cancel,
                initial_focus_index=1 if spec.destructive else 0,
                body=spec.body,
            )
        )
        self._form_state = state

    def set_form_value(self, row: int, value: int) -> None:
        """Focus row ``row`` and choose option ``value``."""
        state = self._form_state
        if state is None:
            return
        fields = state.visible_fields()
        if not 0 <= row < len(fields):
            return
        state.field_index = row
        field = fields[row]
        state.values[field.id] = max(0, min(value, len(field.options) - 1))
        self._after_form_change(state, field.id)

    def step_form_value(self, row: int, delta: int) -> None:
        """Focus row ``row`` and step its option, stopping at either end."""
        state = self._form_state
        if state is None:
            return
        fields = state.visible_fields()
        if not 0 <= row < len(fields):
            return
        state.field_index = row
        field = fields[row]
        state.values[field.id] = step_index(
            state.values[field.id], len(field.options), delta
        )
        self._after_form_change(state, field.id)

    def press_form_step(self, row: int, delta: int) -> None:
        """Pointer down on a stepper arrow: step once, then repeat while held."""
        self.step_form_value(row, delta)
        self._form_hold = _FormStepHold(row, delta, RepeatClock())

    def release_form_step(self) -> None:
        """Pointer up after ``press_form_step``."""
        self._form_hold = None

    def _stop_form_repeat(self) -> None:
        self._form_hold = None
        self._form_key_repeat.disarm()

    def open_form_choice(self, row: int) -> None:
        """Focus row ``row`` and open its option list, when it is a combo."""
        state = self._form_state
        if state is None:
            return
        fields = state.visible_fields()
        if not 0 <= row < len(fields):
            return
        state.field_index = row
        field = fields[row]
        if field.stepper or choice_kind(len(field.options)) is not ChoiceKind.COMBO:
            return
        self._form_choice = ChoiceListState(
            target=row,
            options=field.options,
            start=state.values[field.id],
            on_pick=lambda index: self.set_form_value(row, index),
        )

    def hover_form_choice(self, index: int) -> None:
        if self._form_choice is not None:
            self._form_choice.hover(index)

    def pick_form_choice(self, index: int) -> None:
        choice = self._form_choice
        if choice is None:
            return
        self._form_choice = None
        choice.pick(index)

    def close_form_choice(self) -> None:
        self._form_choice = None

    def help_sections(self) -> tuple[ModalHelpSection, ...]:
        """Help for the open form: the focused field, then the dialog and its
        keys. Empty when no form is open or it has no help.
        """
        state = self._form_state
        if state is None or self._request is None:
            return ()
        spec = state.spec
        fields = state.visible_fields()
        if not spec.help and not any(
            field.help or field.option_help for field in fields
        ):
            return ()
        row = state.field_index
        sections: list[ModalHelpSection] = []
        if row is not None and 0 <= row < len(fields):
            field = fields[row]
            if field.help or field.option_help:
                sections.append(
                    ModalHelpSection(
                        _help_title(field.label),
                        field.help,
                        tuple(zip(field.options, field.option_help)),
                    )
                )
        confirm = spec.confirm_label.lower()
        keys: list[tuple[str, str]] = [
            ("Up/Down", "move between settings"),
            ("Left/Right", "change the setting"),
        ]
        if any(field.large_step > 1 for field in fields):
            keys.append(("PgUp/PgDn", "large step"))
        if any(
            not field.stepper and choice_kind(len(field.options)) is ChoiceKind.COMBO
            for field in fields
        ):
            keys.append(("Space", "open the setting's list"))
        keys.append(
            ("Enter", "press the focused button" if spec.destructive else confirm)
        )
        keys.append(("Esc", "cancel"))
        sections.append(
            ModalHelpSection(_help_title(spec.title.rstrip("?")), spec.help, tuple(keys))
        )
        return tuple(sections)

    def focus_form_row(self, row: int) -> None:
        state = self._form_state
        if state is not None and 0 <= row < len(state.visible_fields()):
            state.field_index = row

    def _after_form_change(self, state: FormState, field_id: str) -> None:
        on_change = state.spec.on_change
        if on_change is not None:
            on_change(field_id, state.values)
        state.refresh_info()
        visible = len(state.visible_fields())
        if state.field_index is not None and state.field_index >= visible:
            state.field_index = visible - 1 if visible else None

    def _move_form_focus(self, state: FormState, delta: int) -> None:
        """Walk the fields, then the button row as one stop, and wrap."""
        count = len(state.visible_fields())
        slots = count + 1
        position = count if state.field_index is None else state.field_index
        position = (position + delta) % slots
        state.field_index = None if position == count else position

    def _handle_form_keydown(self, event: pygame.event.Event) -> bool:
        state = self._form_state
        assert state is not None
        key = event.key
        self.enter_keyboard_modality()
        # Any key stops a held step; a step key re-arms it below.
        self._form_key_repeat.disarm()
        choice = self._form_choice
        if choice is not None:
            outcome = handle_choice_list_key(choice, key)
            if outcome in (ChoiceListKey.PICKED, ChoiceListKey.CLOSED):
                self._form_choice = None
            return True
        opens_list = key == pygame.K_SPACE or (
            key == pygame.K_DOWN and event.mod & pygame.KMOD_ALT
        )
        if opens_list and state.field_index is not None:
            self.open_form_choice(state.field_index)
            return True
        if key == pygame.K_ESCAPE:
            self.cancel()
        elif key == pygame.K_TAB:
            self._move_form_focus(state, -1 if event.mod & pygame.KMOD_SHIFT else 1)
        elif key in (pygame.K_UP, pygame.K_DOWN):
            self._move_form_focus(state, -1 if key == pygame.K_UP else 1)
        elif key in (pygame.K_LEFT, pygame.K_RIGHT) and state.field_index is None:
            delta = -1 if key == pygame.K_LEFT else 1
            self._focus_index = (self._focus_index + delta) % self._option_count()
        elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            if self._step_focused_field(key):
                self._form_key_repeat.on_keydown(
                    key,
                    event.mod,
                    on_repeat=lambda held, _mod: self._step_focused_field(held),
                )
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._activate_form(state)
        return True

    def _step_focused_field(self, key: int) -> bool:
        """Step the focused field for an arrow or page key. False with no field."""
        state = self._form_state
        if state is None or state.field_index is None:
            return False
        if key in (pygame.K_LEFT, pygame.K_RIGHT):
            delta = -1 if key == pygame.K_LEFT else 1
        else:
            field = state.visible_fields()[state.field_index]
            delta = field.large_step if key == pygame.K_PAGEUP else -field.large_step
        self.step_form_value(state.field_index, delta)
        return True

    def _activate_form(self, state: FormState) -> None:
        """Enter runs the focused button.

        On a field it confirms. A destructive form moves to its buttons first,
        so Enter on a field can never delete anything.
        """
        if state.field_index is None:
            self.activate_option(self._focus_index)
        elif state.spec.destructive:
            state.field_index = None
        else:
            self.activate_option(0)

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
                    ModalOption("Save", on_save, ButtonRole.PRIMARY),
                    ModalOption("Don't save", on_discard),
                    ModalOption("Cancel", on_cancel_action),
                ],
                on_dismiss=on_cancel,
            )
        )

    def hover_option(self, index: int) -> None:
        """Focus option ``index``, clamped into the option list."""
        if self._input_modality is InputModality.KEYBOARD:
            return
        self._focus_option(index)

    def _focus_option(self, index: int) -> None:
        count = self._option_count()
        if count <= 0:
            return
        self._focus_index = max(0, min(index, count - 1))

    def activate_option(self, index: int) -> None:
        """Activate option ``index``. Same path as Enter on that option."""
        if self._option_count() <= 0:
            return
        self._focus_option(index)
        self._activate_focused()

    def cancel(self) -> None:
        """Same as Esc. A PROGRESS modal without a Cancel button ignores it."""
        request = self._request
        if request is None:
            return
        if request.kind == ModalKind.PROGRESS and not request.options:
            return
        if request.kind == ModalKind.TEXT:
            state = self._text_state
            if state is None:
                return
            if state.editing:
                state.draft = state.initial
                state.caret_index = len(state.initial)
                state.error = None
                self._leave_text_edit(state)
                return
            self._dismiss_text(invoke_cancel=True)
            return
        self._dismiss()

    def focus_text_field(self, caret_index: int) -> None:
        """TEXT only. Enter edit mode and place the caret. Does not clear an error."""
        state = self._text_state_or_none()
        if state is None:
            return
        self._begin_field_edit(state, caret_index)

    def activate_text_button(self, index: int) -> None:
        """TEXT only. ``0`` confirms (with validation); ``1`` cancels.

        A click while the field is editing does both in that one call:
        confirm commits the draft, cancel discards it.
        """
        state = self._text_state_or_none()
        if state is None:
            return
        if index == 0:
            self._confirm_text(state)
        elif index == 1:
            self._dismiss_text(invoke_cancel=True)

    def hover_text_button(self, index: int) -> None:
        """TEXT only. Leave edit mode and focus button ``index`` (clamped to 0 or 1)."""
        if self._input_modality is InputModality.KEYBOARD:
            return
        state = self._text_state_or_none()
        if state is None:
            return
        if state.editing:
            self.stop_text_input()
            state.editing = False
        state.focus_region = TextFocusRegion.BUTTONS
        state.button_index = max(0, min(index, 1))

    def hover_text_field(self) -> None:
        """TEXT only. Focus the field without entering edit mode.

        Already editing stays editing.
        """
        if self._input_modality is InputModality.KEYBOARD:
            return
        state = self._text_state_or_none()
        if state is None or state.editing:
            return
        state.focus_region = TextFocusRegion.FIELD

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Return True when the event is consumed (including while blocking)."""
        if not self.active or event.type != pygame.KEYDOWN:
            return False

        request = self._request
        assert request is not None
        if request.kind == ModalKind.PROGRESS and not request.options:
            return True
        if request.kind == ModalKind.TEXT:
            return self._handle_text_keydown(event)
        if request.kind == ModalKind.FORM:
            return self._handle_form_keydown(event)

        if event.key == pygame.K_ESCAPE:
            self.cancel()
            return True

        option_count = len(request.options)
        if option_count == 0:
            return True
        if event.key in (pygame.K_UP, pygame.K_LEFT):
            self.enter_keyboard_modality()
            self._focus_index = (self._focus_index - 1) % option_count
            return True
        if event.key in (pygame.K_DOWN, pygame.K_RIGHT):
            self.enter_keyboard_modality()
            self._focus_index = (self._focus_index + 1) % option_count
            return True

        if event.key == pygame.K_RETURN:
            self.activate_option(self._focus_index)
            return True

        return True

    def handle_keyup(self, event: pygame.event.Event) -> bool:
        """Return True when a TEXT or FORM modal consumed the event."""
        if event.type != pygame.KEYUP or self._request is None:
            return False
        if self._request.kind == ModalKind.FORM:
            self._form_key_repeat.on_keyup(event.key)
            return True
        if self._request.kind != ModalKind.TEXT:
            return False
        self._text_key_repeat.on_keyup(event.key)
        return True

    def tick(self, dt_sec: float) -> None:
        self._text_key_repeat.tick(dt_sec)
        self._form_key_repeat.tick(dt_sec)
        hold = self._form_hold
        if hold is not None:
            for _ in range(hold.clock.tick(dt_sec)):
                self.step_form_value(hold.row, hold.delta)
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
        insert_text_at_caret(state, text)
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
            self.cancel()
            return True
        if event.key == pygame.K_RETURN:
            if mod_shift(event.mod):
                if not state.single_line:
                    insert_text_at_caret(state, "\n")
                return True
            if self._show_text_validation_error(state):
                return True
            self._leave_text_edit(
                state, focus_region=TextFocusRegion.BUTTONS
            )
            return True
        if event.key in TEXT_EDIT_REPEAT_KEYS:
            apply_text_edit_key(state, event.key, self._text_field_wrap)
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
        apply_text_edit_key(state, key, self._text_field_wrap)

    def _handle_text_navigate_keydown(
        self,
        event: pygame.event.Event,
        state: TextModalState,
    ) -> bool:
        if event.key == pygame.K_ESCAPE:
            self.cancel()
            return True
        if event.key in (pygame.K_UP, pygame.K_DOWN):
            self.enter_keyboard_modality()
            if state.focus_region == TextFocusRegion.FIELD:
                self.stop_text_input()
                state.editing = False
                state.focus_region = TextFocusRegion.BUTTONS
                state.button_index = 0
            else:
                state.focus_region = TextFocusRegion.FIELD
            return True
        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.enter_keyboard_modality()
            if state.focus_region == TextFocusRegion.BUTTONS:
                delta = -1 if event.key == pygame.K_LEFT else 1
                state.button_index = (state.button_index + delta) % 2
            return True
        if event.key == pygame.K_RETURN:
            if state.focus_region == TextFocusRegion.FIELD:
                self.focus_text_field(state.caret_index)
                return True
            self.activate_text_button(state.button_index)
            return True
        return True

    def _confirm_text(self, state: TextModalState) -> None:
        if self._show_text_validation_error(state):
            return
        on_confirm = state.on_confirm
        draft = state.draft
        self._dismiss_text(invoke_cancel=False)
        on_confirm(draft)

    def _show_text_validation_error(self, state: TextModalState) -> bool:
        if state.validate is None:
            return False
        error = state.validate(state.draft)
        if error is None:
            return False
        state.error = error
        self._begin_field_edit(state)
        return True

    def _option_count(self) -> int:
        request = self._request
        if request is None or request.kind == ModalKind.TEXT:
            return 0
        return len(request.options)

    def _text_state_or_none(self) -> TextModalState | None:
        if self._request is None or self._request.kind != ModalKind.TEXT:
            return None
        return self._text_state

    def _begin_field_edit(
        self, state: TextModalState, caret_index: int | None = None
    ) -> None:
        state.editing = True
        state.focus_region = TextFocusRegion.FIELD
        if caret_index is not None:
            state.caret_index = max(0, min(caret_index, len(state.draft)))
        reset_caret_blink(state)
        self.start_text_input()

    def _leave_text_edit(
        self,
        state: TextModalState,
        *,
        focus_region: TextFocusRegion = TextFocusRegion.FIELD,
    ) -> None:
        self.stop_text_input()
        state.editing = False
        state.focus_region = focus_region
        if focus_region == TextFocusRegion.BUTTONS:
            state.button_index = 0

    def start_text_input(self) -> None:
        if self._text_input_started:
            return
        self._text_input_started = True
        if self._on_start_text_input is not None:
            self._on_start_text_input()

    def stop_text_input(self) -> None:
        self._text_key_repeat.disarm()
        if not self._text_input_started:
            return
        self._text_input_started = False
        if self._on_stop_text_input is not None:
            self._on_stop_text_input()

    def _dismiss_text(self, *, invoke_cancel: bool) -> None:
        self.stop_text_input()
        state = self._text_state
        self._text_state = None
        self._request = None
        self._focus_index = 0
        if invoke_cancel and state is not None and state.on_cancel is not None:
            state.on_cancel()

    def _dismiss(self) -> None:
        self.stop_text_input()
        request = self._request
        self._request = None
        self._text_state = None
        self._form_state = None
        self._form_choice = None
        self._stop_form_repeat()
        self._focus_index = 0
        if request is not None and request.on_dismiss is not None:
            request.on_dismiss()

    def _activate_focused(self) -> None:
        request = self._request
        if request is None:
            return
        self.stop_text_input()
        focus_index = self._focus_index
        self._request = None
        self._text_state = None
        self._form_state = None
        self._stop_form_repeat()
        self._focus_index = 0
        request.options[focus_index].action()
