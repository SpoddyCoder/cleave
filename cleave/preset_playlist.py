"""Scan Milkdrop preset anchors into playlists and sync config selections."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cleave.config import CleaveConfig

if TYPE_CHECKING:
    from cleave.projectm import ProjectM


def dir_has_presets(path: Path) -> bool:
    """True when any ``.milk`` preset exists anywhere under ``path``."""
    return any(path.rglob("*.milk"))


def list_navigable_dirs(parent: Path) -> tuple[Path, ...]:
    """Sorted immediate subdirectories of ``parent`` that contain presets."""
    if not parent.is_dir():
        return ()
    dirs = [
        child
        for child in parent.iterdir()
        if child.is_dir() and not child.name.startswith(".") and dir_has_presets(child)
    ]
    return tuple(sorted(dirs, key=lambda p: p.name))


def milk_files_in_dir(dir: Path) -> tuple[Path, ...]:
    """Non-recursive ``*.milk`` files directly in ``dir``."""
    return tuple(sorted(dir.glob("*.milk")))


def playlist_at_dir(dir: Path, *, index: int = 0) -> PresetPlaylist:
    """Build a playlist for presets directly in ``dir``."""
    resolved_dir = dir.resolve()
    paths = tuple(p.resolve() for p in milk_files_in_dir(resolved_dir))
    if not paths:
        return PresetPlaylist(current_dir=resolved_dir, paths=(), index=0)
    clamped = index % len(paths)
    return PresetPlaylist(current_dir=resolved_dir, paths=paths, index=clamped)


def _path_at_or_below(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    resolved_root = root.resolve()
    if resolved == resolved_root:
        return True
    try:
        resolved.relative_to(resolved_root)
        return True
    except ValueError:
        return False


def preset_browse_floor(anchor: Path, preset_root: Path) -> Path:
    """Lowest directory this layer may ascend to when browsing presets."""
    resolved_root = preset_root.resolve()
    resolved = anchor.resolve()
    base = resolved.parent if resolved.is_file() else resolved
    if not _path_at_or_below(base, resolved_root):
        return resolved_root
    try:
        rel = base.relative_to(resolved_root)
    except ValueError:
        return resolved_root
    if not rel.parts:
        return resolved_root
    return (resolved_root / rel.parts[0]).resolve()


def navigable_parent(current_dir: Path, preset_root: Path) -> Path:
    """Parent directory for sibling listing, never above ``preset_root``."""
    parent = current_dir.parent.resolve()
    if _path_at_or_below(parent, preset_root):
        return parent
    return preset_root.resolve()


@dataclass
class PresetPlaylist:
    current_dir: Path
    paths: tuple[Path, ...]
    index: int = 0

    @property
    def current(self) -> Path | None:
        if not self.paths:
            return None
        return self.paths[self.index]

    def _apply(self, other: PresetPlaylist) -> None:
        self.current_dir = other.current_dir
        self.paths = other.paths
        self.index = other.index

    def next(self) -> Path | None:
        if not self.paths:
            return None
        self.index = (self.index + 1) % len(self.paths)
        return self.current

    def prev(self) -> Path | None:
        if not self.paths:
            return None
        self.index = (self.index - 1) % len(self.paths)
        return self.current

    def step_by(self, delta: int) -> Path | None:
        if not self.paths:
            return None
        self.index = (self.index + delta) % len(self.paths)
        return self.current

    def step_sibling(self, delta: int = 1, *, preset_root: Path) -> bool:
        siblings = list_navigable_dirs(navigable_parent(self.current_dir, preset_root))
        if not siblings:
            return False
        resolved_current = self.current_dir.resolve()
        try:
            idx = next(
                i for i, sibling in enumerate(siblings) if sibling.resolve() == resolved_current
            )
        except StopIteration:
            idx = 0
        new_idx = (idx + delta) % len(siblings)
        self._apply(playlist_at_dir(siblings[new_idx], index=0))
        return True

    def enter_child(self, preset_root: Path) -> bool:
        children = list_navigable_dirs(self.current_dir)
        if not children:
            return False
        self._apply(playlist_at_dir(children[0], index=0))
        return True

    def go_parent(self, preset_root: Path) -> bool:
        parent = self.current_dir.parent
        if parent == self.current_dir:
            return False
        if not _path_at_or_below(parent, preset_root):
            return False
        self._apply(playlist_at_dir(parent, index=0))
        return True

    def load_into(self, pm: ProjectM, smooth: bool = True) -> None:
        if self.current is None:
            return
        pm.load_preset(self.current, smooth=smooth)

    def config_preset_path(self, preset_root: Path) -> str:
        if self.current is not None:
            return to_config_relative(self.current, preset_root)
        rel = to_config_relative(self.current_dir, preset_root)
        return rel if rel.endswith("/") else f"{rel}/"


def scan_single_layer(
    slot: str,
    preset_root: Path,
    project_dir: Path,
) -> PresetPlaylist:
    resolved_root = preset_root.resolve()
    paths = list(resolved_root.rglob("*.milk"))
    if paths:
        anchor = random.choice(paths)
        return scan_preset_playlist(anchor)
    return scan_preset_playlist(resolved_root)


def scan_preset_playlist(anchor: Path) -> PresetPlaylist:
    """Build a playlist from a .milk file or a directory of presets."""
    resolved = anchor.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"preset anchor not found: {resolved}")

    if resolved.is_file():
        if resolved.suffix.lower() != ".milk":
            raise ValueError(f"preset anchor is not a .milk file: {resolved}")
        current_dir = resolved.parent.resolve()
        paths = tuple(p.resolve() for p in milk_files_in_dir(current_dir))
        if paths:
            try:
                index = paths.index(resolved)
            except ValueError:
                index = 0
        else:
            index = 0
        return PresetPlaylist(current_dir=current_dir, paths=paths, index=index)

    if resolved.is_dir():
        return playlist_at_dir(resolved, index=0)

    raise ValueError(f"preset anchor is not a file or directory: {resolved}")


def directory_display(playlist: PresetPlaylist, preset_root: Path) -> str:
    """Directory path for overlay with sibling position among navigable dirs."""
    rel = to_config_relative(playlist.current_dir, preset_root).rstrip("/") + "/"
    siblings = list_navigable_dirs(
        navigable_parent(playlist.current_dir, preset_root)
    )
    if not siblings:
        return f"{rel} (1/1)"
    resolved_current = playlist.current_dir.resolve()
    try:
        position = (
            next(
                i
                for i, sibling in enumerate(siblings)
                if sibling.resolve() == resolved_current
            )
            + 1
        )
    except StopIteration:
        position = 1
    return f"{rel} ({position}/{len(siblings)})"


def preset_filename_display(playlist: PresetPlaylist) -> str:
    """Current preset filename with position, or empty-state label."""
    if playlist.current is None:
        return "NO PRESETS FOUND"
    total = len(playlist.paths)
    position = playlist.index + 1
    return f"{playlist.current.name} ({position}/{total})"


def to_config_relative(path: Path, preset_root: Path) -> str:
    """Preset path relative to preset_root, using forward slashes."""
    return path.resolve().relative_to(preset_root.resolve()).as_posix()


def scan_all_layers(cfg: CleaveConfig) -> dict[str, PresetPlaylist]:
    """Scan one preset playlist per configured layer."""
    return {
        slot: scan_preset_playlist(cfg.layers[slot].preset)
        for slot in cfg.layer_z_order
        if slot in cfg.layers
    }
