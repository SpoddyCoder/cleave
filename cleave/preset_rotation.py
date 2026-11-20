"""Deterministic, seek-stable preset rotation for list-based switching."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PresetRotation:
    """Maps a non-negative index to a preset path, wrapping round the list.

    ``path_for(count)`` returns ``paths[count % n]``, so index 0 is always the
    first list item.
    """

    paths: tuple[Path, ...]

    def path_for(self, count: int) -> Path | None:
        n = len(self.paths)
        if n == 0:
            return None
        return self.paths[int(count) % n]
