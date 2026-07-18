"""Tests for cleave.viz.render offline video pipeline."""

from __future__ import annotations

import importlib
import math
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cleave.config import VIZ_CONFIG_FILENAME, RenderConfig, load_config
from cleave.preset_playlist import PresetPlaylist
from cleave.timeline import SlotCue, TimelineLane, canonicalize
from cleave.viz.layer_visibility import effective_layer_enabled
from cleave.viz.session import (
    LayerRuntime,
    TimelineRuntime,
    TuningSession,
    default_render_overlay_runtime,
    session_from_cfg,
)
from tests.support.config import TEST_LAYER_STEMS, default_render_post_fx_runtime
from cleave.paths import repo_root
from cleave.config_schema import (
    DEFAULT_LAYER_SLOTS,
    DEFAULT_RENDER_FPS,
    DEFAULT_RENDER_HEIGHT,
    DEFAULT_RENDER_WIDTH,
    template_project_editor_section,
)
from cleave.extract import STEM_NAMES, stems_dir
from cleave.project import write_manifest
from cleave.separate import project_stems_complete

render_mod = importlib.import_module("cleave.viz.render")
from cleave.viz.frame_finish import resolve_overlay_config
from cleave.viz.render import (  # noqa: E402
    RenderSegment,
    _default_output_path,
    _is_partial_segment,
    _resolve_segment,
    validate_render_project,
)
from tests.cleave.viz.test_render_overlay import _overlay_cfg
from tests.support.config import write_minimal_config


def _render_frame_bytes(
    width: int = DEFAULT_RENDER_WIDTH, height: int = DEFAULT_RENDER_HEIGHT
) -> bytes:
    return b"\xff" * (width * height * 4)


def _attach_render_post_fx_session(
    runtime: MagicMock,
    *,
    enabled: bool = False,
    fade_in: float = 0.0,
    fade_out: float = 0.0,
) -> None:
    runtime.seed.session.render_post_fx = default_render_post_fx_runtime(
        enabled=enabled,
        expanded=False,
        fade_in=fade_in,
        fade_out=fade_out,
    )


def _playlist(slot: str) -> PresetPlaylist:
    current_dir = Path(f"/tmp/presets/{slot}")
    paths = tuple(current_dir / f"preset-{i}.milk" for i in range(2))
    return PresetPlaylist(current_dir=current_dir, paths=paths, index=0)


def _session_with_enable_cue_at(beat_t: float) -> TuningSession:
    """Timeline on; layer_1 off until a cue at beat_t turns it on."""
    cues = canonicalize(False, [SlotCue(t=beat_t, visible=True)])
    lane = TimelineLane(baseline=False, cues=cues)
    return TuningSession(
        layer_z_order=list(DEFAULT_LAYER_SLOTS),
        timeline=TimelineRuntime(
            enabled=True,
            lanes={"layer_1": lane},
        ),
        layers={
            slot: LayerRuntime(
                playlist=_playlist(slot),
                browse_floor=Path(f"/tmp/presets/{slot}"),
                stem=TEST_LAYER_STEMS[slot],
                enabled=True,
            )
            for slot in DEFAULT_LAYER_SLOTS
        },
    )


def _attach_session_from_cfg(
    runtime: MagicMock, cfg, *, playlists: dict | None = None
) -> None:
    runtime.seed.cfg = cfg
    if playlists is None:
        playlists = {name: MagicMock() for name in cfg.layer_z_order}
    runtime.seed.session = session_from_cfg(cfg, playlists)


