"""Unit tests for live tuning confirm dialogs."""

from __future__ import annotations

import pygame

from cleave.viz.confirm import UnsavedQuitDialog, UnsavedQuitRequest


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0)


def test_unsaved_quit_dialog_left_right_cycles_three_options() -> None:
    dialog = UnsavedQuitDialog()
    dialog.prompt(
        UnsavedQuitRequest(on_save=lambda: None, on_discard=lambda: None)
    )
    assert dialog.focus_index == 0

    dialog.handle_keydown(_keydown(pygame.K_RIGHT))
    assert dialog.focus_index == 1

    dialog.handle_keydown(_keydown(pygame.K_RIGHT))
    assert dialog.focus_index == 2

    dialog.handle_keydown(_keydown(pygame.K_RIGHT))
    assert dialog.focus_index == 0

    dialog.handle_keydown(_keydown(pygame.K_LEFT))
    assert dialog.focus_index == 2


def test_unsaved_quit_dialog_enter_activates_focused_option() -> None:
    events: list[str] = []
    dialog = UnsavedQuitDialog()
    dialog.prompt(
        UnsavedQuitRequest(
            on_save=lambda: events.append("save"),
            on_discard=lambda: events.append("discard"),
        )
    )

    dialog.handle_keydown(_keydown(pygame.K_RIGHT))
    dialog.handle_keydown(_keydown(pygame.K_RETURN))
    assert events == ["discard"]
    assert not dialog.active

    dialog.prompt(
        UnsavedQuitRequest(
            on_save=lambda: events.append("save"),
            on_discard=lambda: events.append("discard"),
        )
    )
    dialog.handle_keydown(_keydown(pygame.K_RETURN))
    assert events == ["discard", "save"]


def test_unsaved_quit_dialog_escape_cancels() -> None:
    events: list[str] = []
    dialog = UnsavedQuitDialog()
    dialog.prompt(
        UnsavedQuitRequest(
            on_save=lambda: events.append("save"),
            on_discard=lambda: events.append("discard"),
            on_cancel=lambda: events.append("cancel"),
        )
    )

    dialog.handle_keydown(_keydown(pygame.K_ESCAPE))
    assert events == ["cancel"]
    assert not dialog.active


def test_unsaved_quit_dialog_message() -> None:
    dialog = UnsavedQuitDialog()
    assert (
        dialog.message
        == "Unsaved changes - save changes before exit?"
    )


def test_unsaved_quit_dialog_consumes_keys_while_active() -> None:
    dialog = UnsavedQuitDialog()
    dialog.prompt(
        UnsavedQuitRequest(on_save=lambda: None, on_discard=lambda: None)
    )
    assert dialog.handle_keydown(_keydown(pygame.K_a)) is True
    assert dialog.active
