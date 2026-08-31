"""Tests for scripts/changelog_section.py and CHANGELOG.md."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from cleave import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = REPO_ROOT / "scripts" / "changelog_section.py"


def _load_changelog_section():
    spec = importlib.util.spec_from_file_location("changelog_section", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


changelog_section = _load_changelog_section()


_SAMPLE = """# Changelog

## [Unreleased]

## [0.2.0] - 2026-09-01

### Added

- Two.

## [0.1.0] - 2026-08-31

### Added

- One.

[unreleased]: https://example.com/compare/v0.2.0...HEAD
[0.2.0]: https://example.com/releases/tag/v0.2.0
[0.1.0]: https://example.com/releases/tag/v0.1.0
"""


def test_extract_section_returns_body_without_heading() -> None:
    body = changelog_section.extract_section(_SAMPLE, "0.2.0")
    assert body.startswith("### Added")
    assert "- Two." in body
    assert "0.2.0" not in body
    assert "One." not in body
    assert "unreleased" not in body.lower()


def test_extract_section_accepts_v_prefix() -> None:
    body = changelog_section.extract_section(_SAMPLE, "v0.1.0")
    assert "- One." in body
    assert "Two." not in body
    assert "[0.1.0]:" not in body


def test_extract_section_unknown_version_raises() -> None:
    with pytest.raises(changelog_section.ChangelogSectionError, match="9.9.9"):
        changelog_section.extract_section(_SAMPLE, "9.9.9")


def test_extract_section_empty_raises() -> None:
    with pytest.raises(changelog_section.ChangelogSectionError, match="empty"):
        changelog_section.extract_section(_SAMPLE, "Unreleased")


def test_main_prints_section(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(_SAMPLE, encoding="utf-8")
    assert changelog_section.main(["0.1.0", "-f", str(path)]) == 0
    assert "- One." in capsys.readouterr().out


def test_main_errors_on_unknown_version(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(_SAMPLE, encoding="utf-8")
    assert changelog_section.main(["1.2.3", "--file", str(path)]) == 1
    err = capsys.readouterr().err
    assert "error:" in err
    assert "1.2.3" in err


def test_changelog_has_section_for_current_version() -> None:
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    body = changelog_section.extract_section(text, __version__)
    assert body.startswith("### ")
