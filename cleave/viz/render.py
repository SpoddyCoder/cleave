"""Offline video render: GL frames piped to ffmpeg with project mix audio."""

from __future__ import annotations

import math
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pygame

from cleave.config import VIZ_CONFIG_FILENAME, load_config
from cleave.paths import default_project_config, repo_root, resolve_project
from cleave.preset_playlist import scan_all_layers
from cleave.project import load_manifest, manifest_path, mix_path
from cleave.separate import project_stems_complete, signals_complete
from cleave.viz.app import (
    RenderVisualizerRuntime,
    VisualizerApp,
    _init_gl_resources_render,
    build_runtime_base,
)
from cleave.viz.frame_finish import RenderOverlayPanelCache, finish_content_frame
from cleave.viz.layer_pipeline import LayerFramePipeline

_PREPARE_HINT = "run `cleave separate` or `cleave play` first"


@dataclass(frozen=True)
class RenderResult:
    output_path: Path
    display_width: int
    display_height: int
    mix_filename: str
    segment: RenderSegment | None = None


@dataclass(frozen=True)
class RenderSegment:
    start_sec: int
    end_label_sec: int
    end_explicit: bool
    start_frame: int
    end_frame_exclusive: int
    frame_count: int


def _resolve_segment(
    start_sec: int | None,
    end_sec: int | None,
    *,
    duration_sec: float,
    fps: int,
) -> RenderSegment:
    start = 0 if start_sec is None else start_sec
    end_explicit = end_sec is not None
    duration_ceil = math.ceil(duration_sec)

    if start < 0:
        raise ValueError("start must be >= 0")
    if end_explicit and end_sec < 0:
        raise ValueError("end must be >= 0")
    if end_explicit:
        assert end_sec is not None
        if start >= end_sec:
            raise ValueError("start must be less than end")
        if end_sec > duration_ceil:
            raise ValueError(f"end must be <= {duration_ceil}")
        end_frame_exclusive = end_sec * fps
        end_label_sec = end_sec
    else:
        end_frame_exclusive = math.ceil(duration_sec * fps)
        end_label_sec = duration_ceil

    start_frame = start * fps
    frame_count = end_frame_exclusive - start_frame
    if start_frame >= end_frame_exclusive:
        raise ValueError("segment produces no frames")

    return RenderSegment(
        start_sec=start,
        end_label_sec=end_label_sec,
        end_explicit=end_explicit,
        start_frame=start_frame,
        end_frame_exclusive=end_frame_exclusive,
        frame_count=frame_count,
    )


def _is_partial_segment(
    segment: RenderSegment,
    *,
    duration_sec: float,
) -> bool:
    if segment.start_sec > 0:
        return True
    if segment.end_explicit and segment.end_label_sec < math.ceil(duration_sec):
        return True
    return False


def _default_output_path(
    project: Path,
    name: str,
    segment: RenderSegment,
    *,
    duration_sec: float,
) -> Path:
    if _is_partial_segment(segment, duration_sec=duration_sec):
        return (
            project
            / "renders"
            / f"{name}_{segment.start_sec}-{segment.end_label_sec}s.mp4"
        )
    return project / "renders" / f"{name}.mp4"


def _resolve_render_config_path(
    config_override: Path | None, project_dir: Path
) -> Path:
    if config_override is not None:
        path = config_override.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"config file not found: {path}")
        return path

    path = default_project_config(project_dir)
    if not path.is_file():
        raise FileNotFoundError(
            f"no {VIZ_CONFIG_FILENAME} in {project_dir}; {_PREPARE_HINT}"
        )
    return path


def validate_render_project(
    project_dir: Path | str, *, config: Path | None = None
) -> Path:
    """Ensure *project_dir* is ready for offline render; return resolved path."""
    project = resolve_project(project_dir)

    if not manifest_path(project).is_file():
        raise FileNotFoundError(
            f"no {manifest_path(project).name} in {project}; {_PREPARE_HINT}"
        )

    if not project_stems_complete(project):
        raise FileNotFoundError(f"missing stem wavs in {project}; {_PREPARE_HINT}")

    if not signals_complete(project):
        raise FileNotFoundError(f"no signals.json in {project}; {_PREPARE_HINT}")

    _resolve_render_config_path(config, project)

    audio_path = mix_path(project)
    if not audio_path.is_file():
        raise FileNotFoundError(f"mix audio not found: {audio_path}; {_PREPARE_HINT}")

    return project


