"""Offline video render: GL frames piped to ffmpeg with project mix audio."""

from __future__ import annotations

import math
import os
import shutil
import subprocess
from pathlib import Path

import pygame

from cleave.config import PROJECT_VIZ_CONFIG_FILENAME, load_config
from cleave.easing import fade_alpha
from cleave.paths import default_project_config, repo_root, resolve_project
from cleave.preset_playlist import scan_all_layers
from cleave.project import manifest_path, mix_path
from cleave.separate import project_stems_complete, signals_complete
from cleave.viz.app import (
    VisualizerApp,
    _init_gl_resources_render,
    build_runtime_full,
)
from cleave.viz.layer import _destroy_layers
from cleave.viz.render_overlay import build_panel_surface, composite_render_overlay

_PREPARE_HINT = "run `cleave separate` or `cleave play` first"


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
            f"no {PROJECT_VIZ_CONFIG_FILENAME} in {project_dir}; {_PREPARE_HINT}"
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
) -> Path:
    """Render project visuals to an MP4 muxed with the project mix audio."""
    project = validate_render_project(project_dir, config=config)
    config_path = _resolve_render_config_path(config, project)
    cfg = load_config(config_path, repo_root())

    if output is None:
        output_path = project / "renders" / f"{cfg.visualizer.name}.mp4"
    else:
        output_path = Path(output).expanduser()
        if output_path.suffix.lower() != ".mp4":
            raise ValueError("output path must end with .mp4")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FileNotFoundError("ffmpeg not found on PATH")

    audio_path = mix_path(project)
    playlists = scan_all_layers(cfg)
    runtime = build_runtime_full(cfg, project, audio_path, playlists)

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    pygame.init()
    try:
        pygame.display.set_mode(
            (runtime.width, runtime.height), pygame.OPENGL | pygame.HIDDEN
        )
    except pygame.error as exc:
        pygame.quit()
        raise RuntimeError(f"failed to open OpenGL context: {exc}") from exc

    proc: subprocess.Popen[bytes] | None = None
    try:
        _init_gl_resources_render(runtime)
        app = VisualizerApp(runtime)

        duration_sec = runtime.duration_sec
        fps = runtime.fps
        width = runtime.width
        height = runtime.height
        frame_count = math.ceil(duration_sec * fps)
        frame_bytes = width * height * 4

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

        assert runtime.compositor is not None
        overlay_cfg = (
            cfg.render.overlay
            if cfg.render is not None and cfg.render.overlay is not None
            else None
        )
        overlay_panel = None
        if overlay_cfg is not None and overlay_cfg.enabled:
            overlay_panel = build_panel_surface(overlay_cfg)

        pp = runtime.session.render_post_fx
        if pp.enabled:
            fade_in = pp.fade_in
            fade_out = pp.fade_out
        else:
            fade_in = 0.0
            fade_out = 0.0

        for frame_idx in range(frame_count):
            t_sec = frame_idx / fps
            app.tick_frame(t_sec, paused=False, draw_overlay=False)
            if overlay_cfg is not None and overlay_cfg.enabled:
                composite_render_overlay(
                    runtime.compositor,
                    overlay_cfg,
                    t_sec,
                    width,
                    height,
                    panel=overlay_panel,
                )
            alpha = fade_alpha(t_sec, duration_sec, fade_in, fade_out)
            runtime.compositor.apply_frame_fade(alpha)
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
        _destroy_layers(runtime.layers)
        if runtime.compositor is not None:
            runtime.compositor.destroy()
        if runtime.post_process is not None:
            runtime.post_process.destroy()
        if proc is not None and proc.stdin is not None:
            proc.stdin.close()
            proc.kill()
            proc.wait()
        pygame.quit()

    return output_path.resolve()
