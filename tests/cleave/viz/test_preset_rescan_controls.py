"""Tests for Settings > Rescan presets (worker-thread re-index under a dialog)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from cleave.preset_library import PresetLibrary
from cleave.viz import preset_rescan_controls
from cleave.viz.modal import ModalHost, ModalKind
from cleave.viz.preset_rescan_controls import (
    CANCELLING_MESSAGE,
    FAILED_TITLE,
    SCANNING_MESSAGE,
    PresetRescanController,
    done_message,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class _Harness:
    def __init__(self, library: PresetLibrary, root: Path) -> None:
        self.modal = ModalHost()
        self.notes: list[str] = []
        self.holds = 0
        self.resumes = 0
        self.controller = PresetRescanController(
            library,
            root,
            self.modal,
            hold_playback=self._hold,
            on_notification=self.notes.append,
        )

    def _hold(self):
        self.holds += 1

        def resume() -> None:
            self.resumes += 1

        return resume

    def run_until_idle(self, timeout: float = 5.0) -> None:
        deadline = time.monotonic() + timeout
        while self.controller.busy:
            assert time.monotonic() < deadline, "rescan did not finish"
            self.controller.tick()
            time.sleep(0.005)


def test_rescan_adopts_new_presets_and_resumes_playback(tmp_path: Path) -> None:
    root = tmp_path / "presets"
    fav = _write(root / "old" / "a.milk", "a")
    library = PresetLibrary.open(tmp_path / "cleave.db")
    library.index(root)
    library.set_favourite(fav, True)
    copy = _write(root / "new pack" / "copy.milk", "a")
    _write(root / "new pack" / "b.milk", "b")
    revision = library.revision
    harness = _Harness(library, root)

    harness.controller.start()
    view = harness.modal.view_state()
    assert view is not None and view.kind == ModalKind.PROGRESS
    assert view.message == SCANNING_MESSAGE
    assert view.large_text is False
    assert harness.holds == 1
    harness.run_until_idle()

    assert library.revision > revision
    assert harness.modal.view_state() is None
    assert harness.notes == [done_message(3)]
    assert harness.resumes == 1
    assert library.is_favourite(copy.resolve())
    library.close()


def test_rescan_works_on_an_in_memory_library(tmp_path: Path) -> None:
    root = tmp_path / "presets"
    _write(root / "a.milk", "a")
    library = PresetLibrary.in_memory()
    harness = _Harness(library, root)

    harness.controller.start()
    harness.run_until_idle()

    assert harness.notes == [done_message(1)]
    assert library.collection_paths("favourites") == ()


def test_cancel_keeps_previous_index(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "presets"
    _write(root / "a.milk", "a")
    library = PresetLibrary.in_memory()
    library.index(root)
    revision = library.revision
    gate = threading.Event()

    def slow_build(conn, preset_root, on_progress):
        while on_progress(0, 10):
            gate.wait(0.01)
        return None

    monkeypatch.setattr(preset_rescan_controls, "build_index", slow_build)
    harness = _Harness(library, root)
    harness.controller.start()
    harness.controller.tick()

    harness.modal.cancel()
    view = harness.modal.view_state()
    assert view is not None and view.message == CANCELLING_MESSAGE
    assert view.large_text is False
    harness.run_until_idle()

    assert library.revision == revision
    assert harness.notes == []
    assert harness.resumes == 1
    assert harness.modal.view_state() is None


def test_failure_shows_a_notice(tmp_path: Path, monkeypatch) -> None:
    def broken(conn, preset_root, on_progress):
        raise OSError("disk gone")

    monkeypatch.setattr(preset_rescan_controls, "build_index", broken)
    harness = _Harness(PresetLibrary.in_memory(), tmp_path)

    harness.controller.start()
    harness.run_until_idle()

    view = harness.modal.view_state()
    assert view is not None
    assert view.message == FAILED_TITLE
    assert view.body == "disk gone"
    assert harness.resumes == 1


def test_start_while_busy_is_ignored(tmp_path: Path, monkeypatch) -> None:
    gate = threading.Event()

    def blocked(conn, preset_root, on_progress):
        gate.wait(5)
        return None

    monkeypatch.setattr(preset_rescan_controls, "build_index", blocked)
    harness = _Harness(PresetLibrary.in_memory(), tmp_path)
    harness.controller.start()
    harness.controller.start()
    assert harness.holds == 1
    gate.set()
    harness.run_until_idle()