def _mock_render_runtime(
    *,
    width: int,
    height: int,
    fps: int,
    duration_sec: float,
    upscale: float = 1.0,
    display_width: int | None = None,
    display_height: int | None = None,
    output_width: int | None = None,
    output_height: int | None = None,
) -> tuple[MagicMock, MagicMock]:
    seed = MagicMock()
    seed.width = width
    seed.height = height
    seed.upscale = upscale
    seed.display_width = width if display_width is None else display_width
    seed.display_height = height if display_height is None else display_height
    seed.duration_sec = duration_sec
    seed.pcm_bank = MagicMock()
    seed.cfg = MagicMock()
    render_w = DEFAULT_RENDER_WIDTH if output_width is None else output_width
    render_h = DEFAULT_RENDER_HEIGHT if output_height is None else output_height
    seed.cfg.render = RenderConfig(fps=fps, width=render_w, height=render_h)
    seed.session = TuningSession(
        layer_z_order=list(DEFAULT_LAYER_SLOTS),
        render_overlay=replace(default_render_overlay_runtime(), enabled=False),
        render_post_fx=default_render_post_fx_runtime(
            enabled=False,
            expanded=False,
            fade_in=0.0,
            fade_out=0.0,
        ),
    )

    runtime = MagicMock()
    runtime.seed = seed
    runtime.layers = []
    runtime.compositor = MagicMock()
    runtime.post_process = MagicMock()
    return seed, runtime


def _write_stub_stems(project: Path) -> None:
    base = stems_dir(project)
    base.mkdir(parents=True, exist_ok=True)
    for name in STEM_NAMES:
        (base / f"{name}.wav").write_bytes(b"wav")


def _setup_render_project(
    tmp_path: Path,
    *,
    render_fps: int = 10,
    render_width: int | None = None,
    render_height: int | None = None,
    editor: dict | None = None,
) -> Path:
    preset_root = tmp_path / "presets"
    project = tmp_path / "my-track"
    render: dict[str, int] = {"fps": render_fps}
    if render_width is not None:
        render["width"] = render_width
    if render_height is not None:
        render["height"] = render_height
    overrides: dict = {"render": render}
    if editor is not None:
        overrides["editor"] = editor
    write_minimal_config(project, preset_root, **overrides)
    _write_stub_stems(project)
    (project / "signals.json").write_text('{"version": 3}')
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
    (project / "signals.json").write_text('{"version": 3}')
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
    (project / "signals.json").write_text('{"version": 3}')
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


def test_resolve_segment_defaults_to_full_track() -> None:
    segment = _resolve_segment(None, None, duration_sec=59.5, fps=30)
    assert segment == RenderSegment(
        start_sec=0,
        end_label_sec=60,
        end_explicit=False,
        start_frame=0,
        end_frame_exclusive=math.ceil(59.5 * 30),
        frame_count=math.ceil(59.5 * 30),
    )


def test_resolve_segment_partial_range() -> None:
    segment = _resolve_segment(10, 20, duration_sec=60.0, fps=10)
    assert segment.start_sec == 10
    assert segment.end_label_sec == 20
    assert segment.end_explicit is True
    assert segment.start_frame == 100
    assert segment.end_frame_exclusive == 200
    assert segment.frame_count == 100


def test_resolve_segment_start_only_uses_full_end_label() -> None:
    segment = _resolve_segment(10, None, duration_sec=59.5, fps=10)
    assert segment.end_label_sec == 60
    assert segment.end_explicit is False
    assert segment.frame_count == math.ceil(59.5 * 10) - 100


