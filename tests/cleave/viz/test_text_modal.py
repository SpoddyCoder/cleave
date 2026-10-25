"""Unit tests for the text-input modal host."""

from __future__ import annotations

from collections.abc import Callable

import pygame

from cleave.viz.key_repeat import INITIAL_DELAY_SEC
from cleave.viz.modal import (
    ModalHost,
    ModalKind,
    ModalLabeledLine,
    ModalOption,
    TextFocusRegion,
    capital_case_modal_option,
)


def _keydown(key: int, mod: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod)


def _keyup(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYUP, key=key)


def _open_text(
    modal: ModalHost,
    *,
    cta: str = "Change text...",
    initial: str = "hello",
    single_line: bool = False,
    validate: Callable[[str], str | None] | None = None,
) -> tuple[list[str], list[str]]:
    confirmed: list[str] = []
    cancelled: list[str] = []
    modal.prompt_text(
        cta,
        initial,
        on_confirm=confirmed.append,
        on_cancel=lambda: cancelled.append("cancel"),
        single_line=single_line,
        validate=validate,
    )
    return confirmed, cancelled


def _confirm_text(modal: ModalHost) -> None:
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    modal.handle_keydown(_keydown(pygame.K_RETURN))


def test_prompt_text_open_shows_initial() -> None:
    modal = ModalHost()
    _open_text(modal, cta="Change text...", initial="hello", single_line=True)
    view = modal.view_state()
    assert view is not None
    assert view.draft == "hello"
    assert view.editing is True
    assert view.caret_index == len("hello")
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.cta == "Change text..."
    assert view.single_line is True
    assert view.message is None
    assert view.options == ()
    assert view.error is None


def test_handle_text_input_inserts_at_caret() -> None:
    modal = ModalHost()
    _open_text(modal, initial="ab")
    assert modal.handle_text_input("c") is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "abc"
    assert view.caret_index == 3

    modal.handle_keydown(_keydown(pygame.K_LEFT))
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    assert modal.handle_text_input("X") is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "aXbc"
    assert view.caret_index == 2


def test_handle_text_input_empty_string_consumes_without_change() -> None:
    modal = ModalHost()
    _open_text(modal, initial="ab")
    assert modal.handle_text_input("") is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "ab"
    assert view.caret_index == 2


def test_shift_enter_inserts_newline_when_multiline() -> None:
    modal = ModalHost()
    _open_text(modal, initial="ab", single_line=False)
    assert modal.handle_keydown(_keydown(pygame.K_RETURN, pygame.KMOD_SHIFT)) is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "ab\n"
    assert view.caret_index == 3
    assert view.editing is True


def test_shift_enter_noops_when_single_line() -> None:
    modal = ModalHost()
    _open_text(modal, initial="ab", single_line=True)
    assert modal.handle_keydown(_keydown(pygame.K_RETURN, pygame.KMOD_SHIFT)) is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "ab"
    assert view.caret_index == 2
    assert view.editing is True


def test_handle_text_input_rejects_newline_when_single_line() -> None:
    modal = ModalHost()
    _open_text(modal, initial="ab", single_line=True)
    assert modal.handle_text_input("\n") is True
    assert modal.handle_text_input("x\ny") is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "ab"
    assert "\n" not in view.draft
    assert view.caret_index == 2


def test_escape_in_edit_discards_draft() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(modal, initial="hello")
    modal.handle_text_input("!")
    assert modal.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "hello"
    assert view.caret_index == len("hello")
    assert view.editing is False
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.error is None
    assert modal.active
    assert confirmed == []
    assert cancelled == []


def test_enter_in_edit_jumps_to_confirm() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(modal, initial="hello")
    modal.handle_text_input("!")
    assert modal.handle_keydown(_keydown(pygame.K_RETURN)) is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "hello!"
    assert view.editing is False
    assert view.focus_region == TextFocusRegion.BUTTONS
    assert view.button_index == 0
    assert modal.active
    assert confirmed == []
    assert cancelled == []


def test_enter_in_edit_highlights_confirm_not_last_button() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello")
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    view = modal.view_state()
    assert view is not None
    assert view.button_index == 1
    modal.handle_keydown(_keydown(pygame.K_UP))
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    view = modal.view_state()
    assert view is not None
    assert view.editing is False
    assert view.focus_region == TextFocusRegion.BUTTONS
    assert view.button_index == 0


def test_escape_in_navigate_cancels() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(modal, initial="hello")
    modal.handle_text_input("!")
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    assert modal.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    assert not modal.active
    assert cancelled == ["cancel"]
    assert confirmed == []


