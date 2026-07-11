"""Unit tests for live tuning modal host."""

from __future__ import annotations

import pygame

from cleave.viz.modal import ModalHost, ModalOption


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0)


def test_unsaved_quit_left_right_cycles_three_options() -> None:
    modal = ModalHost()
    modal.prompt_unsaved_quit(on_save=lambda: None, on_discard=lambda: None)
    view = modal.view_state()
    assert view is not None
    assert view.focus_index == 0

    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    assert modal.view_state() is not None
    assert modal.view_state().focus_index == 1

    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    assert modal.view_state().focus_index == 2

    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    assert modal.view_state().focus_index == 0

    modal.handle_keydown(_keydown(pygame.K_LEFT))
    assert modal.view_state().focus_index == 2


def test_unsaved_quit_enter_activates_focused_option() -> None:
    events: list[str] = []
    modal = ModalHost()
    modal.prompt_unsaved_quit(
        on_save=lambda: events.append("save"),
        on_discard=lambda: events.append("discard"),
    )

    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    assert events == ["discard"]
    assert not modal.active

    modal.prompt_unsaved_quit(
        on_save=lambda: events.append("save"),
        on_discard=lambda: events.append("discard"),
    )
    modal.handle_keydown(_keydown(pygame.K_RETURN))
    assert events == ["discard", "save"]


def test_unsaved_quit_escape_cancels() -> None:
    events: list[str] = []
    modal = ModalHost()
    modal.prompt_unsaved_quit(
        on_save=lambda: events.append("save"),
        on_discard=lambda: events.append("discard"),
        on_cancel=lambda: events.append("cancel"),
    )

    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    assert events == ["cancel"]
    assert not modal.active


def test_unsaved_quit_message() -> None:
    modal = ModalHost()
    modal.prompt_unsaved_quit(on_save=lambda: None, on_discard=lambda: None)
    view = modal.view_state()
    assert view is not None
    assert view.message == "Unsaved changes - save changes before exit?"


def test_unsaved_quit_consumes_keys_while_active() -> None:
    modal = ModalHost()
    modal.prompt_unsaved_quit(on_save=lambda: None, on_discard=lambda: None)
    assert modal.handle_keydown(_keydown(pygame.K_a)) is True
    assert modal.active


def test_prompt_choice_initial_focus_index() -> None:
    modal = ModalHost()
    modal.prompt_choice(
        "Pick one",
        [
            ModalOption("a", lambda: None),
            ModalOption("b", lambda: None),
            ModalOption("c", lambda: None),
            ModalOption("d", lambda: None),
        ],
        initial_focus_index=2,
    )
    view = modal.view_state()
    assert view is not None
    assert view.focus_index == 2


def test_prompt_choice_initial_focus_index_out_of_range_defaults_to_zero() -> None:
    modal = ModalHost()
    modal.prompt_choice(
        "Pick one",
        [
            ModalOption("a", lambda: None),
            ModalOption("b", lambda: None),
        ],
        initial_focus_index=5,
    )
    view = modal.view_state()
    assert view is not None
    assert view.focus_index == 0

    modal.prompt_choice(
        "Pick one",
        [
            ModalOption("a", lambda: None),
            ModalOption("b", lambda: None),
        ],
        initial_focus_index=-1,
    )
    assert modal.view_state().focus_index == 0


def test_prompt_choice_omitted_initial_focus_stays_zero() -> None:
    modal = ModalHost()
    modal.prompt_choice(
        "Pick one",
        [
            ModalOption("a", lambda: None),
            ModalOption("b", lambda: None),
        ],
    )
    view = modal.view_state()
    assert view is not None
    assert view.focus_index == 0
