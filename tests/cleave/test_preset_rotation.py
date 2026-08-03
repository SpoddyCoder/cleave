"""Tests for seek-stable list indexing via PresetRotation."""

from __future__ import annotations

from pathlib import Path

from cleave.preset_rotation import PresetRotation


def test_path_for_wraps_with_anchor() -> None:
    paths = (Path("a.milk"), Path("b.milk"), Path("c.milk"))
    rotation = PresetRotation(paths=paths, anchor=1)
    assert rotation.path_for(0) == Path("b.milk")
    assert rotation.path_for(1) == Path("c.milk")
    assert rotation.path_for(2) == Path("a.milk")
    assert rotation.path_for(3) == Path("b.milk")


def test_path_for_empty_returns_none() -> None:
    rotation = PresetRotation(paths=())
    assert rotation.path_for(0) is None


def test_anchor_normalizes_out_of_range() -> None:
    paths = (Path("a.milk"), Path("b.milk"))
    rotation = PresetRotation(paths=paths, anchor=5)
    assert rotation.anchor == 1
    assert rotation.path_for(0) == Path("b.milk")
