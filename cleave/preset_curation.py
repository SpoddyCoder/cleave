"""File operations for favourites and blacklist preset curation."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from cleave.viz.user_presets import copy_with_dedup, resolve_user_preset_dest

FAVOURITES_DIR = "favourites"
BLACKLIST_DIR = "blacklist"
COLOCATED_TEXTURE_SUFFIXES = (".jpg", ".png", ".tga", ".bmp", ".dds")


def favourites_root(preset_root: Path) -> Path:
    return preset_root / FAVOURITES_DIR


def blacklist_root(preset_root: Path) -> Path:
    return preset_root / BLACKLIST_DIR


def _milk_names_under(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {p.name for p in root.rglob("*.milk")}


@dataclass
class PresetCurationIndex:
    favourites: set[str]
    blacklist: set[str]

    @classmethod
    def build(cls, preset_root: Path) -> PresetCurationIndex:
        return cls(
            favourites=_milk_names_under(favourites_root(preset_root)),
            blacklist=_milk_names_under(blacklist_root(preset_root)),
        )

    def marker(self, name: str) -> str:
        fav = name in self.favourites
        bl = name in self.blacklist
        if fav and bl:
            return " [F][B]"
        if fav:
            return " [F]"
        if bl:
            return " [B]"
        return ""

    def mark_favourite(self, name: str) -> None:
        self.favourites.add(name)

    def mark_blacklisted(self, name: str) -> None:
        self.blacklist.add(name)


def list_destination_subdirs(base: Path) -> tuple[str, ...]:
    """Sorted top-level subdirectory names under ``base``, excluding dot-dirs."""
    if not base.is_dir():
        return ()
    names = [
        child.name
        for child in base.iterdir()
        if child.is_dir() and not child.name.startswith(".")
    ]
    return tuple(sorted(names))


def copy_to_favourites(src_milk: Path, dest_dir: Path) -> Path:
    """Copy ``src_milk`` and co-located textures into ``dest_dir``."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_milk = copy_with_dedup(dest_dir, src_milk)
    for suffix in COLOCATED_TEXTURE_SUFFIXES:
        for texture in sorted(src_milk.parent.glob(f"*{suffix}")):
            if texture.is_file():
                copy_with_dedup(dest_dir, texture)
    return dest_milk


def move_to_blacklist(src_milk: Path, dest_dir: Path) -> Path:
    """Move ``src_milk`` into ``dest_dir``; textures in the source dir are left behind."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path, _needs_copy = resolve_user_preset_dest(dest_dir, src_milk)
    shutil.move(str(src_milk), str(dest_path))
    return dest_path


def scrub_user_preset_paths(layers: Mapping[str, object], removed: Path) -> list[str]:
    """Remove ``removed`` from layer user preset lists; return affected slot names."""
    removed_resolved = removed.resolve()
    affected: list[str] = []
    for slot, layer in layers.items():
        user_presets: list[str] = layer.user_presets  # type: ignore[attr-defined]
        filtered = [
            path
            for path in user_presets
            if Path(path).resolve() != removed_resolved
        ]
        if len(filtered) != len(user_presets):
            user_presets[:] = filtered
            affected.append(slot)
    return affected
