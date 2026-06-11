"""Tests for the Cleave CLI."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cleave.cli import build_parser, cmd_play, cmd_render, cmd_separate
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
    assert not args.high_quality
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
    assert not args.high_quality
    assert args.config is None


def test_render_parser_uses_project_dir_and_options() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "render",
            "my-project",
            "-c",
            "cfg.yaml",
            "-o",
            "out.mp4",
            "-fi",
            "1.5",
            "-fo",
            "2.0",
        ]
    )
    assert args.project_dir == "my-project"
    assert args.config == Path("cfg.yaml")
    assert args.output == Path("out.mp4")
    assert args.fade_in == 1.5
    assert args.fade_out == 2.0


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


def test_cmd_render_calls_render(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    output = tmp_path / "video.mp4"

    with patch.object(
        importlib.import_module("cleave.viz.render"), "render", return_value=output.resolve()
    ) as render:
        cmd_render(
            build_parser().parse_args(
                [
                    "render",
                    "my-track",
                    "-c",
                    "cfg.yaml",
                    "-o",
                    "video.mp4",
                    "-fi",
                    "1.0",
                    "-fo",
                    "0.5",
                ]
            )
        )

    render.assert_called_once_with(
        project.resolve(),
        config=Path("cfg.yaml"),
        output=Path("video.mp4"),
        fade_in=1.0,
        fade_out=0.5,
        high_quality=False,
    )
    out = capsys.readouterr().out
    assert f"Rendered to {output.resolve()}" in out


def test_cmd_render_passes_high_quality_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    _complete_project(tmp_path)

    with patch.object(
        importlib.import_module("cleave.viz.render"), "render", return_value=tmp_path / "out.mp4"
    ) as render:
        cmd_render(build_parser().parse_args(["render", "my-track", "--hq"]))

    render.assert_called_once()
    assert render.call_args.kwargs["high_quality"] is True


def test_cmd_render_errors_when_project_incomplete(
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

    with pytest.raises(SystemExit) as exc_info:
        cmd_render(build_parser().parse_args(["render", "my-track"]))

    assert exc_info.value.code == 1
    assert "signals.json" in capsys.readouterr().err


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

    run_separate.assert_called_once_with(Path("my-track"), high_quality=False)


def test_cmd_play_forwards_high_quality_to_run_separate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)

    with (
        patch("cleave.cli.run_separate", return_value=project.resolve()) as run_separate,
        patch("cleave.viz.launch"),
    ):
        cmd_play(build_parser().parse_args(["play", "my-track", "--high-quality"]))

    run_separate.assert_called_once_with(Path("my-track"), high_quality=True)


def test_shortcut_flags() -> None:
    parser = build_parser()
    assert parser.parse_args(["separate", "song", "-hq", "-f"]).high_quality
    assert parser.parse_args(["separate", "song", "-hq", "-f"]).force
    assert parser.parse_args(["play", "song", "-hq"]).high_quality
    assert parser.parse_args(["play", "song", "-c", "cfg.yaml"]).config == Path(
        "cfg.yaml"
    )
    render_args = parser.parse_args(
        ["render", "song", "-c", "cfg.yaml", "-o", "out.mp4", "-fi", "1", "-fo", "2"]
    )
    assert render_args.config == Path("cfg.yaml")
    assert render_args.output == Path("out.mp4")
    assert render_args.fade_in == 1.0
    assert render_args.fade_out == 2.0


def test_module_help_lists_subcommands() -> None:
    root = subprocess.run(
        [sys.executable, "-m", "cleave", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    out = root.stdout
    assert "separate" in out
    assert "analyse" not in out
    assert "play" in out
    assert "render" in out
    assert out.startswith("usage: cleave [-h] <command> target")
    assert "target                Source audio file or cleave project" in out
    assert "{separate,play}" not in out
    assert "pygame" not in out.lower()

    play = subprocess.run(
        [sys.executable, "-m", "cleave", "play", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert play.stdout.startswith("usage: cleave play [-h] [-hq] [-c CONFIG] target")

    render = subprocess.run(
        [sys.executable, "-m", "cleave", "render", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    render_usage = render.stdout.split("positional arguments:")[0]
    assert (
        "usage: cleave render [-h] [-c CONFIG] [-o OUTPUT] [-fi SECONDS] [-fo SECONDS]"
        in render_usage
    )
    assert "project_dir" in render_usage
    assert "project_dir" in render.stdout
    assert "Cleave project directory" in render.stdout
    assert "-c CONFIG, --config CONFIG" in render.stdout
    assert "-o OUTPUT, --output OUTPUT" in render.stdout
    assert "-fi SECONDS, --fade-in SECONDS" in render.stdout
    assert "-fo SECONDS, --fade-out SECONDS" in render.stdout