def render(
    project_dir: Path | str,
    *,
    config: Path | None = None,
    output: Path | None = None,
    high_quality: bool = False,
    start_sec: int | None = None,
    end_sec: int | None = None,
) -> RenderResult:
    """Render project visuals to an MP4 muxed with the project mix audio."""
    project = validate_render_project(project_dir, config=config)
    config_path = _resolve_render_config_path(config, project)
    cfg = load_config(config_path, repo_root())

    if output is not None:
        output_path = Path(output).expanduser()
        if output_path.suffix.lower() != ".mp4":
            raise ValueError("output path must end with .mp4")

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FileNotFoundError("ffmpeg not found on PATH")

    audio_path = mix_path(project)
    playlists = scan_all_layers(cfg)
    seed = build_runtime_base(cfg, project, audio_path, playlists)

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    pygame.init()
    try:
        pygame.display.set_mode(
            (seed.display_width, seed.display_height),
            pygame.OPENGL | pygame.HIDDEN,
        )
    except pygame.error as exc:
        pygame.quit()
        raise RuntimeError(f"failed to open OpenGL context: {exc}") from exc

    proc: subprocess.Popen[bytes] | None = None
    runtime: RenderVisualizerRuntime | None = None
    try:
        runtime = _init_gl_resources_render(seed)
        app = VisualizerApp(runtime)

        duration_sec = runtime.seed.duration_sec
        fps = runtime.seed.fps
        segment = _resolve_segment(
            start_sec, end_sec, duration_sec=duration_sec, fps=fps
        )
        if output is None:
            output_path = _default_output_path(
                project,
                cfg.visualizer.name,
                segment,
                duration_sec=duration_sec,
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        width = runtime.seed.display_width
        height = runtime.seed.display_height
        frame_count = segment.frame_count
        frame_bytes = width * height * 4
        audio_duration_sec = frame_count / fps

        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
            "-i",
            str(audio_path),
            "-ss",
            str(segment.start_sec),
            "-t",
            str(audio_duration_sec),
            "-c:v",
            "libx264",
        ]
        if high_quality:
            cmd.extend(["-preset", "veryslow"])
        cmd.extend(
            [
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(output_path),
            ]
        )
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        assert proc.stdin is not None

        panel_cache = RenderOverlayPanelCache()

        warmup_frames = round(cfg.visualizer.warmup_sec * fps)
        if warmup_frames > 0:
            LayerFramePipeline.warmup(
                runtime.layers,
                runtime.seed.pcm_bank,
                segment.start_frame / fps,
                warmup_frames,
                fps,
                runtime.seed.n_pcm,
                session=runtime.seed.session,
            )

        for frame_idx in range(frame_count):
            t_sec = (segment.start_frame + frame_idx) / fps
            app.tick_frame(t_sec, paused=False, draw_overlay=False)
            finish_content_frame(
                runtime,
                t_sec,
                panel_cache=panel_cache,
            )
            frame = runtime.compositor.read_rgba_frame()
            if len(frame) != frame_bytes:
                raise RuntimeError(
                    f"expected {frame_bytes} frame bytes, got {len(frame)}"
                )
            proc.stdin.write(frame)

        proc.stdin.close()
        proc.stdin = None
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"ffmpeg exited with status {rc}")

    finally:
        if runtime is not None:
            LayerFramePipeline.destroy(runtime.layers)
            runtime.compositor.destroy()
            runtime.post_process.destroy()
        if proc is not None and proc.stdin is not None:
            proc.stdin.close()
            proc.kill()
            proc.wait()
        pygame.quit()

    manifest = load_manifest(project)
    partial = _is_partial_segment(segment, duration_sec=duration_sec)
    return RenderResult(
        output_path=output_path.resolve(),
        display_width=width,
        display_height=height,
        mix_filename=manifest.mix_filename,
        segment=segment if partial else None,
    )
