"""Attach a windowed Windows PE to its parent console, if any."""

from __future__ import annotations

import os
import sys

ATTACH_PARENT_PROCESS = -1
STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE = -12


class _EofStdin:
    """Readable dummy that always returns EOF."""

    def read(self, *_args: object, **_kwargs: object) -> str:
        return ""

    def readline(self, *_args: object, **_kwargs: object) -> str:
        return ""

    def readlines(self, *_args: object, **_kwargs: object) -> list[str]:
        return []

    def __iter__(self):
        return iter(())

    def close(self) -> None:
        return None

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False


def _bind_nul_stdio() -> None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
    sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")
    sys.stdin = _EofStdin()


def attach_parent_console() -> bool:
    """Attach to the parent console when this is a windowed Windows process.

    Returns True when attached so callers can print to that console. Returns
    False on non-Windows, or when launched from Explorer / Start Menu / drop
    on the exe (stdio then goes to NUL so print does not crash on None).
    """
    if sys.platform != "win32":
        return False

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    attach = kernel32.AttachConsole
    attach.argtypes = [wintypes.DWORD]
    attach.restype = wintypes.BOOL
    if not attach(ATTACH_PARENT_PROCESS):
        _bind_nul_stdio()
        return False

    import msvcrt

    sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
    sys.stdout = open(
        "CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1
    )
    sys.stderr = open(
        "CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1
    )

    set_handle = kernel32.SetStdHandle
    set_handle.argtypes = [wintypes.DWORD, wintypes.HANDLE]
    set_handle.restype = wintypes.BOOL
    set_handle(STD_INPUT_HANDLE, msvcrt.get_osfhandle(sys.stdin.fileno()))
    set_handle(STD_OUTPUT_HANDLE, msvcrt.get_osfhandle(sys.stdout.fileno()))
    set_handle(STD_ERROR_HANDLE, msvcrt.get_osfhandle(sys.stderr.fileno()))
    return True
