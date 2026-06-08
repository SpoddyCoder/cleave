"""Tests for the Cleave CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cleave.cli import build_parser, cmd_analyse, cmd_play, cmd_separate
from cleave.extract import STEM_NAMES
from cleave.project import write_manifest
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
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "my-track.flac",
        demucs_model="htdemucs",
    )

    signals_path = project / "signals.json"

    with patch("cleave.cli.run_analyse", return_value=signals_path) as run_analyse:
        cmd_analyse(build_parser().parse_args(["analyse", "my-track"]))

    run_analyse.assert_called_once_with(project.resolve(), slow=False)
    assert f"Wrote signals to {signals_path}" in capsys.readouterr().out


def test_cmd_analyse_requires_project_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    for name in STEM_NAMES:
        (project / f"{name}.wav").write_bytes(b"wav")

    with pytest.raises(SystemExit) as exc_info:
        cmd_analyse(build_parser().parse_args(["analyse", "my-track"]))

    assert exc_info.value.code == 1
    assert "project manifest not found" in capsys.readouterr().err


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


def test_play_parser_uses_project_arg() -> None:
    parser = build_parser()
    args = parser.parse_args(["play", "my-track"])
    assert args.project == "my-track"
    assert args.config is None
    assert args.preset is None


def test_cmd_play_calls_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "my-track.flac",
        demucs_model="htdemucs",
    )

    with patch("cleave.viz.launch") as launch:
        cmd_play(build_parser().parse_args(["play", "my-track"]))

    launch.assert_called_once_with(
        project.resolve(),
        config=None,
        preset=None,
    )


def test_cmd_play_requires_project_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        cmd_play(build_parser().parse_args(["play", "my-track"]))

    assert exc_info.value.code == 1
    assert "project manifest not found" in capsys.readouterr().err


def test_module_help_lists_subcommands() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "cleave", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout
    assert "separate" in out
    assert "analyse" in out
    assert "play" in out
    assert "pygame" not in out.lower()
