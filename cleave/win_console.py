"""Attach a windowed Windows PE to its parent console, if any."""

from __future__ import annotations

import os
import sys

ATTACH_PARENT_PROCESS = -1
STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE = -12
FILE_TYPE_DISK = 0x0001
FILE_TYPE_PIPE = 0x0003


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


def _handle_file_type(kernel32, handle) -> int:
    kind = kernel32.GetFileType(handle)
    if not isinstance(kind, int):
        return 0
    return kind & 0xFFFF


def _bind_os_handle(kernel32, n_std: int, mode: str):
    """Python file object for an existing pipe or disk std handle, or None."""
    handle = kernel32.GetStdHandle(n_std)
    if _handle_file_type(kernel32, handle) not in (FILE_TYPE_DISK, FILE_TYPE_PIPE):
        return None
    try:
        handle_int = int(handle)
    except (TypeError, ValueError):
        value = getattr(handle, "value", None)
        try:
            handle_int = int(value)
        except (TypeError, ValueError):
            return None
    import msvcrt

    flags = os.O_RDONLY if "r" in mode else os.O_WRONLY
    flags |= getattr(os, "O_BINARY", 0)
    try:
        fd = msvcrt.open_osfhandle(handle_int, flags)
        return open(fd, mode, encoding="utf-8", errors="replace", buffering=1)
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def _bind_redirected_stdio(kernel32) -> bool:
    """Keep pipe/file stdio from a capturing parent. Skip AttachConsole.

    Windowed PEs start with sys.stdout is None even when CreateProcess passed
    pipes (CI ``capture_output=True``). AttachConsole plus CONOUT$ would steal
    that capture, so ``--version`` prints to the parent console and the pipe
    stays empty.
    """
    stdout = _bind_os_handle(kernel32, STD_OUTPUT_HANDLE, "w")
    stderr = _bind_os_handle(kernel32, STD_ERROR_HANDLE, "w")
    if stdout is None and stderr is None:
        return False
    stdin = _bind_os_handle(kernel32, STD_INPUT_HANDLE, "r")
    sys.stdout = stdout or open(os.devnull, "w", encoding="utf-8", errors="replace")
    sys.stderr = stderr or sys.stdout
    sys.stdin = stdin if stdin is not None else _EofStdin()
    return True


def attach_parent_console() -> bool:
    """Attach to the parent console when this is a windowed Windows process.

    Returns True when stdout is usable: a redirected pipe or file, or an
    attached parent console. Returns False on non-Windows, or when launched
    from Explorer / Start Menu / drop on the exe (stdio then goes to NUL so
    print does not crash on None).
    """
    if sys.platform != "win32":
        return False

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel32.GetStdHandle.restype = wintypes.HANDLE
    kernel32.GetFileType.argtypes = [wintypes.HANDLE]
    kernel32.GetFileType.restype = wintypes.DWORD
    if _bind_redirected_stdio(kernel32):
        return True

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
