"""Filesystem layout for Cleave data and projects."""

from __future__ import annotations

import os
from pathlib import Path

from cleave.config import VIZ_CONFIG_FILENAME

# Repo root when running from a checkout (`cleave/` package lives here).
_REPO_ROOT = Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    """Return the repository root directory."""
    return _REPO_ROOT.resolve()


def data_dir() -> Path:
    """Return Cleave data root (``CLEAVE_DATA``, ``XDG_DATA_HOME/cleave``, or ``~/.local/share/cleave``)."""
    override = os.environ.get("CLEAVE_DATA")
    if override:
        return Path(override).expanduser().resolve()
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return (Path(xdg_data_home) / "cleave").resolve()
    return (Path.home() / ".local" / "share" / "cleave").resolve()


def projects_dir() -> Path:
    """Return the directory that holds per-track project folders."""
    return data_dir() / "projects"


def project_dir(slug: str) -> Path:
    """Return the project directory for *slug* under :func:`projects_dir`."""
    return projects_dir() / slug


def validate_project_slug(slug: str) -> None:
    """Raise :class:`ValueError` when *slug* is not a safe project identifier."""
    if "/" in slug or "\\" in slug or slug in (".", ".."):
        raise ValueError(f"invalid project slug: {slug!r}")


def resolve_project(path_or_slug: Path | str) -> Path:
    """Resolve a project slug or path to an existing project directory.

    * Slug: ``sights-and-sounds-26`` -> ``projects_dir() / slug``
    * Relative: ``projects/sights-and-sounds-26`` -> under :func:`data_dir`
    * Absolute: path to the project directory as-is
    """
    raw = Path(path_or_slug)

    if raw.is_absolute():
        candidate = raw.resolve()
    elif len(raw.parts) >= 2 and raw.parts[0] == "projects":
        candidate = (data_dir() / raw).resolve()
    else:
        slug = os.fspath(path_or_slug)
        validate_project_slug(slug)
        candidate = project_dir(slug).resolve()

    if not candidate.is_dir():
        raise FileNotFoundError(f"project not found: {candidate}")

    return candidate


def project_slug(audio_path: Path) -> str:
    """Derive a project slug from an audio file path (stem of the filename)."""
    return audio_path.stem


def default_project_config(project: Path) -> Path:
    """Return the default per-project visualizer config path inside *project*."""
    return project / VIZ_CONFIG_FILENAME