def test_cancel_button_calls_on_cancel() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(modal, initial="hello")
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    modal.handle_keydown(_keydown(pygame.K_DOWN))
    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    view = modal.view_state()
    assert view is not None
    assert view.focus_region == TextFocusRegion.BUTTONS
    assert view.button_index == 1
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    assert not modal.active
    assert cancelled == ["cancel"]
    assert confirmed == []


def test_confirm_failing_validator_stays_in_field() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(
        modal, initial="bad", validate=lambda _draft: "invalid hex colour"
    )
    assert modal.handle_keydown(_keydown(pygame.K_RETURN)) is True
    assert modal.active
    view = modal.view_state()
    assert view is not None
    assert view.error == "invalid hex colour"
    assert view.draft == "bad"
    assert view.editing is True
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.caret_visible is True
    assert confirmed == []
    assert cancelled == []
    assert modal.handle_text_input("x") is True
    view = modal.view_state()
    assert view is not None
    assert view.error is None
    assert view.draft == "badx"
    assert view.editing is True


def test_enter_in_edit_with_valid_draft_jumps_to_confirm() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(
        modal, initial="ok", validate=lambda _draft: None
    )
    assert modal.handle_keydown(_keydown(pygame.K_RETURN)) is True
    view = modal.view_state()
    assert view is not None
    assert view.error is None
    assert view.editing is False
    assert view.focus_region == TextFocusRegion.BUTTONS
    assert view.button_index == 0
    assert modal.active
    assert confirmed == []
    assert cancelled == []


def test_confirm_button_failing_validator_returns_to_field() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(
        modal, initial="bad", validate=lambda _draft: "invalid hex colour"
    )
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    modal.handle_keydown(_keydown(pygame.K_DOWN))
    view = modal.view_state()
    assert view is not None
    assert view.editing is False
    assert view.focus_region == TextFocusRegion.BUTTONS
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    view = modal.view_state()
    assert view is not None
    assert modal.active
    assert view.error == "invalid hex colour"
    assert view.editing is True
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.caret_visible is True
    assert confirmed == []
    assert cancelled == []


def test_draft_edit_clears_error() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(
        modal, initial="bad", validate=lambda _draft: "nope"
    )
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    view = modal.view_state()
    assert view is not None
    assert view.error == "nope"
    assert view.editing is True

    assert modal.handle_text_input("x") is True
    view = modal.view_state()
    assert view is not None
    assert view.error is None
    assert view.draft == "badx"

    modal.handle_keydown(_keydown(pygame.K_RETURN))
    view = modal.view_state()
    assert view is not None
    assert view.error == "nope"
    assert view.editing is True
    modal.handle_keydown(_keydown(pygame.K_BACKSPACE))
    view = modal.view_state()
    assert view is not None
    assert view.error is None
    assert view.draft == "bad"
    assert confirmed == []
    assert cancelled == []
    assert modal.active


def test_confirm_passing_validator_dismisses() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(
        modal, initial="ok", validate=lambda _draft: None
    )
    _confirm_text(modal)
    assert not modal.active
    assert confirmed == ["ok"]
    assert cancelled == []


def test_confirm_without_validator_still_commits() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(modal, initial="hello")
    modal.handle_text_input("!")
    _confirm_text(modal)
    assert not modal.active
    assert confirmed == ["hello!"]
    assert cancelled == []


def test_confirm_button_commits_draft() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(modal, initial="hello")
    modal.handle_text_input("!")
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    view = modal.view_state()
    assert view is not None
    assert view.focus_region == TextFocusRegion.BUTTONS
    assert view.button_index == 0
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    assert not modal.active
    assert confirmed == ["hello!"]
    assert cancelled == []


def test_left_right_on_field_are_noop_in_navigate() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello")
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    view = modal.view_state()
    assert view is not None
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.button_index == 0
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    view = modal.view_state()
    assert view is not None
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.button_index == 0
    assert modal.active


def test_left_right_on_buttons_cycle() -> None:
    modal = ModalHost()
    _open_text(modal)
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    view = modal.view_state()
    assert view is not None
    assert view.button_index == 0
    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    assert modal.view_state().button_index == 1
    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    assert modal.view_state().button_index == 0
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    assert modal.view_state().button_index == 1


