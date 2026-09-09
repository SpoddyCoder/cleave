"""Accept/reject rules for paths the user tries to open."""

from __future__ import annotations

from pathlib import Path

from cleave.open_target import (
    OpenTargetKind,
    classify_open_target,
    looks_like_windows_path,
    open_target_rejection,
)
from cleave.project import PROJECT_FILENAME


def _wav(tmp_path: Path, name: str = "song.wav") -> Path:
    path = tmp_path / name
    path.write_bytes(b"RIFF")
    return path


def _project(tmp_path: Path, name: str = "song") -> Path:
    path = tmp_path / name
    path.mkdir()
    (path / PROJECT_FILENAME).write_text("slug: song\n")
    return path


def test_wav_file_is_audio(tmp_path: Path) -> None:
    target = classify_open_target(_wav(tmp_path))
    assert target is not None
    assert target.kind is OpenTargetKind.AUDIO


def test_wav_suffix_is_case_insensitive(tmp_path: Path) -> None:
    target = classify_open_target(_wav(tmp_path, "SONG.WAV"))
    assert target is not None
    assert target.kind is OpenTargetKind.AUDIO


def test_project_directory_is_project(tmp_path: Path) -> None:
    project = _project(tmp_path)
    target = classify_open_target(project)
    assert target is not None
    assert target.kind is OpenTargetKind.PROJECT
    assert target.path == project


def test_non_wav_file_rejected(tmp_path: Path) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("hello")
    assert classify_open_target(notes) is None


def test_empty_directory_rejected(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert classify_open_target(empty) is None


def test_directory_without_manifest_rejected(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()
    (documents / "song.wav").write_bytes(b"RIFF")
    assert classify_open_target(documents) is None


def test_missing_path_rejected(tmp_path: Path) -> None:
    assert classify_open_target(tmp_path / "nope.wav") is None


def test_windows_path_on_posix_does_not_raise() -> None:
    assert classify_open_target(Path(r"C:\Users\me\song.wav")) is None
    assert looks_like_windows_path(r"C:\Users\me")
    assert looks_like_windows_path("d:/Music")
    assert not looks_like_windows_path("/mnt/c/Users")


def test_rejection_messages(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    notes = tmp_path / "notes.txt"
    notes.write_text("hello")

    assert PROJECT_FILENAME in open_target_rejection(empty)
    assert ".wav" in open_target_rejection(notes)
    assert "not found" == open_target_rejection(tmp_path / "gone.wav")
    assert "/mnt/c" in open_target_rejection(Path(r"C:\Music\song.wav"))
