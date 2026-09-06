"""Locate the FFmpeg executable for offline render and frozen stem split."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager

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


@contextmanager
def sidecar_ffmpeg_on_path() -> Iterator[None]:
    """Prepend ``install_dir()`` to PATH when frozen so child processes see the sidecar.

    Frozen lookup in :func:`ffmpeg_executable` stays beside the exe (no PATH
    fallback). Demucs 4.0.1 shells out to ``ffmpeg`` by name. Checkout leaves
    PATH unchanged.
    """
    if not is_frozen():
        yield
        return
    ffmpeg_executable()
    root = str(install_dir())
    old = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{root}{os.pathsep}{old}" if old else root
    try:
        yield
    finally:
        os.environ["PATH"] = old
