"""Transport bar pause, drag, and typed entry."""

from __future__ import annotations

import pygame

from cleave.viz.inline_edit import InlineEditController
from cleave.viz.playback import PlaybackState
from cleave.viz.transport_controls import (
    TIME_ENTRY_ERROR,
    TransportControls,
    TransportField,
    bar_at,
    parse_bar_text,
    parse_clock_text,
)
from tests.support.viz import keydown


class _Player:
    def __init__(self, position: float = 0.0) -> None:
        self.position = position
        self.paused: list[bool] = []

    def audible_position_sec(self) -> float:
        return self.position

    def pause(self, value: bool) -> None:
        self.paused.append(value)


_DOWNBEATS = (0.5, 2.5, 4.5, 6.5)


def _transport(
    position: float = 0.0,
) -> tuple[TransportControls, InlineEditController, list[float], _Player]:
    player = _Player(position)
    seeks: list[float] = []
    inline = InlineEditController()
    transport = TransportControls(
        PlaybackState(player=player),  # type: ignore[arg-type]
        100.0,
        _DOWNBEATS,
        inline,
        seeks.append,
    )
    return transport, inline, seeks, player


def test_parse_clock_text() -> None:
    assert parse_clock_text("75") == 75.0
    assert parse_clock_text("1:15") == 75.0
    assert parse_clock_text(" 01:15.5 ") == 75.5
    assert parse_clock_text("1:00:00") == 3600.0
    assert parse_clock_text("1:75") is None
    assert parse_clock_text("abc") is None
    assert parse_clock_text("") is None
    assert parse_clock_text("1:2:3:4") is None
    assert parse_clock_text("-3") is None


def test_parse_bar_text_and_bar_at() -> None:
    assert parse_bar_text("3", 4) == 3
    assert parse_bar_text("0", 4) is None
    assert parse_bar_text("5", 4) is None
    assert parse_bar_text("x", 4) is None
    assert bar_at(0.0, _DOWNBEATS) == 1
    assert bar_at(2.5, _DOWNBEATS) == 2
    assert bar_at(99.0, _DOWNBEATS) == 4


def test_toggle_pause() -> None:
    transport, _inline, _seeks, player = _transport()
    transport.toggle_pause()
    transport.toggle_pause()
    assert player.paused == [True, False]


def test_time_drag_steps_from_its_anchor() -> None:
    transport, _inline, seeks, player = _transport(10.0)
    transport.begin_drag(TransportField.TIME)
    transport.drag_step(TransportField.TIME, 2)
    player.position = 3.0  # the audible clock has not caught up
    transport.drag_step(TransportField.TIME, -3)
    assert seeks == [12.0, 9.0]
    transport.end_drag()
    transport.drag_step(TransportField.TIME, 1)
    assert seeks == [12.0, 9.0]


def test_bar_drag_seeks_to_downbeats_and_clamps() -> None:
    transport, _inline, seeks, _player = _transport(2.6)
    transport.begin_drag(TransportField.BAR)
    transport.drag_step(TransportField.BAR, 1)
    transport.drag_step(TransportField.BAR, 5)
    transport.drag_step(TransportField.BAR, -9)
    assert seeks == [4.5, 6.5, 0.5]


def test_time_entry_seeks_on_enter() -> None:
    transport, inline, seeks, _player = _transport(65.0)
    transport.begin_entry(TransportField.TIME)
    assert inline.text_target is TransportField.TIME
    assert inline.text_view().draft == "01:05"
    for _ in range(5):
        inline.handle_keydown(keydown(pygame.K_BACKSPACE))
    inline.handle_text_input("2:00")
    inline.handle_keydown(keydown(pygame.K_RETURN))
    assert seeks == [120.0]
    assert not inline.active


def test_time_entry_rejects_bad_text() -> None:
    transport, inline, seeks, _player = _transport()
    transport.begin_entry(TransportField.TIME)
    inline.handle_text_input("x")
    inline.handle_keydown(keydown(pygame.K_RETURN))
    assert inline.text_view().error == TIME_ENTRY_ERROR
    assert seeks == []


def test_bar_entry_seeks_to_the_bar() -> None:
    transport, inline, seeks, _player = _transport(0.0)
    transport.begin_entry(TransportField.BAR)
    assert inline.text_view().draft == "1"
    inline.handle_keydown(keydown(pygame.K_BACKSPACE))
    inline.handle_text_input("3")
    inline.handle_keydown(keydown(pygame.K_RETURN))
    assert seeks == [4.5]


def test_bar_needs_a_grid() -> None:
    inline = InlineEditController()
    seeks: list[float] = []
    transport = TransportControls(
        PlaybackState(player=_Player()),  # type: ignore[arg-type]
        100.0,
        (),
        inline,
        seeks.append,
    )
    transport.begin_drag(TransportField.BAR)
    transport.drag_step(TransportField.BAR, 1)
    transport.begin_entry(TransportField.BAR)
    assert seeks == []
    assert not inline.active
