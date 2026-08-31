"""Tests for the package version single source."""

from __future__ import annotations

import re
from pathlib import Path

from cleave import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def test_version_is_three_part_semver() -> None:
    assert _SEMVER.fullmatch(__version__), __version__


def test_pyproject_version_attr_points_at_cleave() -> None:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = {attr = "cleave.__version__"}' in text