def test_up_down_toggle_focus_region_resets_button_index() -> None:
    modal = ModalHost()
    _open_text(modal)
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    modal.handle_keydown(_keydown(pygame.K_DOWN))
    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    view = modal.view_state()
    assert view is not None
    assert view.focus_region == TextFocusRegion.BUTTONS
    assert view.button_index == 1
    modal.handle_keydown(_keydown(pygame.K_UP))
    view = modal.view_state()
    assert view is not None
    assert view.focus_region == TextFocusRegion.FIELD
    modal.handle_keydown(_keydown(pygame.K_DOWN))
    view = modal.view_state()
    assert view is not None
    assert view.focus_region == TextFocusRegion.BUTTONS
    assert view.button_index == 0


def test_up_in_edit_moves_to_previous_line_same_column() -> None:
    modal = ModalHost()
    _open_text(modal, initial="ab\ncd", single_line=False)
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert view.caret_index == 5

    modal.handle_keydown(_keydown(pygame.K_UP))
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.caret_index == 2


def test_down_in_edit_moves_to_next_line_same_column() -> None:
    modal = ModalHost()
    _open_text(modal, initial="ab\ncd", single_line=False)
    for _ in range(4):
        modal.handle_keydown(_keydown(pygame.K_LEFT))
    view = modal.view_state()
    assert view is not None
    assert view.caret_index == 1

    modal.handle_keydown(_keydown(pygame.K_DOWN))
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.caret_index == 4


def test_up_on_first_line_stays_in_edit() -> None:
    modal = ModalHost()
    _open_text(modal, initial="ab\ncd", single_line=False)
    for _ in range(4):
        modal.handle_keydown(_keydown(pygame.K_LEFT))
    view = modal.view_state()
    assert view is not None
    assert view.caret_index == 1
    assert view.editing is True

    modal.handle_keydown(_keydown(pygame.K_UP))
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.caret_index == 1


def test_down_on_last_line_stays_in_edit() -> None:
    modal = ModalHost()
    _open_text(modal, initial="ab\ncd", single_line=False)
    view = modal.view_state()
    assert view is not None
    assert view.caret_index == 5
    assert view.editing is True

    modal.handle_keydown(_keydown(pygame.K_DOWN))
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.caret_index == 5


def test_up_down_clamp_column_to_shorter_line() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello\nhi", single_line=False)
    modal.handle_keydown(_keydown(pygame.K_UP))
    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    view = modal.view_state()
    assert view is not None
    assert view.caret_index == 4

    modal.handle_keydown(_keydown(pygame.K_DOWN))
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert view.caret_index == 8


def test_single_line_up_down_noop_in_edit() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello", single_line=True)
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    view = modal.view_state()
    assert view is not None
    assert view.caret_index == 4
    assert view.editing is True

    modal.handle_keydown(_keydown(pygame.K_UP))
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.caret_index == 4
    assert view.draft == "hello"

    modal.handle_keydown(_keydown(pygame.K_DOWN))
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.caret_index == 4
    assert "\n" not in view.draft


def _wrap_chunks(width: int):
    def wrap(draft: str) -> list[str]:
        lines: list[str] = []
        for para in draft.split("\n"):
            if not para:
                lines.append("")
                continue
            for index in range(0, len(para), width):
                lines.append(para[index : index + width])
        return lines or [""]

    return wrap


def test_up_down_use_bound_visual_wrap_lines() -> None:
    modal = ModalHost()
    modal.set_text_field_wrap(_wrap_chunks(2))
    _open_text(modal, initial="abcd", single_line=False)
    view = modal.view_state()
    assert view is not None
    assert view.caret_index == 4

    modal.handle_keydown(_keydown(pygame.K_UP))
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.caret_index == 2

    modal.handle_keydown(_keydown(pygame.K_LEFT))
    view = modal.view_state()
    assert view is not None
    assert view.caret_index == 1
    modal.handle_keydown(_keydown(pygame.K_DOWN))
    view = modal.view_state()
    assert view is not None
    assert view.caret_index == 3
    assert view.draft == "abcd"


def test_y_and_n_noop_in_edit_and_navigate() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(modal, initial="hello")
    modal.handle_keydown(_keydown(pygame.K_y))
    modal.handle_keydown(_keydown(pygame.K_n))
    view = modal.view_state()
    assert view is not None
    assert modal.active
    assert view.editing is True
    assert view.draft == "hello"
    assert view.focus_region == TextFocusRegion.FIELD

    modal.handle_keydown(_keydown(pygame.K_RETURN))
    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    modal.handle_keydown(_keydown(pygame.K_y))
    modal.handle_keydown(_keydown(pygame.K_n))
    view = modal.view_state()
    assert view is not None
    assert modal.active
    assert view.editing is False
    assert view.focus_region == TextFocusRegion.BUTTONS
    assert view.button_index == 1
    assert confirmed == []
    assert cancelled == []


