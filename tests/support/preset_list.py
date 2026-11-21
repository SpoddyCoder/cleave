"""Build preset list entries for tests."""

from __future__ import annotations

from pathlib import Path

from cleave.preset_list_entry import PresetListEntry


def entries(*paths: str | Path) -> list[PresetListEntry]:
    """One source-less entry per path, in order."""
    return [PresetListEntry(path=str(path)) for path in paths]
