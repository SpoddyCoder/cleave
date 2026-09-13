"""Unit tests for in-editor render subprocess argv and progress lines."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from cleave.render_progress import (
    format_render_progress_line,
    parse_render_progress_line,
)
from cleave.viz.project_render_job import (
    ProjectRenderSpec,
    render_job_argv,
    write_render_snapshot,
)


def _spec(tmp_path: Path, *, quality: str = "normal") -> ProjectRenderSpec:
    return ProjectRenderSpec(
        project_dir=tmp_path / "song",
        config_path=tmp_path / "snap.yaml",
        output_path=tmp_path / "song" / "renders" / "song.mp4",
        quality=quality,  # type: ignore[arg-type]
        start_sec=10,
        end_sec=40,
        width=1920,
        height=1080,
        fps=60,
    )


def test_parse_render_progress_line() -> None:
    assert parse_render_progress_line(format_render_progress_line(0.42)) == 0.42
    assert parse_render_progress_line("CLEAVE_RENDER_PROGRESS 1.0000\n") == 1.0
    assert parse_render_progress_line("Encoding 10 frames...") is None
    assert parse_render_progress_line("CLEAVE_RENDER_PROGRESS nope") is None


def test_render_job_argv_checkout_normal(tmp_path: Path) -> None:
    argv = render_job_argv(
        _spec(tmp_path),
        frozen=False,
        executable="/env/bin/python",
    )
    assert argv[:4] == ["/env/bin/python", "-m", "cleave", "render"]
    assert "--hq" not in argv
    assert "--viz-quality" not in argv
    assert argv[argv.index("--start") + 1] == "10"
    assert argv[argv.index("--end") + 1] == "40"
    assert argv[argv.index("--width") + 1] == "1920"
    assert argv[argv.index("--height") + 1] == "1080"
    assert argv[argv.index("--fps") + 1] == "60"
    assert argv[argv.index("-o") + 1].endswith("song.mp4")


def test_render_job_argv_frozen_high(tmp_path: Path) -> None:
    argv = render_job_argv(
        _spec(tmp_path, quality="high"),
        frozen=True,
        executable=r"C:\Cleave\cleave.exe",
    )
    assert argv[:2] == [r"C:\Cleave\cleave.exe", "render"]
    assert "--hq" in argv
    assert "--viz-quality" not in argv


def test_render_job_argv_viz_quality(tmp_path: Path) -> None:
    argv = render_job_argv(
        _spec(tmp_path, quality="viz"),
        frozen=False,
        executable="python",
    )
    assert "--viz-quality" in argv
    assert "--hq" not in argv


@patch("cleave.viz.project_render_job.write_session_snapshot")
def test_write_render_snapshot_places_file_in_project_dir(
    mock_write: MagicMock, tmp_path: Path
) -> None:
    project_dir = tmp_path / "song"
    project_dir.mkdir()
    cfg = MagicMock()
    cfg.config_path = project_dir / "cleave-viz.yaml"
    session = MagicMock()

    path = write_render_snapshot(cfg, session)
    try:
        assert path.parent.resolve() == project_dir.resolve()
        assert path.name.startswith("cleave-render-")
        assert path.suffix == ".yaml"
        mock_write.assert_called_once_with(path, cfg=cfg, session=session)
    finally:
        path.unlink(missing_ok=True)
