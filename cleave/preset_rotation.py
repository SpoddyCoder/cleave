"""Deterministic, seek-stable preset rotation for list-based switching."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PresetRotation:
    """Maps a non-negative index to a preset path.

    Wraps ``paths`` with an ``anchor`` offset so ``path_for(count)`` returns
    ``paths[(anchor + count) % n]``.
    """

    paths: tuple[Path, ...]
    anchor: int = 0

    def __post_init__(self) -> None:
        n = len(self.paths)
        if n > 0 and not (0 <= self.anchor < n):
            object.__setattr__(self, "anchor", self.anchor % n)

    def path_for(self, count: int) -> Path | None:
        n = len(self.paths)
        if n == 0:
            return None
        return self.paths[(self.anchor + int(count)) % n]
