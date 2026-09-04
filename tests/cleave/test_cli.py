"""Tests for the Cleave CLI."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cleave import __version__
from cleave.cli import (
    COMMANDS,
    _format_elapsed,
    build_parser,
    cmd_backup,
    cmd_play,
    cmd_render,
    cmd_restore,
    cmd_separate,
    main,
    normalise_argv,
    owns_console,
)
from cleave.viz.render import RenderResult
from cleave.stems import STEM_NAMES, stems_dir
from cleave.project import write_manifest


def _write_stub_stems(project: Path) -> None:
    base = stems_dir(project)
    base.mkdir(parents=True, exist_ok=True)
    for name in STEM_NAMES:
        (base / f"{name}.wav").write_bytes(b"wav")


def test_format_elapsed() -> None:
    assert _format_elapsed(0.4) == "0 mins 0 secs"
    assert _format_elapsed(65.4) == "1 mins 5 secs"
    assert _format_elapsed(3723.6) == "62 mins 4 secs"


def test_cli_beat_detection_stem_choices_match_stems() -> None:
    from cleave import cli
    from cleave.stems import BEAT_DETECTION_STEM_CHOICES

    assert cli.BEAT_DETECTION_STEM_CHOICES == BEAT_DETECTION_STEM_CHOICES


def test_cli_import_and_build_parser_stay_light() -> None:
    """Fresh process: import cli + build_parser must not load pygame/torch/librosa."""
    repo_root = Path(__file__).resolve().parents[2]
    script = """
import sys
from cleave.cli import build_parser

build_parser()
heavy = [name for name in ("pygame", "torch", "librosa") if name in sys.modules]
if heavy:
    raise SystemExit(f"unexpected heavy imports: {heavy}")
"""
    env = {**os.environ, "PYTHONPATH": str(repo_root)}
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(repo_root),
    )
    assert result.returncode == 0, result.stderr


def test_import_separate_does_not_import_torch() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = """
import sys
import cleave.separate

if "torch" in sys.modules:
    raise SystemExit("unexpected torch import")
if "cleave.analyse" in sys.modules:
    raise SystemExit("unexpected analyse import")
