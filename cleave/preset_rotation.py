"""Deterministic, seek-stable preset rotation for timeline switching."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PresetRotation:
    """Maps a non-negative transition count to a preset path.

    Non-shuffle wraps ``paths`` with an ``anchor`` offset.
    Shuffle concatenates seeded permutations of ``paths`` (one full bag of
    length ``n`` per block) so each path appears once before any repeats.
    ``path_for(count)`` indexes ``anchor + count`` into that sequence.
    """

    paths: tuple[Path, ...]
    shuffle: bool
    seed: int
    anchor: int = 0

    def __post_init__(self) -> None:
        n = len(self.paths)
        if n > 0 and not (0 <= self.anchor < n):
            object.__setattr__(self, "anchor", self.anchor % n)

    def path_for(self, count: int) -> Path | None:
        n = len(self.paths)
        if n == 0:
            return None
        index = self.anchor + int(count)
        if not self.shuffle:
            return self.paths[index % n]
        return self._shuffled_at(index)

    def _shuffled_at(self, index: int) -> Path:
        n = len(self.paths)
        block, offset = divmod(index, n)
        order = list(range(n))
        # Mix seed with block index; keep in 64-bit range for Random.seed.
        block_seed = (self.seed + block * 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        rng = random.Random(block_seed)
        rng.shuffle(order)
        return self.paths[order[offset]]


def rotation_seed(paths: Sequence[Path], *, salt: str = "") -> int:
    """Stable seed so live preview and offline render agree."""
    digest = hashlib.sha256()
    digest.update(salt.encode("utf-8"))
    for path in paths:
        digest.update(b"\0")
        digest.update(str(path).encode("utf-8"))
    return int.from_bytes(digest.digest()[:8], "big")


def layer_rotation_seed(
    paths: Sequence[Path],
    *,
    slot: str,
    shuffle_salt: int = 0,
) -> int:
    """Seed for a layer's shuffled rotation (slot + persisted salt)."""
    return rotation_seed(paths, salt=f"{slot}:{int(shuffle_salt)}")


def first_shuffle_bag_order(
    paths: Sequence[Path],
    *,
    seed: int,
) -> list[Path]:
    """Return the first shuffle-bag order for ``paths`` under ``seed``."""
    if not paths:
        return []
    rotation = PresetRotation(
        paths=tuple(paths),
        shuffle=True,
        seed=seed,
        anchor=0,
    )
    ordered: list[Path] = []
    for i in range(len(paths)):
        path = rotation.path_for(i)
        if path is not None:
            ordered.append(path)
    return ordered
