"""Visualizer bootstrap: config resolution, paths, and preset loading."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

from cleave.config import (
    DEFAULT_PRESET_ROOT,
    DEFAULT_VISUALIZER_FPS,
    DEFAULT_VISUALIZER_HEIGHT,
    DEFAULT_VISUALIZER_WIDTH,
    clamp_beat_sensitivity,
    find_config_path,
)
from cleave.paths import default_project_config, repo_root
from cleave.project import resolve_mix_path as _resolve_mix_path
from cleave.preset_playlist import PresetPlaylist, scan_preset_playlist
from cleave.signals import Signals, load_signals

STEM_DRUMS = "drums"


def load_stem_signals(project_dir: Path) -> Signals | None:
    signals_path = project_dir / "signals.json"
    if not signals_path.is_file():
        return None
    return load_signals(signals_path)


def resolve_config_path(
    config_override: Path | None,
    project_dir: Path,
) -> Path | None:
    """Resolve config: CLI override, project default, then global search."""
    if config_override is not None:
        return config_override
    default_cfg = default_project_config(project_dir)
    if default_cfg.is_file():
        return default_cfg
    return find_config_path(None, repo_root())


def resolve_mix_path(project_dir: Path) -> Path:
    return _resolve_mix_path(project_dir)


def visualizer_settings_from_config(
    config_path: Path | None,
) -> tuple[int, int, int]:
    """Load visualizer width/height/fps without preset validation."""
    path = find_config_path(config_path, repo_root())
    if path is None or not path.is_file():
        return (
            DEFAULT_VISUALIZER_WIDTH,
            DEFAULT_VISUALIZER_HEIGHT,
            DEFAULT_VISUALIZER_FPS,
        )

    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        return (
            DEFAULT_VISUALIZER_WIDTH,
            DEFAULT_VISUALIZER_HEIGHT,
            DEFAULT_VISUALIZER_FPS,
        )

    visualizer = data.get("visualizer")
    if not isinstance(visualizer, dict):
        return (
            DEFAULT_VISUALIZER_WIDTH,
            DEFAULT_VISUALIZER_HEIGHT,
            DEFAULT_VISUALIZER_FPS,
        )

    return (
        int(visualizer.get("width", DEFAULT_VISUALIZER_WIDTH)),
        int(visualizer.get("height", DEFAULT_VISUALIZER_HEIGHT)),
        int(visualizer.get("fps", DEFAULT_VISUALIZER_FPS)),
    )


def texture_paths_from_config(config_path: Path | None) -> list[Path]:
    """Load texture search paths without validating preset files."""
    path = find_config_path(config_path, repo_root())
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


def preset_root_from_config(config_path: Path | None) -> Path:
    """Load preset_root without validating preset files."""
    path = find_config_path(config_path, repo_root())
    if path is None or not path.is_file():
        return Path(os.path.expanduser(str(DEFAULT_PRESET_ROOT))).resolve()

    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        return Path(os.path.expanduser(str(DEFAULT_PRESET_ROOT))).resolve()

    paths_raw = data.get("paths")
    if not isinstance(paths_raw, dict):
        return Path(os.path.expanduser(str(DEFAULT_PRESET_ROOT))).resolve()

    raw = paths_raw.get("preset_root", DEFAULT_PRESET_ROOT)
    return Path(os.path.expanduser(str(raw))).resolve()


def _print_playlist_scan(name: str, playlist: PresetPlaylist) -> None:
    print(
        f"{name}: {len(playlist.paths)} presets in {playlist.current_dir}",
        file=sys.stderr,
    )


def resolve_drums_preset(
    preset_override: Path,
    config_path: Path | None,
) -> tuple[PresetPlaylist, list[Path], float]:
    """Return (playlist, texture_paths, beat_sensitivity) for --preset drums-only mode."""
    playlist = scan_preset_playlist(preset_override)
    textures = texture_paths_from_config(config_path)
    beat_sensitivity = 1.0
    path = find_config_path(config_path, repo_root())
    if path is not None and path.is_file():
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if isinstance(data, dict):
            visualizer = data.get("visualizer")
            if isinstance(visualizer, dict):
                beat_sensitivity = clamp_beat_sensitivity(
                    visualizer.get("beat_sensitivity", 1.0)
                )
    return playlist, textures, beat_sensitivity
