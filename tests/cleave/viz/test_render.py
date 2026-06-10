"""Tests for cleave.viz.render offline video pipeline."""

from __future__ import annotations

import importlib
import math
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cleave.config import PROJECT_VIZ_CONFIG_FILENAME
from cleave.extract import STEM_NAMES, stems_dir
from cleave.project import write_manifest
from cleave.separate import project_stems_complete

render_mod = importlib.import_module("cleave.viz.render")
from cleave.viz.render import (  # noqa: E402
    _smoothstep,
    validate_render_project,
    visual_fade_alpha,
)
from tests.support.config import write_minimal_config


def _write_stub_stems(project: Path) -> None:
    base = stems_dir(project)
    base.mkdir(parents=True, exist_ok=True)
    for name in STEM_NAMES:
        (base / f"{name}.wav").write_bytes(b"wav")


def _setup_render_project(tmp_path: Path) -> Path:
    preset_root = tmp_path / "presets"
    project = tmp_path / "my-track"
    write_minimal_config(project, preset_root)
    _write_stub_stems(project)
    (project / "signals.json").write_text("{}")
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )
    return project


def test_smoothstep_endpoints() -> None:
    assert _smoothstep(0.0) == 0.0
    assert _smoothstep(1.0) == 1.0


def test_visual_fade_alpha_no_fades() -> None:
    assert visual_fade_alpha(0.0, 10.0, 0.0, 0.0) == 1.0
    assert visual_fade_alpha(5.0, 10.0, 0.0, 0.0) == 1.0
    assert visual_fade_alpha(10.0, 10.0, 0.0, 0.0) == 1.0


def test_visual_fade_alpha_fade_in() -> None:
    assert visual_fade_alpha(0.0, 10.0, 2.0, 0.0) == 0.0
    assert visual_fade_alpha(1.0, 10.0, 2.0, 0.0) == _smoothstep(0.5)
    assert visual_fade_alpha(2.0, 10.0, 2.0, 0.0) == 1.0
    assert visual_fade_alpha(5.0, 10.0, 2.0, 0.0) == 1.0


def test_visual_fade_alpha_fade_out() -> None:
    assert visual_fade_alpha(8.0, 10.0, 0.0, 2.0) == 1.0
    assert visual_fade_alpha(9.0, 10.0, 0.0, 2.0) == _smoothstep(0.5)
    assert visual_fade_alpha(10.0, 10.0, 0.0, 2.0) == 0.0


def test_visual_fade_alpha_combined() -> None:
    duration = 10.0
    fade_in = 2.0
    fade_out = 2.0
    assert visual_fade_alpha(1.0, duration, fade_in, fade_out) == _smoothstep(0.5)
    assert visual_fade_alpha(5.0, duration, fade_in, fade_out) == 1.0
    assert visual_fade_alpha(9.0, duration, fade_in, fade_out) == _smoothstep(0.5)


def test_validate_render_project_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="project not found"):
        validate_render_project(tmp_path / "missing")


def test_validate_render_project_missing_manifest(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    with pytest.raises(FileNotFoundError, match="project.yaml"):
        validate_render_project(project)


def test_validate_render_project_missing_stems(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )
    with pytest.raises(FileNotFoundError, match="missing stem wavs"):
        validate_render_project(project)


def test_validate_render_project_missing_signals(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    _write_stub_stems(project)
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )
    with pytest.raises(FileNotFoundError, match="signals.json"):
        validate_render_project(project)


def test_validate_render_project_missing_viz_config(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    _write_stub_stems(project)
    (project / "signals.json").write_text("{}")
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )
    with pytest.raises(FileNotFoundError, match=PROJECT_VIZ_CONFIG_FILENAME):
        validate_render_project(project)


def test_validate_render_project_missing_mix(tmp_path: Path) -> None:
    preset_root = tmp_path / "presets"
    project = tmp_path / "my-track"
    write_minimal_config(project, preset_root)
    _write_stub_stems(project)
    (project / "signals.json").write_text("{}")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )
    with pytest.raises(FileNotFoundError, match="mix audio not found"):
        validate_render_project(project)


def test_validate_render_project_ok(tmp_path: Path) -> None:
    project = _setup_render_project(tmp_path)
    assert validate_render_project(project) == project.resolve()
    assert project_stems_complete(project)


@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "_init_gl_resources_render")
@patch.object(render_mod, "build_runtime_full")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
def test_render_frame_count_and_ffmpeg_args(
    mock_app_cls: MagicMock,
    _mock_scan: MagicMock,
    mock_build: MagicMock,
    mock_init_gl: MagicMock,
    mock_subprocess: MagicMock,
    mock_shutil: MagicMock,
    _mock_pygame: MagicMock,
    tmp_path: Path,
) -> None:
    mock_shutil.which.return_value = "/usr/bin/ffmpeg"
    project = _setup_render_project(tmp_path)
    width, height, fps = 4, 4, 10
    duration_sec = 2.0
    frame_count = math.ceil(duration_sec * fps)

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = b"\xff" * (width * height * 4)

    runtime = MagicMock()
    runtime.width = width
    runtime.height = height
    runtime.fps = fps
    runtime.duration_sec = duration_sec
    runtime.layers = []
    runtime.compositor = None
    runtime.post_process = MagicMock()
    mock_build.return_value = runtime

    def _attach_compositor(rt: MagicMock) -> None:
        rt.compositor = compositor

    mock_init_gl.side_effect = _attach_compositor

    mock_app = MagicMock()
    mock_app_cls.return_value = mock_app

    stdin_mock = MagicMock()
    proc = MagicMock()
    proc.stdin = stdin_mock
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    output = render_mod.render(project, fade_in=0.0, fade_out=0.0)

    expected_output = project / "renders" / "cleave-test.mp4"
    assert output == expected_output.resolve()
    assert mock_app.tick_frame.call_count == frame_count
    assert compositor.read_rgba_frame.call_count == frame_count
    assert stdin_mock.write.call_count == frame_count
    stdin_mock.close.assert_called_once()
    proc.wait.assert_called_once()

    cmd = mock_subprocess.Popen.call_args[0][0]
    assert cmd[0] == "/usr/bin/ffmpeg"
    assert "-s" in cmd and f"{width}x{height}" in cmd
    assert "-r" in cmd and str(fps) in cmd
    assert str(project / "my-track.flac") in cmd
    assert str(expected_output) in cmd


def test_render_output_must_be_mp4(tmp_path: Path) -> None:
    project = _setup_render_project(tmp_path)
    with pytest.raises(ValueError, match="\\.mp4"):
        render_mod.render(project, output=tmp_path / "out.mkv")
