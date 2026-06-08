"""Tests for Demucs separation and project layout."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from cleave.extract import STEM_NAMES
from cleave.separate import (
    ProjectStemsExist,
    project_stems_complete,
    run_separate,
)


def test_project_stems_complete_false_when_missing(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    assert project_stems_complete(project) is False


def test_project_stems_complete_true_when_all_present(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    for name in STEM_NAMES:
        (project / f"{name}.wav").write_bytes(b"wav")
    assert project_stems_complete(project) is True


def test_run_separate_raises_project_stems_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    audio = tmp_path / "my-track.flac"
    audio.write_bytes(b"audio")

    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    for name in STEM_NAMES:
        (project / f"{name}.wav").write_bytes(b"wav")

    with pytest.raises(ProjectStemsExist) as exc_info:
        run_separate(audio)

    assert exc_info.value.project_dir == project.resolve()


def test_run_separate_creates_project_and_renders(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"audio")

    project = tmp_path / "projects" / "song"
    demucs_out = tmp_path / "demucs-out" / "htdemucs" / "song"
    demucs_out.mkdir(parents=True)
    for name in STEM_NAMES:
        (demucs_out / f"{name}.wav").write_bytes(b"wav")

    def fake_run(cmd: list[str], *, check: bool) -> None:
        out_flag = cmd.index("-o")
        out_root = Path(cmd[out_flag + 1])
        target = out_root / "htdemucs" / "song"
        target.parent.mkdir(parents=True, exist_ok=True)
        for name in STEM_NAMES:
            shutil_copy = demucs_out / f"{name}.wav"
            target.mkdir(parents=True, exist_ok=True)
            (target / f"{name}.wav").write_bytes(shutil_copy.read_bytes())

    with patch("cleave.separate.subprocess.run", side_effect=fake_run):
        result = run_separate(audio)

    assert result == project.resolve()
    assert project.is_dir()
    assert (project / "renders").is_dir()
    for name in STEM_NAMES:
        assert (project / f"{name}.wav").is_file()
