"""Tests for cleave.viz.render offline video pipeline."""

from __future__ import annotations

import importlib
import math
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cleave.config import VIZ_CONFIG_FILENAME, RenderConfig, load_config
from cleave.viz.controls import RenderPostFxRuntime
from cleave.paths import repo_root
from cleave.extract import STEM_NAMES, stems_dir
from cleave.project import write_manifest
from cleave.separate import project_stems_complete

render_mod = importlib.import_module("cleave.viz.render")
from cleave.viz.render import validate_render_project  # noqa: E402
from tests.cleave.viz.test_render_overlay import _overlay_cfg
from tests.support.config import write_minimal_config


def _attach_render_post_fx_session(
    runtime: MagicMock,
    *,
    enabled: bool = False,
    fade_in: float = 0.0,
    fade_out: float = 0.0,
) -> None:
    runtime.session = MagicMock()
    runtime.session.render_post_fx = RenderPostFxRuntime(
        enabled=enabled,
        expanded=False,
        fade_in=fade_in,
        fade_out=fade_out,
    )


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
    with pytest.raises(FileNotFoundError, match=VIZ_CONFIG_FILENAME):
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
    runtime.display_width = width
    runtime.display_height = height
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

    _attach_render_post_fx_session(runtime)

    output = render_mod.render(project)

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
    assert "-preset" not in cmd
    assert str(project / "my-track.flac") in cmd
    assert str(expected_output) in cmd


@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "_init_gl_resources_render")
@patch.object(render_mod, "build_runtime_full")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
def test_render_ffmpeg_preset_veryslow_when_high_quality(
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

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = b"\xff" * (width * height * 4)

    runtime = MagicMock()
    runtime.width = width
    runtime.height = height
    runtime.display_width = width
    runtime.display_height = height
    runtime.fps = fps
    runtime.duration_sec = duration_sec
    runtime.layers = []
    runtime.compositor = None
    runtime.post_process = MagicMock()
    mock_build.return_value = runtime

    def _attach_compositor(rt: MagicMock) -> None:
        rt.compositor = compositor

    mock_init_gl.side_effect = _attach_compositor
    mock_app_cls.return_value = MagicMock()

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_render_post_fx_session(runtime)

    render_mod.render(project, high_quality=True)

    cmd = mock_subprocess.Popen.call_args[0][0]
    preset_idx = cmd.index("-preset")
    assert cmd[preset_idx + 1] == "veryslow"


@patch.object(render_mod, "fade_alpha", side_effect=lambda t, d, fi, fo: 0.5)
@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "_init_gl_resources_render")
@patch.object(render_mod, "build_runtime_full")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
def test_render_applies_fade_via_compositor(
    mock_app_cls: MagicMock,
    _mock_scan: MagicMock,
    mock_build: MagicMock,
    mock_init_gl: MagicMock,
    mock_subprocess: MagicMock,
    mock_shutil: MagicMock,
    _mock_pygame: MagicMock,
    _mock_fade_alpha: MagicMock,
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
    runtime.display_width = width
    runtime.display_height = height
    runtime.fps = fps
    runtime.duration_sec = duration_sec
    runtime.layers = []
    runtime.compositor = None
    runtime.post_process = MagicMock()
    mock_build.return_value = runtime

    def _attach_compositor(rt: MagicMock) -> None:
        rt.compositor = compositor

    mock_init_gl.side_effect = _attach_compositor
    mock_app_cls.return_value = MagicMock()

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_render_post_fx_session(
        runtime, enabled=True, fade_in=1.0, fade_out=1.0
    )

    render_mod.render(project)

    assert compositor.apply_frame_fade.call_count == frame_count
    for call in compositor.apply_frame_fade.call_args_list:
        assert call.args == (0.5,)


def test_render_output_must_be_mp4(tmp_path: Path) -> None:
    project = _setup_render_project(tmp_path)
    with pytest.raises(ValueError, match="\\.mp4"):
        render_mod.render(project, output=tmp_path / "out.mkv")


@patch.object(render_mod, "build_panel_surface")
@patch.object(render_mod, "composite_render_overlay")
@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "_init_gl_resources_render")
@patch.object(render_mod, "build_runtime_full")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
@patch.object(render_mod, "load_config")
def test_render_calls_overlay_compositing_when_enabled(
    mock_load_config: MagicMock,
    mock_app_cls: MagicMock,
    _mock_scan: MagicMock,
    mock_build: MagicMock,
    mock_init_gl: MagicMock,
    mock_subprocess: MagicMock,
    mock_shutil: MagicMock,
    _mock_pygame: MagicMock,
    mock_composite: MagicMock,
    mock_build_panel: MagicMock,
    tmp_path: Path,
) -> None:
    mock_shutil.which.return_value = "/usr/bin/ffmpeg"
    project = _setup_render_project(tmp_path)
    width, height, fps = 4, 4, 10
    duration_sec = 2.0
    frame_count = math.ceil(duration_sec * fps)

    overlay_cfg = _overlay_cfg()
    base_cfg = load_config(project / VIZ_CONFIG_FILENAME, repo_root())
    mock_load_config.return_value = replace(
        base_cfg, render=RenderConfig(overlay=overlay_cfg, post_fx=None)
    )

    overlay_panel = MagicMock()
    mock_build_panel.return_value = overlay_panel

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = b"\xff" * (width * height * 4)

    runtime = MagicMock()
    runtime.width = width
    runtime.height = height
    runtime.display_width = width
    runtime.display_height = height
    runtime.fps = fps
    runtime.duration_sec = duration_sec
    runtime.layers = []
    runtime.compositor = None
    runtime.post_process = MagicMock()
    mock_build.return_value = runtime

    def _attach_compositor(rt: MagicMock) -> None:
        rt.compositor = compositor

    mock_init_gl.side_effect = _attach_compositor

    mock_app_cls.return_value = MagicMock()

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_render_post_fx_session(runtime)

    render_mod.render(project)

    mock_build_panel.assert_called_once_with(overlay_cfg)
    assert mock_composite.call_count == frame_count
    for call in mock_composite.call_args_list:
        assert call.args[:2] == (compositor, overlay_cfg)
        assert call.kwargs == {"panel": overlay_panel}


