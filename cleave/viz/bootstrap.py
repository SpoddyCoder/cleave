"""Visualizer bootstrap: config resolution, paths, and preset loading."""

from __future__ import annotations

import sys
from pathlib import Path

from cleave.config import find_config_path
from cleave.paths import default_project_config, repo_root
from cleave.project import resolve_mix_path as _resolve_mix_path
from cleave.preset_playlist import PresetPlaylist
from cleave.signals import Signals, load_signals


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


def _print_playlist_scan(name: str, playlist: PresetPlaylist) -> None:
    print(
        f"{name}: {len(playlist.paths)} presets in {playlist.current_dir}",
        file=sys.stderr,
    )
