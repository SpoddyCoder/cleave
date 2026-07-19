"""Tests for deterministic PresetRotation."""

from __future__ import annotations

from pathlib import Path

from cleave.preset_rotation import PresetRotation, rotation_seed


def _paths(*names: str) -> tuple[Path, ...]:
    return tuple(Path(name) for name in names)


def test_path_for_empty_returns_none() -> None:
    rotation = PresetRotation(paths=(), shuffle=False, seed=1, anchor=0)
    assert rotation.path_for(0) is None
    assert rotation.path_for(3) is None


def test_non_shuffle_wraps_with_anchor() -> None:
    paths = _paths("a.milk", "b.milk", "c.milk")
    rotation = PresetRotation(paths=paths, shuffle=False, seed=0, anchor=1)
    assert rotation.path_for(0) == Path("b.milk")
    assert rotation.path_for(1) == Path("c.milk")
    assert rotation.path_for(2) == Path("a.milk")
    assert rotation.path_for(3) == Path("b.milk")


def test_non_shuffle_anchor_normalizes_modulo() -> None:
    paths = _paths("a.milk", "b.milk")
    rotation = PresetRotation(paths=paths, shuffle=False, seed=0, anchor=5)
    assert rotation.anchor == 1
    assert rotation.path_for(0) == Path("b.milk")


def test_shuffle_no_repeat_within_block() -> None:
    paths = _paths("a.milk", "b.milk", "c.milk", "d.milk")
    rotation = PresetRotation(paths=paths, shuffle=True, seed=42, anchor=0)
    first_block = [rotation.path_for(i) for i in range(4)]
    assert sorted(first_block) == sorted(paths)
    assert len(set(first_block)) == 4
    second_block = [rotation.path_for(i) for i in range(4, 8)]
    assert sorted(second_block) == sorted(paths)
    assert len(set(second_block)) == 4


def test_shuffle_deterministic_by_seed() -> None:
    paths = _paths("a.milk", "b.milk", "c.milk")
    a = PresetRotation(paths=paths, shuffle=True, seed=7, anchor=0)
    b = PresetRotation(paths=paths, shuffle=True, seed=7, anchor=0)
    c = PresetRotation(paths=paths, shuffle=True, seed=8, anchor=0)
    seq_a = [a.path_for(i) for i in range(9)]
    seq_b = [b.path_for(i) for i in range(9)]
    seq_c = [c.path_for(i) for i in range(9)]
    assert seq_a == seq_b
    assert seq_a != seq_c


def test_shuffle_respects_anchor_offset() -> None:
    paths = _paths("a.milk", "b.milk", "c.milk")
    base = PresetRotation(paths=paths, shuffle=True, seed=11, anchor=0)
    offset = PresetRotation(paths=paths, shuffle=True, seed=11, anchor=2)
    assert offset.path_for(0) == base.path_for(2)
    assert offset.path_for(1) == base.path_for(3)


def test_rotation_seed_stable_across_calls() -> None:
    paths = _paths("a.milk", "b.milk")
    assert rotation_seed(paths, salt="layer_1") == rotation_seed(
        paths, salt="layer_1"
    )
    assert rotation_seed(paths, salt="layer_1") != rotation_seed(
        paths, salt="layer_2"
    )
