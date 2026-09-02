"""Tests for libprojectM ctypes search order."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cleave.projectm import CORE_LINUX_SONAME, CORE_WINDOWS_DLL, library_candidates
from cleave.projectm_playlist import (
    PLAYLIST_LINUX_SONAMES,
    PLAYLIST_WINDOWS_DLL,
    library_candidates as playlist_library_candidates,
)


@pytest.fixture
def _no_pkg_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cleave.projectm._pkg_config_candidates", lambda: [])
    monkeypatch.setattr("cleave.projectm_playlist._pkg_config_candidates", lambda: [])


def test_library_candidates_checkout_linux_env_first(
    monkeypatch: pytest.MonkeyPatch, _no_pkg_config: None
) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("PROJECTM_LIB", "/custom/libprojectM-4.so")
    candidates = library_candidates()
    assert candidates[0] == "/custom/libprojectM-4.so"
    assert CORE_LINUX_SONAME in candidates[-1] or any(
        CORE_LINUX_SONAME in item for item in candidates
    )


def test_library_candidates_frozen_prepends_install_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _no_pkg_config: None
) -> None:
    exe = tmp_path / "cleave"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("PROJECTM_LIB", "/custom/libprojectM-4.so")
    candidates = library_candidates()
    assert candidates[0] == str((tmp_path / CORE_LINUX_SONAME).resolve())
    assert candidates[1] == "/custom/libprojectM-4.so"


def test_library_candidates_win32_prepends_dll(
    monkeypatch: pytest.MonkeyPatch, _no_pkg_config: None
) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("PROJECTM_LIB", r"C:\custom\projectM-4.dll")
    from cleave.paths import repo_root

    candidates = library_candidates()
    assert candidates[0] == str(repo_root() / CORE_WINDOWS_DLL)
    assert candidates[1] == r"C:\custom\projectM-4.dll"
    assert all("libprojectM-4.so" not in item for item in candidates)


def test_playlist_library_candidates_frozen_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _no_pkg_config: None
) -> None:
    exe = tmp_path / "cleave.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("PROJECTM_PLAYLIST_LIB", raising=False)
    candidates = playlist_library_candidates()
    assert candidates[0] == str((tmp_path / PLAYLIST_WINDOWS_DLL).resolve())


def test_playlist_library_candidates_frozen_linux_so_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _no_pkg_config: None
) -> None:
    exe = tmp_path / "cleave"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("PROJECTM_PLAYLIST_LIB", raising=False)
    candidates = playlist_library_candidates()
    expected = [str((tmp_path / name).resolve()) for name in PLAYLIST_LINUX_SONAMES]
    assert candidates[: len(expected)] == expected