"""
    env = {**os.environ, "PYTHONPATH": str(repo_root)}
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(repo_root),
    )
    assert result.returncode == 0, result.stderr


def test_cli_version_prints_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"cleave {__version__}"


def test_no_args_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "usage: cleave" in out
    assert "play" in out
    assert "separate" in out


def test_bare_unknown_arg_still_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["definitely-not-a-project-or-file"])
    assert exc.value.code != 0
    err = capsys.readouterr().err
    assert "invalid choice" in err or "the following arguments are required" in err


def test_normalise_argv_empty_and_known_commands() -> None:
    parser = build_parser()
    choices = next(
        action.choices
        for action in parser._actions
        if getattr(action, "choices", None) and action.dest == "command"
    )
    assert set(COMMANDS) == set(choices)
    assert normalise_argv([]) == []
    assert normalise_argv(["--version"]) == ["--version"]
    assert normalise_argv(["play", "song"]) == ["play", "song"]
    assert normalise_argv(["separate", "song"]) == ["separate", "song"]
    assert normalise_argv(["render", "song"]) == ["render", "song"]
    assert normalise_argv(["nope"]) == ["nope"]
    assert normalise_argv(["foo", "bar"]) == ["foo", "bar"]


def test_normalise_argv_prepends_play_for_file(tmp_path: Path) -> None:
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"audio")
    assert normalise_argv([str(audio)]) == ["play", str(audio)]


def test_normalise_argv_prepends_play_for_directory(tmp_path: Path) -> None:
    folder = tmp_path / "project"
    folder.mkdir()
    assert normalise_argv([str(folder)]) == ["play", str(folder)]


def test_normalise_argv_prepends_play_for_slug(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    (tmp_path / "projects" / "song").mkdir(parents=True)
    assert normalise_argv(["song"]) == ["play", "song"]


def test_owns_console_false_off_windows() -> None:
    if sys.platform == "win32":
        pytest.skip("Linux/macOS gate only")
    assert owns_console() is False


def test_error_does_not_pause_when_not_frozen() -> None:
    with patch("builtins.input") as pause_input:
        with pytest.raises(SystemExit):
            main(["definitely-not-a-project-or-file"])
    pause_input.assert_not_called()


def test_error_pauses_when_frozen_and_owns_console(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cleave.cli.is_frozen", lambda: True)
    monkeypatch.setattr("cleave.cli.owns_console", lambda: True)
    with patch("builtins.input") as pause_input:
        with pytest.raises(SystemExit) as exc:
            main(["definitely-not-a-project-or-file"])
        assert exc.value.code != 0
    pause_input.assert_called_once_with("Press Enter to close...")


def test_error_does_not_pause_when_frozen_in_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cleave.cli.is_frozen", lambda: True)
    monkeypatch.setattr("cleave.cli.owns_console", lambda: False)
    with patch("builtins.input") as pause_input:
        with pytest.raises(SystemExit):
            main(["definitely-not-a-project-or-file"])
    pause_input.assert_not_called()


def test_version_does_not_pause_when_frozen(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("cleave.cli.is_frozen", lambda: True)
    monkeypatch.setattr("cleave.cli.owns_console", lambda: True)
    with patch("builtins.input") as pause_input:
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0
    pause_input.assert_not_called()
    assert capsys.readouterr().out.strip() == f"cleave {__version__}"


def test_no_args_help_does_not_pause_when_frozen(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("cleave.cli.is_frozen", lambda: True)
    monkeypatch.setattr("cleave.cli.owns_console", lambda: True)
    with patch("builtins.input") as pause_input:
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 0
    pause_input.assert_not_called()
    assert "usage: cleave" in capsys.readouterr().out


def test_handled_error_pauses_when_frozen_and_owns_console(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    monkeypatch.setattr("cleave.cli.is_frozen", lambda: True)
    monkeypatch.setattr("cleave.cli.owns_console", lambda: True)
    with patch("builtins.input") as pause_input:
        with pytest.raises(SystemExit) as exc:
            main(["play", "missing-project"])
        assert exc.value.code == 1
    pause_input.assert_called_once_with("Press Enter to close...")


def test_separate_parser_uses_target_arg() -> None:
    parser = build_parser()
    args = parser.parse_args(["separate", "my-track.flac"])
    assert args.target == "my-track.flac"
    assert not args.high_quality
    assert not args.force
    assert args.beat_detection_stem is None


def test_separate_parser_accepts_beat_detection_stem() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["separate", "my-track.flac", "-bds", "drums"]
    )
    assert args.beat_detection_stem == "drums"
    long_args = parser.parse_args(
        ["separate", "song", "--beat-detection-stem", "full-mix"]
    )
    assert long_args.beat_detection_stem == "full-mix"
    play_args = parser.parse_args(["play", "song", "-bds", "bass"])
    assert play_args.beat_detection_stem == "bass"


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
    (project / "signals.json").write_text('{"version": 4}')

    with patch("cleave.separate.run_separate") as run_separate:
        cmd_separate(build_parser().parse_args(["separate", "song"]))

    run_separate.assert_not_called()
    out = capsys.readouterr().out
    assert "has stems and signals" in out
    assert "--force" in out


def test_cmd_separate_does_not_noop_when_beat_stem_differs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
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
    (project / "signals.json").write_text(
        '{"version": 4, "beat_detection_stem": "full_mix"}'
    )

    with patch("cleave.separate.run_separate", return_value=project.resolve()) as run_separate:
        cmd_separate(
            build_parser().parse_args(["separate", "song", "-bds", "drums"])
        )

    run_separate.assert_called_once_with(
        Path("song"),
        high_quality=False,
        force=False,
        beat_detection_stem="drums",
    )


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

    with patch("cleave.separate.run_separate", return_value=project.resolve()):
        cmd_separate(build_parser().parse_args(["separate", "my-track"]))

    out = capsys.readouterr().out
    assert f"Wrote signals to {signals_path}" in out
    assert "my-track.flac audio separated and analysed, in" in out
    assert "high-quality mode" not in out


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

    with patch("cleave.separate.run_separate", return_value=project.resolve()):
        cmd_separate(build_parser().parse_args(["separate", "song", "--force"]))

    out = capsys.readouterr().out
    assert "Re-separated and analysed" in out
    assert "song.flac audio separated and analysed, in" in out


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
        ]
    )
    assert args.project_dir == "my-project"
    assert args.config == Path("cfg.yaml")
    assert args.output == Path("out.mp4")
    assert not args.viz_quality


def test_render_parser_accepts_viz_quality_short_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["render", "my-project", "-vq"])
    assert args.viz_quality is True


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
    (project / "signals.json").write_text('{"version": 4}')
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


def test_bare_path_runs_play(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)

    with patch("cleave.viz.launch") as launch:
        main(["my-track"])

    launch.assert_called_once_with(
        project.resolve(),
        config=None,
    )


def test_bare_file_runs_play(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"audio")
    project = tmp_path / "projects" / "song"

    with (
        patch("cleave.separate.run_separate", return_value=project.resolve()) as run_separate,
        patch("cleave.viz.launch") as launch,
    ):
        main([str(audio)])

    run_separate.assert_called_once_with(
        Path(str(audio)), high_quality=False, beat_detection_stem=None
    )
    launch.assert_called_once_with(project.resolve(), config=None)


def test_cmd_play_existing_project_does_not_import_torch(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    _complete_project(tmp_path)
    script = """
