"""Live visualizer: overlay, controls, and app loop."""

from __future__ import annotations

import sys
from pathlib import Path

from cleave.config import load_config
from cleave.paths import repo_root
from cleave.preset_playlist import scan_all_layers
from cleave.projectm import ProjectMLibraryError
from cleave.viz.app import VisualizerApp, build_runtime_drums_only, build_runtime_full
from cleave.viz.bootstrap import (
    STEM_DRUMS,
    _print_playlist_scan,
    preset_root_from_config,
    resolve_config_path,
    resolve_drums_preset,
    resolve_mix_path,
    visualizer_settings_from_config,
)

__all__ = [
    "VisualizerApp",
    "build_runtime_drums_only",
    "build_runtime_full",
    "launch",
]


def launch(
    project_dir: Path,
    *,
    source: Path | None = None,
    config: Path | None = None,
    preset: Path | None = None,
) -> None:
    """Entry for cleave.py shim and future `python -m cleave play`."""
    audio_path = resolve_mix_path(project_dir, source)
    config_path = resolve_config_path(config, project_dir)

    try:
        if preset is not None:
            playlist, texture_paths, beat_sensitivity = resolve_drums_preset(
                preset,
                config_path,
            )
            _print_playlist_scan(STEM_DRUMS, playlist)
            width, height, fps = visualizer_settings_from_config(config_path)
            preset_root = preset_root_from_config(config_path)
            runtime = build_runtime_drums_only(
                project_dir,
                audio_path,
                playlist,
                texture_paths,
                beat_sensitivity,
                config_path,
                preset_root,
                preset,
                width,
                height,
                fps,
            )
            VisualizerApp(runtime).run()
        else:
            cfg = load_config(config_path, repo_root())
            playlists = scan_all_layers(cfg)
            for name, pl in playlists.items():
                _print_playlist_scan(name, pl)
            runtime = build_runtime_full(cfg, project_dir, audio_path, playlists)
            VisualizerApp(runtime).run()
    except ProjectMLibraryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
