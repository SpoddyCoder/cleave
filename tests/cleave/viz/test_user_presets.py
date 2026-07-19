"""Tests for cleave.viz.user_presets."""

from __future__ import annotations

from pathlib import Path

from cleave.project import PROJECT_FILENAME
from cleave.viz.user_presets import (
    cleanup_unreferenced_user_presets,
    iter_project_viz_config_paths,
    resolve_user_preset_dest,
    user_preset_item_display_name,
    user_preset_referenced_on_disk,
)


def _write_viz_yaml(path: Path, preset_relpaths: list[str]) -> None:
    if not preset_relpaths:
        path.write_text("layers:\n  layer_1: {}\n", encoding="utf-8")
        return
    presets = "\n".join(f"      - {rel}" for rel in preset_relpaths)
    path.write_text(
        "layers:\n"
        "  layer_1:\n"
        "    preset_switching_presets:\n"
        f"{presets}\n",
        encoding="utf-8",
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


def test_cleanup_deletes_orphan_milk(tmp_path: Path) -> None:
    presets = tmp_path / "user-presets"
    presets.mkdir()
    orphan = presets / "orphan.milk"
    orphan.write_text("x", encoding="utf-8")
    _write_viz_yaml(tmp_path / "cleave-viz.yaml", [])

    removed = cleanup_unreferenced_user_presets(tmp_path)

    assert orphan.resolve() in removed
    assert not orphan.exists()


def test_cleanup_keeps_milk_referenced_by_cleave_viz(tmp_path: Path) -> None:
    presets = tmp_path / "user-presets"
    presets.mkdir()
    kept = presets / "kept.milk"
    kept.write_text("x", encoding="utf-8")
    _write_viz_yaml(tmp_path / "cleave-viz.yaml", ["user-presets/kept.milk"])

    removed = cleanup_unreferenced_user_presets(tmp_path)

    assert removed == []
    assert kept.exists()


def test_cleanup_keeps_milk_referenced_only_by_unnamed_yaml(tmp_path: Path) -> None:
    presets = tmp_path / "user-presets"
    presets.mkdir()
    kept = presets / "kept.milk"
    kept.write_text("x", encoding="utf-8")
    orphan = presets / "orphan.milk"
    orphan.write_text("y", encoding="utf-8")
    _write_viz_yaml(tmp_path / "cleave-viz.yaml", [])
    _write_viz_yaml(tmp_path / "unnamed-1.yaml", ["user-presets/kept.milk"])

    removed = cleanup_unreferenced_user_presets(tmp_path)

    assert kept.exists()
    assert orphan.resolve() in removed
    assert not orphan.exists()


def test_cleanup_ignores_project_yaml_and_non_viz_yaml(tmp_path: Path) -> None:
    presets = tmp_path / "user-presets"
    presets.mkdir()
    orphan = presets / "orphan.milk"
    orphan.write_text("x", encoding="utf-8")
    (tmp_path / PROJECT_FILENAME).write_text(
        "version: 1\n"
        "slug: demo\n"
        "mix:\n  filename: mix.wav\n"
        "ingest:\n  original: /tmp/a.wav\n  separated_at: t\n  demucs_model: htdemucs\n"
        "layers:\n"
        "  layer_1:\n"
        "    preset_switching_presets:\n"
        "      - user-presets/orphan.milk\n",
        encoding="utf-8",
    )
    (tmp_path / "notes.yaml").write_text("title: hello\n", encoding="utf-8")
    _write_viz_yaml(tmp_path / "cleave-viz.yaml", [])

    assert tmp_path / PROJECT_FILENAME not in iter_project_viz_config_paths(tmp_path)
    assert tmp_path / "notes.yaml" not in iter_project_viz_config_paths(tmp_path)

    removed = cleanup_unreferenced_user_presets(tmp_path)

    assert orphan.resolve() in removed
    assert not orphan.exists()


def test_cleanup_does_not_delete_outside_user_presets(tmp_path: Path) -> None:
    presets = tmp_path / "user-presets"
    presets.mkdir()
    outside = tmp_path / "outside.milk"
    outside.write_text("x", encoding="utf-8")
    _write_viz_yaml(tmp_path / "cleave-viz.yaml", [])

    cleanup_unreferenced_user_presets(tmp_path)

    assert outside.exists()


def test_user_preset_referenced_on_disk_skip_config(tmp_path: Path) -> None:
    presets = tmp_path / "user-presets"
    presets.mkdir()
    milk = presets / "shared.milk"
    milk.write_text("x", encoding="utf-8")
    active = tmp_path / "cleave-viz.yaml"
    other = tmp_path / "unnamed-1.yaml"
    _write_viz_yaml(active, ["user-presets/shared.milk"])
    _write_viz_yaml(other, ["user-presets/shared.milk"])

    assert user_preset_referenced_on_disk(tmp_path, milk, skip_config=active) is True
    _write_viz_yaml(other, [])
    assert user_preset_referenced_on_disk(tmp_path, milk, skip_config=active) is False
