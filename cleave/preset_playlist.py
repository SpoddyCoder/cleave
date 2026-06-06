"""Scan Milkdrop preset anchors into playlists and sync config selections."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from cleave.config import CleaveConfig
from cleave.extract import STEM_NAMES

if TYPE_CHECKING:
    from cleave.projectm import ProjectM


@dataclass
class PresetPlaylist:
    anchor: Path
    paths: tuple[Path, ...]
    index: int = 0

    @property
    def current(self) -> Path:
        return self.paths[self.index]

    def next(self) -> Path:
        self.index = (self.index + 1) % len(self.paths)
        return self.current

    def prev(self) -> Path:
        self.index = (self.index - 1) % len(self.paths)
        return self.current

    def step_by(self, delta: int) -> Path:
        self.index = (self.index + delta) % len(self.paths)
        return self.current

    def load_into(self, pm: ProjectM, smooth: bool = True) -> None:
        pm.load_preset(self.current, smooth=smooth)


def scan_preset_playlist(anchor: Path) -> PresetPlaylist:
    """Build a playlist from a .milk file or a directory tree of presets."""
    resolved = anchor.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"preset anchor not found: {resolved}")

    if resolved.is_file():
        if resolved.suffix.lower() != ".milk":
            raise ValueError(f"preset anchor is not a .milk file: {resolved}")
        dir_anchor = resolved.parent
        paths = tuple(sorted(dir_anchor.rglob("*.milk")))
        if not paths:
            raise ValueError(f"no .milk presets found under: {dir_anchor}")
        try:
            index = paths.index(resolved)
        except ValueError:
            index = 0
        return PresetPlaylist(anchor=dir_anchor, paths=paths, index=index)

    if resolved.is_dir():
        paths = tuple(sorted(resolved.rglob("*.milk")))
        if not paths:
            raise ValueError(f"no .milk presets found under: {resolved}")
        return PresetPlaylist(anchor=resolved, paths=paths, index=0)

    raise ValueError(f"preset anchor is not a file or directory: {resolved}")


def directory_display(playlist: PresetPlaylist, preset_root: Path) -> str:
    """Directory path for overlay, relative to preset_root (no filename)."""
    return to_config_relative(playlist.anchor, preset_root)


def preset_filename_display(playlist: PresetPlaylist) -> str:
    """Current preset filename with position in the active directory playlist."""
    total = len(playlist.paths)
    position = playlist.index + 1
    return f"{playlist.current.name} ({position}/{total})"


def to_config_relative(path: Path, preset_root: Path) -> str:
    """Preset path relative to preset_root, using forward slashes."""
    return path.resolve().relative_to(preset_root.resolve()).as_posix()


def _layer_names(cfg: CleaveConfig) -> tuple[str, ...]:
    if all(name in cfg.layers for name in STEM_NAMES):
        return STEM_NAMES
    return tuple(cfg.layers.keys())


def scan_all_layers(cfg: CleaveConfig) -> dict[str, PresetPlaylist]:
    """Scan one preset playlist per configured layer."""
    return {
        name: scan_preset_playlist(cfg.layers[name].preset)
        for name in _layer_names(cfg)
    }


def write_layer_presets(
    config_path: Path,
    preset_root: Path,
    playlists: dict[str, PresetPlaylist],
) -> None:
    """Write each layer's current preset path back to cleave.config.yaml."""
    with config_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"config root must be a mapping: {config_path}")

    layers = data.get("layers")
    if layers is None:
        layers = {}
    if not isinstance(layers, dict):
        raise ValueError("layers must be a mapping")

    root = preset_root.resolve()
    for stem, playlist in playlists.items():
        layer = layers.get(stem)
        if layer is None:
            layer = {}
            layers[stem] = layer
        if not isinstance(layer, dict):
            raise ValueError(f"layers.{stem} must be a mapping")
        layer["preset"] = to_config_relative(playlist.current, root)

    data["layers"] = layers

    with config_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, default_flow_style=False, sort_keys=False)
