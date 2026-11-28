"""Tests for preset curation backup and restore (JSON keyed by content hash)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from cleave.preset_curation import (
    FORMAT,
    Curation,
    CurationBackupError,
    back_up_library,
    backup_filename,
    preview_restore,
    read_backup,
    restore_into,
    write_backup,
)
from cleave.preset_library import CurationEntry, PresetLibrary, preset_hash

_NOW = datetime(2026, 11, 28, 14, 5, 12)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _library(tmp_path: Path) -> tuple[PresetLibrary, Path, Path, Path]:
    root = tmp_path / "presets"
    a = _write(root / "pack" / "a.milk", "a")
    b = _write(root / "pack" / "b.milk", "b")
    c = _write(root / "pack" / "c.milk", "c")
    library = PresetLibrary.in_memory()
    library.index(root)
    return library, a, b, c


def test_backup_round_trip_keeps_every_kind(tmp_path: Path) -> None:
    library, a, b, c = _library(tmp_path)
    library.set_favourite(a, True)
    library.set_role(a, "lead")
    library.set_blacklisted(b, True)
    library.set_role(c, "bed")

    path, counts = back_up_library(library, tmp_path / "backups", now=_NOW)

    assert path.name == backup_filename(_NOW) == "cleave-curation-2026-11-28-140512.json"
    assert counts.summary() == "3 presets: 1 favourite, 2 roles, 1 blacklisted"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["format"] == FORMAT
    assert all("path" not in entry for entry in payload["presets"])
    assert set(read_backup(path).entries) == set(library.curation_entries())


def test_fresh_library_restores_before_presets_exist(tmp_path: Path) -> None:
    library, a, _, _ = _library(tmp_path)
    library.set_role(a, "pulse")
    path, _ = back_up_library(library, tmp_path / "backups", now=_NOW)

    fresh = PresetLibrary.in_memory()
    entries = read_backup(path)
    assert preview_restore(fresh, entries).installed == 0
    assert restore_into(fresh, entries, replace=False, safety_dir=tmp_path / "s") is None

    fresh_root = tmp_path / "fresh"
    copy = _write(fresh_root / "renamed.milk", "a")
    fresh.index(fresh_root)
    assert fresh.role_of(copy) == "pulse"
    assert fresh.collection_paths("pulse") == (copy.resolve(),)
    assert fresh.marker(copy) == " [R:P]"


def test_merge_adds_flags_and_backup_role_wins(tmp_path: Path) -> None:
    library, a, b, c = _library(tmp_path)
    library.set_favourite(a, True)
    library.set_role(b, "bed")
    library.set_role(c, "accent")
    entries = Curation(
        (
            CurationEntry(hash=preset_hash(b), name="b.milk", role="lead"),
            CurationEntry(
                hash=preset_hash(c), name="c.milk", role="accent", blacklisted=True
            ),
        )
    )

    preview = preview_restore(library, entries)
    assert preview.role_changes == 1
    assert preview.installed == 2
    safety = restore_into(library, entries, replace=False, safety_dir=tmp_path / "s", now=_NOW)

    assert library.is_favourite(a)
    assert library.role_of(b) == "lead"
    assert library.is_blacklisted(c) and library.role_of(c) == "accent"
    assert safety is not None
    saved = {entry.hash: entry for entry in read_backup(safety).entries}
    assert saved[preset_hash(b)].role == "bed"
    assert saved[preset_hash(a)].favourite


def test_replace_clears_current_curation(tmp_path: Path) -> None:
    library, a, b, _ = _library(tmp_path)
    library.set_favourite(a, True)
    library.set_blacklisted(a, True)
    entries = Curation((CurationEntry(hash=preset_hash(b), name="b.milk", favourite=True),))

    restore_into(library, entries, replace=True, safety_dir=tmp_path / "s")

    assert not library.is_favourite(a)
    assert not library.is_blacklisted(a)
    assert library.is_favourite(b)
    assert library.collection_paths("favourites") == (b.resolve(),)


def test_backup_never_overwrites(tmp_path: Path) -> None:
    entry = Curation((CurationEntry(hash="0" * 32, name="x.milk", favourite=True),))
    first = write_backup(entry, tmp_path, now=_NOW)
    second = write_backup(entry, tmp_path, now=_NOW)
    assert first != second and second.exists()
    with pytest.raises(CurationBackupError, match="already exists"):
        write_backup(entry, first)


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ("not json", "not a preset curation backup"),
        (json.dumps({"format": "other", "version": 1, "presets": []}), "not a preset"),
        (json.dumps({"format": FORMAT, "version": 99, "presets": []}), "newer Cleave"),
        (json.dumps({"format": FORMAT, "version": 1, "presets": [{"hash": "zz"}]}), "valid hash"),
        (
            json.dumps(
                {"format": FORMAT, "version": 1, "presets": [{"hash": "a" * 32, "role": "solo"}]}
            ),
            "unknown role",
        ),
        (
            json.dumps(
                {
                    "format": FORMAT,
                    "version": 2,
                    "presets": [{"hash": "a" * 32, "tags": ["a-tier"]}],
                }
            ),
            "tags but is not a favourite",
        ),
        (
            json.dumps(
                {
                    "format": FORMAT,
                    "version": 2,
                    "presets": [{"hash": "a" * 32, "favourite": True, "tags": ["x/y"]}],
                }
            ),
            "bad tag",
        ),
    ],
)
def test_read_rejects_bad_files(tmp_path: Path, payload: str, match: str) -> None:
    path = _write(tmp_path / "bad.json", payload)
    with pytest.raises(CurationBackupError, match=match):
        read_backup(path)


def test_backup_round_trip_keeps_tags(tmp_path: Path) -> None:
    library, a, b, _ = _library(tmp_path)
    library.add_tag("a-tier")
    library.add_tag("unused")
    library.set_tagged(a, "a-tier", True)
    library.set_favourite(b, True)

    path, counts = back_up_library(library, tmp_path / "backups", now=_NOW)

    assert counts.summary() == "2 presets: 2 favourites, 0 roles, 0 blacklisted, 2 tags"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 2
    assert payload["tags"] == ["a-tier", "unused"]
    curation = read_backup(path)
    assert curation.tags == ("a-tier", "unused")

    fresh = PresetLibrary.in_memory()
    fresh.index(tmp_path / "presets")
    restore_into(fresh, curation, replace=False, safety_dir=tmp_path / "s")
    assert fresh.tags() == ("a-tier", "unused")
    assert fresh.tags_of(a) == ("a-tier",)
    assert fresh.is_favourite(b) and fresh.tags_of(b) == ()


def test_version_1_backup_restores_without_tags(tmp_path: Path) -> None:
    library, a, _, _ = _library(tmp_path)
    path = _write(
        tmp_path / "old.json",
        json.dumps(
            {
                "format": FORMAT,
                "version": 1,
                "presets": [{"hash": preset_hash(a), "name": "a.milk", "favourite": True}],
            }
        ),
    )
    curation = read_backup(path)
    assert curation.tags == ()
    restore_into(library, curation, replace=False, safety_dir=tmp_path / "s")
    assert library.is_favourite(a)


def test_preset_tags_join_the_tag_list(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "tags.json",
        json.dumps(
            {
                "format": FORMAT,
                "version": 2,
                "tags": ["B-tier"],
                "presets": [
                    {"hash": "a" * 32, "favourite": True, "tags": [" a-tier ", "b-TIER"]}
                ],
            }
        ),
    )
    curation = read_backup(path)
    assert curation.tags == ("a-tier", "B-tier")
    assert curation.entries[0].tags == ("a-tier", "b-TIER")
