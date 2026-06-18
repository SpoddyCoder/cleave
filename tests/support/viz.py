"""Shared visualizer and tuning-control helpers for unit tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pygame

from cleave.config import CleaveConfig, LayerConfig, PathsConfig, VisualizerConfig
from cleave.extract import STEM_NAMES
from cleave.preset_playlist import PresetPlaylist
from cleave.viz.controls import TuningControls
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.playback import PlaybackState


class StubMixPlayer:
    """Minimal MixPlayer stand-in for control tests (no SDL audio)."""

    def __init__(self, position_sec: float = 0.0) -> None:
        self._position_sec = position_sec

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def pause(self, on: bool) -> None:
        pass

    def seek(self, position_sec: float) -> None:
        self._position_sec = position_sec

    def current_sec(self) -> float:
        return self._position_sec

    def finished(self) -> bool:
        return False


REPO_ROOT_EXAMPLE = Path("/tmp/cleave-viz.yaml")
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


def stub_playback_state() -> PlaybackState:
    return PlaybackState(player=StubMixPlayer())


def noop_layer_bindings(**overrides: Callable) -> LiveLayerBindings:
    base = LiveLayerBindings(
        on_preset_change=lambda _stem, _playlist: None,
        on_blend_change=lambda _stem, _blend: None,
        on_opacity_change=lambda _stem, _pct: None,
        on_layer_enabled_change=lambda _stem, _enabled: None,
        on_timeline_enabled_change=lambda: None,
        on_solo_change=lambda: None,
        on_beat_change=lambda _stem, _beat: None,
        on_seek=lambda _delta: None,
    )
    if overrides:
        return replace(base, **overrides)
    return base


def make_test_cfg(
    stems: tuple[str, ...] = ("drums", "bass"),
    *,
    preset_root: Path | None = None,
    config_path: Path | None = None,
) -> CleaveConfig:
    root = preset_root or Path("/tmp/presets")
    return CleaveConfig(
        paths=PathsConfig(preset_root=root, texture_paths=()),
        layers={
            name: LayerConfig(preset=root / name / "preset-0.milk")
            for name in STEM_NAMES
        },
        layer_z_order=stems,
        visualizer=VisualizerConfig(),
        config_path=config_path or Path("/tmp/test/cleave.config.yaml"),
    )


def make_controls(
    stems: tuple[str, ...] = ("drums", "bass"),
    *,
    launch_config_path: Path | None = DEFAULT_ACTIVE_CONFIG,
    repo_root_example: Path = REPO_ROOT_EXAMPLE,
) -> TuningControls:
    preset_root = Path("/tmp/presets")
    cfg = make_test_cfg(stems, preset_root=preset_root)
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
        cfg,
        preset_root=preset_root,
        playback=stub_playback_state(),
        duration_sec=120.0,
        launch_config_path=launch_config_path,
        repo_root_example=repo_root_example,
    )
