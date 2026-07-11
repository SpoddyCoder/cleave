"""Live visualizer: overlay, controls, and app loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = [
    "VisualizerApp",
    "build_runtime_base",
    "launch",
    "render",
]


def __getattr__(name: str) -> Any:
    if name == "VisualizerApp":
        from cleave.viz.app import VisualizerApp as _VisualizerApp

        return _VisualizerApp
    if name == "build_runtime_base":
        from cleave.viz.app import build_runtime_base as _build_runtime_base

        return _build_runtime_base
    if name == "render":
        from cleave.viz.render import render as _render

        return _render
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def launch(
    project_dir: Path,
    *,
    config: Path | None = None,
) -> None:
    """Entry for `python -m cleave play` and programmatic launch."""
    import sys

    from cleave.config import load_config
    from cleave.paths import repo_root
    from cleave.preset_playlist import scan_all_layers
    from cleave.projectm import ProjectMLibraryError
    from cleave.viz.app import VisualizerApp, build_runtime_base
    from cleave.viz.bootstrap import resolve_config_path, resolve_mix_path

    audio_path = resolve_mix_path(project_dir)
    config_path = resolve_config_path(config, project_dir)

    try:
        cfg = load_config(config_path, repo_root())
        playlists = scan_all_layers(cfg)
        runtime = build_runtime_base(cfg, project_dir, audio_path, playlists)
        VisualizerApp(runtime).run()
    except ProjectMLibraryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
