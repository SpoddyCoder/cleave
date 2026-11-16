"""Which build this is: a release tag, or a dev build past one.

A release build is exactly the tag ``v{__version__}`` and shows that tag.
Anything else is a dev build and shows ``git describe`` output, such as
``v0.3.0-12-gabc1234`` (with ``-dirty`` for uncommitted changes), plus
``(dev build)``.

Frozen builds have no git. The freeze workflow runs
``scripts/stamp_build_version.py`` first, which writes the describe string to
``cleave/_build_version.py`` (gitignored). A source checkout asks git
first, so a stamp left over from a local freeze never goes stale there. With
neither, the build is a dev build of the last-shipped version.
"""

from __future__ import annotations

import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from cleave import __version__

DEV_BUILD_SUFFIX = "(dev build)"
STAMP_MODULE = Path(__file__).resolve().parent / "_build_version.py"
_REPO_ROOT = Path(__file__).resolve().parent.parent


def release_tag() -> str:
    """Tag of the last-shipped version, such as ``v0.3.0``."""
    return f"v{__version__}"


def git_describe(repo_root: Path = _REPO_ROOT) -> str | None:
    """``git describe`` of a checkout, or None without git or a release tag."""
    if not (repo_root / ".git").exists():
        return None
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--dirty", "--match", "v[0-9]*"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            **kwargs,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    describe = result.stdout.strip()
    if result.returncode != 0 or not describe:
        return None
    return describe


def _stamped_describe() -> str | None:
    try:
        from cleave import _build_version  # type: ignore[attr-defined]
    except ImportError:
        return None
    return getattr(_build_version, "DESCRIBE", None) or None


def build_describe() -> str | None:
    """Frozen: the build-time stamp. Source: git, else the stamp. Else None."""
    if not getattr(sys, "frozen", False):
        describe = git_describe()
        if describe is not None:
            return describe
    return _stamped_describe()


def format_version(describe: str | None) -> str:
    """The release tag on a release build, otherwise a dev build label."""
    tag = release_tag()
    if describe == tag:
        return tag
    return f"{describe or tag} {DEV_BUILD_SUFFIX}"


@lru_cache(maxsize=1)
def display_version() -> str:
    """Version line for About and ``--version``."""
    return format_version(build_describe())
