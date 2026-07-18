"""Shared visualizer and tuning-control helpers for unit tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pygame

from cleave.config import CleaveConfig, LayerConfig, PathsConfig, EditorConfig
from cleave.config_schema import DEFAULT_LAYER_SLOTS
from tests.support.config import TEST_LAYER_STEMS
from cleave.preset_playlist import PresetPlaylist
from cleave.viz.controls import TuningControls
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.playback import PlaybackState
from cleave.viz.theme import TuningUiMetrics, tuning_ui_metrics


def baseline_tuning_ui_metrics() -> TuningUiMetrics:
    """Unscaled tuning metrics for layout tests that assume 14px spacing."""
    return tuning_ui_metrics(scale=1.0)


class StubMixPlayer:
    """Minimal MixPlayer stand-in for control tests (no SDL audio)."""

    def __init__(self, position_sec: float = 0.0) -> None:
        self._position_sec = position_sec
        self._residual_delay_sec = 0.0

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def pause(self, on: bool) -> None:
        pass

    def seek(self, position_sec: float) -> None:
        self._position_sec = position_sec

    def set_residual_delay_sec(self, sec: float) -> None:
        self._residual_delay_sec = max(0.0, min(float(sec), 2.0))

    def set_click_beats(self, _beat_times) -> None:
        pass

    def file_position_sec(self) -> float:
        return self._position_sec

    def audible_position_sec(self) -> float:
        return max(0.0, self._position_sec - self._residual_delay_sec)

    def audible_position_zero_residual_sec(self) -> float:
        return self._position_sec

    def finished(self) -> bool:
        return False


REPO_ROOT_EXAMPLE = Path("/tmp/cleave-viz.yaml")
DEFAULT_ACTIVE_CONFIG = Path("/tmp/projects/my-track/active.yaml")


def keydown(key: int, *, mod: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod)


def overlay_font() -> pygame.font.Font:
    pygame.font.init()
    return pygame.font.SysFont("monospace", baseline_tuning_ui_metrics().font_size)


def make_playlist(name: str, count: int = 3) -> PresetPlaylist:
    current_dir = Path(f"/tmp/presets/{name}")
    paths = tuple(current_dir / f"preset-{i}.milk" for i in range(count))
    return PresetPlaylist(current_dir=current_dir, paths=paths, index=0)


def stub_playback_state() -> PlaybackState:
    return PlaybackState(player=StubMixPlayer())


def noop_layer_bindings(**overrides: Callable) -> LiveLayerBindings:
    base = LiveLayerBindings(
        on_preset_change=lambda _slot, _playlist: None,
        on_preset_switching_change=lambda _slot: None,
        lock_preset_for_modal=lambda _slot: None,
        unlock_preset_after_modal=lambda _slot: None,
        on_blend_change=lambda _slot, _blend: None,
        on_stem_change=lambda _slot, _stem: None,
        on_opacity_change=lambda _slot, _pct: None,
        on_layer_enabled_change=lambda _slot, _enabled: None,
        on_timeline_enabled_change=lambda: None,
        on_solo_change=lambda: None,
        on_beat_change=lambda _slot, _beat: None,
        on_seek=lambda _delta: None,
    )
    if overrides:
        return replace(base, **overrides)
    return base


def make_test_cfg(
    slots: tuple[str, ...] = ("layer_1", "layer_2"),
    *,
    preset_root: Path | None = None,
    config_path: Path | None = None,
) -> CleaveConfig:
    root = preset_root or Path("/tmp/presets")
    return CleaveConfig(
        paths=PathsConfig(preset_root=root, texture_paths=()),
        layers={
            slot: LayerConfig(
                preset=root / slot / "preset-0.milk",
                stem=TEST_LAYER_STEMS.get(slot, "drums"),
            )
            for slot in DEFAULT_LAYER_SLOTS
        },
        layer_z_order=list(slots),
        editor=EditorConfig(),
        config_path=config_path or Path("/tmp/test/cleave.config.yaml"),
        user_config_path=Path("/tmp/user-config.yaml"),
    )


def make_controls(
    slots: tuple[str, ...] = ("layer_1", "layer_2"),
    *,
    launch_config_path: Path | None = DEFAULT_ACTIVE_CONFIG,
    repo_root_example: Path = REPO_ROOT_EXAMPLE,
) -> TuningControls:
    preset_root = Path("/tmp/presets")
    cfg = make_test_cfg(slots, preset_root=preset_root)
    session = TuningSession(
        layer_z_order=list(slots),
        layers={
            slot: LayerRuntime(
                playlist=make_playlist(slot),
                browse_floor=preset_root / slot,
                stem=TEST_LAYER_STEMS.get(slot, "drums"),
                opacity_pct=50,
            )
            for slot in slots
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