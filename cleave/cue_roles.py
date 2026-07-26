"""Cue role labels and role-pool preset paths under ``preset_root/roles/``."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

CueRole = Literal["bed", "pulse", "lead", "accent"]

CUE_ROLES: tuple[CueRole, ...] = ("bed", "pulse", "lead", "accent")

CUE_ROLE_DIR = "roles"


def role_pool_paths(preset_root: Path, role: CueRole) -> tuple[Path, ...]:
    """Sorted non-recursive ``*.milk`` under ``preset_root/roles/<role>/``.

    Same rule as ``milk_files_in_dir`` in ``cleave.preset_playlist``.
    """
    return tuple(sorted((preset_root / CUE_ROLE_DIR / role).glob("*.milk")))