@patch.object(render_mod, "build_panel_surface")
@patch.object(render_mod, "composite_render_overlay")
@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "_init_gl_resources_render")
@patch.object(render_mod, "build_runtime_full")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
@patch.object(render_mod, "load_config")
def test_render_skips_overlay_when_disabled(
    mock_load_config: MagicMock,
    mock_app_cls: MagicMock,
    _mock_scan: MagicMock,
    mock_build: MagicMock,
    mock_init_gl: MagicMock,
    mock_subprocess: MagicMock,
    mock_shutil: MagicMock,
    _mock_pygame: MagicMock,
    mock_composite: MagicMock,
    mock_build_panel: MagicMock,
    tmp_path: Path,
) -> None:
    mock_shutil.which.return_value = "/usr/bin/ffmpeg"
    project = _setup_render_project(tmp_path)

    overlay_cfg = _overlay_cfg(enabled=False)
    base_cfg = load_config(project / VIZ_CONFIG_FILENAME, repo_root())
    mock_load_config.return_value = replace(
        base_cfg, render=RenderConfig(overlay=overlay_cfg, post_fx=None)
    )

    width, height = 4, 4
    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = b"\xff" * (width * height * 4)

    runtime = MagicMock()
    runtime.width = width
    runtime.height = height
    runtime.display_width = width
    runtime.display_height = height
    runtime.fps = 10
    runtime.duration_sec = 2.0
    runtime.layers = []
    runtime.compositor = None
    runtime.post_process = MagicMock()
    mock_build.return_value = runtime

    def _attach_compositor(rt: MagicMock) -> None:
        rt.compositor = compositor

    mock_init_gl.side_effect = _attach_compositor
    mock_app_cls.return_value = MagicMock()

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_render_post_fx_session(runtime)

    render_mod.render(project)

    mock_build_panel.assert_not_called()
    mock_composite.assert_not_called()


@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "_init_gl_resources_render")
@patch.object(render_mod, "build_runtime_full")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
def test_render_ffmpeg_uses_display_dimensions_with_upscale(
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
    content_w, content_h, fps = 4, 4, 10
    upscale = 2.0
    display_w = int(content_w * upscale)
    display_h = int(content_h * upscale)
    duration_sec = 2.0

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = b"\xff" * (display_w * display_h * 4)

    runtime = MagicMock()
    runtime.width = content_w
    runtime.height = content_h
    runtime.upscale = upscale
    runtime.display_width = display_w
    runtime.display_height = display_h
    runtime.fps = fps
    runtime.duration_sec = duration_sec
    runtime.layers = []
    runtime.compositor = None
    runtime.post_process = MagicMock()
    mock_build.return_value = runtime

    def _attach_compositor(rt: MagicMock) -> None:
        rt.compositor = compositor

    mock_init_gl.side_effect = _attach_compositor
    mock_app_cls.return_value = MagicMock()

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_render_post_fx_session(runtime)

    render_mod.render(project)

    cmd = mock_subprocess.Popen.call_args[0][0]
    assert "-s" in cmd and f"{display_w}x{display_h}" in cmd
    assert compositor.present_content.call_count == math.ceil(duration_sec * fps)
