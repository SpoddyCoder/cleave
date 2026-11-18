"""Settings > Rescan presets: re-index the preset folder without leaving the editor.

The index is built on a worker thread with its own SQLite connection, under a
progress dialog with Cancel. The finished index replaces the live one on the
main thread, so favourites, roles, and the blacklist pick up new and changed
presets. Cancel leaves the previous index in use.
"""

from __future__ import annotations

import queue
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cleave.preset_library import PresetIndex, PresetLibrary, build_index
from cleave.viz.modal import ModalHost

PROGRESS_TITLE = "Rescan presets"
SCANNING_MESSAGE = "Scanning preset folders…"
INDEXING_MESSAGE = "Indexing presets…"
CANCELLING_MESSAGE = "Cancelling…"
FAILED_TITLE = "Could not rescan presets"
_ABORT_JOIN_SEC = 1.0


def done_message(count: int) -> str:
    return f"Presets rescanned: {count:,} found"


@dataclass(frozen=True)
class _Progress:
    done: int
    total: int


@dataclass(frozen=True)
class _Finished:
    index: PresetIndex | None
    error: str | None = None


_WorkerEvent = _Progress | _Finished


class _RescanWorker:
    """Run :func:`build_index` on a daemon thread; events go to a queue."""

    def __init__(self, database_uri: str, preset_root: Path) -> None:
        self.events: queue.SimpleQueue[_WorkerEvent] = queue.SimpleQueue()
        self.cancel = threading.Event()
        self._database_uri = database_uri
        self._preset_root = preset_root
        self._thread = threading.Thread(
            target=self._run, name="cleave-preset-rescan", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        def on_progress(done: int, total: int) -> bool:
            if self.cancel.is_set():
                return False
            self.events.put(_Progress(done, total))
            return True

        try:
            conn = sqlite3.connect(self._database_uri, uri=True)
            try:
                index = build_index(conn, self._preset_root, on_progress)
            finally:
                conn.close()
        except (OSError, sqlite3.Error) as exc:
            self.events.put(_Finished(None, str(exc) or type(exc).__name__))
            return
        self.events.put(_Finished(index))

    def join(self, timeout: float) -> None:
        self._thread.join(timeout)


class PresetRescanController:
    """Prompt-free rescan of ``preset_root`` into ``library``, with progress.

    ``hold_playback`` pauses playback and returns the call that resumes it.
    Call :meth:`tick` every frame.
    """

    def __init__(
        self,
        library: PresetLibrary,
        preset_root: Path,
        modal_host: ModalHost,
        *,
        hold_playback: Callable[[], Callable[[], None]],
        on_notification: Callable[[str], None],
    ) -> None:
        self._library = library
        self._preset_root = preset_root
        self._modal = modal_host
        self._hold_playback = hold_playback
        self._notify = on_notification
        self._worker: _RescanWorker | None = None
        self._resume: Callable[[], None] | None = None
        self._cancelling = False

    @property
    def busy(self) -> bool:
        return self._worker is not None

    def start(self) -> None:
        if self._worker is not None:
            return
        self._resume = self._hold_playback()
        self._cancelling = False
        self._modal.prompt_progress(
            PROGRESS_TITLE, body=SCANNING_MESSAGE, on_cancel=self._cancel
        )
        self._worker = _RescanWorker(self._library.database_uri, self._preset_root)

    def tick(self) -> None:
        worker = self._worker
        if worker is None:
            return
        latest: _Progress | None = None
        while True:
            try:
                event = worker.events.get_nowait()
            except queue.Empty:
                break
            if isinstance(event, _Finished):
                self._finish(event)
                return
            latest = event
        if latest is not None and not self._cancelling:
            fraction = latest.done / latest.total if latest.total else 0.0
            self._modal.update_progress(fraction, body=INDEXING_MESSAGE)

    def abort(self) -> None:
        """Stop without adopting anything (the window is closing)."""
        worker = self._worker
        if worker is None:
            return
        worker.cancel.set()
        worker.join(_ABORT_JOIN_SEC)
        self._end()

    def _cancel(self) -> None:
        worker = self._worker
        if worker is None:
            return
        worker.cancel.set()
        self._cancelling = True
        self._modal.prompt_progress(PROGRESS_TITLE, body=CANCELLING_MESSAGE)

    def _finish(self, event: _Finished) -> None:
        self._end()
        if event.error is not None:
            self._modal.prompt_notice(FAILED_TITLE, body=event.error)
            return
        if event.index is None:
            return
        self._library.adopt(event.index)
        self._notify(done_message(len(event.index.path_hash)))

    def _end(self) -> None:
        self._worker = None
        self._cancelling = False
        if self._modal.active:
            self._modal.dismiss()
        resume = self._resume
        self._resume = None
        if resume is not None:
            resume()
