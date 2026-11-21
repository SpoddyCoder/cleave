"""Tests for cleave.viz.user_presets."""

from __future__ import annotations

from pathlib import Path

from cleave.preset_list_entry import PresetListEntry
from cleave.project import PROJECT_FILENAME
from cleave.viz.user_presets import (
    cleanup_unreferenced_user_presets,
    copy_with_dedup,
    iter_project_viz_config_paths,
    path_list_digest,
    path_list_identity,
    preset_list_display_names,
    preset_list_item_display_name,
    preview_anchor,
    resolve_user_preset_dest,
    user_preset_referenced_on_disk,
)
from tests.support.preset_list import entries


def _write_viz_yaml(path: Path, preset_relpaths: list[str]) -> None:
    if not preset_relpaths:
        path.write_text("layers:\n  layer_1: {}\n", encoding="utf-8")
        return
    presets = "\n".join(f"      - path: {rel}" for rel in preset_relpaths)
    path.write_text(
        "layers:\n"
        "  layer_1:\n"
        "    preset_switching_list:\n"
        f"{presets}\n",
        encoding="utf-8",
    )


def test_preset_list_item_display_name_single() -> None:
    paths = entries("/tmp/presets/foo.milk")
    assert preset_list_item_display_name(paths, 0) == "foo.milk"


def test_preset_list_item_display_name_duplicates() -> None:
    paths = entries(
        "/tmp/presets/foo.milk",
        "/tmp/presets/foo.milk",
        "/tmp/presets/bar.milk",
    )
    assert preset_list_item_display_name(paths, 0) == "foo.milk (1)"
    assert preset_list_item_display_name(paths, 1) == "foo.milk (2)"
    assert preset_list_item_display_name(paths, 2) == "bar.milk"


def test_preset_list_display_names_single() -> None:
    paths = entries("/tmp/presets/foo.milk")
    assert preset_list_display_names(paths) == ["foo.milk"]


def test_preset_list_display_names_duplicates() -> None:
    paths = entries(
        "/tmp/presets/foo.milk",
        "/tmp/presets/foo.milk",
        "/tmp/presets/bar.milk",
    )
    assert preset_list_display_names(paths) == [
        "foo.milk (1)",
        "foo.milk (2)",
        "bar.milk",
    ]


def test_preset_list_display_names_empty() -> None:
    assert preset_list_display_names([]) == []


def test_path_list_digest_empty() -> None:
    assert path_list_digest([]) == ""


def test_path_list_digest_changes_on_content() -> None:
    a = path_list_digest(["/a/foo.milk"])
    b = path_list_digest(["/a/bar.milk"])
    assert a != b


def test_path_list_digest_changes_on_order() -> None:
    first = path_list_digest(["/a/foo.milk", "/a/bar.milk"])
    second = path_list_digest(["/a/bar.milk", "/a/foo.milk"])
    assert first != second


def test_path_list_digest_stable_for_same_paths() -> None:
    paths = ["/a/foo.milk", "/a/bar.milk"]
    assert path_list_digest(paths) == path_list_digest(paths)


def test_path_list_identity() -> None:
    paths = ["/a/foo.milk", "/a/bar.milk"]
    identity = path_list_identity(paths)
    assert identity == {
        "len": 2,
        "digest": path_list_digest(paths),
    }


def test_resolve_user_preset_dest_creates_canonical_path(tmp_path: Path) -> None:
    src = tmp_path / "src" / "preset.milk"
    src.parent.mkdir()
    src.write_text("preset", encoding="utf-8")
    dest_dir = tmp_path / "presets"

    dest, needs_copy = resolve_user_preset_dest(dest_dir, src)

    assert dest == dest_dir / "preset.milk"
    assert needs_copy is True


def test_resolve_user_preset_dest_reuses_existing_copy(tmp_path: Path) -> None:
    src = tmp_path / "src" / "preset.milk"
    src.parent.mkdir()
    src.write_text("preset", encoding="utf-8")
    dest_dir = tmp_path / "presets"
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
    dest_dir = tmp_path / "presets"
    dest_dir.mkdir()
    (dest_dir / "preset.milk").write_text("old", encoding="utf-8")

    dest, needs_copy = resolve_user_preset_dest(dest_dir, src)

    assert dest == dest_dir / "preset_2.milk"
    assert needs_copy is True


def test_cleanup_deletes_orphan_milk(tmp_path: Path) -> None:
    presets = tmp_path / "presets"
    presets.mkdir()
    orphan = presets / "orphan.milk"
    orphan.write_text("x", encoding="utf-8")
    _write_viz_yaml(tmp_path / "cleave-viz.yaml", [])

    removed = cleanup_unreferenced_user_presets(tmp_path)

    assert orphan.resolve() in removed
    assert not orphan.exists()