import os
import sys
from unittest.mock import patch
from cleave.cli import build_parser, cmd_play

with patch("cleave.viz.launch"):
    cmd_play(build_parser().parse_args(["play", "my-track"]))
if "torch" in sys.modules:
    raise SystemExit("unexpected torch import")
"""
    env = {**os.environ, "PYTHONPATH": str(repo_root), "CLEAVE_DATA": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(repo_root),
    )
    assert result.returncode == 0, result.stderr


def test_cmd_play_missing_torch_on_raw_audio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    monkeypatch.setattr("cleave.separate.stem_split_available", lambda: False)
    monkeypatch.setattr("cleave.separate.is_frozen", lambda: True)
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"audio")

    with pytest.raises(SystemExit) as exc:
        cmd_play(build_parser().parse_args(["play", str(audio)]))
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "not in this Windows build" in err


def test_cmd_separate_high_quality_completion_message(
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

    with patch("cleave.separate.run_separate", return_value=project.resolve()):
        cmd_separate(build_parser().parse_args(["separate", "song", "-hq"]))

    out = capsys.readouterr().out
    assert "song.flac audio separated and analysed, in high-quality mode, in" in out


def test_cmd_render_high_quality_completion_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    render_result = RenderResult(
        output_path=(project / "renders" / "out.mp4").resolve(),
        output_width=2560,
        output_height=1440,
        mix_filename="my-track.flac",
    )

    with patch.object(
        importlib.import_module("cleave.viz.render"),
        "render",
        return_value=render_result,
    ):
        cmd_render(build_parser().parse_args(["render", "my-track", "--hq"]))

    out = capsys.readouterr().out
    assert (
        "my-track.flac final render at 2560x1440 completed, "
        "in high-quality mode, in"
    ) in out


def test_cmd_render_calls_render(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    output = tmp_path / "video.mp4"

    render_result = RenderResult(
        output_path=output.resolve(),
        output_width=1280,
        output_height=720,
        mix_filename="my-track.flac",
    )
    with patch.object(
        importlib.import_module("cleave.viz.render"),
        "render",
        return_value=render_result,
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
                ]
            )
        )

    render.assert_called_once_with(
        project.resolve(),
        config=Path("cfg.yaml"),
        output=Path("video.mp4"),
        high_quality=False,
        viz_quality=False,
        start_sec=None,
        end_sec=None,
    )
    out = capsys.readouterr().out
    assert f"Rendered to {output.resolve()}" in out
    assert (
        "my-track.flac final render at 1280x720 completed, in" in out
    )
    assert "high-quality mode" not in out


def test_cmd_render_passes_high_quality_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    _complete_project(tmp_path)

    render_result = RenderResult(
        output_path=(tmp_path / "out.mp4").resolve(),
        output_width=2560,
        output_height=1440,
        mix_filename="my-track.flac",
    )
    with patch.object(
        importlib.import_module("cleave.viz.render"),
        "render",
        return_value=render_result,
    ) as render:
        cmd_render(
            build_parser().parse_args(["render", "my-track", "--hq"]),
        )

    render.assert_called_once()
    assert render.call_args.kwargs["high_quality"] is True


def test_cmd_render_passes_start_and_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    _complete_project(tmp_path)

    render_result = RenderResult(
        output_path=(tmp_path / "out.mp4").resolve(),
        output_width=1280,
        output_height=720,
        mix_filename="my-track.flac",
    )
    with patch.object(
        importlib.import_module("cleave.viz.render"),
        "render",
        return_value=render_result,
    ) as render:
        cmd_render(
            build_parser().parse_args(
                ["render", "my-track", "--start", "10", "--end", "20"]
            ),
        )

    render.assert_called_once_with(
        (tmp_path / "projects" / "my-track").resolve(),
        config=None,
        output=None,
        high_quality=False,
        viz_quality=False,
        start_sec=10,
        end_sec=20,
    )


def test_cmd_render_passes_viz_quality_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    _complete_project(tmp_path)

    render_result = RenderResult(
        output_path=(tmp_path / "out.mp4").resolve(),
        output_width=1280,
        output_height=720,
        mix_filename="my-track.flac",
    )
    with patch.object(
        importlib.import_module("cleave.viz.render"),
        "render",
        return_value=render_result,
    ) as render:
        cmd_render(
            build_parser().parse_args(["render", "my-track", "--viz-quality"]),
        )

    assert render.call_args.kwargs["viz_quality"] is True


def test_cmd_render_viz_quality_completion_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    render_result = RenderResult(
        output_path=(project / "renders" / "out.mp4").resolve(),
        output_width=1280,
        output_height=720,
        mix_filename="my-track.flac",
    )

    with patch.object(
        importlib.import_module("cleave.viz.render"),
        "render",
        return_value=render_result,
    ):
        cmd_render(build_parser().parse_args(["render", "my-track", "-vq"]))

    out = capsys.readouterr().out
    assert (
        "my-track.flac final render at 1280x720 completed, "
        "in viz-quality mode, in"
    ) in out


def test_cmd_render_segment_completion_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from cleave.viz.render import RenderSegment

    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    render_result = RenderResult(
        output_path=(project / "renders" / "out.mp4").resolve(),
        output_width=1280,
        output_height=720,
        mix_filename="my-track.flac",
        segment=RenderSegment(
            start_sec=10,
            end_label_sec=20,
            end_explicit=True,
            start_frame=300,
            end_frame_exclusive=600,
            frame_count=300,
        ),
    )

    with patch.object(
        importlib.import_module("cleave.viz.render"),
        "render",
        return_value=render_result,
    ):
        cmd_render(
            build_parser().parse_args(["render", "my-track", "--start", "10", "--end", "20"])
        )

    out = capsys.readouterr().out
    assert "my-track.flac segment render 10-20s at 1280x720 completed, in" in out


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
        patch("cleave.separate.run_separate", return_value=project.resolve()) as run_separate,
        patch("cleave.viz.launch"),
    ):
        cmd_play(build_parser().parse_args(["play", "my-track"]))

    run_separate.assert_called_once_with(
        Path("my-track"), high_quality=False, beat_detection_stem=None
    )


def test_cmd_play_forwards_high_quality_to_run_separate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)

    with (
        patch("cleave.separate.run_separate", return_value=project.resolve()) as run_separate,
        patch("cleave.viz.launch"),
    ):
        cmd_play(build_parser().parse_args(["play", "my-track", "--high-quality"]))

    run_separate.assert_called_once_with(
        Path("my-track"), high_quality=True, beat_detection_stem=None
    )


def test_cmd_play_forwards_beat_detection_stem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)

    with (
        patch("cleave.separate.run_separate", return_value=project.resolve()) as run_separate,
        patch("cleave.viz.launch"),
    ):
        cmd_play(
            build_parser().parse_args(["play", "my-track", "-bds", "vocals"])
        )

    run_separate.assert_called_once_with(
        Path("my-track"), high_quality=False, beat_detection_stem="vocals"
    )


def test_backup_parser_uses_project_dir_destination_and_options() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["backup", "my-project", "/tmp/backups", "--force"]
    )
    assert args.project_dir == "my-project"
    assert args.destination == "/tmp/backups"
    assert args.force


def test_restore_parser_uses_archive_and_options() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["restore", "song.cleave-tar.gz", "--as", "song-copy", "--force"]
    )
    assert args.archive == "song.cleave-tar.gz"
    assert args.as_slug == "song-copy"
    assert args.force


def test_cmd_backup_calls_backup_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    archive = tmp_path / "song.cleave-tar.gz"

    with patch("cleave.archive.backup_project", return_value=archive.resolve()) as backup:
        cmd_backup(
            build_parser().parse_args(["backup", "my-track", str(tmp_path / "backups")])
        )

    backup.assert_called_once_with(
        project.resolve(),
        Path(tmp_path / "backups"),
        force=False,
    )
    out = capsys.readouterr().out
    assert f"Backed up to {archive.resolve()}" in out


def test_cmd_backup_passes_force_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = _complete_project(tmp_path)
    archive = tmp_path / "song.cleave-tar.gz"

    with patch("cleave.archive.backup_project", return_value=archive) as backup:
        cmd_backup(
            build_parser().parse_args(
                ["backup", "my-track", str(tmp_path / "backups"), "--force"]
            )
        )

    backup.assert_called_once_with(
        project.resolve(),
        Path(tmp_path / "backups"),
        force=True,
    )


def test_cmd_restore_calls_restore_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    archive = tmp_path / "song.cleave-tar.gz"
    restored = tmp_path / "projects" / "song"

    with patch("cleave.archive.restore_project", return_value=restored.resolve()) as restore:
        cmd_restore(
            build_parser().parse_args(
                ["restore", str(archive), "--as", "song-copy", "--force"]
            )
        )

    restore.assert_called_once_with(
        Path(archive),
        as_slug="song-copy",
        force=True,
    )
    out = capsys.readouterr().out
    assert f"Restored to {restored.resolve()}" in out


def test_shortcut_flags() -> None:
    parser = build_parser()
    assert parser.parse_args(["separate", "song", "-hq", "-f"]).high_quality
    assert parser.parse_args(["separate", "song", "-hq", "-f"]).force
    assert parser.parse_args(["play", "song", "-hq"]).high_quality
    assert parser.parse_args(["play", "song", "-c", "cfg.yaml"]).config == Path(
        "cfg.yaml"
    )
    assert (
        parser.parse_args(["separate", "song", "-bds", "other"]).beat_detection_stem
        == "other"
    )
    render_args = parser.parse_args(
        ["render", "song", "-c", "cfg.yaml", "-o", "out.mp4", "--start", "5"]
    )
    assert render_args.config == Path("cfg.yaml")
    assert render_args.output == Path("out.mp4")
    assert render_args.start == 5
    assert render_args.end is None


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
    assert "backup" in out
    assert "restore" in out
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
    assert play.stdout.startswith(
        "usage: cleave play [-h] [-hq] [-bds {drums,full-mix,bass,vocals,other}]"
    )

    render = subprocess.run(
        [sys.executable, "-m", "cleave", "render", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    render_usage = render.stdout.split("positional arguments:")[0]
    assert "usage: cleave render [-h] [-c CONFIG] [-o OUTPUT]" in render_usage
    assert "project_dir" in render_usage
    assert "project_dir" in render.stdout
    assert "Cleave project directory" in render.stdout
    assert "-c CONFIG, --config CONFIG" in render.stdout
    assert "-o OUTPUT, --output OUTPUT" in render.stdout
    assert "--start SEC" in render.stdout
    assert "--end SEC" in render.stdout
    assert "-hq" in render.stdout
