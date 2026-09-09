"""File picker navigation, listing, drives, and paste."""

from __future__ import annotations

from pathlib import Path

import pytest

from cleave.open_target import OpenTargetKind
from cleave.paths import drive_roots, install_dir
from cleave.project import PROJECT_FILENAME
from cleave.viz.file_picker import (
    MAX_ROWS,
    FilePicker,
    PickerAction,
    PickerFocus,
    PickerRowKind,
    picker_shortcuts,
)


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path / "cleave"))
    return tmp_path


def _project(parent: Path, name: str) -> Path:
    path = parent / name
    path.mkdir(parents=True)
    (path / PROJECT_FILENAME).write_text("slug: x\n")
    return path


def _wav(parent: Path, name: str) -> Path:
    path = parent / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF")
    return path


def _labels(picker: FilePicker) -> list[str]:
    return [row.label for row in picker.rows]


def test_starts_in_projects_dir_and_creates_it(data_root: Path) -> None:
    from cleave.paths import projects_dir

    picker = FilePicker()
    assert picker.current == projects_dir()
    assert projects_dir().is_dir()


def test_listing_order_directories_then_wavs(tmp_path: Path) -> None:
    (tmp_path / "beta").mkdir()
    (tmp_path / "alpha").mkdir()
    _wav(tmp_path, "zz.wav")
    _wav(tmp_path, "aa.wav")
    _wav(tmp_path, "notes.txt")

    picker = FilePicker(current=tmp_path)
    assert _labels(picker) == ["..", "alpha", "beta", "aa.wav", "zz.wav"]


def test_dotfiles_skipped(tmp_path: Path) -> None:
    (tmp_path / ".hidden").mkdir()
    _wav(tmp_path, ".secret.wav")
    _wav(tmp_path, "song.wav")

    picker = FilePicker(current=tmp_path)
    assert _labels(picker) == ["..", "song.wav"]


def test_project_directories_tagged(tmp_path: Path) -> None:
    _project(tmp_path, "song")
    (tmp_path / "plain").mkdir()

    picker = FilePicker(current=tmp_path)
    kinds = {row.label: row.kind for row in picker.rows}
    assert kinds["song"] is PickerRowKind.PROJECT
    assert kinds["plain"] is PickerRowKind.DIRECTORY


def test_enter_directory_and_parent_restores_highlight(tmp_path: Path) -> None:
    child = tmp_path / "music"
    _wav(child, "song.wav")

    picker = FilePicker(current=tmp_path)
    picker.handle(PickerAction.MOVE_DOWN)
    picker.handle(PickerAction.ENTER)
    assert picker.current == child

    picker.handle(PickerAction.PARENT)
    assert picker.current == tmp_path
    assert picker.selected_row is not None
    assert picker.selected_row.label == "music"


def test_parent_row_walks_up(tmp_path: Path) -> None:
    child = tmp_path / "music"
    child.mkdir()

    picker = FilePicker(current=child)
    assert picker.selected_row is not None
    assert picker.selected_row.kind is PickerRowKind.PARENT
    picker.handle(PickerAction.ACCEPT)
    assert picker.current == tmp_path


def test_accept_wav_returns_audio_target(tmp_path: Path) -> None:
    song = _wav(tmp_path, "song.wav")

    picker = FilePicker(current=tmp_path)
    picker.handle(PickerAction.MOVE_DOWN)
    target = picker.handle(PickerAction.ACCEPT)
    assert target is not None
    assert target.kind is OpenTargetKind.AUDIO
    assert target.path == song


def test_accept_project_returns_project_target(tmp_path: Path) -> None:
    project = _project(tmp_path, "song")

    picker = FilePicker(current=tmp_path)
    picker.handle(PickerAction.MOVE_DOWN)
    target = picker.handle(PickerAction.ACCEPT)
    assert target is not None
    assert target.kind is OpenTargetKind.PROJECT
    assert target.path == project


def test_right_enters_project_without_accepting(tmp_path: Path) -> None:
    project = _project(tmp_path, "song")

    picker = FilePicker(current=tmp_path)
    picker.handle(PickerAction.MOVE_DOWN)
    assert picker.handle(PickerAction.ENTER) is None
    assert picker.current == project


def test_accept_plain_directory_enters_it(tmp_path: Path) -> None:
    plain = tmp_path / "Documents"
    plain.mkdir()

    picker = FilePicker(current=tmp_path)
    picker.handle(PickerAction.MOVE_DOWN)
    assert picker.handle(PickerAction.ACCEPT) is None
    assert picker.current == plain


