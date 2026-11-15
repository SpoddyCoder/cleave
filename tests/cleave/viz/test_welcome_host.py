"""The welcome step's flow with fake downloads, without a GL window."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pygame
import pytest

from cleave.first_run import FirstRunItem, FirstRunItemId
from cleave.model_weights import WeightDownloadError
from cleave.viz.welcome_host import run_welcome


@pytest.fixture(autouse=True)
def _pygame_ready() -> None:
    pygame.init()


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0)


def _item(
    item_id: FirstRunItemId,
    download: Callable[..., None],
    *,
    default_on: bool = True,
) -> FirstRunItem:
    return FirstRunItem(
        id=item_id,
        label=item_id.value,
        size_mb=10,
        default_on=default_on,
        help="",
        needed=lambda: True,
        download=download,
    )


def _run(items: tuple[FirstRunItem, ...], batches: list[list[pygame.event.Event]]):
    window = MagicMock()
    window.quit_requested = False
    pending = list(batches)

    def next_batch() -> list[pygame.event.Event]:
        return pending.pop(0) if pending else []

    with (
        patch("pygame.event.get", side_effect=next_batch),
        patch("cleave.viz.loading_modal.present_frame"),
        patch("cleave.viz.welcome_host.persist_first_run_state") as persist,
    ):
        run_welcome(window, items)
    return window, persist


def _recording(log: list[str], name: str) -> Callable[..., None]:
    def download(progress) -> None:
        progress("msg", 0.5)
        log.append(name)

    return download


def test_skip_marks_done_without_downloading() -> None:
    log: list[str] = []
    items = (_item(FirstRunItemId.PRESETS, _recording(log, "presets")),)
    _window, persist = _run(items, [[_keydown(pygame.K_ESCAPE)]])
    assert log == []
    persist.assert_called_once()
    assert persist.call_args.args[0].welcome_done is True


def test_download_runs_ticked_items_only() -> None:
    log: list[str] = []
    items = (
        _item(FirstRunItemId.PRESETS, _recording(log, "presets")),
        _item(FirstRunItemId.DEMUCS_HQ, _recording(log, "hq"), default_on=False),
    )
    _window, persist = _run(items, [[_keydown(pygame.K_RETURN)]])
    assert log == ["presets"]
    persist.assert_called_once()


def test_failure_then_retry_downloads_failed_item_again() -> None:
    attempts: list[int] = []
    log: list[str] = []

    def flaky(progress) -> None:
        attempts.append(1)
        if len(attempts) == 1:
            raise WeightDownloadError("no network")
        log.append("demucs")

    items = (
        _item(FirstRunItemId.PRESETS, _recording(log, "presets")),
        _item(FirstRunItemId.DEMUCS, flaky),
    )
    # Form Enter; then frames during downloads; Retry is focused, Enter picks it.
    batches = [[_keydown(pygame.K_RETURN)]] + [[] for _ in range(4)] + [
        [_keydown(pygame.K_RETURN)]
    ]
    _window, persist = _run(items, batches)
    assert log == ["presets", "demucs"]
    assert len(attempts) == 2
    persist.assert_called_once()


def test_cancel_stops_downloads_and_marks_done() -> None:
    log: list[str] = []

    def slow(progress) -> None:
        progress("msg", 0.1)
        progress("msg", 0.2)
        log.append("presets")

    items = (
        _item(FirstRunItemId.PRESETS, slow),
        _item(FirstRunItemId.DEMUCS, _recording(log, "demucs")),
    )
    _window, persist = _run(
        items, [[_keydown(pygame.K_RETURN)], [_keydown(pygame.K_ESCAPE)]]
    )
    assert log == []
    persist.assert_called_once()


def test_closing_the_window_does_not_mark_done() -> None:
    items = (_item(FirstRunItemId.PRESETS, lambda _p: None),)
    window, persist = _run(items, [[pygame.event.Event(pygame.QUIT)]])
    assert window.quit_requested
    persist.assert_not_called()