def test_backspace_at_caret_zero_is_noop() -> None:
    modal = ModalHost()
    _open_text(modal, initial="ab")
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    view = modal.view_state()
    assert view is not None
    assert view.caret_index == 0
    assert modal.handle_keydown(_keydown(pygame.K_BACKSPACE)) is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "ab"
    assert view.caret_index == 0


def test_confirm_allows_empty_string() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(modal, initial="")
    _confirm_text(modal)
    assert confirmed == [""]
    assert cancelled == []
    assert not modal.active


def test_handle_text_input_while_not_editing_returns_false() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello")
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    view = modal.view_state()
    assert view is not None
    assert view.editing is False
    assert modal.handle_text_input("x") is False
    view = modal.view_state()
    assert view is not None
    assert view.draft == "hello"


def test_handle_text_input_without_text_modal_returns_false() -> None:
    modal = ModalHost()
    assert modal.handle_text_input("x") is False
    modal.prompt_yes_no("Overwrite?", on_confirm=lambda: None)
    assert modal.handle_text_input("x") is False
    assert modal.active


def _host_with_text_callbacks() -> tuple[ModalHost, list[str], list[str]]:
    starts: list[str] = []
    stops: list[str] = []
    modal = ModalHost(
        on_start_text_input=lambda: starts.append("start"),
        on_stop_text_input=lambda: stops.append("stop"),
    )
    return modal, starts, stops


def test_prompt_text_fires_start_once() -> None:
    modal, starts, stops = _host_with_text_callbacks()
    _open_text(modal)
    assert starts == ["start"]
    assert stops == []


def test_escape_from_edit_stops_and_reenter_starts() -> None:
    modal, starts, stops = _host_with_text_callbacks()
    _open_text(modal)
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    view = modal.view_state()
    assert view is not None
    assert view.editing is False
    assert starts == ["start"]
    assert stops == ["stop"]

    modal.handle_keydown(_keydown(pygame.K_RETURN))
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert starts == ["start", "start"]
    assert stops == ["stop"]


def test_dismiss_from_navigate_does_not_double_stop() -> None:
    modal, starts, stops = _host_with_text_callbacks()
    _open_text(modal)
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    assert not modal.active
    assert starts == ["start"]
    assert stops == ["stop"]


def test_cancel_and_confirm_do_not_double_stop() -> None:
    modal, starts, stops = _host_with_text_callbacks()
    _open_text(modal)
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    assert not modal.active
    assert starts == ["start"]
    assert stops == ["stop"]

    modal, starts, stops = _host_with_text_callbacks()
    _open_text(modal)
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    assert not modal.active
    assert starts == ["start"]
    assert stops == ["stop"]


def test_dismiss_while_editing_fires_stop() -> None:
    modal, starts, stops = _host_with_text_callbacks()
    _open_text(modal)
    modal.dismiss()
    assert not modal.active
    assert starts == ["start"]
    assert stops == ["stop"]


def test_prompt_replacing_text_modal_fires_stop() -> None:
    modal, starts, stops = _host_with_text_callbacks()
    _open_text(modal)
    modal.prompt_yes_no("Overwrite?", on_confirm=lambda: None)
    assert starts == ["start"]
    assert stops == ["stop"]


def test_shift_enter_does_not_fire_stop() -> None:
    modal, starts, stops = _host_with_text_callbacks()
    _open_text(modal, single_line=False)
    modal.handle_keydown(_keydown(pygame.K_RETURN, pygame.KMOD_SHIFT))
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert starts == ["start"]
    assert stops == []


def test_yes_no_prompt_does_not_fire_start_or_stop() -> None:
    modal, starts, stops = _host_with_text_callbacks()
    modal.prompt_yes_no("Overwrite?", on_confirm=lambda: None)
    assert starts == []
    assert stops == []
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    assert starts == []
    assert stops == []


def test_textinput_event_text_applied_via_handle_text_input() -> None:
    modal = ModalHost()
    _open_text(modal, initial="ab")
    event = pygame.event.Event(pygame.TEXTINPUT, text="c")
    assert modal.handle_text_input(event.text) is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "abc"
    assert view.caret_index == 3


def test_backspace_keydown_while_editing_arms_and_keyup_disarms() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello")
    assert modal.handle_keydown(_keydown(pygame.K_BACKSPACE)) is True
    assert modal.text_key_repeat_armed is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "hell"
    assert modal.handle_keyup(_keyup(pygame.K_BACKSPACE)) is True
    assert modal.text_key_repeat_armed is False


