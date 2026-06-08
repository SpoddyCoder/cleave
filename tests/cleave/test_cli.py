"""Tests for the Cleave CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cleave.cli import build_parser, cmd_play, cmd_separate
from cleave.extract import STEM_NAMES, stems_dir
from cleave.project import write_manifest


def _write_stub_stems(project: Path) -> None:
    base = stems_dir(project)
    base.mkdir(parents=True, exist_ok=True)
    for name in STEM_NAMES:
        (base / f"{name}.wav").write_bytes(b"wav")


def test_separate_parser_uses_target_arg() -> None:
    parser = build_parser()
    args = parser.parse_args(["separate", "my-track.flac"])
    assert args.target == "my-track.flac"
    assert not args.slow
    assert not args.force


def test_cmd_separate_noop_when_complete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "song"
    project.mkdir(parents=True)
    _write_stub_stems(project)
    mix = project / "song.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "song.flac",
        demucs_model="htdemucs",
    )
    (project / "signals.json").write_text("{}")

    with patch("cleave.cli.run_separate") as run_separate:
        cmd_separate(build_parser().parse_args(["separate", "song"]))

    run_separate.assert_not_called()
    out = capsys.readouterr().out
    assert "has stems and signals" in out
    assert "--force" in out


def test_cmd_separate_analyse_only_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    _write_stub_stems(project)
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

    with patch("cleave.cli.run_separate", return_value=project.resolve()):
        cmd_separate(build_parser().parse_args(["separate", "my-track"]))

    out = capsys.readouterr().out
    assert f"Wrote signals to {signals_path}" in out


def test_cmd_separate_force_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "song"
    project.mkdir(parents=True)
    _write_stub_stems(project)
    mix = project / "song.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "song.flac",
        demucs_model="htdemucs",
    )
    (project / "signals.json").write_text("{}")

    with patch("cleave.cli.run_separate", return_value=project.resolve()):
        cmd_separate(build_parser().parse_args(["separate", "song", "--force"]))

    out = capsys.readouterr().out
    assert "Re-separated and analysed" in out


def test_play_parser_uses_target_arg() -> None:
    parser = build_parser()
    args = parser.parse_args(["play", "my-track.flac"])
    assert args.target == "my-track.flac"
    assert not args.slow
    assert args.config is None


def _complete_project(tmp_path: Path, slug: str = "my-track") -> Path:
    project = tmp_path / "projects" / slug
    project.mkdir(parents=True)
    _write_stub_stems(project)
    mix = project / f"{slug}.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug=slug,
        mix_filename=f"{slug}.flac",
        original_path=tmp_path / f"{slug}.flac",
        demucs_model="htdemucs",
    )
    (project / "signals.json").write_text("{}")
    return project


def test_cmd_play_calls_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)

    with patch("cleave.viz.launch") as launch:
        cmd_play(build_parser().parse_args(["play", "my-track"]))

    launch.assert_called_once_with(
        project.resolve(),
        config=None,
    )


def test_cmd_play_calls_run_separate_when_incomplete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    _write_stub_stems(project)
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "my-track.flac",
        demucs_model="htdemucs",
    )

    with (
        patch("cleave.cli.run_separate", return_value=project.resolve()) as run_separate,
        patch("cleave.viz.launch"),
    ):
        cmd_play(build_parser().parse_args(["play", "my-track"]))

    run_separate.assert_called_once_with(Path("my-track"), slow=False)


def test_cmd_play_forwards_slow_to_run_separate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)

    with (
        patch("cleave.cli.run_separate", return_value=project.resolve()) as run_separate,
        patch("cleave.viz.launch"),
    ):
        cmd_play(build_parser().parse_args(["play", "my-track", "--slow"]))

    run_separate.assert_called_once_with(Path("my-track"), slow=True)


def test_module_help_lists_subcommands() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "cleave", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout
    assert "separate" in out
    assert "analyse" not in out
    assert "play" in out
    assert "pygame" not in out.lower()