@pytest.mark.parametrize(
    ("start_sec", "end_sec", "match"),
    [
        (-1, None, "start must be >= 0"),
        (0, -1, "end must be >= 0"),
        (20, 10, "start must be less than end"),
        (0, 61, "end must be <= 60"),
        (60, None, "segment produces no frames"),
    ],
)
def test_resolve_segment_validation_errors(
    start_sec: int | None, end_sec: int | None, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        _resolve_segment(start_sec, end_sec, duration_sec=59.5, fps=30)


def test_is_partial_segment() -> None:
    full = _resolve_segment(None, None, duration_sec=60.0, fps=30)
    assert not _is_partial_segment(full, duration_sec=60.0)

    from_start = _resolve_segment(10, None, duration_sec=60.0, fps=30)
    assert _is_partial_segment(from_start, duration_sec=60.0)

    clipped = _resolve_segment(0, 30, duration_sec=60.0, fps=30)
    assert _is_partial_segment(clipped, duration_sec=60.0)

    full_end = _resolve_segment(0, 60, duration_sec=59.5, fps=30)
    assert not _is_partial_segment(full_end, duration_sec=59.5)


def test_default_output_path_suffix_only_for_partial_segments(tmp_path: Path) -> None:
    full = _resolve_segment(None, None, duration_sec=60.0, fps=30)
    assert _default_output_path(
        tmp_path, "my-viz", full, duration_sec=60.0
    ) == tmp_path / "renders" / "my-viz.mp4"

    partial = _resolve_segment(10, 20, duration_sec=60.0, fps=30)
    assert _default_output_path(
        tmp_path, "my-viz", partial, duration_sec=60.0
    ) == tmp_path / "renders" / "my-viz_10-20s.mp4"

    start_only = _resolve_segment(10, None, duration_sec=59.5, fps=30)
    assert _default_output_path(
        tmp_path, "my-viz", start_only, duration_sec=59.5
    ) == tmp_path / "renders" / "my-viz_10-60s.mp4"


@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
def test_render_default_passes_viz_quality_false_to_init_gl(
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
    project = _setup_render_project(
        tmp_path,
        render_width=1920,
        render_height=1080,
    )
    fps = 10
    duration_sec = 2.0

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = _render_frame_bytes(1920, 1080)

    seed, runtime = _mock_render_runtime(
        width=1920, height=1080, fps=fps, duration_sec=duration_sec
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime

    mock_app = MagicMock()
    mock_app_cls.return_value = mock_app

    stdin_mock = MagicMock()
    proc = MagicMock()
    proc.stdin = stdin_mock
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_render_post_fx_session(runtime)

    render_mod.render(project)

    mock_init_gl.assert_called_once()
    assert mock_init_gl.call_args.kwargs["viz_quality"] is False


@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
def test_render_viz_quality_passes_flag_to_init_gl(
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
    project = _setup_render_project(
        tmp_path,
        render_width=1920,
        render_height=1080,
    )
    fps = 10
    duration_sec = 2.0

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = _render_frame_bytes(1920, 1080)

    seed, runtime = _mock_render_runtime(
        width=1920, height=1080, fps=fps, duration_sec=duration_sec
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime

    mock_app = MagicMock()
    mock_app_cls.return_value = mock_app

    stdin_mock = MagicMock()
    proc = MagicMock()
    proc.stdin = stdin_mock
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_render_post_fx_session(runtime)

    render_mod.render(project, viz_quality=True)

    mock_init_gl.assert_called_once()
    assert mock_init_gl.call_args.kwargs["viz_quality"] is True


@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
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
    compositor.read_rgba_frame.return_value = _render_frame_bytes()

    seed, runtime = _mock_render_runtime(
        width=width, height=height, fps=fps, duration_sec=duration_sec
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime

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
    assert output.output_path == expected_output.resolve()
    assert mock_app.tick_frame.call_count == frame_count
    assert compositor.read_rgba_frame.call_count == frame_count
    assert stdin_mock.write.call_count == frame_count
    stdin_mock.close.assert_called_once()
    proc.wait.assert_called_once()

    cmd = mock_subprocess.Popen.call_args[0][0]
    assert cmd[0] == "/usr/bin/ffmpeg"
    assert "-s" in cmd and f"{DEFAULT_RENDER_WIDTH}x{DEFAULT_RENDER_HEIGHT}" in cmd
    assert "-r" in cmd and str(fps) in cmd
    assert "-preset" not in cmd
    assert str(project / "my-track.flac") in cmd
    assert str(expected_output) in cmd


@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
def test_render_segment_frame_count_tick_times_and_ffmpeg_trim(
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
    duration_sec = 60.0
    start_sec, end_sec = 10, 20
    frame_count = (end_sec - start_sec) * fps

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = _render_frame_bytes()

    seed, runtime = _mock_render_runtime(
        width=width, height=height, fps=fps, duration_sec=duration_sec
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime

    mock_app = MagicMock()
    mock_app_cls.return_value = mock_app

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_render_post_fx_session(runtime)

    output = render_mod.render(project, start_sec=start_sec, end_sec=end_sec)

    expected_output = project / "renders" / "cleave-test_10-20s.mp4"
    assert output.output_path == expected_output.resolve()
    assert mock_app.tick_frame.call_count == frame_count
    tick_times = [call.args[0] for call in mock_app.tick_frame.call_args_list]
    assert tick_times[0] == pytest.approx(start_sec)
    assert tick_times[-1] == pytest.approx(end_sec - 1 / fps)

    cmd = mock_subprocess.Popen.call_args[0][0]
    audio_path = str(project / "my-track.flac")
    audio_idx = cmd.index(audio_path)
    ss_idx = cmd.index("-ss")
    t_idx = cmd.index("-t")
    assert ss_idx < audio_idx
    assert t_idx < audio_idx
    assert cmd[ss_idx + 1] == str(start_sec)
    assert cmd[t_idx + 1] == str(frame_count / fps)
    assert cmd[audio_idx - 1] == "-i"
    assert cmd[audio_idx - 2] == str(frame_count / fps)
    assert cmd[audio_idx - 3] == "-t"
    assert cmd[audio_idx - 4] == str(start_sec)
    assert cmd[audio_idx - 5] == "-ss"


@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
@pytest.mark.parametrize(
    "start_sec,end_sec,duration_sec,beat_t",
    [
        (None, None, 5.0, 1.5),
        (10, 20, 60.0, 12.0),
    ],
    ids=["full_song", "partial_segment"],
)
def test_render_cue_at_beat_aligns_with_file_timeline_and_mux(
    mock_app_cls: MagicMock,
    _mock_scan: MagicMock,
    mock_build: MagicMock,
    mock_init_gl: MagicMock,
    mock_subprocess: MagicMock,
    mock_shutil: MagicMock,
    _mock_pygame: MagicMock,
    tmp_path: Path,
    start_sec: int | None,
    end_sec: int | None,
    duration_sec: float,
    beat_t: float,
) -> None:
    """Cue at on-grid beat t flips at round(t*fps); tick times match ffmpeg mux."""
    mock_shutil.which.return_value = "/usr/bin/ffmpeg"
    fps = 30
    project = _setup_render_project(tmp_path, render_fps=fps)
    width, height = 4, 4

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = _render_frame_bytes()

    seed, runtime = _mock_render_runtime(
        width=width, height=height, fps=fps, duration_sec=duration_sec
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime

    mock_app = MagicMock()
    mock_app_cls.return_value = mock_app

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_render_post_fx_session(runtime)

    render_kwargs: dict = {}
    if start_sec is not None:
        render_kwargs["start_sec"] = start_sec
    if end_sec is not None:
        render_kwargs["end_sec"] = end_sec
    render_mod.render(project, **render_kwargs)

    segment = _resolve_segment(
        start_sec, end_sec, duration_sec=duration_sec, fps=fps
    )
    tick_times = [call.args[0] for call in mock_app.tick_frame.call_args_list]
    assert len(tick_times) == segment.frame_count
    for frame_idx, t_sec in enumerate(tick_times):
        assert t_sec == pytest.approx(
            (segment.start_frame + frame_idx) / fps
        )

    transition_abs_frame = round(beat_t * fps)
    transition_frame_idx = transition_abs_frame - segment.start_frame
    assert 0 <= transition_frame_idx < segment.frame_count
    assert tick_times[transition_frame_idx] == pytest.approx(beat_t)

    session = _session_with_enable_cue_at(beat_t)
    for frame_idx, t_sec in enumerate(tick_times):
        visible = effective_layer_enabled(session, "layer_1", t_sec)
        if frame_idx < transition_frame_idx:
            assert visible is False
        else:
            assert visible is True

    cmd = mock_subprocess.Popen.call_args[0][0]
    audio_path = str(project / "my-track.flac")
    audio_idx = cmd.index(audio_path)
    assert cmd[cmd.index("-ss") + 1] == str(segment.start_sec)
    assert cmd[cmd.index("-t") + 1] == str(segment.frame_count / fps)
    assert cmd[audio_idx - 5] == "-ss"
    assert cmd[audio_idx - 4] == str(segment.start_sec)
    assert cmd[audio_idx - 3] == "-t"
    assert cmd[audio_idx - 2] == str(segment.frame_count / fps)


@patch("cleave.viz.frame_finish.live_frame_fade_alpha", return_value=1.0)
@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
def test_render_segment_fade_alpha_uses_full_duration(
    mock_app_cls: MagicMock,
    _mock_scan: MagicMock,
    mock_build: MagicMock,
    mock_init_gl: MagicMock,
    mock_subprocess: MagicMock,
    mock_shutil: MagicMock,
    _mock_pygame: MagicMock,
    mock_fade_alpha: MagicMock,
    tmp_path: Path,
) -> None:
    mock_shutil.which.return_value = "/usr/bin/ffmpeg"
    project = _setup_render_project(tmp_path)
    width, height, fps = 4, 4, 10
    duration_sec = 60.0

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = _render_frame_bytes()

    seed, runtime = _mock_render_runtime(
        width=width, height=height, fps=fps, duration_sec=duration_sec
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime
    mock_app_cls.return_value = MagicMock()

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_render_post_fx_session(runtime, enabled=True, fade_in=5.0, fade_out=5.0)

    render_mod.render(project, start_sec=10, end_sec=20)

    for call in mock_fade_alpha.call_args_list:
        assert call.args[1] == duration_sec


@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
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
    compositor.read_rgba_frame.return_value = _render_frame_bytes()

    seed, runtime = _mock_render_runtime(
        width=width, height=height, fps=fps, duration_sec=duration_sec
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime
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


@patch("cleave.viz.frame_finish.live_frame_fade_alpha", side_effect=lambda *_a, **_k: 0.5)
@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
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
    compositor.read_rgba_frame.return_value = _render_frame_bytes()

    seed, runtime = _mock_render_runtime(
        width=width, height=height, fps=fps, duration_sec=duration_sec
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime
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


@patch("cleave.viz.frame_finish.live_overlay_alpha", return_value=1.0)
@patch("cleave.viz.frame_finish.build_panel_surface")
@patch("cleave.viz.frame_finish.composite_render_overlay_with_alpha")
@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
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
    _mock_overlay_alpha: MagicMock,
    tmp_path: Path,
) -> None:
    mock_shutil.which.return_value = "/usr/bin/ffmpeg"
    project = _setup_render_project(tmp_path)
    width, height, fps = 4, 4, 10
    duration_sec = 2.0
    frame_count = math.ceil(duration_sec * fps)

    overlay_cfg = _overlay_cfg(start_delay=0.0)
    base_cfg = load_config(project / VIZ_CONFIG_FILENAME, repo_root())
    mock_load_config.return_value = replace(
        base_cfg, render=RenderConfig(fps=fps, overlay=overlay_cfg, post_fx=None)
    )

    overlay_panel = MagicMock()
    mock_build_panel.return_value = overlay_panel

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = _render_frame_bytes()

    seed, runtime = _mock_render_runtime(
        width=width, height=height, fps=fps, duration_sec=duration_sec
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime

    mock_app_cls.return_value = MagicMock()

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_session_from_cfg(runtime, mock_load_config.return_value)

    render_mod.render(project)

    expected_cfg = resolve_overlay_config(
        mock_load_config.return_value, runtime.seed.session
    )
    mock_build_panel.assert_called_once_with(expected_cfg)
    assert mock_composite.call_count == frame_count
    for call in mock_composite.call_args_list:
        assert call.args[0] == compositor
        assert call.args[1] == expected_cfg
        assert call.args[3:5] == (width, height)
        assert call.kwargs == {"panel": overlay_panel}


@patch("cleave.viz.frame_finish.build_panel_surface")
@patch("cleave.viz.frame_finish.composite_render_overlay_with_alpha")
@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
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
    fps = base_cfg.render.fps if base_cfg.render is not None else 10
    mock_load_config.return_value = replace(
        base_cfg, render=RenderConfig(fps=fps, overlay=overlay_cfg, post_fx=None)
    )

    width, height = 4, 4
    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = _render_frame_bytes()

    seed, runtime = _mock_render_runtime(
        width=width, height=height, fps=10, duration_sec=2.0
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime
    mock_app_cls.return_value = MagicMock()

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_session_from_cfg(runtime, mock_load_config.return_value)

    render_mod.render(project)

    mock_build_panel.assert_not_called()
    mock_composite.assert_not_called()


@patch("cleave.viz.frame_finish.live_overlay_alpha", return_value=1.0)
@patch("cleave.viz.frame_finish.composite_render_overlay_with_alpha")
@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
@patch.object(render_mod, "load_config")
def test_render_composites_default_overlay_when_render_absent(
    mock_load_config: MagicMock,
    mock_app_cls: MagicMock,
    _mock_scan: MagicMock,
    mock_build: MagicMock,
    mock_init_gl: MagicMock,
    mock_subprocess: MagicMock,
    mock_shutil: MagicMock,
    _mock_pygame: MagicMock,
    mock_composite: MagicMock,
    _mock_overlay_alpha: MagicMock,
    tmp_path: Path,
) -> None:
    mock_shutil.which.return_value = "/usr/bin/ffmpeg"
    project = _setup_render_project(tmp_path)
    width, height = 4, 4
    duration_sec = 60.0
    start_sec, end_sec = 10, 12
    frame_count = (end_sec - start_sec) * DEFAULT_RENDER_FPS

    base_cfg = load_config(project / VIZ_CONFIG_FILENAME, repo_root())
    mock_load_config.return_value = replace(base_cfg, render=None)

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = _render_frame_bytes()

    seed, runtime = _mock_render_runtime(
        width=width, height=height, fps=DEFAULT_RENDER_FPS, duration_sec=duration_sec
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime
    mock_app_cls.return_value = MagicMock()

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_session_from_cfg(runtime, mock_load_config.return_value)

    render_mod.render(project, start_sec=start_sec, end_sec=end_sec)

    assert mock_composite.call_count == frame_count


@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
def test_render_ffmpeg_ignores_upscale_uses_render_resolution(
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
    project = _setup_render_project(
        tmp_path,
        render_fps=10,
        render_width=1280,
        render_height=720,
        editor={
            **template_project_editor_section(name="cleave-test"),
            "width": 640,
            "height": 360,
            "upscale": 2.0,
        },
    )
    content_w, content_h, fps = 640, 360, 10
    upscale = 2.0
    live_display_w = int(content_w * upscale)
    live_display_h = int(content_h * upscale)
    render_w, render_h = 1280, 720
    duration_sec = 2.0

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = b"\xff" * (render_w * render_h * 4)

    seed, runtime = _mock_render_runtime(
        width=content_w,
        height=content_h,
        fps=fps,
        duration_sec=duration_sec,
        upscale=upscale,
        display_width=live_display_w,
        display_height=live_display_h,
        output_width=render_w,
        output_height=render_h,
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime
    mock_app_cls.return_value = MagicMock()

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_render_post_fx_session(runtime)

    render_mod.render(project)

    cmd = mock_subprocess.Popen.call_args[0][0]
    assert "-s" in cmd and f"{render_w}x{render_h}" in cmd
    mock_init_gl.assert_called_once_with(
        seed, output_width=render_w, output_height=render_h, viz_quality=False
    )
    assert compositor.present_content.call_count == math.ceil(duration_sec * fps)


@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
def test_render_ffmpeg_uses_explicit_render_resolution(
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
    project = _setup_render_project(
        tmp_path, render_fps=10, render_width=1920, render_height=1080
    )
    content_w, content_h, fps = 4, 4, 10
    render_w, render_h = 1920, 1080
    duration_sec = 2.0

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = b"\xff" * (render_w * render_h * 4)

    seed, runtime = _mock_render_runtime(
        width=content_w,
        height=content_h,
        fps=fps,
        duration_sec=duration_sec,
        output_width=render_w,
        output_height=render_h,
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime
    mock_app_cls.return_value = MagicMock()

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_render_post_fx_session(runtime)

    render_mod.render(project)

    cmd = mock_subprocess.Popen.call_args[0][0]
    assert "-s" in cmd and f"{render_w}x{render_h}" in cmd
    mock_init_gl.assert_called_once_with(
        seed, output_width=render_w, output_height=render_h, viz_quality=False
    )


@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
def test_render_present_content_every_frame_at_upscale_one(
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
    upscale = 1.0
    render_w, render_h = DEFAULT_RENDER_WIDTH, DEFAULT_RENDER_HEIGHT
    duration_sec = 2.0

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = b"\xff" * (render_w * render_h * 4)

    seed, runtime = _mock_render_runtime(
        width=content_w,
        height=content_h,
        fps=fps,
        duration_sec=duration_sec,
        upscale=upscale,
        output_width=render_w,
        output_height=render_h,
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime
    mock_app_cls.return_value = MagicMock()

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_render_post_fx_session(runtime)

    render_mod.render(project)

    assert compositor.present_content.call_count == math.ceil(duration_sec * fps)


@patch("cleave.viz.frame_finish.live_overlay_alpha", return_value=1.0)
@patch("cleave.viz.frame_finish.build_panel_surface")
@patch.object(render_mod, "pygame")
@patch.object(render_mod, "shutil")
@patch.object(render_mod, "subprocess")
@patch.object(render_mod, "init_gl_resources_render")
@patch.object(render_mod, "build_runtime_base")
@patch.object(render_mod, "scan_all_layers", return_value={})
@patch.object(render_mod, "VisualizerApp")
@patch.object(render_mod, "load_config")
def test_render_upscale_overlay_frame_order_uses_content_dims(
    mock_load_config: MagicMock,
    mock_app_cls: MagicMock,
    _mock_scan: MagicMock,
    mock_build: MagicMock,
    mock_init_gl: MagicMock,
    mock_subprocess: MagicMock,
    mock_shutil: MagicMock,
    _mock_pygame: MagicMock,
    mock_build_panel: MagicMock,
    _mock_overlay_alpha: MagicMock,
    tmp_path: Path,
) -> None:
    mock_shutil.which.return_value = "/usr/bin/ffmpeg"
    project = _setup_render_project(tmp_path)
    content_w, content_h, fps = 4, 4, 10
    upscale = 2.0
    live_display_w = int(content_w * upscale)
    live_display_h = int(content_h * upscale)
    render_w, render_h = 1280, 720
    duration_sec = 2.0
    frame_count = math.ceil(duration_sec * fps)

    overlay_cfg = _overlay_cfg(start_delay=0.0, display_time=30.0)
    base_cfg = load_config(project / VIZ_CONFIG_FILENAME, repo_root())
    mock_load_config.return_value = replace(
        base_cfg,
        render=RenderConfig(
            fps=fps, width=render_w, height=render_h, overlay=overlay_cfg, post_fx=None
        ),
    )
    overlay_panel = MagicMock()
    mock_build_panel.return_value = overlay_panel

    compositor = MagicMock()
    compositor.read_rgba_frame.return_value = b"\xff" * (render_w * render_h * 4)
    call_order: list[str] = []

    def _track(name: str):
        def _wrapper(*_args, **_kwargs):
            call_order.append(name)

        return _wrapper

    compositor.apply_frame_fade.side_effect = _track("apply_frame_fade")
    compositor.present_content.side_effect = _track("present_content")
    compositor.read_rgba_frame.side_effect = lambda: (
        call_order.append("read_rgba_frame"),
        compositor.read_rgba_frame.return_value,
    )[1]

    seed, runtime = _mock_render_runtime(
        width=content_w,
        height=content_h,
        fps=fps,
        duration_sec=duration_sec,
        upscale=upscale,
        display_width=live_display_w,
        display_height=live_display_h,
        output_width=render_w,
        output_height=render_h,
    )
    runtime.compositor = compositor
    mock_build.return_value = seed
    mock_init_gl.return_value = runtime
    mock_app_cls.return_value = MagicMock()

    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.wait.return_value = 0
    mock_subprocess.Popen.return_value = proc

    _attach_session_from_cfg(runtime, mock_load_config.return_value)

    with patch(
        "cleave.viz.frame_finish.composite_render_overlay_with_alpha",
        side_effect=lambda *args, **kwargs: call_order.append(
            "composite_render_overlay"
        ),
    ) as mock_composite:
        render_mod.render(project)

    assert mock_composite.call_count == frame_count
    for call in mock_composite.call_args_list:
        assert call.args[3:5] == (content_w, content_h)

    expected_per_frame = [
        "apply_frame_fade",
        "composite_render_overlay",
        "present_content",
        "read_rgba_frame",
    ]
    for frame_idx in range(frame_count):
        start = frame_idx * len(expected_per_frame)
        assert call_order[start : start + len(expected_per_frame)] == expected_per_frame
