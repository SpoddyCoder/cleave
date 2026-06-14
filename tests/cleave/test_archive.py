"""Tests for cleave.archive backup and restore."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from cleave.archive import (
    backup_project,
    confirm_overwrite,
    resolve_backup_output,
    restore_project,
)
from cleave.extract import STEM_NAMES, stems_dir
from cleave.project import PROJECT_FILENAME, load_manifest, write_manifest


def _write_stub_stems(project: Path) -> None:
    base = stems_dir(project)
    base.mkdir(parents=True, exist_ok=True)
    for name in STEM_NAMES:
        (base / f"{name}.wav").write_bytes(b"wav")


def _complete_project(tmp_path: Path, slug: str = "my-track") -> Path:
    project = tmp_path / "projects" / slug
    project.mkdir(parents=True)
    _write_stub_stems(project)
    mix = project / f"{slug}.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug=slug,
        mix_filename=f"{slug}.flac",
        original_path=tmp_path / f"{slug}.flac",
        demucs_model="htdemucs",
    )
    (project / "signals.json").write_text('{"beats": []}')
    (project / "cleave-viz.yaml").write_text("layers: []\n")
    return project


def _project_tree(root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[str(path.relative_to(root))] = path.read_bytes()
    return files


def _write_archive_from_project(project: Path, slug: str, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(project, arcname=slug)


def test_resolve_backup_output_directory_destination(tmp_path: Path) -> None:
    dest = tmp_path / "backups"
    dest.mkdir()
    assert resolve_backup_output(dest, "song") == dest / "song.cleave-tar.gz"


def test_resolve_backup_output_explicit_cleave_tar_gz(tmp_path: Path) -> None:
    dest = tmp_path / "backups" / "custom.cleave-tar.gz"
    assert resolve_backup_output(dest, "song") == dest


def test_resolve_backup_output_explicit_tar_gz(tmp_path: Path) -> None:
    dest = tmp_path / "backups" / "custom.tar.gz"
    assert resolve_backup_output(dest, "song") == dest


def test_resolve_backup_output_creates_parent_directory(tmp_path: Path) -> None:
    dest = tmp_path / "new" / "nested" / "out"
    assert resolve_backup_output(dest, "song") == dest / "song.cleave-tar.gz"
    assert dest.is_dir()


def test_confirm_overwrite_force_returns_true() -> None:
    assert confirm_overwrite("overwrite?", force=True) is True


def test_confirm_overwrite_non_tty_returns_false() -> None:
    with patch("cleave.archive.sys.stdin.isatty", return_value=False):
        assert confirm_overwrite("overwrite?", force=False) is False


def test_confirm_overwrite_tty_yes() -> None:
    with (
        patch("cleave.archive.sys.stdin.isatty", return_value=True),
        patch("cleave.archive.input", return_value="y"),
    ):
        assert confirm_overwrite("overwrite?", force=False) is True


def test_confirm_overwrite_tty_no() -> None:
    with (
        patch("cleave.archive.sys.stdin.isatty", return_value=True),
        patch("cleave.archive.input", return_value="n"),
    ):
        assert confirm_overwrite("overwrite?", force=False) is False


def test_backup_default_output_name_in_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    dest = tmp_path / "backups"
    dest.mkdir()

    output = backup_project(project, dest, force=False)

    assert output == dest / "my-track.cleave-tar.gz"
    assert output.is_file()


def test_backup_explicit_output_filename(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    output_path = tmp_path / "backups" / "custom-name.cleave-tar.gz"

    output = backup_project(project, output_path, force=False)

    assert output == output_path.resolve()
    assert output.is_file()


def test_backup_round_trip_restores_identical_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    original_tree = _project_tree(project)
    archive = backup_project(project, tmp_path / "backups", force=False)

    import shutil

    shutil.rmtree(project)

    restored = restore_project(archive, force=False)

    assert restored == project.resolve()
    assert _project_tree(restored) == original_tree


def test_backup_existing_archive_prompt_no_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    dest = tmp_path / "backups"
    dest.mkdir()
    archive = dest / "my-track.cleave-tar.gz"
    archive.write_bytes(b"existing")

    with (
        patch("cleave.archive.sys.stdin.isatty", return_value=True),
        patch("cleave.archive.input", return_value="n"),
    ):
        with pytest.raises(FileExistsError, match="backup already exists"):
            backup_project(project, dest, force=False)

    assert archive.read_bytes() == b"existing"


def test_backup_existing_archive_prompt_yes_overwrites(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    dest = tmp_path / "backups"
    dest.mkdir()
    archive = dest / "my-track.cleave-tar.gz"
    archive.write_bytes(b"existing")

    with (
        patch("cleave.archive.sys.stdin.isatty", return_value=True),
        patch("cleave.archive.input", return_value="y"),
    ):
        output = backup_project(project, dest, force=False)

    assert output == archive.resolve()
    assert archive.read_bytes() != b"existing"
    with tarfile.open(archive, "r:gz") as tar:
        names = {m.name for m in tar.getmembers()}
    assert "my-track/project.yaml" in names


def test_backup_force_overwrites_without_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    dest = tmp_path / "backups"
    dest.mkdir()
    archive = dest / "my-track.cleave-tar.gz"
    archive.write_bytes(b"existing")

    with patch("cleave.archive.input") as mock_input:
        output = backup_project(project, dest, force=True)

    mock_input.assert_not_called()
    assert output == archive.resolve()
    with tarfile.open(archive, "r:gz") as tar:
        assert tar.getnames()


def test_backup_non_tty_existing_aborts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    dest = tmp_path / "backups"
    dest.mkdir()
    archive = dest / "my-track.cleave-tar.gz"
    archive.write_bytes(b"existing")

    with patch("cleave.archive.sys.stdin.isatty", return_value=False):
        with pytest.raises(FileExistsError, match="backup already exists"):
            backup_project(project, dest, force=False)

    assert archive.read_bytes() == b"existing"


def test_restore_archive_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="archive not found"):
        restore_project(tmp_path / "missing.cleave-tar.gz")


def test_restore_empty_archive_raises_value_error(tmp_path: Path) -> None:
    archive = tmp_path / "empty.cleave-tar.gz"
    with tarfile.open(archive, "w:gz"):
        pass

    with pytest.raises(ValueError, match="exactly one top-level directory"):
        restore_project(archive)


def test_restore_two_top_level_dirs_raises_value_error(tmp_path: Path) -> None:
    archive = tmp_path / "bad.cleave-tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in ("alpha/one.txt", "beta/two.txt"):
            data = b"x"
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

    with pytest.raises(ValueError, match="exactly one top-level directory"):
        restore_project(archive)


def test_restore_slug_dir_mismatch_raises_value_error(tmp_path: Path) -> None:
    project = tmp_path / "wrong-dir"
    project.mkdir()
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )
    archive = tmp_path / "mismatch.cleave-tar.gz"
    _write_archive_from_project(project, "wrong-dir", archive)

    with pytest.raises(ValueError, match="does not match manifest slug"):
        restore_project(archive)


def test_restore_as_slug_rewrites_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path, slug="song")
    archive = backup_project(project, tmp_path / "backups", force=False)

    restored = restore_project(archive, as_slug="song-copy", force=False)

    assert restored == tmp_path / "projects" / "song-copy"
    manifest = load_manifest(restored)
    assert manifest.slug == "song-copy"
    assert manifest.restored_from == "song"


def test_restore_as_invalid_slug_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path, slug="song")
    archive = backup_project(project, tmp_path / "backups", force=False)

    with pytest.raises(ValueError, match="invalid project slug"):
        restore_project(archive, as_slug="../bad", force=False)


def test_restore_existing_project_prompt_no_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path, slug="song")
    marker = project / "marker.txt"
    marker.write_text("keep me")
    original_tree = _project_tree(project)
    archive = backup_project(project, tmp_path / "backups", force=False)

    with (
        patch("cleave.archive.sys.stdin.isatty", return_value=True),
        patch("cleave.archive.input", return_value="n"),
    ):
        with pytest.raises(FileExistsError, match="project already exists"):
            restore_project(archive, force=False)

    assert marker.read_text() == "keep me"
    assert _project_tree(project) == original_tree


def test_restore_existing_project_prompt_yes_replaces(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path, slug="song")
    archive = backup_project(project, tmp_path / "backups", force=False)
    (project / "marker.txt").write_text("old")

    with (
        patch("cleave.archive.sys.stdin.isatty", return_value=True),
        patch("cleave.archive.input", return_value="y"),
    ):
        restored = restore_project(archive, force=False)

    assert restored == project.resolve()
    assert not (project / "marker.txt").exists()
    assert load_manifest(project).slug == "song"


def test_restore_force_replaces_without_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path, slug="song")
    archive = backup_project(project, tmp_path / "backups", force=False)
    (project / "marker.txt").write_text("old")

    with patch("cleave.archive.input") as mock_input:
        restored = restore_project(archive, force=True)

    mock_input.assert_not_called()
    assert restored == project.resolve()
    assert not (project / "marker.txt").exists()


def test_restore_non_tty_existing_aborts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path, slug="song")
    archive = backup_project(project, tmp_path / "backups", force=False)
    marker = project / "marker.txt"
    marker.write_text("keep me")

    with patch("cleave.archive.sys.stdin.isatty", return_value=False):
        with pytest.raises(FileExistsError, match="project already exists"):
            restore_project(archive, force=False)

    assert marker.read_text() == "keep me"


def test_restore_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "evil.cleave-tar.gz"
    manifest = {
        "version": 1,
        "slug": "song",
        "mix": {"filename": "song.flac"},
        "ingest": {
            "original_path": "/tmp/source.flac",
            "separated_at": "2026-06-08T20:15:00+00:00",
            "demucs_model": "htdemucs",
        },
    }
    manifest_bytes = yaml.safe_dump(manifest, sort_keys=False).encode()

    with tarfile.open(archive, "w:gz") as tar:
        for name, data in (
            ("song/project.yaml", manifest_bytes),
            ("song/../../outside.txt", b"pwned"),
        ):
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

    with pytest.raises(ValueError, match="unsafe path in archive"):
        restore_project(archive)

    assert not (tmp_path / "outside.txt").exists()