def test_arrow_keydown_while_editing_arms_and_keyup_disarms() -> None:
    for key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
        modal = ModalHost()
        _open_text(modal, initial="hello")
        assert modal.handle_keydown(_keydown(key)) is True
        assert modal.text_key_repeat_armed is True
        assert modal.handle_keyup(_keyup(key)) is True
        assert modal.text_key_repeat_armed is False


def test_leave_edit_disarms_repeat_without_keyup() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello")
    modal.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert modal.text_key_repeat_armed is True
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    view = modal.view_state()
    assert view is not None
    assert view.editing is False
    assert modal.text_key_repeat_armed is False


def test_dismiss_while_armed_disarms_repeat() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello")
    modal.handle_keydown(_keydown(pygame.K_BACKSPACE))
    assert modal.text_key_repeat_armed is True
    modal.dismiss()
    assert not modal.active
    assert modal.text_key_repeat_armed is False


def test_prompt_replacing_text_modal_disarms_repeat() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello")
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    assert modal.text_key_repeat_armed is True
    modal.prompt_yes_no("Overwrite?", on_confirm=lambda: None)
    assert modal.text_key_repeat_armed is False


def test_yes_no_arrow_does_not_arm_text_repeat() -> None:
    modal = ModalHost()
    modal.prompt_yes_no("Overwrite?", on_confirm=lambda: None)
    assert modal.handle_keydown(_keydown(pygame.K_LEFT)) is True
    assert modal.handle_keydown(_keydown(pygame.K_RIGHT)) is True
    assert modal.handle_keydown(_keydown(pygame.K_UP)) is True
    assert modal.handle_keydown(_keydown(pygame.K_DOWN)) is True
    assert modal.text_key_repeat_armed is False
    assert modal.handle_keyup(_keyup(pygame.K_LEFT)) is False


def test_navigate_does_not_arm_text_repeat() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello")
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    view = modal.view_state()
    assert view is not None
    assert view.editing is False
    modal.handle_keydown(_keydown(pygame.K_BACKSPACE))
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    modal.handle_keydown(_keydown(pygame.K_DOWN))
    assert modal.text_key_repeat_armed is False


def test_tick_fires_backspace() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello")
    modal.handle_keydown(_keydown(pygame.K_BACKSPACE))
    view = modal.view_state()
    assert view is not None
    assert view.draft == "hell"
    assert view.caret_index == 4
    modal.tick(INITIAL_DELAY_SEC)
    view = modal.view_state()
    assert view is not None
    assert view.draft == "hel"
    assert view.caret_index == 3
    assert modal.text_key_repeat_armed is True


def test_space_inserts_while_editing() -> None:
    modal = ModalHost()
    _open_text(modal, initial="ab")
    event = pygame.event.Event(pygame.TEXTINPUT, text=" ")
    assert modal.handle_text_input(event.text) is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "ab "
    assert view.caret_index == 3


def test_caret_visible_on_open_and_blinks() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello")
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert view.caret_visible is True

    modal.tick(0.49)
    view = modal.view_state()
    assert view is not None
    assert view.caret_visible is True

    modal.tick(0.02)
    view = modal.view_state()
    assert view is not None
    assert view.caret_visible is False

    modal.tick(0.49)
    view = modal.view_state()
    assert view is not None
    assert view.caret_visible is True


def test_edit_actions_reset_caret_blink() -> None:
    modal = ModalHost()
    _open_text(modal, initial="ab", single_line=False)
    modal.tick(0.6)
    view = modal.view_state()
    assert view is not None
    assert view.caret_visible is False

    assert modal.handle_text_input("c") is True
    view = modal.view_state()
    assert view is not None
    assert view.caret_visible is True
    assert view.draft == "abc"

    modal.tick(0.6)
    assert modal.view_state().caret_visible is False
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    modal.handle_keyup(_keyup(pygame.K_LEFT))
    assert modal.view_state().caret_visible is True

    modal.tick(0.6)
    assert modal.view_state().caret_visible is False
    modal.handle_keydown(_keydown(pygame.K_BACKSPACE))
    modal.handle_keyup(_keyup(pygame.K_BACKSPACE))
    assert modal.view_state().caret_visible is True

    modal.tick(0.6)
    assert modal.view_state().caret_visible is False
    modal.handle_keydown(_keydown(pygame.K_RETURN, pygame.KMOD_SHIFT))
    view = modal.view_state()
    assert view is not None
    assert view.caret_visible is True
    assert "\n" in view.draft


def test_caret_hidden_when_not_editing() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello")
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    view = modal.view_state()
    assert view is not None
    assert view.editing is False
    assert view.caret_visible is False
    modal.tick(0.1)
    view = modal.view_state()
    assert view is not None
    assert view.caret_visible is False


