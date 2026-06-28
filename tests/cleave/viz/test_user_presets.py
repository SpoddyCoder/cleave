"""Tests for cleave.viz.user_presets."""

from __future__ import annotations

from pathlib import Path

from cleave.viz.user_presets import (
    resolve_user_preset_dest,
    user_preset_item_display_name,
)


def test_user_preset_item_display_name_single() -> None:
    paths = ["/tmp/user-presets/foo.milk"]
    assert user_preset_item_display_name(paths, 0) == "foo.milk"


def test_user_preset_item_display_name_duplicates() -> None:
    paths = [
        "/tmp/user-presets/foo.milk",
        "/tmp/user-presets/foo.milk",
        "/tmp/user-presets/bar.milk",
    ]
    assert user_preset_item_display_name(paths, 0) == "foo.milk (1)"
    assert user_preset_item_display_name(paths, 1) == "foo.milk (2)"
    assert user_preset_item_display_name(paths, 2) == "bar.milk"


def test_resolve_user_preset_dest_creates_canonical_path(tmp_path: Path) -> None:
    src = tmp_path / "src" / "preset.milk"
    src.parent.mkdir()
    src.write_text("preset", encoding="utf-8")
    dest_dir = tmp_path / "user-presets"

    dest, needs_copy = resolve_user_preset_dest(dest_dir, src)

    assert dest == dest_dir / "preset.milk"
    assert needs_copy is True


def test_resolve_user_preset_dest_reuses_existing_copy(tmp_path: Path) -> None:
    src = tmp_path / "src" / "preset.milk"
    src.parent.mkdir()
    src.write_text("preset", encoding="utf-8")
    dest_dir = tmp_path / "user-presets"
    dest_dir.mkdir()
    existing = dest_dir / "preset.milk"
    existing.write_text("preset", encoding="utf-8")

    dest, needs_copy = resolve_user_preset_dest(dest_dir, src)

    assert dest == existing
    assert needs_copy is False


def test_resolve_user_preset_dest_same_name_different_content(tmp_path: Path) -> None:
    src = tmp_path / "src" / "preset.milk"
    src.parent.mkdir()
    src.write_text("new", encoding="utf-8")
    dest_dir = tmp_path / "user-presets"
    dest_dir.mkdir()
    (dest_dir / "preset.milk").write_text("old", encoding="utf-8")

    dest, needs_copy = resolve_user_preset_dest(dest_dir, src)

    assert dest == dest_dir / "preset_2.milk"
    assert needs_copy is True
