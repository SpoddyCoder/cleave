"""Tests for FFmpeg sidecar lookup."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cleave.ffmpeg import ffmpeg_executable


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
