"""Tests for parent-console attach on windowed Windows builds."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from cleave.win_console import (
    ATTACH_PARENT_PROCESS,
    STD_ERROR_HANDLE,
    STD_INPUT_HANDLE,
    STD_OUTPUT_HANDLE,
    attach_parent_console,
)


def test_attach_parent_console_noop_off_windows() -> None:
    if sys.platform == "win32":
        pytest.skip("Linux/macOS gate only")
    stdin, stdout, stderr = sys.stdin, sys.stdout, sys.stderr
    assert attach_parent_console() is False
    assert sys.stdin is stdin
    assert sys.stdout is stdout
    assert sys.stderr is stderr


def test_attach_parent_console_success_rebinds_stdio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "stdin", sys.stdin)
    monkeypatch.setattr(sys, "stdout", sys.stdout)
    monkeypatch.setattr(sys, "stderr", sys.stderr)

    kernel32 = MagicMock()
    kernel32.AttachConsole.return_value = 1
    windll = MagicMock(kernel32=kernel32)
    fake_msvcrt = MagicMock()
    fake_msvcrt.get_osfhandle.side_effect = lambda fd: 100 + fd

    conin = MagicMock()
    conin.fileno.return_value = 0
    conout_out = MagicMock()
    conout_out.fileno.return_value = 1
    conout_err = MagicMock()
    conout_err.fileno.return_value = 2
    opened: list[str] = []

    def fake_open(name: str, mode: str = "r", **_kwargs: object) -> MagicMock:
        opened.append(name)
        if name == "CONIN$":
            return conin
        if name == "CONOUT$" and mode.startswith("w"):
            return conout_err if len(opened) > 2 else conout_out
        raise AssertionError(f"unexpected open({name!r}, {mode!r})")

    with (
        patch("ctypes.windll", windll, create=True),
        patch.dict(sys.modules, {"msvcrt": fake_msvcrt}),
        patch("builtins.open", fake_open),
    ):
        assert attach_parent_console() is True

    assert sys.stdin is conin
    assert sys.stdout is conout_out
    assert sys.stderr is conout_err
    kernel32.AttachConsole.assert_called_once_with(ATTACH_PARENT_PROCESS)
    kernel32.SetStdHandle.assert_any_call(STD_INPUT_HANDLE, 100)
    kernel32.SetStdHandle.assert_any_call(STD_OUTPUT_HANDLE, 101)
    kernel32.SetStdHandle.assert_any_call(STD_ERROR_HANDLE, 102)


def test_attach_parent_console_failure_uses_devnull(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "stdin", sys.stdin)
    monkeypatch.setattr(sys, "stdout", sys.stdout)
    monkeypatch.setattr(sys, "stderr", sys.stderr)

    kernel32 = MagicMock()
    kernel32.AttachConsole.return_value = 0
    windll = MagicMock(kernel32=kernel32)

    with patch("ctypes.windll", windll, create=True):
        assert attach_parent_console() is False

    assert sys.stdout.name == os.devnull
    assert sys.stderr.name == os.devnull
    assert sys.stdin.readline() == ""
    sys.stdout.write("silent")
    sys.stderr.write("silent")
    sys.stdout.close()
    sys.stderr.close()
    kernel32.SetStdHandle.assert_not_called()
