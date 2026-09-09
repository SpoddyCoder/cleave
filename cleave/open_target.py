"""Decide whether a filesystem path is something Cleave can open.

Shared by the in-window file picker, pasted paths, dropped files, and the CLI.
No viz import: this must stay usable from headless tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from cleave.project import PROJECT_FILENAME

AUDIO_SUFFIX = ".wav"

_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


class OpenTargetKind(Enum):
    """What kind of thing a path turned out to be."""

    AUDIO = "audio"
    PROJECT = "project"


@dataclass(frozen=True)
class OpenTarget:
    """An accepted path plus how the rest of the pipeline should read it.

    ``path`` is suitable for :func:`cleave.separate.resolve_separate_target`.
    """

    path: Path
    kind: OpenTargetKind


def is_audio_target(path: Path) -> bool:
    """True when *path* is a wav file Cleave can separate."""
    try:
        return path.suffix.lower() == AUDIO_SUFFIX and path.is_file()
    except OSError:
        return False


def is_project_target(path: Path) -> bool:
    """True when *path* is a directory holding a project config.

    Stricter than :func:`cleave.paths.resolve_project`, which accepts any
    existing directory. Opening ``Documents`` must not try to play it.
    """
    try:
        return path.is_dir() and (path / PROJECT_FILENAME).is_file()
    except OSError:
        return False


def classify_open_target(path: Path) -> OpenTarget | None:
    """Return the :class:`OpenTarget` for *path*, or None when unusable.

    Never raises. A Windows-style path on POSIX is simply not accepted.
    """
    if is_audio_target(path):
        return OpenTarget(path=path, kind=OpenTargetKind.AUDIO)
    if is_project_target(path):
        return OpenTarget(path=path, kind=OpenTargetKind.PROJECT)
    return None


def looks_like_windows_path(text: str) -> bool:
    """True when *text* is a drive-letter path such as ``C:\\Users``."""
    return bool(_WINDOWS_ABSOLUTE.match(text.strip()))


def open_target_rejection(path: Path) -> str:
    """Return a short message explaining why *path* cannot be opened."""
    try:
        exists = path.exists()
    except OSError:
        exists = False

    if not exists:
        if looks_like_windows_path(str(path)):
            return "Windows path. Use /mnt/c/... or the Drives shortcut"
        return "not found"
    if path.is_dir():
        return f"no {PROJECT_FILENAME} here"
    return f"not a {AUDIO_SUFFIX} file"
