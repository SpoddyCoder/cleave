"""Tests for the Cleave CLI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from cleave.cli import build_parser, cmd_analyse, cmd_separate
from cleave.extract import STEM_NAMES
from cleave.separate import ProjectStemsExist


def test_analyse_parser_uses_project_arg() -> None:
    parser = build_parser()
    args = parser.parse_args(["analyse", "my-track"])
    assert args.project == "my-track"
    assert not hasattr(args, "stems_dir")


def test_cmd_analyse_resolves_project_slug(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    for name in STEM_NAMES:
        (project / f"{name}.wav").write_bytes(b"wav")

    signals_path = project / "signals.json"

    with patch("cleave.cli.run_analyse", return_value=signals_path) as run_analyse:
        cmd_analyse(build_parser().parse_args(["analyse", "my-track"]))

    run_analyse.assert_called_once_with(project.resolve(), source=None, slow=False)
    assert f"Wrote signals to {signals_path}" in capsys.readouterr().out


def test_cmd_separate_handles_project_stems_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"audio")
    project = tmp_path / "projects" / "song"

    with patch(
        "cleave.cli.run_separate",
        side_effect=ProjectStemsExist(project.resolve()),
    ):
        cmd_separate(build_parser().parse_args(["separate", str(audio)]))

    out = capsys.readouterr().out
    assert "stem wavs already exist in project" in out
    assert "--force" in out
