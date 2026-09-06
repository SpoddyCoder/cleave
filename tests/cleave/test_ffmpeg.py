"""Tests for FFmpeg sidecar lookup."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from cleave.ffmpeg import ffmpeg_executable, sidecar_ffmpeg_on_path


def test_ffmpeg_executable_checkout_which(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr("cleave.ffmpeg.shutil.which", lambda _name: "/usr/bin/ffmpeg")
    assert ffmpeg_executable() == "/usr/bin/ffmpeg"


def test_ffmpeg_executable_checkout_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr("cleave.ffmpeg.shutil.which", lambda _name: None)
    with pytest.raises(FileNotFoundError, match="ffmpeg not found on PATH"):
        ffmpeg_executable()


def test_ffmpeg_executable_frozen_missing_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "cleave.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(FileNotFoundError, match="ffmpeg.exe"):
        ffmpeg_executable()


def test_ffmpeg_executable_frozen_present_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "cleave.exe"
    sidecar = tmp_path / "ffmpeg.exe"
    sidecar.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "win32")
    assert ffmpeg_executable() == str(sidecar.resolve())


def test_ffmpeg_executable_frozen_missing_linux(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "cleave"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(FileNotFoundError, match=str(tmp_path / "ffmpeg")):
        ffmpeg_executable()


def test_ffmpeg_executable_frozen_ignores_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "cleave.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr("cleave.ffmpeg.shutil.which", lambda _name: "/usr/bin/ffmpeg")
    with pytest.raises(FileNotFoundError, match="ffmpeg.exe"):
        ffmpeg_executable()


def test_sidecar_ffmpeg_on_path_checkout_leaves_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setenv("PATH", "/usr/bin")
    with sidecar_ffmpeg_on_path():
        assert os.environ["PATH"] == "/usr/bin"
    assert os.environ["PATH"] == "/usr/bin"


def test_sidecar_ffmpeg_on_path_frozen_prepends_install_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "cleave.exe"
    (tmp_path / "ffmpeg.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("PATH", r"C:\Windows\system32")
    with sidecar_ffmpeg_on_path():
        assert os.environ["PATH"].split(os.pathsep)[0] == str(tmp_path.resolve())
    assert os.environ["PATH"] == r"C:\Windows\system32"


def test_sidecar_ffmpeg_on_path_frozen_missing_names_sidecar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "cleave.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(FileNotFoundError, match="ffmpeg.exe"):
        with sidecar_ffmpeg_on_path():
            pass
