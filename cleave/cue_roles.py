"""Cue role labels and role-pool preset paths under ``preset_root/roles/``."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

CueRole = Literal["bed", "pulse", "lead", "accent"]

CUE_ROLES: tuple[CueRole, ...] = ("bed", "pulse", "lead", "accent")

CUE_ROLE_DIR = "roles"

CUE_ROLE_MARKER_LETTER: dict[CueRole, str] = {
    "bed": "B",
    "pulse": "P",
    "lead": "L",
    "accent": "A",
}

CUE_ROLE_MARKER_HELP_ENTRIES: tuple[tuple[str, str], ...] = tuple(
    (f"[R:{CUE_ROLE_MARKER_LETTER[role]}]", role) for role in CUE_ROLES
)


def ensure_role_dirs(preset_root: Path) -> None:
    """Create ``preset_root/roles/`` and the four role subdirectories if missing."""
    roles = preset_root / CUE_ROLE_DIR
    roles.mkdir(parents=True, exist_ok=True)
    for role in CUE_ROLES:
        (roles / role).mkdir(parents=True, exist_ok=True)


def role_pool_paths(preset_root: Path, role: CueRole) -> tuple[Path, ...]:
    """Sorted non-recursive ``*.milk`` under ``preset_root/roles/<role>/``.

    Same rule as ``milk_files_in_dir`` in ``cleave.preset_playlist``.
    """
    return tuple(sorted((preset_root / CUE_ROLE_DIR / role).glob("*.milk")))
