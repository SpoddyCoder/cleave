"""One item of a layer's preset switching list: the project copy and its origin."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PresetListEntry:
    """A preset list item.

    ``path`` is the absolute path of the copy in the project's ``presets/``
    folder, the file switching plays. ``source`` is the absolute path the
    preset was copied from, or ``None`` when it already lived in ``presets/``.
    """

    path: str
    source: str | None = None

    @property
    def file(self) -> Path:
        return Path(self.path)

    @property
    def display_name(self) -> str:
        """The original file name when known, so a deduplicated copy reads as its source."""
        if self.source is not None:
            return Path(self.source).name
        return Path(self.path).name


def entry_paths(entries: Iterable[PresetListEntry]) -> list[Path]:
    """The copy path of each entry, in order."""
    return [entry.file for entry in entries]
