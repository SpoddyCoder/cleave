"""Locate the FFmpeg executable for offline render."""

from __future__ import annotations

import shutil
import sys

from cleave.paths import install_dir, is_frozen


def ffmpeg_executable() -> str:
    """Return the FFmpeg binary path.

    Frozen: ``ffmpeg.exe`` (Windows) or ``ffmpeg`` beside the executable.
    Missing sidecar raises ``FileNotFoundError`` naming that path (no PATH
    fallback). Checkout: ``shutil.which("ffmpeg")``, else "not on PATH".
    """
    if is_frozen():
        name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        path = install_dir() / name
        if not path.is_file():
            raise FileNotFoundError(f"ffmpeg not found: {path}")
        return str(path)
    found = shutil.which("ffmpeg")
    if found is None:
        raise FileNotFoundError("ffmpeg not found on PATH")
    return found
