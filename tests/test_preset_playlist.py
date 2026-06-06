"""Unit tests for preset playlist scanning and directory navigation."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from cleave.preset_playlist import (
    list_navigable_dirs,
    playlist_at_dir,
    preset_filename_display,
    scan_preset_playlist,
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
        assert playlist.step_sibling(-1) is True
        assert playlist.current_dir.resolve() == siblings[2].resolve()

        assert playlist.step_sibling(1) is True
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


def test_go_parent_ascends_and_clamps_at_root() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        parent = root / "parent"
        parent.mkdir()
        _write_milk(parent / "parent.milk")
        child = parent / "child"
        child.mkdir()
        _write_milk(child / "child.milk")

        playlist = playlist_at_dir(child)
        assert playlist.go_parent(root) is True
        assert playlist.current_dir.resolve() == parent.resolve()

        at_root = playlist_at_dir(root)
        _write_milk(root / "root.milk")
        at_root = scan_preset_playlist(root)
        assert at_root.go_parent(root) is False
        assert at_root.current_dir.resolve() == root.resolve()


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


def main() -> int:
    tests = [
        test_scan_file_anchor_non_recursive,
        test_scan_directory_anchor_non_recursive,
        test_list_navigable_dirs_filters_and_includes_subtree,
        test_step_sibling_wraps,
        test_enter_child_first_alphabetical_navigable,
        test_go_parent_ascends_and_clamps_at_root,
        test_empty_directory_display_and_config_path,
        test_container_directory_anchor_no_direct_presets,
    ]
    for test in tests:
        test()
        print(f"ok {test.__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
