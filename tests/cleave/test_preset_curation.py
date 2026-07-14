"""Unit tests for preset favourites and blacklist file operations."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from cleave.preset_curation import (
    BLACKLIST_DIR,
    COLOCATED_TEXTURE_SUFFIXES,
    FAVOURITES_DIR,
    PresetCurationIndex,
    blacklist_root,
    copy_to_favourites,
    curated_milk_src,
    favourites_root,
    find_milk_under,
    list_destination_subdirs,
    move_to_blacklist,
    relocate_curated_milk,
    rewrite_user_preset_paths,
    scrub_user_preset_paths,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_favourites_and_blacklist_roots() -> None:
    preset_root = Path("/tmp/presets")
    assert favourites_root(preset_root) == preset_root / FAVOURITES_DIR
    assert blacklist_root(preset_root) == preset_root / BLACKLIST_DIR


def test_preset_curation_index_build_scans_recursively() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root / FAVOURITES_DIR / "top.milk", "fav-top")
        _write(root / FAVOURITES_DIR / "nested" / "deep.milk", "fav-deep")
        _write(root / BLACKLIST_DIR / "reject.milk", "bl-top")
        _write(root / BLACKLIST_DIR / "pack" / "inner.milk", "bl-inner")
        _write(root / "pack" / "ignored.milk", "not-curated")

        index = PresetCurationIndex.build(root)

        assert index.favourites == {"top.milk", "deep.milk"}
        assert index.blacklist == {"reject.milk", "inner.milk"}


def test_preset_curation_index_build_missing_trees() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        index = PresetCurationIndex.build(Path(tmp))
        assert index.favourites == set()
        assert index.blacklist == set()


def test_preset_curation_index_marker() -> None:
    index = PresetCurationIndex(
        favourites={"fav.milk", "both.milk"},
        blacklist={"bl.milk", "both.milk"},
    )
    assert index.marker("fav.milk") == " [F]"
    assert index.marker("bl.milk") == " [B]"
    assert index.marker("both.milk") == " [F][B]"
    assert index.marker("plain.milk") == ""


def test_preset_curation_index_mark_updates_sets() -> None:
    index = PresetCurationIndex(favourites=set(), blacklist=set())
    index.mark_favourite("a.milk")
    index.mark_blacklisted("b.milk")
    assert index.favourites == {"a.milk"}
    assert index.blacklist == {"b.milk"}
    assert index.marker("a.milk") == " [F]"
    assert index.marker("b.milk") == " [B]"


def test_list_destination_subdirs_sorted_and_excludes_dot_dirs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "beta").mkdir()
        (base / "alpha").mkdir()
        (base / ".hidden").mkdir()
        (base / "file.txt").write_text("x", encoding="utf-8")

        assert list_destination_subdirs(base) == ("alpha", "beta")


def test_list_destination_subdirs_missing_base() -> None:
    assert list_destination_subdirs(Path("/nonexistent/path")) == ()


def test_copy_to_favourites_skips_identical_milk() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src_dir = root / "pack"
        src_dir.mkdir()
        src_milk = src_dir / "preset.milk"
        _write(src_milk, "same-content")

        dest_dir = root / "favourites"
        dest_dir.mkdir()
        existing = dest_dir / "preset.milk"
        _write(existing, "same-content")

        result = copy_to_favourites(src_milk, dest_dir)

        assert result == existing.resolve()
        assert list(dest_dir.glob("*.milk")) == [existing]


def test_copy_to_favourites_suffix_on_different_content() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src_dir = root / "pack"
        src_dir.mkdir()
        src_milk = src_dir / "preset.milk"
        _write(src_milk, "new-content")

        dest_dir = root / "favourites"
        dest_dir.mkdir()
        _write(dest_dir / "preset.milk", "old-content")

        result = copy_to_favourites(src_milk, dest_dir)

        assert result == dest_dir / "preset_2.milk"
        assert result.read_text(encoding="utf-8") == "new-content"


def test_copy_to_favourites_copies_colocated_textures() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src_dir = root / "pack"
        src_dir.mkdir()
        src_milk = src_dir / "preset.milk"
        _write(src_milk, "milk")
        _write(src_dir / "cover.jpg", "jpg-bytes")
        _write(src_dir / "alpha.png", "png-bytes")
        _write(src_dir / "ignored.txt", "not-a-texture")

        dest_dir = root / "favourites" / "keepers"
        result = copy_to_favourites(src_milk, dest_dir)

        assert result == dest_dir / "preset.milk"
        assert (dest_dir / "cover.jpg").read_text(encoding="utf-8") == "jpg-bytes"
        assert (dest_dir / "alpha.png").read_text(encoding="utf-8") == "png-bytes"
        assert not (dest_dir / "ignored.txt").exists()
        assert src_milk.exists()
        assert (src_dir / "cover.jpg").exists()


def test_copy_to_favourites_texture_dedup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src_dir = root / "pack"
        src_dir.mkdir()
        src_milk = src_dir / "preset.milk"
        _write(src_milk, "milk")
        _write(src_dir / "tex.tga", "texture")

        dest_dir = root / "favourites"
        dest_dir.mkdir()
        _write(dest_dir / "tex.tga", "texture")

        copy_to_favourites(src_milk, dest_dir)

        assert list(dest_dir.glob("tex*.tga")) == [dest_dir / "tex.tga"]


def test_move_to_blacklist_moves_milk_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src_dir = root / "pack"
        src_dir.mkdir()
        src_milk = src_dir / "reject.milk"
        _write(src_milk, "milk")
        texture = src_dir / "local.jpg"
        _write(texture, "jpg")

        dest_dir = root / BLACKLIST_DIR
        result = move_to_blacklist(src_milk, dest_dir)

        assert result == dest_dir / "reject.milk"
        assert result.exists()
        assert not src_milk.exists()
        assert texture.exists()
        assert texture.read_text(encoding="utf-8") == "jpg"


def test_move_to_blacklist_uses_dedup_dest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src_dir = root / "pack"
        src_dir.mkdir()
        src_milk = src_dir / "reject.milk"
        _write(src_milk, "new")

        dest_dir = root / BLACKLIST_DIR
        dest_dir.mkdir()
        _write(dest_dir / "reject.milk", "old")

        result = move_to_blacklist(src_milk, dest_dir)

        assert result == dest_dir / "reject_2.milk"
        assert result.read_text(encoding="utf-8") == "new"


@dataclass
class _LayerStub:
    user_presets: list[str] = field(default_factory=list)


def test_relocate_curated_milk_moves_between_sibling_dirs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / FAVOURITES_DIR / "keepers" / "preset.milk"
        _write(src, "milk")
        dest = root / FAVOURITES_DIR / "archive"
        dest.mkdir(parents=True)

        result = relocate_curated_milk(src, dest)

        assert result == dest / "preset.milk"
        assert result.read_text(encoding="utf-8") == "milk"
        assert not src.exists()


def test_relocate_curated_milk_to_parent_root() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fav_root = root / FAVOURITES_DIR
        src = fav_root / "keepers" / "preset.milk"
        _write(src, "milk")

        result = relocate_curated_milk(src, fav_root)

        assert result == fav_root / "preset.milk"
        assert not src.exists()


def test_relocate_curated_milk_same_dir_is_noop() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        dest = root / FAVOURITES_DIR
        src = dest / "preset.milk"
        _write(src, "milk")

        result = relocate_curated_milk(src, dest)

        assert result == src.resolve()
        assert src.exists()


def test_relocate_curated_milk_with_textures() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src_dir = root / FAVOURITES_DIR / "keepers"
        src = src_dir / "preset.milk"
        _write(src, "milk")
        _write(src_dir / "tex.jpg", "jpg")
        dest = root / FAVOURITES_DIR / "archive"
        dest.mkdir(parents=True)

        relocate_curated_milk(src, dest, with_textures=True)

        assert (dest / "preset.milk").exists()
        assert (dest / "tex.jpg").read_text(encoding="utf-8") == "jpg"
        assert not (src_dir / "tex.jpg").exists()


def test_find_milk_under_and_curated_milk_src() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fav = root / FAVOURITES_DIR
        nested = fav / "keepers" / "preset.milk"
        _write(nested, "milk")
        pack = root / "pack" / "preset.milk"
        _write(pack, "other")

        assert find_milk_under(fav, "preset.milk") == nested
        assert curated_milk_src(fav, nested) == nested
        assert curated_milk_src(fav, pack) == nested


def test_rewrite_user_preset_paths_updates_matching_entries() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        old = root / "old.milk"
        new = root / "new.milk"
        kept = root / "kept.milk"
        _write(old, "old")
        _write(new, "new")
        _write(kept, "kept")

        layers = {
            "layer_1": _LayerStub(user_presets=[str(old), str(kept)]),
            "layer_2": _LayerStub(user_presets=[str(kept)]),
        }

        affected = rewrite_user_preset_paths(layers, old, new)

        assert affected == ["layer_1"]
        assert layers["layer_1"].user_presets == [str(new), str(kept)]
        assert layers["layer_2"].user_presets == [str(kept)]


def test_scrub_user_preset_paths_removes_matching_entries() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        removed = root / "removed.milk"
        kept = root / "kept.milk"
        other = root / "other.milk"
        _write(removed, "removed")
        _write(kept, "kept")
        _write(other, "other")

        layers = {
            "layer_1": _LayerStub(user_presets=[str(removed), str(kept)]),
            "layer_2": _LayerStub(user_presets=[str(other)]),
            "layer_3": _LayerStub(user_presets=[str(removed.resolve())]),
        }

        affected = scrub_user_preset_paths(layers, removed)

        assert affected == ["layer_1", "layer_3"]
        assert layers["layer_1"].user_presets == [str(kept)]
        assert layers["layer_2"].user_presets == [str(other)]
        assert layers["layer_3"].user_presets == []


def test_scrub_user_preset_paths_no_match() -> None:
    layers = {"layer_1": _LayerStub(user_presets=["/tmp/a.milk"])}
    assert scrub_user_preset_paths(layers, Path("/tmp/missing.milk")) == []


def test_colocated_texture_suffixes_cover_expected_types() -> None:
    assert COLOCATED_TEXTURE_SUFFIXES == (".jpg", ".png", ".tga", ".bmp", ".dds")
