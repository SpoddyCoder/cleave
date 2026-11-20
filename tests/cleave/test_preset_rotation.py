"""Tests for seek-stable list indexing via PresetRotation."""

from __future__ import annotations

from pathlib import Path

from cleave.preset_rotation import PresetRotation


def test_path_for_starts_at_first_item_and_wraps() -> None:
    paths = (Path("a.milk"), Path("b.milk"), Path("c.milk"))
    rotation = PresetRotation(paths=paths)
    assert rotation.path_for(0) == Path("a.milk")
    assert rotation.path_for(1) == Path("b.milk")
    assert rotation.path_for(2) == Path("c.milk")
    assert rotation.path_for(3) == Path("a.milk")


def test_path_for_empty_returns_none() -> None:
    rotation = PresetRotation(paths=())
    assert rotation.path_for(0) is None
