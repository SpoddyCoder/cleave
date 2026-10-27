"""Starter-pack prompt keys, without a GL window."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame
import pytest

from cleave.viz.starter_pack_host import run_starter_pack_prompt


def _mock_window() -> MagicMock:
    window = MagicMock()
    window.quit_requested = False
    return window


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0)


def _run(window: MagicMock, events: list[list[pygame.event.Event]]):
    batches = list(events)

    def next_batch() -> list[pygame.event.Event]:
        return batches.pop(0) if batches else []

    with (
        patch("pygame.event.get", side_effect=next_batch),
        patch("cleave.viz.starter_pack_host.present_frame") as present,
        patch("cleave.viz.starter_pack_host.download_starter_packs") as download,
    ):
        result = run_starter_pack_prompt(window)
    return result, present, download


@pytest.fixture(autouse=True)
def _pygame_ready() -> None:
    pygame.init()


@pytest.mark.parametrize(
    "key",
    [pygame.K_y, pygame.K_RETURN, pygame.K_KP_ENTER],
)
def test_confirm_starts_download(key: int) -> None:
    window = _mock_window()
    result, present, download = _run(window, [[], [_keydown(key)]])

    assert result is True
    download.assert_called_once()
    present.assert_called()
    assert present.call_args.kwargs["scrim"] is True


@pytest.mark.parametrize("key", [pygame.K_n, pygame.K_ESCAPE])
def test_skip_returns_false(key: int) -> None:
    window = _mock_window()
    result, _present, download = _run(window, [[], [_keydown(key)]])

    assert result is False
    download.assert_not_called()


def test_window_close_returns_none() -> None:
    window = _mock_window()
    result, _present, download = _run(
        window, [[pygame.event.Event(pygame.QUIT)]]
    )

    assert result is None
    assert window.quit_requested
    download.assert_not_called()
