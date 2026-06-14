"""Tests for Cleave filesystem path helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from cleave.config import VIZ_CONFIG_FILENAME
from cleave.paths import (
    data_dir,
    default_project_config,
    project_slug,
    repo_root,
    resolve_project,
    validate_project_slug,
)


def test_data_dir_uses_cleave_data_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom = tmp_path / "custom-data"
    monkeypatch.setenv("CLEAVE_DATA", str(custom))
    assert data_dir() == custom.resolve()


def test_data_dir_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLEAVE_DATA", raising=False)
    assert data_dir() == repo_root().resolve()


def test_resolve_project_by_slug(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "sights-and-sounds-26"
    project.mkdir(parents=True)

    assert resolve_project("sights-and-sounds-26") == project.resolve()


def test_resolve_project_by_relative_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "sights-and-sounds-26"
    project.mkdir(parents=True)

    assert resolve_project("projects/sights-and-sounds-26") == project.resolve()


def test_resolve_project_by_absolute_path(tmp_path: Path) -> None:
    project = tmp_path / "my-project"
    project.mkdir()

    assert resolve_project(project) == project.resolve()


def test_resolve_project_missing_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    (tmp_path / "projects").mkdir()

    with pytest.raises(FileNotFoundError, match="project not found"):
        resolve_project("missing-track")


def test_project_slug() -> None:
    assert project_slug(Path("/music/sights-and-sounds-26.flac")) == "sights-and-sounds-26"
    assert project_slug(Path("song.mp3")) == "song"


def test_default_project_config() -> None:
    project = Path("/tmp/my-project")
    assert default_project_config(project) == project / VIZ_CONFIG_FILENAME


@pytest.mark.parametrize(
    "slug",
    ["foo/bar", r"foo\bar", ".", ".."],
)
def test_validate_project_slug_rejects_invalid(slug: str) -> None:
    with pytest.raises(ValueError, match="invalid project slug"):
        validate_project_slug(slug)


def test_resolve_project_rejects_invalid_slug(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    (tmp_path / "projects").mkdir()

    with pytest.raises(ValueError, match="invalid project slug"):
        resolve_project("bad/slug")
