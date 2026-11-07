"""Inline text and colour editing of inspector rows."""

from __future__ import annotations

import pygame

from cleave.viz.colour_parse import validate_hex_colour
from cleave.viz.inline_edit import ColourTarget, InlineEditController
from cleave.viz.row_kinds import RowDescriptor, RowKind
from tests.support.viz import keydown

_ROW = RowDescriptor(RowKind.OVERLAY_CARD_TITLE_TEXT, card="opening_card")


def _text(
    initial: str = "Title",
    *,
    validate=None,
) -> tuple[InlineEditController, list[str], list[str]]:
    events: list[str] = []
    committed: list[str] = []
    edit = InlineEditController(
        lambda: events.append("start"), lambda: events.append("stop")
    )
    edit.begin_text(_ROW, initial, committed.append, validate=validate)
    return edit, committed, events


def test_enter_commits_and_stops_text_input() -> None:
    edit, committed, events = _text()
    assert edit.text_target == _ROW
    edit.handle_text_input(" two")
    assert edit.handle_keydown(keydown(pygame.K_RETURN)) is True
    assert committed == ["Title two"]
    assert events == ["start", "stop"]
    assert not edit.active


def test_escape_reverts() -> None:
    edit, committed, _events = _text()
    edit.handle_text_input("x")
    edit.handle_keydown(keydown(pygame.K_ESCAPE))
    assert committed == []
    assert not edit.active


def test_every_key_is_consumed_so_hotkeys_cannot_fire() -> None:
    edit, _committed, _events = _text()
    for key in (pygame.K_e, pygame.K_h, pygame.K_p, pygame.K_DELETE, pygame.K_1):
        assert edit.handle_keydown(keydown(key)) is True
    assert edit.active


def test_inactive_controller_leaves_keys_alone() -> None:
    edit = InlineEditController()
    assert edit.handle_keydown(keydown(pygame.K_e)) is False
    assert edit.handle_keyup(pygame.event.Event(pygame.KEYUP, key=pygame.K_e)) is False
    assert edit.handle_text_input("e") is False


def test_arrows_and_backspace_edit_at_the_caret() -> None:
    edit, committed, _events = _text("ab")
    edit.handle_keydown(keydown(pygame.K_LEFT))
    edit.handle_keydown(keydown(pygame.K_BACKSPACE))
    edit.handle_text_input("z")
    assert edit.text_view().draft == "zb"
    assert edit.text_view().caret_index == 1
    edit.handle_keydown(keydown(pygame.K_RETURN))
    assert committed == ["zb"]


def test_invalid_text_stays_open_on_enter_and_is_dropped_on_click_away() -> None:
    edit, committed, _events = _text("#ffffff", validate=validate_hex_colour)
    edit.handle_text_input("zz")
    edit.handle_keydown(keydown(pygame.K_RETURN))
    assert edit.active
    assert edit.text_view().error is not None
    assert committed == []
    edit.finish()
    assert not edit.active
    assert committed == []


def test_click_away_commits_a_valid_edit() -> None:
    edit, committed, _events = _text()
    edit.handle_text_input("!")
    edit.finish()
    assert committed == ["Title!"]


def test_unchanged_text_does_not_commit() -> None:
    edit, committed, _events = _text()
    edit.finish()
    assert committed == []


def test_tab_commits() -> None:
    edit, committed, _events = _text()
    edit.handle_text_input("!")
    assert edit.handle_keydown(keydown(pygame.K_TAB)) is True
    assert committed == ["Title!"]


def test_colour_applies_live_and_escape_restores() -> None:
    applied: list[object] = []
    edit = InlineEditController()
    edit.begin_colour(_ROW, ColourTarget((1, 2, 3), applied.append))
    edit.set_colour((9, 9, 9))
    edit.set_colour((9, 9, 9))
    assert applied == [(9, 9, 9)]
    edit.handle_keydown(keydown(pygame.K_ESCAPE))
    assert applied == [(9, 9, 9), (1, 2, 3)]
    assert not edit.active


def test_colour_finish_keeps_the_pick() -> None:
    applied: list[object] = []
    edit = InlineEditController()
    edit.begin_colour(_ROW, ColourTarget(None, applied.append, optional=True))
    edit.set_colour((9, 9, 9))
    edit.finish()
    assert applied == [(9, 9, 9)]


def test_a_new_edit_finishes_the_last_one() -> None:
    edit, committed, _events = _text()
    edit.handle_text_input("!")
    edit.begin_colour(_ROW, ColourTarget((1, 2, 3), lambda _value: None))
    assert committed == ["Title!"]
    assert edit.text_target is None
    assert edit.colour_edit is not None
