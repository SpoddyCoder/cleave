#!/usr/bin/env python3
"""Milkdrop visualizer (Phase 5 M1): one libprojectM instance, one FBO, drums stem PCM."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pygame
import yaml
from OpenGL.GL import GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, glClear, glClearColor, glViewport

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cleave.config import find_config_path, load_config  # noqa: E402
from cleave.gl_compositor import GlCompositor  # noqa: E402
from cleave.projectm import ProjectM, ProjectMLibraryError  # noqa: E402
from cleave.signals import Signals, load_signals  # noqa: E402
from cleave.stem_pcm import load_stem_pcm, samples_per_frame  # noqa: E402
from cleave.viz_overlay import ControlsOverlay, playback_rows  # noqa: E402
from cleave.viz_playback import (  # noqa: E402
    SKIP_SEC,
    current_sec,
    init_playback,
    seek,
    toggle_pause,
)

WIDTH, HEIGHT = 640, 360
FPS = 30
STEM = "drums"


def resolve_stems_dir(path: Path) -> Path:
    p = path.resolve()
    if p.is_file() and p.name == "signals.json":
        p = p.parent
    if not p.is_dir():
        print(f"error: stems folder not found: {p}", file=sys.stderr)
        sys.exit(1)
    return p


def resolve_audio_path(signals: Signals, override: Path | None) -> Path:
    if override is not None:
        path = override.resolve()
    elif signals.source is None:
        print(
            "error: signals.json has no source; pass --source path/to/mix.wav",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        path = Path(signals.source)
        if not path.is_file():
            path = ROOT / signals.source
    if not path.is_file():
        print(f"error: audio not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path


def resolve_mix_path(stems_dir: Path, source_override: Path | None) -> Path:
    if source_override is not None:
        path = source_override.resolve()
        if not path.is_file():
            print(f"error: audio not found: {path}", file=sys.stderr)
            sys.exit(1)
        return path

    signals_path = stems_dir / "signals.json"
    if signals_path.is_file():
        signals = load_signals(signals_path)
        return resolve_audio_path(signals, None)

    print(
        "error: no signals.json source; pass --source path/to/mix.wav",
        file=sys.stderr,
    )
    sys.exit(1)


def texture_paths_from_config(config_path: Path | None) -> list[Path]:
    """Load texture search paths without validating preset files."""
    path = find_config_path(config_path, ROOT)
    if path is None or not path.is_file():
        return []

    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        return []

    paths_raw = data.get("paths")
    if not isinstance(paths_raw, dict):
        return []

    raw = paths_raw.get("texture_paths")
    if not isinstance(raw, list) or not raw:
        return []

    return [Path(os.path.expanduser(str(p))).resolve() for p in raw]


def resolve_preset_path(
    preset_override: Path | None,
    config_path: Path | None,
) -> tuple[Path, list[Path], float]:
    """Return (preset, texture_paths, beat_sensitivity)."""
    if preset_override is not None:
        preset = preset_override.resolve()
        if not preset.is_file():
            print(f"error: preset not found: {preset}", file=sys.stderr)
            sys.exit(1)
        textures = texture_paths_from_config(config_path)
        return preset, textures, 1.0

    try:
        cfg = load_config(config_path, ROOT)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(
            "hint: install presets under paths.preset_root or pass "
            "--preset path/to/file.milk for M1 testing",
            file=sys.stderr,
        )
        sys.exit(1)

    layer = cfg.layers[STEM]
    beat = layer.beat_sensitivity
    if beat is None:
        beat = cfg.visualizer.beat_sensitivity
    return layer.preset, list(cfg.paths.texture_paths), beat


def run(
    stems_dir: Path,
    audio_path: Path,
    preset_path: Path,
    texture_paths: list[Path],
    beat_sensitivity: float,
) -> None:
    pcm_bank = load_stem_pcm(stems_dir)
    duration_sec = pcm_bank.duration_sec
    n_pcm = samples_per_frame(FPS)

    pygame.init()
    pygame.mixer.init()

    try:
        pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
    except pygame.error as exc:
        print(f"error: failed to open OpenGL window: {exc}", file=sys.stderr)
        pygame.quit()
        sys.exit(1)

    trackname = stems_dir.name
    pygame.display.set_caption(f"Cleave Milkdrop — {trackname}")
    clock = pygame.time.Clock()

    compositor: GlCompositor | None = None
    layer = None
    pm: ProjectM | None = None
    overlay_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    try:
        compositor = GlCompositor(WIDTH, HEIGHT)
        compositor.init()
        layer = compositor.create_layer_fbo(STEM, WIDTH, HEIGHT)

        pm = ProjectM()
        pm.set_window_size(WIDTH, HEIGHT)
        if texture_paths:
            pm.set_texture_paths(texture_paths)
        pm.load_preset(preset_path)
        pm.lock_preset(True)
        pm.set_hard_cut_enabled(False)
        pm.set_fps(FPS)
        pm.set_beat_sensitivity(beat_sensitivity)

        pygame.mixer.music.load(str(audio_path))
        pygame.mixer.music.play()

        playback = init_playback()
        overlay = ControlsOverlay(playback_rows(paused=playback.paused))

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    overlay.notify_input()
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        toggle_pause(playback, duration_sec)
                    elif event.key == pygame.K_LEFT:
                        seek(playback, -SKIP_SEC, duration_sec)
                        pm.flush_pcm()
                    elif event.key == pygame.K_RIGHT:
                        seek(playback, SKIP_SEC, duration_sec)
                        pm.flush_pcm()
                    overlay.replace_rows(
                        playback_rows(paused=playback.paused)
                    )

            t_sec = current_sec(playback, duration_sec)
            pcm = pcm_bank.slice_pcm(STEM, t_sec, n_pcm)
            pm.feed_pcm(pcm)
            pm.set_frame_time(t_sec)

            assert layer is not None and compositor is not None
            with layer:
                glViewport(0, 0, layer.width, layer.height)
                glClearColor(0.0, 0.0, 0.0, 1.0)
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
                pm.render_to_fbo(layer.fbo_id)

            compositor.composite([layer])

            overlay_surface.fill((0, 0, 0, 0))
            overlay.draw(overlay_surface)
            panel = overlay.panel_rect
            if panel is not None:
                px, py, pw, ph = panel
                panel_surface = overlay_surface.subsurface((px, py, pw, ph))
                tex_id = compositor.upload_overlay_texture(panel_surface)
                compositor.draw_overlay(tex_id, px, py, pw, ph)

            pygame.display.flip()
            overlay.update(clock.tick(FPS) / 1000.0)

            if not playback.paused and not pygame.mixer.music.get_busy():
                if t_sec >= duration_sec - 0.05:
                    running = False

    finally:
        if pm is not None:
            pm.destroy()
        if compositor is not None:
            compositor.destroy()
        pygame.mixer.music.stop()
        pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Milkdrop visualizer (M1): one preset, drums stem PCM",
    )
    parser.add_argument("path", type=Path, help="stems folder for the track")
    parser.add_argument(
        "--source",
        type=Path,
        help="Original mix wav (overrides signals.json source)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help=f"Config path (default: {ROOT / 'cleave.config.yaml'})",
    )
    parser.add_argument(
        "--preset",
        type=Path,
        help="Load this .milk file instead of config drums preset (M1 testing)",
    )
    args = parser.parse_args()

    stems_dir = resolve_stems_dir(args.path)
    audio_path = resolve_mix_path(stems_dir, args.source)
    preset_path, texture_paths, beat_sensitivity = resolve_preset_path(
        args.preset,
        args.config,
    )

    try:
        run(
            stems_dir,
            audio_path,
            preset_path,
            texture_paths,
            beat_sensitivity,
        )
    except ProjectMLibraryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