def test_cancel_sets_flag(tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    picker.handle(PickerAction.CANCEL)
    assert picker.cancelled


def test_move_clamps_to_listing(tmp_path: Path) -> None:
    _wav(tmp_path, "song.wav")
    picker = FilePicker(current=tmp_path)

    for _ in range(10):
        picker.handle(PickerAction.MOVE_DOWN)
    assert picker.selected_index == len(picker.rows) - 1
    for _ in range(10):
        picker.handle(PickerAction.MOVE_UP)
    assert picker.selected_index == 0


def test_listing_capped_with_note(tmp_path: Path) -> None:
    for index in range(MAX_ROWS + 5):
        (tmp_path / f"dir{index:04d}").mkdir()

    picker = FilePicker(current=tmp_path)
    view = picker.view_state()
    assert view.truncated
    assert view.rows[-1].kind is PickerRowKind.NOTE


def test_unreadable_directory_does_not_crash(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o000)
    try:
        picker = FilePicker(current=locked)
        assert _labels(picker) == [".."]
    finally:
        locked.chmod(0o755)


def test_volume_root_parent_is_drives_listing() -> None:
    picker = FilePicker(current=Path("/"))
    picker.handle(PickerAction.PARENT)
    assert picker.current is None
    assert picker.view_state().location == "Drives"
    assert all(row.kind is PickerRowKind.DRIVE for row in picker.rows)


def test_drives_listing_enters_a_volume() -> None:
    picker = FilePicker()
    picker.show_drives()
    assert picker.rows
    first = picker.rows[0]
    picker.handle(PickerAction.ENTER)
    assert picker.current == first.target


def test_drive_roots_include_filesystem_root() -> None:
    assert Path("/") in drive_roots()


def test_install_dir_is_not_a_shortcut(data_root: Path) -> None:
    targets = {shortcut.target for shortcut in picker_shortcuts()}
    assert install_dir() not in targets


def test_shortcut_focus_left_right_move_selection(
    data_root: Path, tmp_path: Path
) -> None:
    picker = FilePicker(current=tmp_path)
    picker.handle(PickerAction.TOGGLE_FOCUS)
    assert picker.focus is PickerFocus.SHORTCUTS
    assert picker.selected_shortcut == 0

    picker.handle(PickerAction.ENTER)
    assert picker.selected_shortcut == 1
    picker.handle(PickerAction.PARENT)
    assert picker.selected_shortcut == 0
    picker.handle(PickerAction.PARENT)
    assert picker.selected_shortcut == 0
    assert picker.current == tmp_path


def test_shortcut_focus_up_down_move_selection(
    data_root: Path, tmp_path: Path
) -> None:
    picker = FilePicker(current=tmp_path)
    picker.handle(PickerAction.TOGGLE_FOCUS)
    picker.handle(PickerAction.MOVE_DOWN)
    assert picker.selected_shortcut == 1
    picker.handle(PickerAction.MOVE_UP)
    assert picker.selected_shortcut == 0


def test_shortcut_focus_and_jump(data_root: Path, tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    picker.handle(PickerAction.TOGGLE_FOCUS)
    assert picker.focus is PickerFocus.SHORTCUTS

    home_index = next(
        index
        for index, shortcut in enumerate(picker.shortcuts)
        if shortcut.label == "Home"
    )
    picker.goto_shortcut(home_index)
    assert picker.current == Path.home()
    assert picker.focus is PickerFocus.LIST


def test_shortcut_drives_entry(data_root: Path, tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    drives_index = next(
        index
        for index, shortcut in enumerate(picker.shortcuts)
        if shortcut.drives
    )
    picker.goto_shortcut(drives_index)
    assert picker.current is None


def test_paste_quoted_wav_navigates_without_accepting(tmp_path: Path) -> None:
    song = _wav(tmp_path / "music", "song.wav")

    picker = FilePicker(current=tmp_path)
    picker.paste_path(f'"{song}"')
    assert picker.current == song.parent
    assert picker.selected_row is not None
    assert picker.selected_row.target == song
    assert not picker.status


def test_paste_plain_directory_enters_it(tmp_path: Path) -> None:
    plain = tmp_path / "Documents"
    plain.mkdir()

    picker = FilePicker(current=tmp_path)
    picker.paste_path(str(plain))
    assert picker.current == plain


def test_paste_missing_path_rejects_and_stays(tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    picker.paste_path(str(tmp_path / "gone.wav"))
    assert picker.current == tmp_path
    assert picker.status


def test_paste_windows_path_on_posix_messages_and_stays(tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    picker.paste_path(r'"C:\Users\me\song.wav"')
    assert picker.current == tmp_path
    assert "/mnt/c" in picker.status


def test_paste_empty_clipboard_rejects(tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    picker.paste_path(None)
    assert picker.status
    assert picker.current == tmp_path
