"""File operations for favourites and blacklist preset curation."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from cleave.viz.user_presets import copy_with_dedup, resolve_user_preset_dest

FAVOURITES_DIR = "favourites"
BLACKLIST_DIR = "blacklist"
ORIGIN_SIDECAR_SUFFIX = ".origin"
COLOCATED_TEXTURE_SUFFIXES = (".jpg", ".png", ".tga", ".bmp", ".dds")


def favourites_root(preset_root: Path) -> Path:
    return preset_root / FAVOURITES_DIR


def blacklist_root(preset_root: Path) -> Path:
    return preset_root / BLACKLIST_DIR


def origin_sidecar_path(milk_path: Path) -> Path:
    """Return ``{milk_name}.origin`` beside a blacklisted milk file."""
    return milk_path.parent / f"{milk_path.name}{ORIGIN_SIDECAR_SUFFIX}"


def write_blacklist_origin(milk_path: Path, relative_src: str) -> None:
    """Write the source milk path (relative to preset root, POSIX) beside ``milk_path``."""
    origin_sidecar_path(milk_path).write_text(relative_src, encoding="utf-8")


def read_blacklist_origin(milk_path: Path) -> Path | None:
    """Return the relative origin path from the sidecar, or None if missing/empty."""
    sidecar = origin_sidecar_path(milk_path)
    if not sidecar.is_file():
        return None
    text = sidecar.read_text(encoding="utf-8").strip()
    if not text:
        return None
    return Path(text)


def resolve_blacklist_origin_dir(preset_root: Path, milk_path: Path) -> Path | None:
    """Return the restore destination dir from a valid origin sidecar, else None."""
    relative = read_blacklist_origin(milk_path)
    if relative is None or relative.is_absolute():
        return None
    candidate = (preset_root / relative).resolve()
    try:
        candidate.relative_to(preset_root.resolve())
    except ValueError:
        return None
    return candidate.parent


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

    def marker(self, name: str, *, user: bool = False) -> str:
        letters = ""
        if name in self.favourites:
            letters += "F"
        if name in self.blacklist:
            letters += "B"
        if user:
            letters += "U"
        return f" [{letters}]" if letters else ""

    def mark_favourite(self, name: str) -> None:
        self.favourites.add(name)

    def mark_blacklisted(self, name: str) -> None:
        self.blacklist.add(name)

    def unmark_favourite(self, name: str) -> None:
        self.favourites.discard(name)

    def unmark_blacklisted(self, name: str) -> None:
        self.blacklist.discard(name)


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


def list_restore_destination_subdirs(preset_root: Path) -> tuple[str, ...]:
    """Top-level dirs under ``preset_root`` excluding favourites/ and blacklist/."""
    return tuple(
        name
        for name in list_destination_subdirs(preset_root)
        if name not in (FAVOURITES_DIR, BLACKLIST_DIR)
    )


def find_milk_under(root: Path, name: str) -> Path | None:
    """Return the first ``*.milk`` under ``root`` whose basename is ``name``."""
    if not root.is_dir():
        return None
    for path in sorted(root.rglob("*.milk")):
        if path.name == name and path.is_file():
            return path
    return None


def curated_milk_src(root: Path, src: Path) -> Path | None:
    """Prefer ``src`` when it already lives under ``root``; else find by basename."""
    if not src.is_file():
        return find_milk_under(root, src.name)
    try:
        src.resolve().relative_to(root.resolve())
    except ValueError:
        return find_milk_under(root, src.name)
    return src


def copy_to_favourites(src_milk: Path, dest_dir: Path) -> Path:
    """Copy ``src_milk`` and co-located textures into ``dest_dir``."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_milk = copy_with_dedup(dest_dir, src_milk)
    for suffix in COLOCATED_TEXTURE_SUFFIXES:
        for texture in sorted(src_milk.parent.glob(f"*{suffix}")):
            if texture.is_file():
                copy_with_dedup(dest_dir, texture)
    return dest_milk


def move_to_blacklist(
    src_milk: Path,
    dest_dir: Path,
    preset_root: Path,
) -> Path:
    """Move ``src_milk`` into ``dest_dir``; textures in the source dir are left behind.

    Writes a ``.origin`` sidecar with the source path relative to ``preset_root``
    when ``src_milk`` lives under that root.
    """
    relative_src: str | None = None
    try:
        relative_src = src_milk.resolve().relative_to(preset_root.resolve()).as_posix()
    except ValueError:
        relative_src = None

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path, _needs_copy = resolve_user_preset_dest(dest_dir, src_milk)
    shutil.move(str(src_milk), str(dest_path))
    if relative_src is not None:
        write_blacklist_origin(dest_path, relative_src)
    return dest_path


def delete_favourite_milk(preset_root: Path, src: Path) -> Path | None:
    """Delete the curated favourites ``.milk`` for ``src``; leave textures alone."""
    curated = curated_milk_src(favourites_root(preset_root), src)
    if curated is None:
        return None
    curated.unlink()
    return curated


def restore_from_blacklist(milk: Path, dest_dir: Path) -> Path:
    """Move a blacklisted milk to ``dest_dir`` and remove its ``.origin`` sidecar."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    sidecar = origin_sidecar_path(milk)
    dest_milk = _unique_relocate_dest(dest_dir.resolve(), milk.name)
    shutil.move(str(milk), str(dest_milk))
    if sidecar.is_file():
        sidecar.unlink()
    return dest_milk


def relocate_curated_milk(
    src_milk: Path,
    dest_dir: Path,
    *,
    with_textures: bool = False,
) -> Path:
    """Move ``src_milk`` into ``dest_dir``; same-directory is a no-op.

    Unlike :func:`move_to_blacklist`, this supports relocating between folders under
    the same curation tree (sibling or parent destinations). When a ``.origin``
    sidecar sits beside the milk, it moves with it.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    resolved_src = src_milk.resolve()
    resolved_dest_dir = dest_dir.resolve()
    if resolved_src.parent == resolved_dest_dir:
        return resolved_src

    dest_milk = _unique_relocate_dest(resolved_dest_dir, src_milk.name)
    src_parent = src_milk.parent
    sidecar = origin_sidecar_path(src_milk)
    textures: list[Path] = []
    if with_textures:
        for suffix in COLOCATED_TEXTURE_SUFFIXES:
            textures.extend(
                sorted(
                    path
                    for path in src_parent.glob(f"*{suffix}")
                    if path.is_file()
                )
            )
    shutil.move(str(src_milk), str(dest_milk))
    if sidecar.is_file():
        shutil.move(str(sidecar), str(origin_sidecar_path(dest_milk)))
    for texture in textures:
        shutil.move(
            str(texture),
            str(_unique_relocate_dest(resolved_dest_dir, texture.name)),
        )
    return dest_milk


def _unique_relocate_dest(dest_dir: Path, filename: str) -> Path:
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    index = 2
    while True:
        alt = dest_dir / f"{stem}_{index}{suffix}"
        if not alt.exists():
            return alt
        index += 1


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


def rewrite_user_preset_paths(
    layers: Mapping[str, object],
    old: Path,
    new: Path,
) -> list[str]:
    """Rewrite ``old`` to ``new`` in layer user preset lists; return affected slots."""
    old_resolved = old.resolve()
    new_str = str(new)
    affected: list[str] = []
    for slot, layer in layers.items():
        user_presets: list[str] = layer.user_presets  # type: ignore[attr-defined]
        changed = False
        for index, path in enumerate(user_presets):
            if Path(path).resolve() == old_resolved:
                user_presets[index] = new_str
                changed = True
        if changed:
            affected.append(slot)
    return affected
