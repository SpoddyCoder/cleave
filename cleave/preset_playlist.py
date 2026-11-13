"""Scan Milkdrop preset anchors into playlists and sync config selections."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from cleave.config import CleaveConfig
from cleave.preset_library import (
    COLLECTION_LABEL,
    UNFILTERED_CATALOG,
    PresetCatalog,
    PresetCollection,
)

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


def playlist_at_dir(
    dir: Path,
    *,
    index: int = 0,
    catalog: PresetCatalog = UNFILTERED_CATALOG,
) -> PresetPlaylist:
    """Build a playlist for presets directly in ``dir`` (blacklisted ones hidden)."""
    resolved_dir = dir.resolve()
    paths = catalog.visible(p.resolve() for p in milk_files_in_dir(resolved_dir))
    if not paths:
        return PresetPlaylist(
            current_dir=resolved_dir, paths=(), index=0, catalog=catalog
        )
    clamped = index % len(paths)
    return PresetPlaylist(
        current_dir=resolved_dir, paths=paths, index=clamped, catalog=catalog
    )


def playlist_at_collection(
    collection: PresetCollection,
    *,
    current_dir: Path,
    catalog: PresetCatalog,
) -> PresetPlaylist:
    """Build a playlist over a library collection; ``current_dir`` is kept for exit."""
    return PresetPlaylist(
        current_dir=current_dir.resolve(),
        paths=catalog.collection_paths(collection),
        index=0,
        catalog=catalog,
        collection=collection,
    )


BrowseEntry = Path | PresetCollection


def top_level_entries(
    preset_root: Path, catalog: PresetCatalog
) -> tuple[BrowseEntry, ...]:
    """Library collections, then preset folders directly under ``preset_root``."""
    return (*catalog.collections(), *list_navigable_dirs(preset_root.resolve()))


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


def path_under_preset_root(path: Path, preset_root: Path) -> bool:
    """True when ``path`` is ``preset_root`` or a descendant."""
    return _path_at_or_below(path, preset_root)


def _anchor_directory(anchor: Path) -> Path:
    """Directory for browse/playlist when *anchor* is a file or missing ``.milk``."""
    resolved = anchor.resolve()
    if resolved.is_file() or resolved.suffix.lower() == ".milk":
        return resolved.parent
    return resolved


def preset_browse_floor(anchor: Path, preset_root: Path) -> Path:
    """Lowest directory this layer may ascend to when browsing presets."""
    resolved_root = preset_root.resolve()
    base = _anchor_directory(anchor)
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


def _effective_browse_floor(
    current_dir: Path,
    preset_root: Path,
    *,
    browse_floor: Path | None = None,
) -> Path:
    """Floor for ascent clamps; local pack if ``current_dir`` escaped."""
    resolved_root = preset_root.resolve()
    floor = (
        browse_floor if browse_floor is not None else preset_root
    ).resolve()
    resolved = current_dir.resolve()
    if _path_at_or_below(resolved, floor):
        return floor
    return preset_browse_floor(resolved, resolved_root)


def list_browse_siblings(
    current_dir: Path,
    preset_root: Path,
) -> tuple[Path, ...]:
    """Navigable peer dirs for Left/Right (parent clamped at ``preset_root``)."""
    return list_navigable_dirs(navigable_parent(current_dir, preset_root))


def is_top_level_browse_dir(current_dir: Path, preset_root: Path) -> bool:
    """True when ``current_dir`` is a direct child of ``preset_root``."""
    resolved = current_dir.resolve()
    resolved_root = preset_root.resolve()
    if resolved == resolved_root:
        return False
    return resolved.parent.resolve() == resolved_root


def _can_go_parent(
    current_dir: Path,
    preset_root: Path,
    *,
    browse_floor: Path | None = None,
) -> bool:
    """True when Backspace would ascend (same gate as ``go_parent``)."""
    parent = current_dir.parent
    if parent == current_dir:
        return False
    if not _path_at_or_below(parent, preset_root):
        return False
    floor = _effective_browse_floor(
        current_dir, preset_root, browse_floor=browse_floor
    )
    return _path_at_or_below(parent, floor)


def directory_tree_moves(
    current_dir: Path,
    preset_root: Path,
    *,
    browse_floor: Path | None = None,
) -> tuple[bool, bool]:
    """Whether the directory row can move to a parent, and to a child."""
    can_up = _can_go_parent(
        current_dir, preset_root, browse_floor=browse_floor
    )
    can_down = bool(list_navigable_dirs(current_dir))
    return can_up, can_down


@dataclass(frozen=True)
class DirectoryDisplay:
    """Directory row content: path, sibling position, and available tree moves."""

    path: str
    position: str
    can_go_up: bool
    can_go_down: bool


@dataclass
class PresetPlaylist:
    current_dir: Path
    paths: tuple[Path, ...]
    index: int = 0
    catalog: PresetCatalog = field(default=UNFILTERED_CATALOG, repr=False, compare=False)
    collection: PresetCollection | None = None
    _dir_display_root: Path | None = field(default=None, repr=False)
    _dir_display_floor: Path | None = field(default=None, repr=False)
    _dir_display: DirectoryDisplay | None = field(default=None, repr=False)

    @property
    def current(self) -> Path | None:
        if not self.paths:
            return None
        return self.paths[self.index]

    def _invalidate_dir_display(self) -> None:
        self._dir_display_root = None
        self._dir_display_floor = None
        self._dir_display = None

    def _at_top_level(self, preset_root: Path) -> bool:
        """True when Left/Right steps through collections and top-level folders."""
        if self.collection is not None:
            return True
        resolved_root = preset_root.resolve()
        return navigable_parent(self.current_dir, resolved_root) == resolved_root

    def _entry(self) -> BrowseEntry:
        return self.collection if self.collection is not None else self.current_dir.resolve()

    def _compute_dir_display(
        self,
        preset_root: Path,
        *,
        browse_floor: Path | None = None,
    ) -> DirectoryDisplay:
        if self.collection is not None:
            entries = top_level_entries(preset_root, self.catalog)
            position = entries.index(self.collection) + 1
            return DirectoryDisplay(
                COLLECTION_LABEL[self.collection],
                f"{position}/{len(entries)}",
                False,
                False,
            )
        rel = to_config_relative(self.current_dir, preset_root).rstrip("/") + "/"
        can_go_up, can_go_down = directory_tree_moves(
            self.current_dir, preset_root, browse_floor=browse_floor
        )
        siblings: tuple[BrowseEntry, ...] = (
            top_level_entries(preset_root, self.catalog)
            if self._at_top_level(preset_root)
            else list_browse_siblings(self.current_dir, preset_root)
        )
        if not siblings:
            return DirectoryDisplay(rel, "1/1", can_go_up, can_go_down)
        current = self._entry()
        try:
            position = siblings.index(current) + 1
        except ValueError:
            position = 1
        return DirectoryDisplay(
            rel, f"{position}/{len(siblings)}", can_go_up, can_go_down
        )

    def directory_display(
        self,
        preset_root: Path,
        *,
        browse_floor: Path | None = None,
    ) -> DirectoryDisplay:
        resolved_root = preset_root.resolve()
        resolved_floor = (
            browse_floor if browse_floor is not None else preset_root
        ).resolve()
        if (
            self._dir_display_root == resolved_root
            and self._dir_display_floor == resolved_floor
            and self._dir_display is not None
        ):
            return self._dir_display
        display = self._compute_dir_display(
            preset_root, browse_floor=browse_floor
        )
        self._dir_display_root = resolved_root
        self._dir_display_floor = resolved_floor
        self._dir_display = display
        return display

    def _apply(self, other: PresetPlaylist) -> None:
        self.current_dir = other.current_dir
        self.paths = other.paths
        self.index = other.index
        self.collection = other.collection
        self._invalidate_dir_display()

    def _playlist_for(self, entry: BrowseEntry) -> PresetPlaylist:
        if isinstance(entry, Path):
            return playlist_at_dir(entry, catalog=self.catalog)
        return playlist_at_collection(
            entry, current_dir=self.current_dir, catalog=self.catalog
        )

    def next(self) -> Path | None:
        if not self.paths:
            return None
        self.index = (self.index + 1) % len(self.paths)
        self._invalidate_dir_display()
        return self.current

    def prev(self) -> Path | None:
        if not self.paths:
            return None
        self.index = (self.index - 1) % len(self.paths)
        self._invalidate_dir_display()
        return self.current

    def remove_preset(self, path: Path) -> bool:
        """Remove path from sibling rotation; adjust index; invalidate dir label."""
        resolved = path.resolve()
        try:
            removed_idx = next(
                i for i, candidate in enumerate(self.paths) if candidate.resolve() == resolved
            )
        except StopIteration:
            return False

        self.paths = tuple(
            candidate for candidate in self.paths if candidate.resolve() != resolved
        )
        if not self.paths:
            self.index = 0
        elif removed_idx < self.index:
            self.index -= 1
        elif removed_idx == self.index:
            self.index = min(self.index, len(self.paths) - 1)
        self._invalidate_dir_display()
        return True

    def refresh_collection(self) -> bool:
        """Re-read a collection's members; the current preset stays selected.

        A current preset that just left the collection stays listed until the
        collection is entered again, so curating it never jumps the layer to a
        different preset. Returns True when the current preset changed. No-op
        for folder browsing.
        """
        if self.collection is None:
            return False
        before = self.current
        paths = self.catalog.collection_paths(self.collection)
        if before is not None and before not in paths and before.is_file():
            paths = tuple(sorted((*paths, before)))
        if before is not None and before in paths:
            index = paths.index(before)
        elif paths:
            index = min(self.index, len(paths) - 1)
        else:
            index = 0
        self.paths = paths
        self.index = index
        self._invalidate_dir_display()
        return self.current != before

    def step_by(self, delta: int) -> Path | None:
        if not self.paths:
            return None
        self.index = (self.index + delta) % len(self.paths)
        self._invalidate_dir_display()
        return self.current

    def step_sibling(self, delta: int = 1, *, preset_root: Path) -> bool:
        siblings: tuple[BrowseEntry, ...] = (
            top_level_entries(preset_root, self.catalog)
            if self._at_top_level(preset_root)
            else list_browse_siblings(self.current_dir, preset_root)
        )
        if not siblings:
            return False
        try:
            idx = siblings.index(self._entry())
        except ValueError:
            idx = 0
        new_idx = (idx + delta) % len(siblings)
        self._apply(self._playlist_for(siblings[new_idx]))
        return True

    def enter_child(self, preset_root: Path) -> bool:
        if self.collection is not None:
            return False
        children = list_navigable_dirs(self.current_dir)
        if not children:
            return False
        self._apply(playlist_at_dir(children[0], catalog=self.catalog))
        return True

    def go_parent(
        self,
        preset_root: Path,
        *,
        browse_floor: Path | None = None,
    ) -> bool:
        if self.collection is not None:
            return False
        if not _can_go_parent(
            self.current_dir, preset_root, browse_floor=browse_floor
        ):
            return False
        parent = self.current_dir.parent
        self._apply(playlist_at_dir(parent, catalog=self.catalog))
        return True

    def load_into(self, pm: ProjectM, smooth: bool = False) -> None:
        if self.current is None:
            return
        pm.load_preset(self.current, smooth=smooth)

    def config_preset_path(self, preset_root: Path) -> str:
        """Persisted anchor: the real preset file, never the collection."""
        if self.current is not None:
            return to_config_relative(self.current, preset_root)
        rel = to_config_relative(self.current_dir, preset_root)
        return rel if rel.endswith("/") else f"{rel}/"


def scan_single_layer(
    slot: str,
    preset_root: Path,
    project_dir: Path,
    *,
    catalog: PresetCatalog = UNFILTERED_CATALOG,
) -> PresetPlaylist:
    resolved_root = preset_root.resolve()
    paths = list(catalog.visible(resolved_root.rglob("*.milk")))
    if paths:
        anchor = random.choice(paths)
        return scan_preset_playlist(anchor, catalog=catalog)
    return scan_preset_playlist(resolved_root, catalog=catalog)


def scan_preset_playlist(
    anchor: Path,
    *,
    catalog: PresetCatalog = UNFILTERED_CATALOG,
) -> PresetPlaylist:
    """Build a playlist from a .milk file or a directory of presets.

    Missing anchors yield an empty playlist at the intended directory so play and
    render can still open when browse packs are absent (e.g. after restore).
    A blacklisted anchor file stays selected so a saved project still opens on it.
    """
    resolved = anchor.resolve()
    if not resolved.exists():
        return PresetPlaylist(
            current_dir=_anchor_directory(anchor),
            paths=(),
            index=0,
            catalog=catalog,
        )

    if resolved.is_file():
        if resolved.suffix.lower() != ".milk":
            raise ValueError(f"preset anchor is not a .milk file: {resolved}")
        current_dir = resolved.parent.resolve()
        paths = catalog.visible(p.resolve() for p in milk_files_in_dir(current_dir))
        if resolved not in paths:
            paths = tuple(sorted((*paths, resolved)))
        return PresetPlaylist(
            current_dir=current_dir,
            paths=paths,
            index=paths.index(resolved),
            catalog=catalog,
        )

    if resolved.is_dir():
        return playlist_at_dir(resolved, index=0, catalog=catalog)

    raise ValueError(f"preset anchor is not a file or directory: {resolved}")


def preset_filename_display(playlist: PresetPlaylist) -> str:
    """Current preset filename, or empty-state label."""
    if playlist.current is None:
        return "NO PRESETS FOUND"
    return playlist.current.name


def preset_position_display(playlist: PresetPlaylist) -> str:
    """Position of the current preset in its directory, as ``N/TOTAL``."""
    if playlist.current is None:
        return "0/0"
    return f"{playlist.index + 1}/{len(playlist.paths)}"


def to_config_relative(path: Path, preset_root: Path) -> str:
    """Preset path relative to preset_root, using forward slashes.

    Paths outside preset_root (project preset copies) are absolute so they
    round-trip through config load.
    """
    resolved = path.resolve()
    try:
        return resolved.relative_to(preset_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def scan_all_layers(
    cfg: CleaveConfig,
    *,
    catalog: PresetCatalog = UNFILTERED_CATALOG,
) -> dict[str, PresetPlaylist]:
    """Scan one preset playlist per configured layer."""
    return {
        slot: scan_preset_playlist(cfg.layers[slot].preset, catalog=catalog)
        for slot in cfg.layer_z_order
        if slot in cfg.layers
    }
