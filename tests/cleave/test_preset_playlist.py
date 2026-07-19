"""Unit tests for preset playlist scanning and directory navigation."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from cleave.config import load_config
from cleave.config_schema import DEFAULT_LAYER_SLOTS
from cleave.preset_playlist import (
    directory_display,
    list_navigable_dirs,
    playlist_at_dir,
    preset_browse_floor,
    preset_filename_display,
    scan_all_layers,
    scan_preset_playlist,
    scan_single_layer,
)


def _write_milk(path: Path) -> None:
    path.write_text("milk")


def test_scan_file_anchor_non_recursive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "pack"
        preset_dir.mkdir()
        alpha = preset_dir / "alpha.milk"
        beta = preset_dir / "beta.milk"
        _write_milk(alpha)
        _write_milk(beta)
        nested_dir = preset_dir / "nested"
        nested_dir.mkdir()
        _write_milk(nested_dir / "deep.milk")

        playlist = scan_preset_playlist(beta)
        assert playlist.current_dir == preset_dir.resolve()
        assert playlist.paths == (alpha.resolve(), beta.resolve())
        assert playlist.index == 1
        assert playlist.current == beta.resolve()


def test_scan_directory_anchor_non_recursive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "direct"
        preset_dir.mkdir()
        first = preset_dir / "a.milk"
        second = preset_dir / "b.milk"
        _write_milk(first)
        _write_milk(second)
        sub = preset_dir / "sub"
        sub.mkdir()
        _write_milk(sub / "c.milk")

        playlist = scan_preset_playlist(preset_dir)
        assert playlist.current_dir == preset_dir.resolve()
        assert playlist.paths == (first.resolve(), second.resolve())
        assert playlist.index == 0
        assert playlist.current == first.resolve()


def test_list_navigable_dirs_filters_and_includes_subtree() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        direct = root / "direct-presets"
        direct.mkdir()
        _write_milk(direct / "one.milk")

        subtree = root / "subtree-only"
        subtree.mkdir()
        (subtree / "inner").mkdir()
        _write_milk(subtree / "inner" / "nested.milk")

        empty = root / "no-presets"
        empty.mkdir()

        hidden = root / ".hidden"
        hidden.mkdir()
        _write_milk(hidden / "secret.milk")

        siblings = list_navigable_dirs(root)
        assert siblings == (direct.resolve(), subtree.resolve())


def test_step_sibling_wraps() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        siblings: list[Path] = []
        for name in ("alpha", "beta", "gamma"):
            sibling = root / name
            sibling.mkdir()
            _write_milk(sibling / "preset.milk")
            siblings.append(sibling)

        playlist = playlist_at_dir(siblings[0])
        assert playlist.step_sibling(-1, preset_root=root) is True
        assert playlist.current_dir.resolve() == siblings[2].resolve()

        assert playlist.step_sibling(1, preset_root=root) is True
        assert playlist.current_dir.resolve() == siblings[0].resolve()


def test_enter_child_first_alphabetical_navigable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        parent = root / "parent"
        parent.mkdir()
        _write_milk(parent / "root.milk")

        child_b = parent / "child-b"
        child_b.mkdir()
        _write_milk(child_b / "b.milk")

        child_a = parent / "child-a"
        child_a.mkdir()
        _write_milk(child_a / "a.milk")

        playlist = playlist_at_dir(parent)
        assert playlist.enter_child(root) is True
        assert playlist.current_dir.resolve() == child_a.resolve()
        assert playlist.index == 0
        assert len(playlist.paths) == 1


def test_go_parent_ascends_and_clamps_at_preset_root() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack = root / "pack-a"
        pack.mkdir()
        _write_milk(pack / "pack.milk")
        child = pack / "child"
        child.mkdir()
        _write_milk(child / "child.milk")

        playlist = playlist_at_dir(child)
        assert playlist.go_parent(root) is True
        assert playlist.current_dir.resolve() == pack.resolve()

        assert playlist.go_parent(root) is True
        assert playlist.current_dir.resolve() == root.resolve()

        assert playlist.go_parent(root) is False
        assert playlist.current_dir.resolve() == root.resolve()


def test_go_parent_clamps_at_preset_root_when_browse_floor_is_root() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        parent = root / "parent"
        parent.mkdir()
        _write_milk(parent / "parent.milk")
        child = parent / "child"
        child.mkdir()
        _write_milk(child / "child.milk")

        playlist = playlist_at_dir(child)
        assert playlist.go_parent(root, browse_floor=root) is True
        assert playlist.current_dir.resolve() == parent.resolve()

        at_root = scan_preset_playlist(root)
        assert at_root.go_parent(root, browse_floor=root) is False
        assert at_root.current_dir.resolve() == root.resolve()


def test_go_parent_clamps_at_browse_floor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack = root / "pack-a"
        pack.mkdir()
        _write_milk(pack / "pack.milk")
        child = pack / "child"
        child.mkdir()
        _write_milk(child / "child.milk")

        playlist = playlist_at_dir(child)
        assert playlist.go_parent(root, browse_floor=pack) is True
        assert playlist.current_dir.resolve() == pack.resolve()

        assert playlist.go_parent(root, browse_floor=pack) is False
        assert playlist.current_dir.resolve() == pack.resolve()


def test_step_sibling_hops_top_level_packs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack_a = root / "pack-a"
        pack_b = root / "pack-b"
        pack_a.mkdir()
        pack_b.mkdir()
        _write_milk(pack_a / "a.milk")
        _write_milk(pack_b / "b.milk")

        playlist = playlist_at_dir(pack_a)
        assert directory_display(
            playlist, root, browse_floor=pack_a
        ) == "pack-a/ (1/2)"
        assert playlist.step_sibling(1, preset_root=root) is True
        assert playlist.current_dir.resolve() == pack_b.resolve()
        assert directory_display(
            playlist, root, browse_floor=pack_b
        ) == "pack-b/ (2/2)"


def test_go_parent_recovers_when_outside_browse_floor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack_a = root / "pack-a"
        pack_b = root / "pack-b"
        pack_a.mkdir()
        pack_b.mkdir()
        _write_milk(pack_a / "a.milk")
        _write_milk(pack_b / "b.milk")
        child = pack_b / "child"
        child.mkdir()
        _write_milk(child / "c.milk")

        playlist = playlist_at_dir(child)
        assert directory_display(
            playlist, root, browse_floor=pack_a
        ) == "[▲]pack-b/child/ (1/1)"
        assert playlist.go_parent(root, browse_floor=pack_a) is True
        assert playlist.current_dir.resolve() == pack_b.resolve()
        assert playlist.go_parent(root, browse_floor=pack_a) is False
        assert playlist.step_sibling(1, preset_root=root) is True
        assert playlist.current_dir.resolve() == pack_a.resolve()


def test_preset_browse_floor_uses_first_configured_path_segment() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack = root / "pack-a"
        pack.mkdir()
        inner = pack / "inner"
        inner.mkdir()
        preset = inner / "preset.milk"
        _write_milk(preset)

        assert preset_browse_floor(preset, root).resolve() == pack.resolve()
        assert preset_browse_floor(pack, root).resolve() == pack.resolve()
        assert preset_browse_floor(pack / "solo.milk", root).resolve() == pack.resolve()
        solo = root / "solo.milk"
        _write_milk(solo)
        assert preset_browse_floor(solo, root).resolve() == root.resolve()


def test_directory_display_clamps_sibling_parent_at_preset_root() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack_a = root / "pack-a"
        pack_b = root / "pack-b"
        pack_a.mkdir()
        pack_b.mkdir()
        _write_milk(pack_a / "a.milk")
        _write_milk(pack_b / "b.milk")

        playlist = scan_preset_playlist(root)
        label = directory_display(playlist, root)
        assert label == "[▼]./ (1/2)"


def test_directory_display_label_caches_on_repeated_calls() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack_a = root / "pack-a"
        pack_b = root / "pack-b"
        pack_a.mkdir()
        pack_b.mkdir()
        _write_milk(pack_a / "a.milk")
        _write_milk(pack_b / "b.milk")

        playlist = scan_preset_playlist(root)
        with patch(
            "cleave.preset_playlist.list_navigable_dirs", wraps=list_navigable_dirs
        ) as mock_list:
            first = playlist.directory_display_label(root)
            second = playlist.directory_display_label(root)
            assert first == second == "[▼]./ (1/2)"
            # Sibling listing plus child listing for the tree marker.
            assert mock_list.call_count == 2


def _playlist_with_siblings(root: Path) -> tuple:
    siblings: list[Path] = []
    for name in ("alpha", "beta", "gamma"):
        sibling = root / name
        sibling.mkdir()
        _write_milk(sibling / "preset.milk")
        siblings.append(sibling)
    playlist = playlist_at_dir(siblings[0])
    return playlist, siblings


def test_directory_display_label_invalidated_after_next() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "pack"
        preset_dir.mkdir()
        _write_milk(preset_dir / "a.milk")
        _write_milk(preset_dir / "b.milk")
        playlist = playlist_at_dir(preset_dir)
        playlist.directory_display_label(root)
        with patch(
            "cleave.preset_playlist.list_navigable_dirs", wraps=list_navigable_dirs
        ) as mock_list:
            playlist.next()
            playlist.directory_display_label(root)
            assert mock_list.call_count == 2


def test_directory_display_label_invalidated_after_prev() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "pack"
        preset_dir.mkdir()
        _write_milk(preset_dir / "a.milk")
        _write_milk(preset_dir / "b.milk")
        playlist = playlist_at_dir(preset_dir)
        playlist.directory_display_label(root)
        with patch(
            "cleave.preset_playlist.list_navigable_dirs", wraps=list_navigable_dirs
        ) as mock_list:
            playlist.prev()
            playlist.directory_display_label(root)
            assert mock_list.call_count == 2


def test_directory_display_label_invalidated_after_step_by() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "pack"
        preset_dir.mkdir()
        _write_milk(preset_dir / "a.milk")
        _write_milk(preset_dir / "b.milk")
        playlist = playlist_at_dir(preset_dir)
        playlist.directory_display_label(root)
        with patch(
            "cleave.preset_playlist.list_navigable_dirs", wraps=list_navigable_dirs
        ) as mock_list:
            playlist.step_by(1)
            playlist.directory_display_label(root)
            assert mock_list.call_count == 2


def test_directory_display_label_invalidated_after_step_sibling() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        playlist, siblings = _playlist_with_siblings(root)
        playlist.directory_display_label(root)
        with patch(
            "cleave.preset_playlist.list_navigable_dirs", wraps=list_navigable_dirs
        ) as mock_list:
            playlist.step_sibling(1, preset_root=root)
            label = playlist.directory_display_label(root)
            assert mock_list.call_count >= 1
            assert label == "[▲]beta/ (2/3)"


def test_directory_display_label_invalidated_after_enter_child() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        parent = root / "parent"
        parent.mkdir()
        _write_milk(parent / "root.milk")
        child_a = parent / "child-a"
        child_a.mkdir()
        _write_milk(child_a / "a.milk")
        playlist = playlist_at_dir(parent)
        playlist.directory_display_label(root)
        with patch(
            "cleave.preset_playlist.list_navigable_dirs", wraps=list_navigable_dirs
        ) as mock_list:
            playlist.enter_child(root)
            label = playlist.directory_display_label(root)
            assert mock_list.call_count >= 1
            assert label == "[▲]parent/child-a/ (1/1)"


def test_directory_display_label_invalidated_after_go_parent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack = root / "pack-a"
        pack.mkdir()
        _write_milk(pack / "pack.milk")
        child = pack / "child"
        child.mkdir()
        _write_milk(child / "child.milk")
        playlist = playlist_at_dir(child)
        playlist.directory_display_label(root)
        with patch(
            "cleave.preset_playlist.list_navigable_dirs", wraps=list_navigable_dirs
        ) as mock_list:
            playlist.go_parent(root)
            label = playlist.directory_display_label(root)
            assert mock_list.call_count >= 1
            assert label == "[▲▼]pack-a/ (1/1)"


def test_directory_display_label_tree_markers() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack = root / "pack"
        pack.mkdir()
        _write_milk(pack / "pack.milk")
        child = pack / "child"
        child.mkdir()
        _write_milk(child / "child.milk")

        at_root = scan_preset_playlist(root)
        assert directory_display(at_root, root, browse_floor=root) == "[▼]./ (1/1)"

        at_pack = playlist_at_dir(pack)
        assert directory_display(at_pack, root, browse_floor=root) == (
            "[▲▼]pack/ (1/1)"
        )
        assert directory_display(at_pack, root, browse_floor=pack) == (
            "[▼]pack/ (1/1)"
        )

        at_child = playlist_at_dir(child)
        assert directory_display(at_child, root, browse_floor=pack) == (
            "[▲]pack/child/ (1/1)"
        )


def test_empty_directory_display_and_config_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        empty = root / "empty"
        empty.mkdir()

        playlist = playlist_at_dir(empty)
        assert playlist.paths == ()
        assert playlist.current is None
        assert preset_filename_display(playlist) == "NO PRESETS FOUND"
        assert playlist.config_preset_path(root) == "empty/"


def test_container_directory_anchor_no_direct_presets() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        container = root / "container"
        container.mkdir()
        child = container / "child"
        child.mkdir()
        _write_milk(child / "nested.milk")

        playlist = scan_preset_playlist(container)
        assert playlist.current_dir == container.resolve()
        assert playlist.paths == ()
        assert playlist.index == 0
        assert playlist.current is None
        assert preset_filename_display(playlist) == "NO PRESETS FOUND"
        assert playlist.config_preset_path(root) == "container/"


def test_scan_all_layers_uses_slot_keys(minimal_project: Path) -> None:
    cfg = load_config(project_root=minimal_project)
    playlists = scan_all_layers(cfg)
    assert tuple(playlists.keys()) == DEFAULT_LAYER_SLOTS
    for slot in DEFAULT_LAYER_SLOTS:
        assert playlists[slot].current is not None
        assert len(playlists[slot].paths) >= 1


def test_scan_single_layer_picks_from_available_presets() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "pack"
        preset_dir.mkdir()
        milk_paths = []
        for name in ("alpha.milk", "beta.milk", "gamma.milk"):
            path = preset_dir / name
            _write_milk(path)
            milk_paths.append(path.resolve())

        playlist = scan_single_layer("layer_5", preset_dir, root)
        assert playlist.current in milk_paths


def test_scan_single_layer_empty_root_returns_empty_playlist() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        empty = root / "empty"
        empty.mkdir()

        playlist = scan_single_layer("layer_5", empty, root)
        assert playlist.current is None
        assert playlist.paths == ()


def test_remove_preset_adjusts_index_when_removed_before_current() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "pack"
        preset_dir.mkdir()
        alpha = preset_dir / "a.milk"
        beta = preset_dir / "b.milk"
        gamma = preset_dir / "c.milk"
        _write_milk(alpha)
        _write_milk(beta)
        _write_milk(gamma)

        playlist = playlist_at_dir(preset_dir, index=2)
        assert playlist.remove_preset(alpha) is True
        assert playlist.paths == (beta.resolve(), gamma.resolve())
        assert playlist.index == 1
        assert playlist.current == gamma.resolve()


def test_remove_preset_at_current_index() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "pack"
        preset_dir.mkdir()
        alpha = preset_dir / "a.milk"
        beta = preset_dir / "b.milk"
        _write_milk(alpha)
        _write_milk(beta)

        playlist = playlist_at_dir(preset_dir, index=1)
        assert playlist.remove_preset(beta) is True
        assert playlist.paths == (alpha.resolve(),)
        assert playlist.index == 0
        assert playlist.current == alpha.resolve()


def test_remove_preset_empty_list_sets_index_zero() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "pack"
        preset_dir.mkdir()
        only = preset_dir / "only.milk"
        _write_milk(only)

        playlist = playlist_at_dir(preset_dir, index=0)
        assert playlist.remove_preset(only) is True
        assert playlist.paths == ()
        assert playlist.index == 0
        assert playlist.current is None


def test_remove_preset_missing_returns_false() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "pack"
        preset_dir.mkdir()
        alpha = preset_dir / "a.milk"
        _write_milk(alpha)

        playlist = playlist_at_dir(preset_dir, index=0)
        missing = preset_dir / "missing.milk"
        assert playlist.remove_preset(missing) is False
        assert playlist.paths == (alpha.resolve(),)
        assert playlist.index == 0


def test_remove_preset_invalidates_dir_display_cache() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack_a = root / "pack-a"
        pack_b = root / "pack-b"
        pack_a.mkdir()
        pack_b.mkdir()
        alpha = pack_a / "a.milk"
        beta = pack_a / "b.milk"
        _write_milk(alpha)
        _write_milk(beta)
        _write_milk(pack_b / "b.milk")

        playlist = playlist_at_dir(pack_a, index=0)
        playlist.directory_display_label(root)
        with patch(
            "cleave.preset_playlist.list_navigable_dirs", wraps=list_navigable_dirs
        ) as mock_list:
            playlist.remove_preset(alpha)
            playlist.directory_display_label(root)
            # Sibling listing plus child listing for the tree marker.
            assert mock_list.call_count == 2
