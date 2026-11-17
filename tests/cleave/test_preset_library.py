"""Tests for the SQLite preset library (content hashes and curation state)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from cleave import preset_library
from cleave.preset_library import (
    PresetLibrary,
    PresetLibraryError,
    marker_tooltip,
    preset_hash,
)
from cleave.preset_playlist import playlist_at_collection, playlist_at_dir


def _write(path: Path, content: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def test_hash_ignores_line_endings(tmp_path: Path) -> None:
    lf = _write(tmp_path / "lf.milk", b"a=1\nb=2\n")
    crlf = _write(tmp_path / "crlf.milk", b"a=1\r\nb=2\r\n")
    assert preset_hash(lf) == preset_hash(crlf)


def test_reindex_rehashes_only_changed_files(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "presets"
    a = _write(root / "pack" / "a.milk", "a")
    b = _write(root / "pack" / "b.milk", "b")
    db = tmp_path / "cleave.db"
    calls: list[Path] = []
    real = preset_library.preset_hash

    def counting(path: Path) -> str:
        calls.append(path)
        return real(path)

    monkeypatch.setattr(preset_library, "preset_hash", counting)
    library = PresetLibrary.open(db)
    library.index(root)
    assert len(calls) == 2
    library.close()

    calls.clear()
    _write(b, "b changed")
    os.utime(b, ns=(b.stat().st_atime_ns, b.stat().st_mtime_ns + 1_000_000))
    a.unlink()
    library = PresetLibrary.open(db)
    library.index(root)
    assert calls == [b.resolve()]
    conn = sqlite3.connect(db)
    paths = [row[0] for row in conn.execute("SELECT path FROM files")]
    conn.close()
    assert paths == [str(b.resolve())]


def test_flags_persist_and_follow_a_moved_preset(tmp_path: Path) -> None:
    root = tmp_path / "presets"
    src = _write(root / "pack" / "demo.milk", "demo")
    db = tmp_path / "cleave.db"
    library = PresetLibrary.open(db)
    library.index(root)
    library.set_favourite(src, True)
    library.set_role(src, "pulse")
    library.close()

    moved = root / "other" / "renamed.milk"
    moved.parent.mkdir()
    src.rename(moved)
    library = PresetLibrary.open(db)
    library.index(root)
    assert library.is_favourite(moved)
    assert library.role_of(moved) == "pulse"
    assert library.collection_paths("favourites") == (moved.resolve(),)
    assert library.marker(moved) == " [F] [R:P]"


def test_collection_dedupes_by_hash_and_stays_under_root(tmp_path: Path) -> None:
    root = tmp_path / "presets"
    first = _write(root / "a" / "same.milk", "same")
    _write(root / "b" / "same.milk", "same")
    outside = _write(tmp_path / "project" / "user_presets" / "same.milk", "same")
    library = PresetLibrary.in_memory()
    library.index(root)
    library.set_favourite(outside, True)

    assert library.collection_paths("favourites") == (first.resolve(),)
    assert library.marker(outside, in_preset_list=True) == " [F] [L]"


def test_visible_drops_blacklisted(tmp_path: Path) -> None:
    root = tmp_path / "presets"
    keep = _write(root / "pack" / "keep.milk", "keep")
    hide = _write(root / "pack" / "hide.milk", "hide")
    library = PresetLibrary.in_memory()
    library.index(root)
    library.set_blacklisted(hide, True)

    assert library.visible([keep.resolve(), hide.resolve()]) == (keep.resolve(),)
    assert playlist_at_dir(root / "pack", catalog=library).paths == (keep.resolve(),)
    assert library.collection_paths("blacklisted") == (hide.resolve(),)
    assert library.marker(hide) == " [B]"


def test_schema_version_mismatch_raises(tmp_path: Path) -> None:
    db = tmp_path / "cleave.db"
    PresetLibrary.open(db).close()
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA user_version = 99")
    conn.commit()
    conn.close()
    with pytest.raises(PresetLibraryError):
        PresetLibrary.open(db)


def test_index_cancel_returns_false(tmp_path: Path) -> None:
    _write(tmp_path / "presets" / "a.milk", "a")
    library = PresetLibrary.in_memory()
    assert library.index(tmp_path / "presets", lambda done, total: False) is False


def test_top_level_browse_steps_through_collections(tmp_path: Path) -> None:
    root = tmp_path / "presets"
    fav = _write(root / "alpha" / "fav.milk", "fav")
    _write(root / "beta" / "b.milk", "b")
    library = PresetLibrary.in_memory()
    library.index(root)
    library.set_favourite(fav, True)
    playlist = playlist_at_dir(root / "alpha", catalog=library)

    display = playlist.directory_display(root)
    assert (display.path, display.position) == ("alpha/", "7/8")

    assert playlist.step_sibling(-1, preset_root=root)
    assert playlist.collection == "blacklisted"
    assert playlist.paths == ()
    assert playlist.config_preset_path(root) == "alpha/"

    for _ in range(5):
        playlist.step_sibling(-1, preset_root=root)
    assert playlist.collection == "favourites"
    assert playlist.current == fav.resolve()
    display = playlist.directory_display(root)
    assert (display.path, display.position) == ("Favourites", "1/8")
    assert (display.can_go_up, display.can_go_down) == (False, False)
    assert not playlist.go_parent(root)
    assert not playlist.enter_child(root)
    assert playlist.config_preset_path(root) == "alpha/fav.milk"

    assert playlist.step_sibling(-1, preset_root=root)
    assert playlist.collection is None
    assert playlist.current_dir == (root / "beta").resolve()


def test_collection_playlist_from_unfiltered_catalog_is_empty(tmp_path: Path) -> None:
    playlist = playlist_at_collection(
        "favourites", current_dir=tmp_path, catalog=PresetLibrary.in_memory()
    )
    assert playlist.paths == ()


def test_enter_collection_jumps_from_a_nested_folder(tmp_path: Path) -> None:
    root = tmp_path / "presets"
    fav = _write(root / "alpha" / "deep" / "fav.milk", "fav")
    library = PresetLibrary.in_memory()
    library.index(root)
    library.set_favourite(fav, True)
    playlist = playlist_at_dir(root / "alpha" / "deep", catalog=library)

    assert playlist.enter_collection("favourites")
    assert playlist.collection == "favourites"
    assert playlist.current == fav.resolve()
    assert playlist.current_dir == (root / "alpha" / "deep").resolve()
    assert not playlist.enter_collection("favourites")

    assert playlist.enter_collection("bed")
    assert playlist.collection == "bed"
    assert playlist.paths == ()


def test_marker_tooltip_names_flags_and_roles() -> None:
    assert marker_tooltip("[F]") == "Favourite"
    assert marker_tooltip("[B]") == "Blacklisted"
    assert marker_tooltip("[L]") == "In the preset list"
    assert marker_tooltip("[FB]") is None
    assert marker_tooltip("[R:B]") == "Role: bed (calm, dark background)"
    assert marker_tooltip("[R:Z]") is None
    assert marker_tooltip("[X]") is None
    assert marker_tooltip("F") is None


def test_scan_follows_symlinked_folders_once_under_real_paths(tmp_path: Path) -> None:
    root = tmp_path / "presets"
    real = _write(tmp_path / "elsewhere" / "pack" / "a.milk", "a")
    _write(root / "local" / "b.milk", "b")
    _write(root / "local" / "notes.txt", "x")
    (root / "linked").symlink_to(tmp_path / "elsewhere" / "pack", target_is_directory=True)
    (root / "local" / "loop").symlink_to(root, target_is_directory=True)

    found = sorted(path for path, _, _ in preset_library.scan_milk_files(root))

    assert found == sorted([str(real.resolve()), str((root / "local" / "b.milk").resolve())])


def test_favourite_through_symlinked_folder_matches_index(tmp_path: Path) -> None:
    root = tmp_path / "presets"
    _write(tmp_path / "elsewhere" / "a.milk", "a")
    (root).mkdir()
    (root / "linked").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    library = PresetLibrary.in_memory()
    library.index(root)

    library.set_favourite(root / "linked" / "a.milk", True)

    assert library.is_favourite((tmp_path / "elsewhere" / "a.milk").resolve())


def _bump_mtime(path: Path) -> None:
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))


def test_load_index_reuses_stored_index_without_hashing(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "presets"
    fav = _write(root / "pack" / "fav.milk", "fav")
    db = tmp_path / "cleave.db"
    library = PresetLibrary.open(db)
    library.index(root)
    library.set_favourite(fav, True)
    library.close()

    monkeypatch.setattr(preset_library, "scan_milk_files", None)
    monkeypatch.setattr(preset_library, "preset_hash", None)
    library = PresetLibrary.open(db)

    assert library.load_index(root)
    assert library.root == root.resolve()
    assert library.collection_paths("favourites") == (fav.resolve(),)
    library.close()


def test_load_index_refuses_when_a_pack_is_added_or_removed(tmp_path: Path) -> None:
    root = tmp_path / "presets"
    _write(root / "pack" / "a.milk", "a")
    library = PresetLibrary.in_memory()
    library.index(root)
    revision = library.revision

    _write(root / "new pack" / "b.milk", "b")
    _bump_mtime(root)
    assert not library.load_index(root)
    assert library.revision == revision

    library.index(root)
    assert library.load_index(root)


def test_load_index_refuses_when_a_top_level_folder_changes(tmp_path: Path) -> None:
    root = tmp_path / "presets"
    _write(root / "pack" / "a.milk", "a")
    library = PresetLibrary.in_memory()
    library.index(root)

    _write(root / "pack" / "b.milk", "b")
    _bump_mtime(root / "pack")

    assert not library.load_index(root)


def test_load_index_refuses_a_root_never_indexed(tmp_path: Path) -> None:
    _write(tmp_path / "one" / "a.milk", "a")
    _write(tmp_path / "two" / "b.milk", "b")
    library = PresetLibrary.in_memory()
    library.index(tmp_path / "one")

    assert not library.load_index(tmp_path / "two")
    assert library.load_index(tmp_path / "one")


def test_cancelled_index_leaves_no_fingerprint(tmp_path: Path) -> None:
    root = tmp_path / "presets"
    _write(root / "a.milk", "a")
    library = PresetLibrary.in_memory()

    assert library.index(root, lambda done, total: False) is False
    assert not library.load_index(root)


def test_open_upgrades_version_1_and_keeps_curation(tmp_path: Path) -> None:
    db = tmp_path / "cleave.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE files (path TEXT PRIMARY KEY, size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL, hash TEXT NOT NULL);
        CREATE INDEX files_hash ON files(hash);
        CREATE TABLE favourites (hash TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE blacklist (hash TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE roles (hash TEXT PRIMARY KEY, role TEXT NOT NULL
            CHECK (role IN ('bed', 'pulse', 'lead', 'accent')), name TEXT NOT NULL);
        PRAGMA user_version = 1;
        """
    )
    fav = _write(tmp_path / "presets" / "fav.milk", "fav")
    conn.execute(
        "INSERT INTO favourites (hash, name) VALUES (?, ?)", (preset_hash(fav), "fav.milk")
    )
    conn.commit()
    conn.close()

    library = PresetLibrary.open(db)
    assert library.is_favourite(fav)
    assert not library.load_index(tmp_path / "presets")
    library.index(tmp_path / "presets")
    assert library.load_index(tmp_path / "presets")
    library.close()

    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == preset_library.SCHEMA_VERSION
    conn.close()