def test_reenter_edit_resets_caret_blink() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello")
    modal.tick(0.6)
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert view.caret_visible is True


def _choice(modal: ModalHost, picked: list[int]) -> None:
    modal.prompt_choice(
        "Pick",
        [
            ModalOption("A", lambda: picked.append(0)),
            ModalOption("B", lambda: picked.append(1)),
            ModalOption("C", lambda: picked.append(2)),
        ],
    )


def test_hover_option_matches_arrow_focus() -> None:
    keyed = ModalHost()
    pointed = ModalHost()
    _choice(keyed, [])
    _choice(pointed, [])
    keyed.handle_keydown(_keydown(pygame.K_DOWN))
    keyed.handle_keydown(_keydown(pygame.K_DOWN))
    pointed.hover_option(2)
    assert keyed.view_state() == pointed.view_state()
    assert pointed.view_state() is not None
    assert pointed.view_state().focus_index == 2

    yes_key = ModalHost()
    yes_pointer = ModalHost()
    yes_key.prompt_yes_no("Overwrite?", on_confirm=lambda: None)
    yes_pointer.prompt_yes_no("Overwrite?", on_confirm=lambda: None)
    yes_key.handle_keydown(_keydown(pygame.K_UP))
    yes_pointer.hover_option(1)
    assert yes_key.view_state() == yes_pointer.view_state()

    pointed.hover_option(-3)
    assert pointed.view_state() is not None
    assert pointed.view_state().focus_index == 0
    pointed.hover_option(99)
    assert pointed.view_state().focus_index == 2


def test_activate_option_matches_enter() -> None:
    keyed_picks: list[int] = []
    pointer_picks: list[int] = []
    keyed = ModalHost()
    pointed = ModalHost()
    _choice(keyed, keyed_picks)
    _choice(pointed, pointer_picks)
    keyed.handle_keydown(_keydown(pygame.K_DOWN))
    keyed.handle_keydown(_keydown(pygame.K_DOWN))
    keyed.handle_keydown(_keydown(pygame.K_RETURN))
    pointed.activate_option(2)
    assert not keyed.active
    assert not pointed.active
    assert keyed_picks == pointer_picks == [2]


def test_cancel_matches_escape_for_yes_no_and_text() -> None:
    key_dismissed: list[str] = []
    pointer_dismissed: list[str] = []
    keyed = ModalHost()
    pointed = ModalHost()
    keyed.prompt_yes_no(
        "Overwrite?",
        on_confirm=lambda: None,
        on_cancel=lambda: key_dismissed.append("dismiss"),
    )
    pointed.prompt_yes_no(
        "Overwrite?",
        on_confirm=lambda: None,
        on_cancel=lambda: pointer_dismissed.append("dismiss"),
    )
    assert keyed.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    pointed.cancel()
    assert key_dismissed == pointer_dismissed == ["dismiss"]
    assert not keyed.active
    assert not pointed.active

    edit_key = ModalHost()
    edit_pointer = ModalHost()
    _open_text(edit_key, initial="hello")
    _open_text(edit_pointer, initial="hello")
    edit_key.handle_text_input("!")
    edit_pointer.handle_text_input("!")
    edit_key.handle_keydown(_keydown(pygame.K_ESCAPE))
    edit_pointer.cancel()
    assert edit_key.view_state() == edit_pointer.view_state()
    view = edit_pointer.view_state()
    assert view is not None
    assert view.draft == "hello"
    assert view.editing is False
    assert view.error is None
    assert edit_pointer.active

    nav_key = ModalHost()
    nav_pointer = ModalHost()
    _key_confirmed, key_cancelled = _open_text(nav_key, initial="hello")
    _pointer_confirmed, pointer_cancelled = _open_text(nav_pointer, initial="hello")
    nav_key.handle_keydown(_keydown(pygame.K_ESCAPE))
    nav_pointer.handle_keydown(_keydown(pygame.K_ESCAPE))
    nav_key.handle_keydown(_keydown(pygame.K_ESCAPE))
    nav_pointer.cancel()
    assert not nav_key.active
    assert not nav_pointer.active
    assert key_cancelled == pointer_cancelled == ["cancel"]

    progress = ModalHost()
    progress.prompt_progress("Rendering...", fraction=0.4)
    before = progress.view_state()
    assert progress.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    progress.cancel()
    assert progress.active
    assert progress.view_state() == before
    assert progress.view_state() is not None
    assert progress.view_state().kind == ModalKind.PROGRESS


