"""Helpers for per-layer user-defined preset lists."""

from __future__ import annotations

import filecmp
import os
from pathlib import Path


def user_preset_item_display_name(paths: list[str], index: int) -> str:
    """Format a user preset row label, numbering duplicate paths in the list."""
    path = paths[index]
    resolved = Path(path).resolve()
    name = Path(path).name
    matching = [
        position
        for position, candidate in enumerate(paths)
        if Path(candidate).resolve() == resolved
    ]
    if len(matching) <= 1:
        return name
    instance = matching.index(index) + 1
    return f"{name} ({instance})"


def resolve_user_preset_dest(dest_dir: Path, src_path: Path) -> tuple[Path, bool]:
    """Return destination path and whether the source file must be copied."""
    resolved_src = src_path.resolve()
    presets_dir = dest_dir.resolve()

    try:
        resolved_src.relative_to(presets_dir)
        return resolved_src, False
    except ValueError:
        pass

    canonical = presets_dir / src_path.name
    if canonical.exists():
        if _same_preset_file(src_path, canonical):
            return canonical, False
        return _unique_copy_dest(dest_dir, src_path.name), True

    return canonical, True


def _same_preset_file(left: Path, right: Path) -> bool:
    try:
        if os.path.samefile(left, right):
            return True
    except OSError:
        pass
    return filecmp.cmp(left, right, shallow=False)


def _unique_copy_dest(dest_dir: Path, filename: str) -> Path:
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    index = 2
    while True:
        candidate = dest_dir / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1
