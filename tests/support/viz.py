"""Shared visualizer and tuning-control helpers for unit tests."""

from __future__ import annotations

from pathlib import Path

import pygame

from cleave.preset_playlist import PresetPlaylist
from cleave.viz.controls import LayerRuntime, TuningControls, TuningSession
from cleave.viz.playback import PlaybackState

REPO_ROOT_EXAMPLE = Path("/tmp/cleave.config.yaml")
DEFAULT_ACTIVE_CONFIG = Path("/tmp/projects/my-track/active.yaml")


def keydown(key: int, *, mod: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod)


def overlay_font() -> pygame.font.Font:
    pygame.font.init()
    return pygame.font.SysFont("monospace", 14)


def make_playlist(name: str, count: int = 3) -> PresetPlaylist:
    current_dir = Path(f"/tmp/presets/{name}")
    paths = tuple(current_dir / f"preset-{i}.milk" for i in range(count))
    return PresetPlaylist(current_dir=current_dir, paths=paths, index=0)


def make_controls(
    stems: tuple[str, ...] = ("drums", "bass"),
    *,
    launch_config_path: Path | None = DEFAULT_ACTIVE_CONFIG,
    repo_root_example: Path = REPO_ROOT_EXAMPLE,
) -> TuningControls:
    preset_root = Path("/tmp/presets")
    session = TuningSession(
        layer_z_order=list(stems),
        layers={
            stem: LayerRuntime(
                playlist=make_playlist(stem),
                browse_floor=preset_root / stem,
                opacity_pct=50,
            )
            for stem in stems
        },
    )
    return TuningControls(
        session,
        preset_root=preset_root,
        playback=PlaybackState(),
        duration_sec=120.0,
        launch_config_path=launch_config_path,
        repo_root_example=repo_root_example,
    )