def test_focus_text_field_enters_editing_at_caret() -> None:
    def opened() -> tuple[ModalHost, list[str], list[str]]:
        modal, starts, stops = _host_with_text_callbacks()
        _open_text(modal, initial="hello")
        modal.handle_keydown(_keydown(pygame.K_ESCAPE))
        return modal, starts, stops

    keyed, key_starts, key_stops = opened()
    pointed, pointer_starts, pointer_stops = opened()
    keyed.handle_keydown(_keydown(pygame.K_RETURN))
    pointed.focus_text_field(len("hello"))
    assert keyed.view_state() == pointed.view_state()
    view = pointed.view_state()
    assert view is not None
    assert view.editing is True
    assert view.caret_index == len("hello")
    assert view.focus_region == TextFocusRegion.FIELD
    assert key_starts == pointer_starts == ["start", "start"]
    assert key_stops == pointer_stops == ["stop"]

    pointed.focus_text_field(2)
    view = pointed.view_state()
    assert view is not None
    assert view.editing is True
    assert view.caret_index == 2

    errored = ModalHost()
    _open_text(errored, initial="bad", validate=lambda _draft: "nope")
    errored.handle_keydown(_keydown(pygame.K_RETURN))
    errored.focus_text_field(1)
    view = errored.view_state()
    assert view is not None
    assert view.error == "nope"
    assert view.caret_index == 1
    assert view.editing is True


def test_activate_text_button_confirm_matches_enter() -> None:
    def failing(draft: str) -> str | None:
        if draft == "bad":
            return "invalid hex colour"
        return None

    keyed = ModalHost()
    pointed = ModalHost()
    key_confirmed, key_cancelled = _open_text(keyed, initial="bad", validate=failing)
    pointer_confirmed, pointer_cancelled = _open_text(
        pointed, initial="bad", validate=failing
    )
    for modal in (keyed, pointed):
        modal.handle_keydown(_keydown(pygame.K_ESCAPE))
        modal.handle_keydown(_keydown(pygame.K_DOWN))
    keyed.handle_keydown(_keydown(pygame.K_RETURN))
    pointed.activate_text_button(0)
    assert keyed.active and pointed.active
    assert keyed.view_state() == pointed.view_state()
    view = pointed.view_state()
    assert view is not None
    assert view.error == "invalid hex colour"
    assert view.editing is True
    assert view.focus_region == TextFocusRegion.FIELD
    assert key_confirmed == pointer_confirmed == []
    assert key_cancelled == pointer_cancelled == []

    keyed = ModalHost()
    pointed = ModalHost()
    key_confirmed, _key_cancelled = _open_text(
        keyed, initial="ok", validate=lambda _draft: None
    )
    pointer_confirmed, _pointer_cancelled = _open_text(
        pointed, initial="ok", validate=lambda _draft: None
    )
    for modal in (keyed, pointed):
        modal.handle_text_input("!")
        modal.handle_keydown(_keydown(pygame.K_RETURN))
    keyed.handle_keydown(_keydown(pygame.K_RETURN))
    pointed.activate_text_button(0)
    assert not keyed.active
    assert not pointed.active
    assert key_confirmed == pointer_confirmed == ["ok!"]


def test_hover_text_button_focuses_button_and_leaves_edit() -> None:
    modal, starts, stops = _host_with_text_callbacks()
    _open_text(modal, initial="hello")
    modal.handle_text_input("!")
    modal.hover_text_button(1)
    view = modal.view_state()
    assert view is not None
    assert view.draft == "hello!"
    assert view.editing is False
    assert view.focus_region == TextFocusRegion.BUTTONS
    assert view.button_index == 1
    assert starts == ["start"]
    assert stops == ["stop"]

    keyed = ModalHost()
    pointed = ModalHost()
    _open_text(keyed, initial="hello")
    _open_text(pointed, initial="hello")
    keyed.handle_keydown(_keydown(pygame.K_ESCAPE))
    pointed.handle_keydown(_keydown(pygame.K_ESCAPE))
    keyed.handle_keydown(_keydown(pygame.K_DOWN))
    keyed.handle_keydown(_keydown(pygame.K_RIGHT))
    pointed.hover_text_button(1)
    assert keyed.view_state() == pointed.view_state()

    pointed.hover_text_field()
    view = pointed.view_state()
    assert view is not None
    assert view.focus_region == TextFocusRegion.FIELD
    assert view.editing is False
    keyed.handle_keydown(_keydown(pygame.K_UP))
    assert keyed.view_state() == pointed.view_state()


