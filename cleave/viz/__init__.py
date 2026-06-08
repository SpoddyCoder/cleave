"""Live visualizer: overlay, controls, and app loop."""

from __future__ import annotations

import sys
from pathlib import Path

from cleave.config import load_config
from cleave.paths import repo_root
from cleave.preset_playlist import scan_all_layers
from cleave.projectm import ProjectMLibraryError
from cleave.viz.app import VisualizerApp, build_runtime_full
from cleave.viz.bootstrap import (
    _print_playlist_scan,
    resolve_config_path,
    resolve_mix_path,
)

__all__ = [
    "VisualizerApp",
    "build_runtime_full",
    "launch",
]


def launch(
    project_dir: Path,
    *,
    config: Path | None = None,
) -> None:
    """Entry for `python -m cleave play` and programmatic launch."""
    audio_path = resolve_mix_path(project_dir)
    config_path = resolve_config_path(config, project_dir)

    try:
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
