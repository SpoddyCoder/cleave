"""Tests for cleave.project manifest helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from cleave.project import (
    PROJECT_FILENAME,
    ProjectManifest,
    load_manifest,
    manifest_path,
    mix_path,
    resolve_mix_path,
    rewrite_manifest_slug,
    write_manifest,
)


def test_write_and_load_manifest(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    original = tmp_path / "source.flac"
    original.write_bytes(b"audio")

    when = datetime(2026, 6, 8, 20, 15, tzinfo=timezone.utc)
    path = write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=original,
        demucs_model="htdemucs",
        separated_at=when,
    )

    assert path == manifest_path(project)
    manifest = load_manifest(project)
    assert manifest == ProjectManifest(
        version=1,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=str(original.resolve()),
        separated_at="2026-06-08T20:15:00+00:00",
        demucs_model="htdemucs",
    )


def test_mix_path_from_manifest(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    mix_file = project / "song.flac"
    mix_file.write_bytes(b"mix")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "elsewhere.flac",
        demucs_model="htdemucs",
    )

    assert mix_path(project) == mix_file.resolve()


def test_load_manifest_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="project manifest not found"):
        load_manifest(tmp_path)


def test_resolve_mix_path_uses_manifest(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    mix_file = project / "song.flac"
    mix_file.write_bytes(b"mix")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "elsewhere.flac",
        demucs_model="htdemucs",
    )

    assert resolve_mix_path(project) == mix_file.resolve()


def test_resolve_mix_path_missing_manifest_exits(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()

    with pytest.raises(SystemExit) as exc_info:
        resolve_mix_path(project)
    assert exc_info.value.code == 1


def test_resolve_mix_path_missing_mix_exits(tmp_path: Path, capsys) -> None:
    project = tmp_path / "song"
    project.mkdir()
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "elsewhere.flac",
        demucs_model="htdemucs",
    )

    with pytest.raises(SystemExit) as exc_info:
        resolve_mix_path(project)
    assert exc_info.value.code == 1
    assert "audio not found" in capsys.readouterr().err


def test_manifest_round_trip_yaml(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    original = tmp_path / "source.flac"
    original.write_bytes(b"audio")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=original,
        demucs_model="htdemucs_ft",
    )

    with (project / PROJECT_FILENAME).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    assert data["version"] == 1
    assert data["slug"] == "song"
    assert data["mix"]["filename"] == "song.flac"
    assert data["ingest"]["demucs_model"] == "htdemucs_ft"


def test_manifest_restored_from_round_trip(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    manifest = ProjectManifest(
        version=1,
        slug="song",
        mix_filename="song.flac",
        original_path=str((tmp_path / "source.flac").resolve()),
        separated_at="2026-06-08T20:15:00+00:00",
        demucs_model="htdemucs",
        restored_from="original-slug",
    )
    with (project / PROJECT_FILENAME).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest.to_dict(), handle, sort_keys=False)

    loaded = load_manifest(project)
    assert loaded == manifest

    with (project / PROJECT_FILENAME).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert data["restored-from"] == "original-slug"


def test_manifest_omits_restored_from_when_none(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )

    with (project / PROJECT_FILENAME).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    assert "restored-from" not in data
    assert load_manifest(project).restored_from is None


def test_rewrite_manifest_slug_updates_slug_and_restored_from(tmp_path: Path) -> None:
    project = tmp_path / "old-slug"
    project.mkdir()
    write_manifest(
        project,
        slug="old-slug",
        mix_filename="old-slug.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )

    rewrite_manifest_slug(project, "new-slug", restored_from="old-slug")

    manifest = load_manifest(project)
    assert manifest.slug == "new-slug"
    assert manifest.restored_from == "old-slug"
    assert manifest.mix_filename == "old-slug.flac"
