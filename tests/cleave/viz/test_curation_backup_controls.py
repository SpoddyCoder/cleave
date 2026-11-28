"""Tests for Settings > Back up / Restore preset curation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cleave.preset_curation import back_up_library
from cleave.preset_library import PresetLibrary
from cleave.viz.curation_backup_controls import (
    BACK_UP_LABEL,
    BACK_UP_TITLE,
    BACKED_UP_TITLE,
    MERGE_LABEL,
    NOTHING_TITLE,
    REPLACE_LABEL,
    RESTORE_FAILED_TITLE,
    RESTORE_TITLE,
    SHOW_IN_FOLDER,
    CurationBackupController,
)
from cleave.viz.modal import ModalHost


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class _Harness:
    def __init__(self, library: PresetLibrary, backups: Path) -> None:
        self.modal = ModalHost()
        self.notes: list[str] = []
        self.opened: list[Path] = []
        self.picks: list[Callable[[Path], None]] = []
        self.controller = CurationBackupController(
            library,
            self.modal,
            backups_dir=lambda: backups,
            prompt_pick_backup=self.picks.append,
            open_folder=self.opened.append,
            on_notification=self.notes.append,
        )

    def press(self, label: str) -> None:
        view = self.modal.view_state()
        assert view is not None
        self.modal.activate_option(view.options.index(label))


def _library(tmp_path: Path) -> tuple[PresetLibrary, Path, Path]:
    root = tmp_path / "presets"
    a = _write(root / "a.milk", "a")
    b = _write(root / "b.milk", "b")
    library = PresetLibrary.in_memory()
    library.index(root)
    return library, a, b


def test_back_up_with_nothing_curated_says_so(tmp_path: Path) -> None:
    library, _, _ = _library(tmp_path)
    harness = _Harness(library, tmp_path / "backups")
    harness.controller.prompt_back_up()
    view = harness.modal.view_state()
    assert view is not None and view.message == NOTHING_TITLE
    assert not (tmp_path / "backups").exists()


def test_back_up_writes_file_and_offers_folder(tmp_path: Path) -> None:
    library, a, _ = _library(tmp_path)
    library.set_role(a, "lead")
    backups = tmp_path / "backups"
    harness = _Harness(library, backups)

    harness.controller.prompt_back_up()

    confirm = harness.modal.view_state()
    assert confirm is not None and confirm.message == BACK_UP_TITLE
    assert confirm.options == (BACK_UP_LABEL, "Cancel")
    lines = {line.label: line.value for line in confirm.labeled_lines}
    assert lines == {
        "Contains": "1 preset: 0 favourites, 1 role, 0 blacklisted",
        "Folder": str(backups),
    }
    assert not backups.exists()
    harness.press(BACK_UP_LABEL)

    view = harness.modal.view_state()
    assert view is not None and view.message == BACKED_UP_TITLE
    assert view.options == (SHOW_IN_FOLDER, "OK")
    assert len(list(backups.glob("*.json"))) == 1
    harness.press(SHOW_IN_FOLDER)
    assert harness.opened == [backups]


def test_restore_previews_then_merges(tmp_path: Path) -> None:
    library, a, b = _library(tmp_path)
    library.set_role(a, "bed")
    backups = tmp_path / "backups"
    source, _ = back_up_library(library, tmp_path / "elsewhere")
    library.set_role(a, "lead")
    library.set_favourite(b, True)
    harness = _Harness(library, backups)

    harness.controller.prompt_restore()
    assert len(harness.picks) == 1
    harness.picks[0](source)

    view = harness.modal.view_state()
    assert view is not None and view.message == RESTORE_TITLE
    assert view.options == (MERGE_LABEL, REPLACE_LABEL, "Cancel")
    lines = {line.label: line.value for line in view.labeled_lines}
    assert lines["In your presets"] == "1 of 1"
    assert "1 preset gets a different role" in lines["Role changes"]

    harness.press(MERGE_LABEL)

    assert library.role_of(a) == "bed"
    assert library.is_favourite(b)
    assert len(list(backups.glob("*.json"))) == 1
    assert harness.notes and harness.notes[0].startswith("Preset curation merged")


def test_restore_replace_and_cancel(tmp_path: Path) -> None:
    library, a, b = _library(tmp_path)
    library.set_role(a, "bed")
    source, _ = back_up_library(library, tmp_path / "elsewhere")
    library.set_favourite(b, True)
    harness = _Harness(library, tmp_path / "backups")

    harness.controller.restore_from(source)
    harness.press("Cancel")
    assert library.is_favourite(b)

    harness.controller.restore_from(source)
    harness.press(REPLACE_LABEL)
    assert not library.is_favourite(b)
    assert library.role_of(a) == "bed"


def test_restore_bad_file_shows_error(tmp_path: Path) -> None:
    library, _, _ = _library(tmp_path)
    harness = _Harness(library, tmp_path / "backups")
    harness.controller.restore_from(_write(tmp_path / "notes.json", "{}"))
    view = harness.modal.view_state()
    assert view is not None and view.message == RESTORE_FAILED_TITLE


def test_back_up_cancel_writes_nothing(tmp_path: Path) -> None:
    library, a, _ = _library(tmp_path)
    library.set_favourite(a, True)
    backups = tmp_path / "backups"
    harness = _Harness(library, backups)
    harness.controller.prompt_back_up()
    harness.press("Cancel")
    assert harness.modal.view_state() is None
    assert not backups.exists()
