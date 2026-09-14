"""Unit tests for the text-input modal host."""

from __future__ import annotations

import pygame

from cleave.viz.modal import ModalHost, TextFocusRegion


def _keydown(key: int, mod: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod)


def _open_text(
    modal: ModalHost,
    *,
    cta: str = "Change text...",
    initial: str = "hello",
    single_line: bool = False,
) -> tuple[list[str], list[str]]:
    confirmed: list[str] = []
    cancelled: list[str] = []
    modal.prompt_text(
        cta,
        initial,
        on_confirm=confirmed.append,
        on_cancel=lambda: cancelled.append("cancel"),
        single_line=single_line,
    )
    return confirmed, cancelled


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


def test_escape_in_edit_keeps_draft() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(modal, initial="hello")
    modal.handle_text_input("!")
    assert modal.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "hello!"
    assert view.editing is False
    assert view.focus_region == TextFocusRegion.FIELD
    assert modal.active
    assert confirmed == []
    assert cancelled == []


def test_enter_in_edit_keeps_draft() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(modal, initial="hello")
    modal.handle_text_input("!")
    assert modal.handle_keydown(_keydown(pygame.K_RETURN)) is True
    view = modal.view_state()
    assert view is not None
    assert view.draft == "hello!"
    assert view.editing is False
    assert view.focus_region == TextFocusRegion.FIELD
    assert modal.active
    assert confirmed == []
    assert cancelled == []


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


def test_confirm_button_commits_draft() -> None:
    modal = ModalHost()
    confirmed, cancelled = _open_text(modal, initial="hello")
    modal.handle_text_input("!")
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    modal.handle_keydown(_keydown(pygame.K_DOWN))
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
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    modal.handle_keydown(_keydown(pygame.K_DOWN))
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

    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    modal.handle_keydown(_keydown(pygame.K_DOWN))
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
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    modal.handle_keydown(_keydown(pygame.K_DOWN))
    modal.handle_keydown(_keydown(pygame.K_RETURN))
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
