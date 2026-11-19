"""The welcome step's flow with fake downloads, without a GL window."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pygame
import pytest

from cleave.first_run import FirstRunItem, FirstRunItemId
from cleave.model_weights import WeightDownloadError
from cleave.viz.controls import TuningControls
from cleave.viz.modal import ModalHost
from cleave.viz.welcome_host import WelcomeFlow, run_welcome

_WAIT_SEC = 5.0


@pytest.fixture(autouse=True)
def _pygame_ready() -> None:
    pygame.init()


@pytest.fixture
def persist() -> Iterator[MagicMock]:
    with patch("cleave.viz.welcome_host.persist_first_run_state") as mock:
        yield mock


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
        name=item_id.value,
        purpose="",
        size_mb=10,
        default_on=default_on,
        needed=lambda: True,
        download=download,
    )


def _recording(log: list[str], name: str) -> Callable[..., None]:
    def download(progress) -> None:
        progress("msg", 0.5)
        log.append(name)

    return download


def _tick_until(flow: WelcomeFlow, done: Callable[[], bool]) -> None:
    deadline = time.monotonic() + _WAIT_SEC
    while not done():
        assert time.monotonic() < deadline, "welcome flow did not settle"
        flow.tick()
        time.sleep(0.005)


def _message(host: ModalHost) -> str | None:
    view = host.view_state()
    return None if view is None else view.message


def _start(items: tuple[FirstRunItem, ...]) -> tuple[WelcomeFlow, ModalHost]:
    host = ModalHost()
    flow = WelcomeFlow(host)
    flow.start(items)
    return flow, host


def test_skip_marks_done_without_downloading(persist: MagicMock) -> None:
    log: list[str] = []
    flow, host = _start((_item(FirstRunItemId.MILKDROP_ORIGINAL, _recording(log, "presets")),))
    host.handle_keydown(_keydown(pygame.K_ESCAPE))
    assert not flow.active
    assert log == []
    persist.assert_called_once()
    assert persist.call_args.args[0].welcome_done is True


def test_download_runs_ticked_items_only(persist: MagicMock) -> None:
    log: list[str] = []
    flow, host = _start(
        (
            _item(FirstRunItemId.MILKDROP_ORIGINAL, _recording(log, "presets")),
            _item(FirstRunItemId.DEMUCS_HQ, _recording(log, "hq"), default_on=False),
        )
    )
    host.handle_keydown(_keydown(pygame.K_RETURN))
    _tick_until(flow, lambda: not flow.active)
    assert log == ["presets"]
    assert not host.active
    persist.assert_called_once()


def test_failure_then_retry_downloads_failed_item_again(persist: MagicMock) -> None:
    attempts: list[int] = []
    log: list[str] = []

    def flaky(progress) -> None:
        attempts.append(1)
        if len(attempts) == 1:
            raise WeightDownloadError("no network")
        log.append("demucs")

    flow, host = _start(
        (
            _item(FirstRunItemId.MILKDROP_ORIGINAL, _recording(log, "presets")),
            _item(FirstRunItemId.DEMUCS, flaky),
        )
    )
    host.handle_keydown(_keydown(pygame.K_RETURN))
    _tick_until(flow, lambda: _message(host) == "Some downloads failed")
    persist.assert_not_called()
    host.handle_keydown(_keydown(pygame.K_RETURN))  # Retry is focused
    _tick_until(flow, lambda: not flow.active)
    assert log == ["presets", "demucs"]
    assert len(attempts) == 2
    persist.assert_called_once()


def test_unexpected_error_is_reported_as_a_failure(persist: MagicMock) -> None:
    def broken(_progress) -> None:
        raise RuntimeError("boom")

    flow, host = _start((_item(FirstRunItemId.DEMUCS, broken),))
    host.handle_keydown(_keydown(pygame.K_RETURN))
    _tick_until(flow, lambda: _message(host) == "Some downloads failed")
    host.handle_keydown(_keydown(pygame.K_ESCAPE))  # Esc continues
    assert not flow.active
    persist.assert_called_once()


def test_cancel_stops_downloads_and_marks_done(persist: MagicMock) -> None:
    log: list[str] = []
    started = threading.Event()
    release = threading.Event()

    def slow(progress) -> None:
        progress("msg", 0.1)
        started.set()
        release.wait(_WAIT_SEC)
        progress("msg", 0.2)
        log.append("presets")

    flow, host = _start(
        (
            _item(FirstRunItemId.MILKDROP_ORIGINAL, slow),
            _item(FirstRunItemId.DEMUCS, _recording(log, "demucs")),
        )
    )
    host.handle_keydown(_keydown(pygame.K_RETURN))
    assert started.wait(_WAIT_SEC)
    host.handle_keydown(_keydown(pygame.K_ESCAPE))
    view = host.view_state()
    assert view is not None and view.body == "Cancelling…"
    release.set()
    _tick_until(flow, lambda: not flow.active)
    assert log == []
    persist.assert_called_once()


def test_abort_does_not_mark_done(persist: MagicMock) -> None:
    release = threading.Event()

    def slow(progress) -> None:
        release.wait(_WAIT_SEC)
        progress("msg", 0.5)

    flow, host = _start((_item(FirstRunItemId.MILKDROP_ORIGINAL, slow),))
    host.handle_keydown(_keydown(pygame.K_RETURN))
    release.set()
    flow.abort()
    assert not flow.active
    assert not host.active
    persist.assert_not_called()


def test_nothing_missing_shows_a_notice(persist: MagicMock) -> None:
    flow, host = _start(())
    assert not flow.active
    assert _message(host) == "Everything is downloaded"
    host.handle_keydown(_keydown(pygame.K_RETURN))
    assert not host.active
    persist.assert_not_called()


def _run_on_window(
    items: tuple[FirstRunItem, ...], batches: list[list[pygame.event.Event]]
) -> MagicMock:
    window = MagicMock()
    window.quit_requested = False
    pending = list(batches)

    def next_batch() -> list[pygame.event.Event]:
        return pending.pop(0) if pending else []

    with (
        patch("pygame.event.get", side_effect=next_batch),
        patch("cleave.viz.loading_modal.present_frame"),
    ):
        run_welcome(window, items)
    return window


def test_loading_window_runs_the_step_to_the_end(persist: MagicMock) -> None:
    log: list[str] = []
    items = (_item(FirstRunItemId.MILKDROP_ORIGINAL, _recording(log, "presets")),)
    _run_on_window(items, [[_keydown(pygame.K_RETURN)]])
    assert log == ["presets"]
    persist.assert_called_once()


def test_closing_the_window_does_not_mark_done(persist: MagicMock) -> None:
    items = (_item(FirstRunItemId.MILKDROP_ORIGINAL, lambda _p: None),)
    window = _run_on_window(items, [[pygame.event.Event(pygame.QUIT)]])
    assert window.quit_requested
    persist.assert_not_called()


def test_on_close_runs_when_the_step_closes_but_not_on_abort(
    persist: MagicMock,
) -> None:
    closed: list[str] = []
    items = (_item(FirstRunItemId.MILKDROP_ORIGINAL, lambda _p: None),)

    host = ModalHost()
    flow = WelcomeFlow(host)
    flow.start(items, on_close=lambda: closed.append("skip"))
    host.handle_keydown(_keydown(pygame.K_ESCAPE))
    assert closed == ["skip"]

    flow.start(items, on_close=lambda: closed.append("abort"))
    flow.abort()
    assert closed == ["skip"]

    flow.start((), on_close=lambda: closed.append("notice"))
    host.handle_keydown(_keydown(pygame.K_RETURN))
    assert closed == ["skip", "notice"]


def _editor_controls(*, paused: bool) -> SimpleNamespace:
    playback = SimpleNamespace(paused=paused)

    def toggle() -> None:
        playback.paused = not playback.paused

    host = ModalHost()
    return SimpleNamespace(
        host=host,
        welcome=WelcomeFlow(host),
        playback=playback,
        transport=SimpleNamespace(toggle_pause=MagicMock(side_effect=toggle)),
        preset_rescan=SimpleNamespace(start=MagicMock()),
    )


def test_editor_pauses_playback_while_the_step_is_open(persist: MagicMock) -> None:
    controls = _editor_controls(paused=False)
    item = _item(FirstRunItemId.MILKDROP_ORIGINAL, lambda _p: None)
    with patch("cleave.first_run.first_run_items", return_value=(item,)):
        TuningControls.prompt_welcome(controls)
    assert controls.playback.paused
    assert controls.welcome.active
    controls.host.handle_keydown(_keydown(pygame.K_ESCAPE))
    assert not controls.playback.paused


def test_editor_leaves_paused_playback_paused(persist: MagicMock) -> None:
    controls = _editor_controls(paused=True)
    with patch("cleave.first_run.first_run_items", return_value=()):
        TuningControls.prompt_welcome(controls)
    controls.host.handle_keydown(_keydown(pygame.K_RETURN))
    assert controls.playback.paused
    controls.transport.toggle_pause.assert_not_called()


def _download_in_editor(
    controls: SimpleNamespace,
    item: FirstRunItem,
    *,
    until: Callable[[], bool] | None = None,
) -> None:
    with patch("cleave.first_run.first_run_items", return_value=(item,)):
        TuningControls.prompt_welcome(controls)
    controls.host.handle_keydown(_keydown(pygame.K_RETURN))
    _tick_until(controls.welcome, until or (lambda: not controls.welcome.active))


def test_editor_rescans_presets_after_downloading_them(persist: MagicMock) -> None:
    controls = _editor_controls(paused=False)
    _download_in_editor(controls, _item(FirstRunItemId.MILKDROP_ORIGINAL, lambda _p: None))

    assert controls.welcome.downloaded == frozenset({FirstRunItemId.MILKDROP_ORIGINAL})
    controls.preset_rescan.start.assert_called_once_with()
    assert not controls.playback.paused


def test_editor_skips_rescan_when_presets_were_not_downloaded(
    persist: MagicMock,
) -> None:
    controls = _editor_controls(paused=False)
    _download_in_editor(controls, _item(FirstRunItemId.DEMUCS, lambda _p: None))

    assert controls.welcome.downloaded == frozenset({FirstRunItemId.DEMUCS})
    controls.preset_rescan.start.assert_not_called()


def test_editor_skips_rescan_when_the_presets_download_fails(
    persist: MagicMock,
) -> None:
    def fail(_progress) -> None:
        raise WeightDownloadError("offline")

    controls = _editor_controls(paused=False)
    _download_in_editor(
        controls,
        _item(FirstRunItemId.MILKDROP_ORIGINAL, fail),
        until=lambda: _message(controls.host) == "Some downloads failed",
    )
    controls.host.handle_keydown(_keydown(pygame.K_ESCAPE))

    assert not controls.welcome.active
    assert controls.welcome.downloaded == frozenset()
    controls.preset_rescan.start.assert_not_called()


def _buttons(host: ModalHost) -> tuple[str, ...]:
    view = host.view_state()
    assert view is not None
    return view.options


def test_startup_form_offers_skip(persist: MagicMock) -> None:
    _flow, host = _start((_item(FirstRunItemId.MILKDROP_ORIGINAL, lambda _p: None),))
    assert _buttons(host) == ("Download", "Skip")


def test_editor_form_offers_cancel(persist: MagicMock) -> None:
    controls = _editor_controls(paused=True)
    item = _item(FirstRunItemId.MILKDROP_ORIGINAL, lambda _p: None)
    with patch("cleave.first_run.first_run_items", return_value=(item,)):
        TuningControls.prompt_welcome(controls)
    assert _buttons(controls.host) == ("Download", "Cancel")
