import subprocess
from pathlib import Path

import pytest

from cleave import __version__, build_version
from cleave.build_version import format_version, git_describe

_TAG = f"v{__version__}"


def test_release_tag_shows_tag_only() -> None:
    assert format_version(_TAG) == _TAG


@pytest.mark.parametrize(
    "describe",
    [f"{_TAG}-12-gabc1234", f"{_TAG}-12-gabc1234-dirty", f"{_TAG}-dirty", "v0.1.0"],
)
def test_anything_else_is_a_dev_build(describe: str) -> None:
    assert format_version(describe) == f"{describe} (dev build)"


def test_unknown_build_is_a_dev_build_of_the_last_release() -> None:
    assert format_version(None) == f"{_TAG} (dev build)"


def test_frozen_uses_the_stamp_and_never_runs_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_version.sys, "frozen", True, raising=False)
    monkeypatch.setattr(build_version, "git_describe", lambda: pytest.fail("git ran"))
    monkeypatch.setattr(build_version, "_stamped_describe", lambda: _TAG)
    assert build_version.build_describe() == _TAG
    monkeypatch.setattr(build_version, "_stamped_describe", lambda: None)
    assert build_version.build_describe() is None


def test_source_prefers_git_over_a_stale_stamp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_version, "_stamped_describe", lambda: "v0.0.1")
    monkeypatch.setattr(build_version, "git_describe", lambda: f"{_TAG}-3-gabc1234")
    assert build_version.build_describe() == f"{_TAG}-3-gabc1234"
    monkeypatch.setattr(build_version, "git_describe", lambda: None)
    assert build_version.build_describe() == "v0.0.1"


def test_git_describe_without_a_checkout_is_none(tmp_path: Path) -> None:
    assert git_describe(tmp_path) is None


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_git_describe_on_and_past_a_tag(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "a")
    _git(tmp_path, "tag", "v1.2.3")
    assert git_describe(tmp_path) == "v1.2.3"
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "b")
    assert git_describe(tmp_path).startswith("v1.2.3-1-g")
