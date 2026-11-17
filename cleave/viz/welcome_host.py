"""The "Welcome to Cleave" step: pick downloads, run them, offer Retry.

One form lists every missing download (presets and model weights). Download
runs them in order on a worker thread under a progress dialog with a status
line per item and a Cancel button. Failures are reported in the same step,
with Retry.

:class:`WelcomeFlow` is tick-driven on a :class:`ModalHost`, so the same step
runs on the loading window at startup (:func:`run_welcome`) and in the editor
from Settings.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass

import pygame
import yaml

from cleave.config_schema.first_run import FirstRunState
from cleave.first_run import (
    FirstRunCancelled,
    FirstRunItem,
    FirstRunItemId,
    FirstRunResult,
    ItemOutcome,
    ItemResult,
    run_downloads,
)
from cleave.user_config import persist_first_run_state
from cleave.viz.loading import LoadingWindow
from cleave.viz.loading_modal import present_modal_frame
from cleave.viz.modal import (
    ButtonRole,
    FormField,
    FormSpec,
    FormValues,
    ModalHost,
    ModalLabeledLine,
    ModalOption,
)

WELCOME_TITLE = "Welcome to Cleave"
_WELCOME_BODY = (
    "Cleave needs a few one-time downloads. "
    "Anything you skip downloads when it is first needed."
)
_SECTION = "Downloads"
SKIP_LABEL = "Skip"
CANCEL_LABEL = "Cancel"
_OFF_ON = ("Off", "On")
_FAILED_TITLE = "Some downloads failed"
_FAILED_BODY = "Check your internet connection, then try again."
_DOWNLOAD_FAILED = "Download failed"
_CANCELLING = "Cancelling…"
_NOTHING_TITLE = "Everything is downloaded"
_NOTHING_BODY = "Cleave already has every download on this computer."

_WAITING = "Waiting"
_DOWNLOADING = "Downloading"
_DONE = "Done"
_FAILED = "Failed"
_CANCELLED = "Cancelled"

_TICK_FPS = 60
_ABORT_JOIN_SEC = 1.0


def _downloading_message(item: FirstRunItem) -> str:
    return f"Downloading {item.name}…"


def _mark_done() -> None:
    try:
        persist_first_run_state(FirstRunState(welcome_done=True))
    except (OSError, ValueError, yaml.YAMLError):
        return


class _DownloadView:
    """Status lines and overall fraction for one download pass."""

    def __init__(self, items: tuple[FirstRunItem, ...]) -> None:
        self.items = items
        self.status = {item.id: _WAITING for item in items}
        self.fraction = 0.0

    def lines(self) -> tuple[ModalLabeledLine, ...]:
        return tuple(
            ModalLabeledLine(item.name, self.status[item.id]) for item in self.items
        )

    def progress(self, item: FirstRunItem, fraction: float | None) -> None:
        index = self.items.index(item)
        item_frac = 0.0 if fraction is None else max(0.0, min(1.0, fraction))
        if fraction is None:
            self.status[item.id] = _DOWNLOADING
        else:
            self.status[item.id] = f"{_DOWNLOADING} {round(item_frac * 100)}%"
        self.fraction = (index + item_frac) / len(self.items)

    def finish(self, result: ItemResult) -> None:
        if result.outcome is ItemOutcome.DONE:
            self.status[result.item.id] = result.note or _DONE
        elif result.outcome is ItemOutcome.FAILED:
            self.status[result.item.id] = _FAILED
        else:
            self.status[result.item.id] = _CANCELLED
        done = sum(1 for status in self.status.values() if status != _WAITING)
        self.fraction = done / len(self.items)


@dataclass(frozen=True)
class _Progress:
    item: FirstRunItem
    fraction: float | None


@dataclass(frozen=True)
class _Finished:
    result: FirstRunResult


_WorkerEvent = _Progress | ItemResult | _Finished


class _DownloadWorker:
    """Run :func:`run_downloads` on a daemon thread; events go to a queue.

    The thread never touches the modal. Setting ``cancel`` makes the next
    progress report raise :class:`FirstRunCancelled`.
    """

    def __init__(self, items: tuple[FirstRunItem, ...]) -> None:
        self.items = items
        self.events: queue.SimpleQueue[_WorkerEvent] = queue.SimpleQueue()
        self.cancel = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="cleave-welcome-downloads", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        reported: list[ItemResult] = []

        def on_progress(
            item: FirstRunItem, _message: str, fraction: float | None
        ) -> None:
            if self.cancel.is_set():
                raise FirstRunCancelled()
            self.events.put(_Progress(item, fraction))

        def on_result(result: ItemResult) -> None:
            reported.append(result)
            self.events.put(result)

        try:
            result = run_downloads(self.items, on_progress, on_result)
        except Exception as exc:
            error = str(exc) or type(exc).__name__
            done = {r.item.id for r in reported}
            for item in self.items:
                if item.id not in done:
                    on_result(ItemResult(item, ItemOutcome.FAILED, error))
            result = FirstRunResult(tuple(reported))
        self.events.put(_Finished(result))

    def join(self, timeout: float) -> None:
        self._thread.join(timeout)


class WelcomeFlow:
    """The welcome step on *host*: form, downloads, and Retry.

    Call :meth:`tick` every frame. Downloading or skipping marks the step done
    in the user config and runs ``on_close``; :meth:`abort` (the window is
    closing) does neither.
    """

    def __init__(self, host: ModalHost) -> None:
        self._host = host
        self._active = False
        self._worker: _DownloadWorker | None = None
        self._view: _DownloadView | None = None
        self._message = ""
        self._cancelling = False
        self._on_close: Callable[[], None] | None = None
        self._downloaded: set[FirstRunItemId] = set()

    @property
    def active(self) -> bool:
        return self._active

    @property
    def downloaded(self) -> frozenset[FirstRunItemId]:
        """Items that finished downloading since the last :meth:`start`.

        Still readable from ``on_close``.
        """
        return frozenset(self._downloaded)

    def start(
        self,
        items: tuple[FirstRunItem, ...],
        *,
        on_close: Callable[[], None] | None = None,
        cancel_label: str = SKIP_LABEL,
    ) -> None:
        """Offer *items* (already filtered to the missing ones).

        *on_close* runs once when the step closes, including the notice shown
        when nothing is missing. *cancel_label* names the form's dismiss
        button: Skip at startup, Cancel when opened from the editor.
        """
        if self._active:
            return
        self._downloaded = set()
        if not items:
            self._host.prompt_notice(_NOTHING_TITLE, on_close, body=_NOTHING_BODY)
            return
        self._active = True
        self._on_close = on_close
        self._prompt_choose(items, cancel_label)

    def tick(self) -> None:
        worker = self._worker
        view = self._view
        if worker is None or view is None:
            return
        while True:
            try:
                event = worker.events.get_nowait()
            except queue.Empty:
                break
            if isinstance(event, _Finished):
                self._finish_downloads(event.result)
                return
            if isinstance(event, ItemResult):
                view.finish(event)
            elif not self._cancelling:
                view.progress(event.item, event.fraction)
                self._message = _downloading_message(event.item)
        self._host.update_progress(
            view.fraction,
            message=None if self._cancelling else self._message,
            labeled_lines=view.lines(),
        )

    def abort(self) -> None:
        """Stop without marking the step done (the window is closing)."""
        if not self._active:
            return
        worker = self._worker
        self._end()
        if worker is not None:
            worker.cancel.set()
            worker.join(_ABORT_JOIN_SEC)
        if self._host.active:
            self._host.dismiss()

    def _prompt_choose(
        self, items: tuple[FirstRunItem, ...], cancel_label: str
    ) -> None:
        def selected(values: FormValues) -> tuple[FirstRunItem, ...]:
            return tuple(item for item in items if values.get(item.id.value) == 1)

        def info(values: FormValues) -> str:
            total = sum(item.size_mb for item in selected(values))
            return f"~{total} MB to download" if total else "nothing to download"

        def confirm(values: FormValues) -> None:
            chosen = selected(values)
            if chosen:
                self._start_downloads(chosen)
            else:
                self._complete()

        self._host.prompt_form(
            FormSpec(
                title=WELCOME_TITLE,
                body=_WELCOME_BODY,
                fields=tuple(
                    FormField(
                        id=item.id.value,
                        label=f"{item.name} - {item.purpose} ({item.size_hint})",
                        options=_OFF_ON,
                        value=1 if item.default_on else 0,
                        help=(f"{item.name}: {item.purpose}.",),
                        section=_SECTION,
                    )
                    for item in items
                ),
                confirm_label="Download",
                on_confirm=confirm,
                cancel_label=cancel_label,
                on_cancel=self._complete,
                info=info,
                help=(_WELCOME_BODY,),
            )
        )

    def _start_downloads(self, items: tuple[FirstRunItem, ...]) -> None:
        self._view = _DownloadView(items)
        self._cancelling = False
        self._message = _downloading_message(items[0])
        self._host.prompt_progress(
            self._message,
            labeled_lines=self._view.lines(),
            on_cancel=self._cancel,
            large_text=False,
        )
        self._worker = _DownloadWorker(items)

    def _cancel(self) -> None:
        worker = self._worker
        view = self._view
        if worker is None or view is None:
            return
        worker.cancel.set()
        self._cancelling = True
        self._host.prompt_progress(
            _CANCELLING,
            labeled_lines=view.lines(),
            fraction=view.fraction,
            large_text=False,
        )

    def _finish_downloads(self, result: FirstRunResult) -> None:
        self._downloaded.update(
            r.item.id for r in result.results if r.outcome is ItemOutcome.DONE
        )
        self._worker = None
        self._view = None
        if self._host.active:
            self._host.dismiss()
        if result.cancelled or not result.failed:
            self._complete()
            return
        failed = tuple(r.item for r in result.failed)
        self._host.prompt_buttons(
            _FAILED_TITLE,
            [
                ModalOption(
                    "Retry", lambda: self._start_downloads(failed), ButtonRole.PRIMARY
                ),
                ModalOption("Continue", self._complete),
            ],
            self._complete,
            labeled_lines=tuple(
                ModalLabeledLine(r.item.name, _DOWNLOAD_FAILED) for r in result.failed
            ),
            body=_FAILED_BODY,
        )

    def _complete(self) -> None:
        if not self._active:
            return
        _mark_done()
        on_close = self._on_close
        self._end()
        if on_close is not None:
            on_close()

    def _end(self) -> None:
        self._active = False
        self._worker = None
        self._view = None
        self._cancelling = False
        self._on_close = None


def run_welcome(window: LoadingWindow, items: tuple[FirstRunItem, ...]) -> None:
    """Run the step on the loading window until it finishes or the window closes.

    Closing the window leaves the step unmarked, so it shows again next launch.
    """
    if not items:
        return
    host = ModalHost()
    flow = WelcomeFlow(host)
    flow.start(items)
    clock = pygame.time.Clock()
    while flow.active and not window.quit_requested:
        dt_sec = clock.tick(_TICK_FPS) / 1000.0
        flow.tick()
        present_modal_frame(window, host, dt_sec)
    if window.quit_requested:
        flow.abort()
