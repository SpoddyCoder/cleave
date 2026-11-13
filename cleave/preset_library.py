"""Preset library: content-hash index and curation state in a SQLite database.

Curation (favourite, blacklist, cue role) is state keyed by a hash of each
preset's contents. Nothing under the preset tree is moved, copied, or deleted.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Literal, Protocol

from cleave.cue_roles import CUE_ROLE_MARKER_LETTER, CueRole

SCHEMA_VERSION = 1

PresetCollection = Literal["favourites", "bed", "pulse", "lead", "accent", "blacklisted"]

PRESET_COLLECTIONS: tuple[PresetCollection, ...] = (
    "favourites",
    "bed",
    "pulse",
    "lead",
    "accent",
    "blacklisted",
)

COLLECTION_LABEL: dict[PresetCollection, str] = {
    "favourites": "Favourites",
    "bed": "Role: bed",
    "pulse": "Role: pulse",
    "lead": "Role: lead",
    "accent": "Role: accent",
    "blacklisted": "Blacklisted",
}

ProgressCallback = Callable[[int, int], bool]

_SCHEMA = """
CREATE TABLE files (
    path TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    hash TEXT NOT NULL
);
CREATE INDEX files_hash ON files(hash);
CREATE TABLE favourites (hash TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE blacklist (hash TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE roles (
    hash TEXT PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('bed', 'pulse', 'lead', 'accent')),
    name TEXT NOT NULL
);
"""


class PresetLibraryError(RuntimeError):
    """The preset library database cannot be opened."""


class PresetCatalog(Protocol):
    """What preset browsing needs: blacklist filtering and virtual collections."""

    def collections(self) -> tuple[PresetCollection, ...]: ...

    def visible(self, paths: Iterable[Path]) -> tuple[Path, ...]: ...

    def collection_paths(self, collection: PresetCollection) -> tuple[Path, ...]: ...


class UnfilteredCatalog:
    """Catalog for headless callers (render, CI): no filter, no collections."""

    def collections(self) -> tuple[PresetCollection, ...]:
        return ()

    def visible(self, paths: Iterable[Path]) -> tuple[Path, ...]:
        return tuple(paths)

    def collection_paths(self, collection: PresetCollection) -> tuple[Path, ...]:
        del collection
        return ()


UNFILTERED_CATALOG = UnfilteredCatalog()


def preset_hash(path: Path) -> str:
    """Hash of a preset's bytes with CRLF normalised to LF."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.blake2b(data, digest_size=16).hexdigest()


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


class PresetLibrary:
    """Hash index of presets plus favourite / blacklist / role state."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._root: Path | None = None
        self._path_hash: dict[Path, str] = {}
        self._alias_hash: dict[Path, str] = {}
        self._favourites: set[str] = set()
        self._blacklist: set[str] = set()
        self._roles: dict[str, CueRole] = {}
        self.revision = 0
        self._load_curation()

    @classmethod
    def in_memory(cls) -> PresetLibrary:
        """Empty, unpersisted library (offline render and tests)."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(_SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return cls(conn)

    @classmethod
    def open(cls, db_path: Path) -> PresetLibrary:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            has_tables = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()[0]
            if has_tables:
                conn.close()
                raise PresetLibraryError(
                    f"preset library {db_path} has no schema version; delete it to rebuild"
                )
            conn.executescript(_SCHEMA)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.commit()
        elif version != SCHEMA_VERSION:
            conn.close()
            raise PresetLibraryError(
                f"preset library {db_path} has schema version {version}, "
                f"expected {SCHEMA_VERSION}; delete it to rebuild"
            )
        return cls(conn)

    def close(self) -> None:
        self._conn.close()

    @property
    def root(self) -> Path | None:
        return self._root

    def _load_curation(self) -> None:
        self._favourites = {
            row[0] for row in self._conn.execute("SELECT hash FROM favourites")
        }
        self._blacklist = {
            row[0] for row in self._conn.execute("SELECT hash FROM blacklist")
        }
        self._roles = {
            row[0]: row[1]
            for row in self._conn.execute("SELECT hash, role FROM roles")
        }

    def index(
        self,
        preset_root: Path,
        on_progress: ProgressCallback | None = None,
    ) -> bool:
        """Hash every ``*.milk`` under ``preset_root``; rehash only changed files.

        Returns False when ``on_progress`` asks to cancel (returns False).
        """
        root = preset_root.resolve()
        cached: dict[str, tuple[int, int, str]] = {
            row[0]: (row[1], row[2], row[3])
            for row in self._conn.execute("SELECT path, size, mtime_ns, hash FROM files")
        }
        found = sorted(p.resolve() for p in root.rglob("*.milk") if p.is_file())
        total = len(found)
        path_hash: dict[Path, str] = {}
        upserts: list[tuple[str, int, int, str]] = []
        for done, path in enumerate(found):
            if on_progress is not None and done % 50 == 0:
                if not on_progress(done, total):
                    return False
            key = str(path)
            try:
                stat = path.stat()
            except OSError:
                continue
            entry = cached.get(key)
            if entry is not None and entry[0] == stat.st_size and entry[1] == stat.st_mtime_ns:
                digest = entry[2]
            else:
                try:
                    digest = preset_hash(path)
                except OSError:
                    continue
                upserts.append((key, stat.st_size, stat.st_mtime_ns, digest))
            path_hash[path] = digest
        stale = [
            (key,)
            for key in cached
            if _is_under(Path(key), root) and Path(key) not in path_hash
        ]
        with self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO files (path, size, mtime_ns, hash) VALUES (?, ?, ?, ?)",
                upserts,
            )
            self._conn.executemany("DELETE FROM files WHERE path = ?", stale)
        if on_progress is not None:
            on_progress(total, total)
        self._root = root
        self._path_hash = path_hash
        self._alias_hash = {}
        self.revision += 1
        return True

    def hash_of(self, path: Path) -> str | None:
        """Content hash of ``path``; hashes and caches files outside the index."""
        digest = self._path_hash.get(path) or self._alias_hash.get(path)
        if digest is not None:
            return digest
        resolved = path.resolve()
        digest = self._path_hash.get(resolved)
        if digest is not None:
            self._alias_hash[path] = digest
            return digest
        try:
            stat = resolved.stat()
        except OSError:
            return None
        row = self._conn.execute(
            "SELECT size, mtime_ns, hash FROM files WHERE path = ?", (str(resolved),)
        ).fetchone()
        if row is not None and row[0] == stat.st_size and row[1] == stat.st_mtime_ns:
            digest = row[2]
        else:
            try:
                digest = preset_hash(resolved)
            except OSError:
                return None
            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO files (path, size, mtime_ns, hash) "
                    "VALUES (?, ?, ?, ?)",
                    (str(resolved), stat.st_size, stat.st_mtime_ns, digest),
                )
        self._alias_hash[path] = digest
        self._alias_hash[resolved] = digest
        return digest

    def is_favourite(self, path: Path) -> bool:
        return self.hash_of(path) in self._favourites

    def is_blacklisted(self, path: Path) -> bool:
        return self.hash_of(path) in self._blacklist

    def role_of(self, path: Path) -> CueRole | None:
        digest = self.hash_of(path)
        if digest is None:
            return None
        return self._roles.get(digest)

    def _set_flag(self, table: str, members: set[str], path: Path, on: bool) -> None:
        digest = self.hash_of(path)
        if digest is None:
            return
        with self._conn:
            if on:
                self._conn.execute(
                    f"INSERT OR REPLACE INTO {table} (hash, name) VALUES (?, ?)",
                    (digest, path.name),
                )
                members.add(digest)
            else:
                self._conn.execute(f"DELETE FROM {table} WHERE hash = ?", (digest,))
                members.discard(digest)
        self.revision += 1

    def set_favourite(self, path: Path, on: bool) -> None:
        self._set_flag("favourites", self._favourites, path, on)

    def set_blacklisted(self, path: Path, on: bool) -> None:
        self._set_flag("blacklist", self._blacklist, path, on)

    def set_role(self, path: Path, role: CueRole | None) -> None:
        digest = self.hash_of(path)
        if digest is None:
            return
        with self._conn:
            if role is None:
                self._conn.execute("DELETE FROM roles WHERE hash = ?", (digest,))
                self._roles.pop(digest, None)
            else:
                self._conn.execute(
                    "INSERT OR REPLACE INTO roles (hash, role, name) VALUES (?, ?, ?)",
                    (digest, role, path.name),
                )
                self._roles[digest] = role
        self.revision += 1

    def _in_collection(self, digest: str, collection: PresetCollection) -> bool:
        if collection == "favourites":
            return digest in self._favourites
        if collection == "blacklisted":
            return digest in self._blacklist
        return self._roles.get(digest) == collection

    def collections(self) -> tuple[PresetCollection, ...]:
        """Collections offered beside top-level preset folders."""
        return PRESET_COLLECTIONS

    def collection_paths(self, collection: PresetCollection) -> tuple[Path, ...]:
        """Indexed files in ``collection``, one path per hash, sorted by path."""
        seen: set[str] = set()
        out: list[Path] = []
        for path in sorted(self._path_hash):
            digest = self._path_hash[path]
            if digest in seen or not self._in_collection(digest, collection):
                continue
            if self._root is not None and not _is_under(path, self._root):
                continue
            if not path.is_file():
                continue
            seen.add(digest)
            out.append(path)
        return tuple(out)

    def visible(self, paths: Iterable[Path]) -> tuple[Path, ...]:
        """``paths`` without blacklisted presets."""
        if not self._blacklist:
            return tuple(paths)
        return tuple(p for p in paths if self.hash_of(p) not in self._blacklist)

    def marker(self, path: Path, *, user: bool = False) -> str:
        """Panel marker such as ``" [FU] [R:B]"``; empty when uncurated."""
        digest = self.hash_of(path)
        letters = ""
        if digest is not None and digest in self._favourites:
            letters += "F"
        if digest is not None and digest in self._blacklist:
            letters += "B"
        if user:
            letters += "U"
        parts: list[str] = []
        if letters:
            parts.append(f"[{letters}]")
        role = self._roles.get(digest) if digest is not None else None
        if role is not None:
            parts.append(f"[R:{CUE_ROLE_MARKER_LETTER[role]}]")
        if not parts:
            return ""
        return " " + " ".join(parts)