def test_hover_text_field_while_editing_stays_editing() -> None:
    modal = ModalHost()
    _open_text(modal, initial="hello")
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    before = modal.view_state()
    modal.hover_text_field()
    assert modal.view_state() == before
    assert before is not None
    assert before.editing is True


def test_text_pointer_methods_noop_on_yes_no() -> None:
    modal = ModalHost()
    modal.prompt_yes_no("Overwrite?", on_confirm=lambda: None)
    before = modal.view_state()
    modal.focus_text_field(0)
    modal.activate_text_button(0)
    modal.hover_text_button(1)
    modal.hover_text_field()
    assert modal.active
    assert modal.view_state() == before


def test_capital_case_modal_option() -> None:
    assert capital_case_modal_option("YES") == "Yes"
    assert capital_case_modal_option("save as new") == "Save As New"
    assert capital_case_modal_option("DON'T SAVE") == "Don't Save"
    assert capital_case_modal_option("(root)") == "(Root)"
    assert capital_case_modal_option("keepers") == "Keepers"
    assert capital_case_modal_option("5.0s") == "5.0s"
    assert capital_case_modal_option("a-tier") == "A-tier"


def test_prompt_choice_renders_n_options() -> None:
    modal = ModalHost()
    modal.prompt_choice(
        "Favourite preset: demo.milk?",
        [
            ModalOption("(root)", lambda: None),
            ModalOption("keepers", lambda: None),
            ModalOption("wip", lambda: None),
            ModalOption("Cancel", lambda: None),
        ],
    )
    view = modal.view_state()
    assert view is not None
    assert view.kind == ModalKind.CHOICE
    assert view.options == ("(Root)", "Keepers", "Wip", "Cancel")


def test_prompt_choice_up_down_and_left_right_cycle_options() -> None:
    modal = ModalHost()
    modal.prompt_choice(
        "Blacklist preset: demo.milk?",
        [
            ModalOption("(root)", lambda: None),
            ModalOption("review", lambda: None),
            ModalOption("Cancel", lambda: None),
        ],
    )
    view = modal.view_state()
    assert view is not None
    assert view.focus_index == 0

    modal.handle_keydown(_keydown(pygame.K_DOWN))
    assert modal.view_state() is not None
    assert modal.view_state().focus_index == 1

    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    assert modal.view_state().focus_index == 2

    modal.handle_keydown(_keydown(pygame.K_DOWN))
    assert modal.view_state().focus_index == 0

    modal.handle_keydown(_keydown(pygame.K_UP))
    assert modal.view_state().focus_index == 2

    modal.handle_keydown(_keydown(pygame.K_LEFT))
    assert modal.view_state().focus_index == 1


def test_prompt_yes_no_passes_labeled_lines() -> None:
    modal = ModalHost()
    labeled = (
        ModalLabeledLine("character", "arc"),
        ModalLabeledLine("conductor", "on"),
    )
    modal.prompt_yes_no(
        "Apply timeline preset?",
        on_confirm=lambda: None,
        cancel_label="Cancel",
        labeled_lines=labeled,
    )
    view = modal.view_state()
    assert view is not None
    assert view.message == "Apply timeline preset?"
    assert view.labeled_lines == labeled
    assert view.options == ("Yes", "Cancel")


def test_prompt_progress_has_bar_and_ignores_keys() -> None:
    modal = ModalHost()
    labeled = (
        ModalLabeledLine("output", "renders/song.mp4"),
        ModalLabeledLine("quality", "high"),
    )
    modal.prompt_progress(
        "Rendering project...",
        labeled_lines=labeled,
        fraction=0.25,
    )
    view = modal.view_state()
    assert view is not None
    assert view.kind == ModalKind.PROGRESS
    assert view.message == "Rendering project..."
    assert view.options == ()
    assert view.progress_fraction == 0.25
    assert view.labeled_lines == labeled
    assert modal.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    assert modal.active is True
    assert modal.handle_keydown(_keydown(pygame.K_RETURN)) is True
    assert modal.active is True
    modal.update_progress(0.8)
    assert modal.view_state() is not None
    assert modal.view_state().progress_fraction == 0.8


def test_prompt_choice_passes_labeled_lines() -> None:
    modal = ModalHost()
    labeled = (ModalLabeledLine("output", "renders/song.mp4"),)
    modal.prompt_choice(
        "Render complete",
        [ModalOption("OK", lambda: None)],
        labeled_lines=labeled,
    )
    view = modal.view_state()
    assert view is not None
    assert view.message == "Render complete"
    assert view.labeled_lines == labeled
    assert view.options == ("Ok",)
