"""Live visualizer: overlay, controls, and app loop."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cleave.viz.loading import LoadingWindow

__all__ = [
    "LaunchError",
    "LoadingWindow",
    "VisualizerApp",
    "build_runtime_base",
    "continue_launch",
    "launch",
    "open_loading_window",
    "render",
]


def __getattr__(name: str) -> Any:
    if name == "LoadingWindow":
        from cleave.viz.loading import LoadingWindow as _LoadingWindow

        return _LoadingWindow
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


class LaunchError(RuntimeError):
    """Editor boot failed. The caller decides between exiting and retrying."""


def open_loading_window(
    *,
    width: int | None = None,
    height: int | None = None,
) -> LoadingWindow:
    """Open the pygame/GL window and draw the loading screen."""
    from cleave.viz.loading import open_loading_window as _open_loading_window

    return _open_loading_window(width=width, height=height)


def continue_launch(
    window: LoadingWindow,
    project_dir: Path,
    *,
    config: Path | None = None,
) -> None:
    """Finish editor boot into an already-open loading window.

    Raises :class:`LaunchError` when boot fails, so a CLI target can exit while
    a picker-driven attempt returns to the picker on the same window.
    """
    from cleave.config import load_config
    from cleave.paths import resource_dir
    from cleave.preset_playlist import scan_all_layers
    from cleave.projectm import ProjectMLibraryError
    from cleave.viz.app import VisualizerApp, build_runtime_base
    from cleave.viz.bootstrap import resolve_config_path, resolve_mix_path
    from cleave.viz.user_presets import cleanup_unreferenced_user_presets

    audio_path = resolve_mix_path(project_dir)
    config_path = resolve_config_path(config, project_dir)

    try:
        cleanup_unreferenced_user_presets(project_dir)
        cfg = load_config(config_path, resource_dir())
        playlists = scan_all_layers(cfg)
        runtime = build_runtime_base(cfg, project_dir, audio_path, playlists)
        VisualizerApp(runtime).run(window)
    except (ProjectMLibraryError, FileNotFoundError, ValueError) as exc:
        window.update(f"error: {exc}")
        raise LaunchError(str(exc)) from exc


def launch(
    project_dir: Path,
    *,
    config: Path | None = None,
) -> None:
    """Entry for `python -m cleave play` and programmatic launch."""
    window = open_loading_window()
    continue_launch(window, project_dir, config=config)
