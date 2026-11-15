"""Loading-window modal runner, without a GL window."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame
import pytest

from cleave.viz.loading_modal import run_modal, show_notice
from cleave.viz.modal import ModalHost, ModalOption


@pytest.fixture(autouse=True)
def _pygame_ready() -> None:
    pygame.init()


def _window() -> MagicMock:
    window = MagicMock()
    window.quit_requested = False
    return window


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0)


def _run_with(batches: list[list[pygame.event.Event]], fn):
    pending = list(batches)
    with (
        patch(
            "pygame.event.get",
            side_effect=lambda: pending.pop(0) if pending else [],
        ),
        patch("cleave.viz.loading_modal.present_frame") as present,
    ):
        return fn(), present


def test_run_modal_ends_on_button() -> None:
    window = _window()
    host = ModalHost()
    chosen: list[str] = []
    host.prompt_buttons(
        "Pick",
        [ModalOption("A", lambda: chosen.append("a")), ModalOption("B", lambda: chosen.append("b"))],
    )
    result, present = _run_with(
        [[], [_keydown(pygame.K_RIGHT)], [_keydown(pygame.K_RETURN)]],
        lambda: run_modal(window, host),
    )
    assert result is True
    assert chosen == ["b"]
    assert present.call_count >= 2


def test_run_modal_quit_returns_false() -> None:
    window = _window()
    host = ModalHost()
    host.prompt_notice("Hi")
    result, _present = _run_with(
        [[pygame.event.Event(pygame.QUIT)]], lambda: run_modal(window, host)
    )
    assert result is False
    assert window.quit_requested
    assert host.active


def test_mouse_events_reach_imgui() -> None:
    window = _window()
    motion = pygame.event.Event(pygame.MOUSEMOTION, pos=(1, 1), rel=(1, 1), buttons=(0, 0, 0))
    result, _present = _run_with(
        [[motion], [_keydown(pygame.K_ESCAPE)]],
        lambda: show_notice(window, "Title", "Body"),
    )
    assert result is True
    window.imgui.process_mouse_event.assert_called_once_with(motion)
