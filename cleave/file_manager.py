"""Open a folder in the desktop file manager."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False


def open_folder(folder: Path) -> None:
    """Open *folder* in Explorer, Finder, or the XDG file manager.

    Under WSL without ``xdg-open``, opens it in Windows Explorer. Raises
    OSError when no file manager can be started.
    """
    if sys.platform == "win32":
        os.startfile(folder)  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
        return
    if shutil.which("xdg-open"):
        subprocess.Popen(
            ["xdg-open", str(folder)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    if _is_wsl() and shutil.which("explorer.exe") and shutil.which("wslpath"):
        try:
            windows_path = subprocess.run(
                ["wslpath", "-w", str(folder)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except subprocess.CalledProcessError as exc:
            raise OSError(f"wslpath failed for {folder}") from exc
        # explorer.exe exits 1 even when it opens the folder.
        subprocess.Popen(["explorer.exe", windows_path])
        return
    raise OSError("no file manager found (install xdg-utils)")
