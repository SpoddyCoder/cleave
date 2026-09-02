"""Tests for Cleave filesystem path helpers."""

from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

import pytest

from cleave.config import VIZ_CONFIG_FILENAME
from cleave.paths import (
    data_dir,
    default_preset_root,
    default_project_config,
    default_texture_paths,
    install_dir,
    is_frozen,
    project_slug,
    repo_root,
    resource_dir,
    resolve_project,
    validate_project_slug,
    windows_documents_dir,
)


def test_data_dir_uses_cleave_data_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom = tmp_path / "custom-data"
    monkeypatch.setenv("CLEAVE_DATA", str(custom))
    assert data_dir() == custom.resolve()


def test_data_dir_cleave_data_overrides_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom = tmp_path / "win-data"
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("CLEAVE_DATA", str(custom))
    assert data_dir() == custom.resolve()


def test_data_dir_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("CLEAVE_DATA", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    expected = (Path.home() / ".local" / "share" / "cleave").resolve()
    assert data_dir() == expected


def test_data_dir_uses_xdg_data_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("CLEAVE_DATA", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert data_dir() == (tmp_path / "cleave").resolve()


def test_data_dir_windows_known_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("CLEAVE_DATA", raising=False)
    docs = tmp_path / "Documents"
    monkeypatch.setattr("cleave.paths.windows_documents_dir", lambda: docs)
    assert data_dir() == (docs / "cleave").resolve()


def test_data_dir_windows_documents_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("CLEAVE_DATA", raising=False)
    monkeypatch.setattr(
        "cleave.paths.windows_documents_dir",
        lambda: Path.home() / "Documents",
    )
    expected = (Path.home() / "Documents" / "cleave").resolve()
    assert data_dir() == expected


def test_windows_documents_dir_does_not_import_hresult_from_wintypes() -> None:
    source = (repo_root() / "cleave" / "paths.py").read_text(encoding="utf-8")
    wintypes_imports: list[set[str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module == "ctypes.wintypes":
            names = {alias.name for alias in node.names}
            assert "HRESULT" not in names
            wintypes_imports.append(names)
    assert wintypes_imports, "expected ctypes.wintypes import in cleave/paths.py"
    assert "HRESULT" not in source


def test_windows_documents_dir_import_error_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def fail_ctypes(name: str, *args: object, **kwargs: object) -> object:
        if name == "ctypes" or name.startswith("ctypes."):
            raise ImportError("simulated ctypes miss")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_ctypes)
    assert windows_documents_dir() == Path.home() / "Documents"


def test_default_preset_root_follows_data_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    assert default_preset_root() == (tmp_path / "presets").resolve()
    assert default_texture_paths() == ((tmp_path / "textures").resolve(),)


def test_default_preset_root_follows_windows_data_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("CLEAVE_DATA", raising=False)
    docs = tmp_path / "Docs"
    monkeypatch.setattr("cleave.paths.windows_documents_dir", lambda: docs)
    assert default_preset_root() == (docs / "cleave" / "presets").resolve()
    assert default_texture_paths() == ((docs / "cleave" / "textures").resolve(),)


def test_is_frozen_false_by_default() -> None:
    assert is_frozen() is bool(getattr(sys, "frozen", False))


def test_install_dir_and_resource_dir_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert install_dir() == repo_root()
    assert resource_dir() == repo_root()


def test_install_dir_and_resource_dir_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "dist" / "cleave" / "cleave.exe"
    meipass = tmp_path / "dist" / "cleave" / "_internal"
    meipass.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    assert install_dir() == exe.parent.resolve()
    assert resource_dir() == meipass.resolve()
    assert install_dir() != resource_dir()


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


def test_material_icons_ttf_is_present() -> None:
    ttf = repo_root() / "assets" / "fonts" / "MaterialIcons-Regular.ttf"
    assert ttf.is_file()


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