def test_cleanup_keeps_milk_referenced_by_cleave_viz(tmp_path: Path) -> None:
    presets = tmp_path / "presets"
    presets.mkdir()
    kept = presets / "kept.milk"
    kept.write_text("x", encoding="utf-8")
    _write_viz_yaml(tmp_path / "cleave-viz.yaml", ["presets/kept.milk"])

    removed = cleanup_unreferenced_user_presets(tmp_path)

    assert removed == []
    assert kept.exists()


def test_cleanup_keeps_milk_referenced_only_by_unnamed_yaml(tmp_path: Path) -> None:
    presets = tmp_path / "presets"
    presets.mkdir()
    kept = presets / "kept.milk"
    kept.write_text("x", encoding="utf-8")
    orphan = presets / "orphan.milk"
    orphan.write_text("y", encoding="utf-8")
    _write_viz_yaml(tmp_path / "cleave-viz.yaml", [])
    _write_viz_yaml(tmp_path / "unnamed-1.yaml", ["presets/kept.milk"])

    removed = cleanup_unreferenced_user_presets(tmp_path)

    assert kept.exists()
    assert orphan.resolve() in removed
    assert not orphan.exists()


def test_cleanup_ignores_project_yaml_and_non_viz_yaml(tmp_path: Path) -> None:
    presets = tmp_path / "presets"
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
        "    preset_switching_list:\n"
        "      - path: presets/orphan.milk\n",
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
    presets = tmp_path / "presets"
    presets.mkdir()
    outside = tmp_path / "outside.milk"
    outside.write_text("x", encoding="utf-8")
    _write_viz_yaml(tmp_path / "cleave-viz.yaml", [])

    cleanup_unreferenced_user_presets(tmp_path)

    assert outside.exists()


def test_user_preset_referenced_on_disk_skip_config(tmp_path: Path) -> None:
    presets = tmp_path / "presets"
    presets.mkdir()
    milk = presets / "shared.milk"
    milk.write_text("x", encoding="utf-8")
    active = tmp_path / "cleave-viz.yaml"
    other = tmp_path / "unnamed-1.yaml"
    _write_viz_yaml(active, ["presets/shared.milk"])
    _write_viz_yaml(other, ["presets/shared.milk"])

    assert user_preset_referenced_on_disk(tmp_path, milk, skip_config=active) is True
    _write_viz_yaml(other, [])
    assert user_preset_referenced_on_disk(tmp_path, milk, skip_config=active) is False


def test_display_names_use_the_original_file_name() -> None:
    entry = PresetListEntry("/proj/presets/foo_2.milk", source="/packs/a/foo.milk")
    assert preset_list_display_names([entry]) == ["foo.milk"]


def test_copy_with_dedup_records_the_source(tmp_path: Path) -> None:
    src = tmp_path / "packs" / "a" / "foo.milk"
    src.parent.mkdir(parents=True)
    src.write_text("x", encoding="utf-8")
    presets = tmp_path / "project" / "presets"

    entry = copy_with_dedup(presets, src)

    assert entry == PresetListEntry(
        str((presets / "foo.milk").resolve()), source=str(src.resolve())
    )
    assert copy_with_dedup(presets, presets / "foo.milk") == PresetListEntry(
        str((presets / "foo.milk").resolve())
    )


def _copied(tmp_path: Path) -> tuple[Path, PresetListEntry]:
    src = tmp_path / "packs" / "a" / "foo.milk"
    src.parent.mkdir(parents=True)
    src.write_text("x", encoding="utf-8")
    return src, copy_with_dedup(tmp_path / "project" / "presets", src)


def test_preview_anchor_is_the_original_while_it_matches(tmp_path: Path) -> None:
    src, entry = _copied(tmp_path)
    assert preview_anchor(entry) == src.resolve()


def test_preview_anchor_falls_back_to_the_copy_when_the_original_changed(
    tmp_path: Path,
) -> None:
    src, entry = _copied(tmp_path)
    src.write_text("edited", encoding="utf-8")
    assert preview_anchor(entry) == entry.file


def test_preview_anchor_falls_back_to_the_copy_when_the_original_is_gone(
    tmp_path: Path,
) -> None:
    src, entry = _copied(tmp_path)
    src.unlink()
    assert preview_anchor(entry) == entry.file


def test_preview_anchor_without_a_source_is_the_copy() -> None:
    entry = PresetListEntry("/proj/presets/foo.milk")
    assert preview_anchor(entry) == entry.file
