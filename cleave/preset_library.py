"""Preset library: content-hash index and curation state in a SQLite database.

Curation (favourite, favourite tags, blacklist, cue role) is state keyed by a
hash of each preset's contents. Nothing under the preset tree is moved, copied, or deleted.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import sqlite3
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from cleave.cue_roles import (
    CUE_ROLE_HELP_BLURB,
    CUE_ROLE_MARKER_LETTER,
    CUE_ROLES,
    CueRole,
)

SCHEMA_VERSION = 3

BuiltinCollection = Literal[
    "favourites", "all_favourites", "bed", "pulse", "lead", "accent", "blacklisted"
]
"""``favourites`` is the Favourites folder: it holds ``all_favourites`` and one
collection per tag, and no presets of its own."""


@dataclass(frozen=True)
class FavouriteTag:
    """The favourites carrying one tag, browsed as a folder inside Favourites."""

    name: str


PresetCollection = BuiltinCollection | FavouriteTag

PRESET_COLLECTIONS: tuple[BuiltinCollection, ...] = (  # the top level
    "favourites",
    "bed",
    "pulse",
    "lead",
    "accent",
    "blacklisted",
)

_BUILTIN_LABEL: dict[BuiltinCollection, str] = {
    "favourites": "Favourites",
    "all_favourites": "All favourites",
    "bed": "Role: bed",
    "pulse": "Role: pulse",
    "lead": "Role: lead",
    "accent": "Role: accent",
    "blacklisted": "Blacklisted",
}

TAG_NAME_MAX = 40


def in_favourites(collection: PresetCollection | None) -> bool:
    """True for a collection inside the Favourites folder: All favourites or a tag."""
    return collection == "all_favourites" or isinstance(collection, FavouriteTag)


def collection_label(collection: PresetCollection, *, full: bool = False) -> str:
    """Display name: ``Favourites``, ``All favourites``, ``Role: bed``, or a tag's name.

    *full* names a collection inside Favourites with its parent, such as
    ``Favourites / a-tier``, for places that show it away from that folder.
    """
    name = (
        collection.name
        if isinstance(collection, FavouriteTag)
        else _BUILTIN_LABEL[collection]
    )
    if full and in_favourites(collection):
        return f"{_BUILTIN_LABEL['favourites']} / {name}"
    return name


def collection_key(collection: PresetCollection | None) -> str | None:
    """Plain-text identity for signatures and keys: ``favourites`` or ``tag:a-tier``."""
    if isinstance(collection, FavouriteTag):
        return f"tag:{collection.name}"
    return collection


def clean_tag_name(text: str) -> str:
    """*text* trimmed, or :class:`ValueError` naming what is wrong with it."""
    name = " ".join(text.split())
    if not name:
        raise ValueError("Enter a name for the tag")
    if len(name) > TAG_NAME_MAX:
        raise ValueError(f"Use at most {TAG_NAME_MAX} characters")
    if "/" in name or "\\" in name:
        raise ValueError("A tag name cannot contain / or \\")
    return name

ProgressCallback = Callable[[int, int], bool]

PRESET_FLAG_MARKERS: tuple[tuple[str, str], ...] = (
    ("[F]", "Favourite"),
    ("[B]", "Blacklisted"),
    ("[L]", "In the preset list"),
)

_MARKER_MEANING: dict[str, str] = dict(PRESET_FLAG_MARKERS)


def marker_tooltip(token: str, *, tags: tuple[str, ...] = ()) -> str | None:
    """Hover text for one marker token from ``PresetLibrary.marker``.

    ``"[F]"``, ``"[B]"``, and ``"[L]"`` name their flag, and ``"[F]"`` lists
    the preset's *tags*; ``"[R:B]"`` names the role. Unknown tokens give None.
    """
    meaning = _MARKER_MEANING.get(token)
    if meaning is not None:
        if token == "[F]" and tags:
            return f"{meaning}. Tags: {', '.join(tags)}"
        return meaning
    for role in CUE_ROLES:
        if token == f"[R:{CUE_ROLE_MARKER_LETTER[role]}]":
            return f"Role: {role} ({CUE_ROLE_HELP_BLURB[role]})"
    return None


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
CREATE TABLE index_state (root TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
CREATE TABLE tags (name TEXT PRIMARY KEY COLLATE NOCASE);
CREATE TABLE favourite_tags (
    hash TEXT NOT NULL,
    tag TEXT NOT NULL COLLATE NOCASE,
    PRIMARY KEY (hash, tag)
);
"""

_UPGRADES: dict[int, str] = {
    1: "CREATE TABLE index_state (root TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);",
    2: (
        "CREATE TABLE tags (name TEXT PRIMARY KEY COLLATE NOCASE); "
        "CREATE TABLE favourite_tags (hash TEXT NOT NULL, "
        "tag TEXT NOT NULL COLLATE NOCASE, PRIMARY KEY (hash, tag));"
    ),
}
"""Script that takes a database from the keyed version to the next one."""


class PresetLibraryError(RuntimeError):
    """The preset library database cannot be opened."""


@dataclass(frozen=True)
class CurationEntry:
    """Curation of one preset, keyed by :func:`preset_hash`.

    ``name`` is the file name the preset had when it was curated; matching
    uses ``hash`` only.
    """

    hash: str
    name: str
    favourite: bool = False
    blacklisted: bool = False
    role: CueRole | None = None
    tags: tuple[str, ...] = ()
    """Tag names; only a favourite carries tags."""


class PresetCatalog(Protocol):
    """What preset browsing needs: blacklist filtering and virtual collections."""

    def collections(self) -> tuple[PresetCollection, ...]: ...

    def favourite_collections(self) -> tuple[PresetCollection, ...]: ...

    def visible(self, paths: Iterable[Path]) -> tuple[Path, ...]: ...

    def collection_paths(self, collection: PresetCollection) -> tuple[Path, ...]: ...

    def indexed_paths(self) -> tuple[Path, ...]: ...

    def preset_counts_by_dir(self) -> dict[Path, int]: ...


class UnfilteredCatalog:
    """Catalog for headless callers (render, CI): no filter, no collections."""

    def collections(self) -> tuple[PresetCollection, ...]:
        return ()

    def favourite_collections(self) -> tuple[PresetCollection, ...]:
        return ()

    def visible(self, paths: Iterable[Path]) -> tuple[Path, ...]:
        return tuple(paths)

    def collection_paths(self, collection: PresetCollection) -> tuple[Path, ...]:
        del collection
        return ()

    def indexed_paths(self) -> tuple[Path, ...]:
        return ()

    def preset_counts_by_dir(self) -> dict[Path, int]:
        return {}


UNFILTERED_CATALOG = UnfilteredCatalog()


def preset_hash(path: Path) -> str:
    """Hash of a preset's bytes with CRLF normalised to LF."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.blake2b(data, digest_size=16).hexdigest()


def _is_milk(name: str) -> bool:
    """``*.milk`` match with the platform's case rule, as ``Path.glob`` uses."""
    return os.path.normcase(name).endswith(".milk")


def scan_milk_files(root: Path) -> list[tuple[str, int, int]]:
    """``(resolved path, size, mtime_ns)`` for every ``*.milk`` under ``root``.

    One ``os.scandir`` pass: directory entries carry the stat on Windows, and
    nothing is resolved except symlinks, so a 100k-file tree walks in well
    under a second. Symlinked directories are followed once each (like
    ``Path.rglob``) and reported under their real path, as ``Path.resolve``
    would.
    """
    out: list[tuple[str, int, int]] = []
    top = os.path.realpath(root)
    seen_dirs = {top}
    stack = [top]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir():
                    real = (
                        os.path.realpath(entry.path) if entry.is_symlink() else entry.path
                    )
                    if real not in seen_dirs:
                        seen_dirs.add(real)
                        stack.append(real)
                    continue
                if not _is_milk(entry.name) or not entry.is_file():
                    continue
                if entry.is_symlink():
                    path = os.path.realpath(entry.path)
                    stat = os.stat(path)
                else:
                    path = entry.path
                    stat = entry.stat()
            except OSError:
                continue
            out.append((path, stat.st_size, stat.st_mtime_ns))
    return out


@dataclass(frozen=True)
class PresetIndex:
    """Result of :func:`build_index`: the indexed root and each file's hash."""

    root: Path
    path_hash: dict[str, str]


def index_fingerprint(root: Path) -> str:
    """Cheap signature of ``root``'s top level: the root and each folder's mtime.

    Adding, removing, or renaming a preset pack (or a file directly in the
    root) changes it. Changes deeper inside a pack do not; Settings > Rescan
    presets picks those up.
    """
    try:
        entries = [(".", os.stat(root).st_mtime_ns)]
        with os.scandir(root) as it:
            for entry in it:
                if entry.is_dir():
                    entries.append((entry.name, entry.stat().st_mtime_ns))
    except OSError:
        return "missing"
    return json.dumps(sorted(entries))


def build_index(
    conn: sqlite3.Connection,
    preset_root: Path,
    on_progress: ProgressCallback | None = None,
) -> PresetIndex | None:
    """Hash every ``*.milk`` under ``preset_root``; rehash only changed files.

    Reads and updates the ``files`` table on *conn*, which may belong to a
    worker thread. Returns None when ``on_progress`` asks to cancel (returns
    False); the table is then untouched.
    """
    root = preset_root.resolve()
    fingerprint = index_fingerprint(root)
    cached: dict[str, tuple[int, int, str]] = {
        row[0]: (row[1], row[2], row[3])
        for row in conn.execute("SELECT path, size, mtime_ns, hash FROM files")
    }
    found = scan_milk_files(root)
    total = len(found)
    path_hash: dict[str, str] = {}
    upserts: list[tuple[str, int, int, str]] = []
    for done, (key, size, mtime_ns) in enumerate(found):
        if on_progress is not None and done % 1000 == 0:
            if not on_progress(done, total):
                return None
        entry = cached.get(key)
        if entry is not None and entry[0] == size and entry[1] == mtime_ns:
            digest = entry[2]
        else:
            try:
                digest = preset_hash(Path(key))
            except OSError:
                continue
            upserts.append((key, size, mtime_ns, digest))
        path_hash[key] = digest
    prefix = os.path.join(str(root), "")
    stale = [
        (key,)
        for key in cached
        if key.startswith(prefix) and key not in path_hash
    ]
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO files (path, size, mtime_ns, hash) VALUES (?, ?, ?, ?)",
            upserts,
        )
        conn.executemany("DELETE FROM files WHERE path = ?", stale)
        conn.execute(
            "INSERT OR REPLACE INTO index_state (root, fingerprint) VALUES (?, ?)",
            (str(root), fingerprint),
        )
    if on_progress is not None:
        on_progress(total, total)
    return PresetIndex(root=root, path_hash=path_hash)


_memory_names = itertools.count()


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


class PresetLibrary:
    """Hash index of presets plus favourite / tag / blacklist / role state.

    ``database_uri`` opens another connection to the same database, for a
    worker thread running :func:`build_index`.
    """

    def __init__(self, conn: sqlite3.Connection, database_uri: str) -> None:
        self._conn = conn
        # The preset browser's listing worker hashes presets missing from the
        # index through this connection; one transaction at a time.
        self._db_lock = threading.RLock()
        self.database_uri = database_uri
        self._root: Path | None = None
        self._path_hash: dict[str, str] = {}
        self._alias_hash: dict[Path, str] = {}
        self._favourites: set[str] = set()
        self._blacklist: set[str] = set()
        self._roles: dict[str, CueRole] = {}
        self._tags: tuple[str, ...] = ()
        self._tag_members: dict[str, set[str]] = {}
        self.revision = 0
        self._sorted_paths: tuple[Path, ...] = ()
        self._sorted_paths_source: dict[str, str] | None = None
        self._dir_counts: dict[Path, int] = {}
        self._dir_counts_revision = -1
        self._load_curation()

    @classmethod
    def in_memory(cls) -> PresetLibrary:
        """Empty, unpersisted library (offline render and tests)."""
        uri = f"file:cleave-presets-{next(_memory_names)}?mode=memory&cache=shared"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.executescript(_SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return cls(conn, uri)

    @classmethod
    def open(cls, db_path: Path) -> PresetLibrary:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Serialized SQLite: the preset browser's listing worker reads hashes
        # through this connection while the editor writes curation.
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
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
            version = SCHEMA_VERSION
        while version in _UPGRADES:
            conn.executescript(
                f"BEGIN; {_UPGRADES[version]} PRAGMA user_version = {version + 1}; COMMIT;"
            )
            version += 1
        if version != SCHEMA_VERSION:
            conn.close()
            raise PresetLibraryError(
                f"preset library {db_path} has schema version {version}, "
                f"expected {SCHEMA_VERSION}; delete it to rebuild"
            )
        return cls(conn, f"{db_path.resolve().as_uri()}?mode=rw")

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
        self._tags = tuple(
            sorted(
                (row[0] for row in self._conn.execute("SELECT name FROM tags")),
                key=str.casefold,
            )
        )
        canonical = {name.casefold(): name for name in self._tags}
        self._tag_members = {name: set() for name in self._tags}
        for digest, tag in self._conn.execute("SELECT hash, tag FROM favourite_tags"):
            name = canonical.get(tag.casefold())
            if name is not None:
                self._tag_members[name].add(digest)

    def index(
        self,
        preset_root: Path,
        on_progress: ProgressCallback | None = None,
    ) -> bool:
        """Index ``preset_root`` on this connection (see :func:`build_index`).

        Returns False when ``on_progress`` asks to cancel (returns False).
        """
        built = build_index(self._conn, preset_root, on_progress)
        if built is None:
            return False
        self.adopt(built)
        return True

    def load_index(self, preset_root: Path) -> bool:
        """Use the stored index of ``preset_root`` when its top level is unchanged.

        Returns False, leaving the library as it was, when the root was never
        indexed or :func:`index_fingerprint` differs; call :meth:`index` then.
        """
        root = preset_root.resolve()
        row = self._conn.execute(
            "SELECT fingerprint FROM index_state WHERE root = ?", (str(root),)
        ).fetchone()
        if row is None or row[0] != index_fingerprint(root):
            return False
        prefix = os.path.join(str(root), "")
        path_hash = {
            path: digest
            for path, digest in self._conn.execute("SELECT path, hash FROM files")
            if path.startswith(prefix)
        }
        self.adopt(PresetIndex(root=root, path_hash=path_hash))
        return True

    def adopt(self, index: PresetIndex) -> None:
        """Use *index* (built here or on a worker connection) from now on."""
        self._root = index.root
        self._path_hash = index.path_hash
        self._alias_hash = {}
        self.revision += 1

    def hash_of(self, path: Path) -> str | None:
        """Content hash of ``path``; hashes and caches files outside the index."""
        digest = self._path_hash.get(str(path)) or self._alias_hash.get(path)
        if digest is not None:
            return digest
        resolved = path.resolve()
        digest = self._path_hash.get(str(resolved))
        if digest is not None:
            self._alias_hash[path] = digest
            return digest
        try:
            stat = resolved.stat()
        except OSError:
            return None
        with self._db_lock:
            row = self._conn.execute(
                "SELECT size, mtime_ns, hash FROM files WHERE path = ?",
                (str(resolved),),
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
        with self._db_lock, self._conn:
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

    def set_favourite(self, path: Path, on: bool) -> int:
        """Favourite or unfavourite *path*; returns how many tags that removed."""
        removed = 0
        if not on:
            digest = self.hash_of(path)
            if digest is not None:
                removed = len(self._tags_of_hash(digest))
                with self._db_lock, self._conn:
                    self._conn.execute(
                        "DELETE FROM favourite_tags WHERE hash = ?", (digest,)
                    )
                for members in self._tag_members.values():
                    members.discard(digest)
        self._set_flag("favourites", self._favourites, path, on)
        return removed

    def tags(self) -> tuple[str, ...]:
        """Every tag, sorted by name ignoring case."""
        return self._tags

    def _tags_of_hash(self, digest: str) -> tuple[str, ...]:
        return tuple(name for name in self._tags if digest in self._tag_members[name])

    def tags_of(self, path: Path) -> tuple[str, ...]:
        """Tags on *path*, sorted by name."""
        digest = self.hash_of(path)
        if digest is None:
            return ()
        return self._tags_of_hash(digest)

    def tag_count(self, tag: str) -> int:
        return len(self._tag_members.get(tag, ()))

    def new_tag_name(self, text: str) -> str:
        """*text* as a new tag's name; :class:`ValueError` when invalid or taken."""
        name = clean_tag_name(text)
        folded = name.casefold()
        if any(existing.casefold() == folded for existing in self._tags):
            raise ValueError(f"There is already a tag named {name}")
        return name

    def add_tag(self, text: str) -> str:
        """Create a tag (see :meth:`new_tag_name`) and return its name."""
        name = self.new_tag_name(text)
        with self._db_lock, self._conn:
            self._conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
        self._tags = tuple(sorted((*self._tags, name), key=str.casefold))
        self._tag_members[name] = set()
        self.revision += 1
        return name

    def set_tagged(self, path: Path, tag: str, on: bool) -> None:
        """Put the tag *tag* on *path*, favouriting it, or take it off."""
        digest = self.hash_of(path)
        if digest is None or tag not in self._tag_members:
            return
        with self._db_lock, self._conn:
            if on:
                self._conn.execute(
                    "INSERT OR REPLACE INTO favourites (hash, name) VALUES (?, ?)",
                    (digest, path.name),
                )
                self._conn.execute(
                    "INSERT OR IGNORE INTO favourite_tags (hash, tag) VALUES (?, ?)",
                    (digest, tag),
                )
                self._favourites.add(digest)
                self._tag_members[tag].add(digest)
            else:
                self._conn.execute(
                    "DELETE FROM favourite_tags WHERE hash = ? AND tag = ?",
                    (digest, tag),
                )
                self._tag_members[tag].discard(digest)
        self.revision += 1

    def set_blacklisted(self, path: Path, on: bool) -> None:
        self._set_flag("blacklist", self._blacklist, path, on)

    def set_role(self, path: Path, role: CueRole | None) -> None:
        digest = self.hash_of(path)
        if digest is None:
            return
        with self._db_lock, self._conn:
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

    def curation_entries(self) -> tuple[CurationEntry, ...]:
        """Every curated preset, sorted by name then hash."""
        names: dict[str, str] = {}
        with self._db_lock:
            for table in ("roles", "blacklist", "favourites"):
                for digest, name in self._conn.execute(
                    f"SELECT hash, name FROM {table}"
                ):
                    names[digest] = name
        entries = [
            CurationEntry(
                hash=digest,
                name=name,
                favourite=digest in self._favourites,
                blacklisted=digest in self._blacklist,
                role=self._roles.get(digest),
                tags=self._tags_of_hash(digest),
            )
            for digest, name in names.items()
        ]
        entries.sort(key=lambda entry: (entry.name.casefold(), entry.hash))
        return tuple(entries)

    def indexed_hashes(self) -> frozenset[str]:
        """Hashes of the presets in the current index."""
        return frozenset(self._path_hash.values())

    def apply_curation(
        self,
        entries: Iterable[CurationEntry],
        *,
        tags: Iterable[str] = (),
        replace: bool,
    ) -> None:
        """Write *entries* and the tag names *tags* in one transaction.

        *replace* clears every favourite, tag, blacklist mark, and role first.
        Otherwise flags and tags are added (never cleared), a tag matches an
        existing one ignoring case, and an entry's role replaces the preset's
        current one.
        """
        favourites: list[tuple[str, str]] = []
        blacklist: list[tuple[str, str]] = []
        roles: list[tuple[str, str, str]] = []
        tag_names: dict[str, str] = {}
        memberships: list[tuple[str, str]] = []
        for name in tags:
            tag_names.setdefault(name.casefold(), name)
        for entry in entries:
            for name in entry.tags:
                tag_names.setdefault(name.casefold(), name)
                memberships.append((entry.hash, name))
            if entry.favourite or entry.tags:
                favourites.append((entry.hash, entry.name))
            if entry.blacklisted:
                blacklist.append((entry.hash, entry.name))
            if entry.role is not None:
                roles.append((entry.hash, entry.role, entry.name))
        with self._db_lock, self._conn:
            if replace:
                for table in ("favourites", "blacklist", "roles", "tags", "favourite_tags"):
                    self._conn.execute(f"DELETE FROM {table}")
            self._conn.executemany(
                "INSERT OR IGNORE INTO tags (name) VALUES (?)",
                [(name,) for name in tag_names.values()],
            )
            self._conn.executemany(
                "INSERT OR IGNORE INTO favourite_tags (hash, tag) VALUES (?, ?)",
                memberships,
            )
            self._conn.executemany(
                "INSERT OR REPLACE INTO favourites (hash, name) VALUES (?, ?)",
                favourites,
            )
            self._conn.executemany(
                "INSERT OR REPLACE INTO blacklist (hash, name) VALUES (?, ?)",
                blacklist,
            )
            self._conn.executemany(
                "INSERT OR REPLACE INTO roles (hash, role, name) VALUES (?, ?, ?)",
                roles,
            )
        self._load_curation()
        self.revision += 1

    def _in_collection(self, digest: str, collection: PresetCollection) -> bool:
        if isinstance(collection, FavouriteTag):
            return digest in self._tag_members.get(collection.name, ())
        if collection == "all_favourites":
            return digest in self._favourites
        if collection == "favourites":
            return False
        if collection == "blacklisted":
            return digest in self._blacklist
        return self._roles.get(digest) == collection

    def collections(self) -> tuple[PresetCollection, ...]:
        """Collections offered beside top-level preset folders."""
        return PRESET_COLLECTIONS

    def tag_collections(self) -> tuple[FavouriteTag, ...]:
        """One collection per tag, sorted by name."""
        return tuple(FavouriteTag(name) for name in self._tags)

    def favourite_collections(self) -> tuple[PresetCollection, ...]:
        """What the Favourites folder holds: All favourites, then each tag."""
        return ("all_favourites", *self.tag_collections())

    def collection_paths(self, collection: PresetCollection) -> tuple[Path, ...]:
        """Indexed files in ``collection``, one path per hash, sorted by path."""
        members = sorted(
            (Path(key), digest)
            for key, digest in self._path_hash.items()
            if self._in_collection(digest, collection)
        )
        seen: set[str] = set()
        out: list[Path] = []
        for path, digest in members:
            if digest in seen:
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

    def indexed_paths(self) -> tuple[Path, ...]:
        """Every indexed preset, sorted by path; empty before the first index."""
        if self._sorted_paths_source is not self._path_hash:
            self._sorted_paths = tuple(Path(key) for key in sorted(self._path_hash))
            self._sorted_paths_source = self._path_hash
        return self._sorted_paths

    def preset_counts_by_dir(self) -> dict[Path, int]:
        """Visible presets at or below each indexed folder, up to the root."""
        if self._dir_counts_revision != self.revision:
            counts: dict[Path, int] = {}
            root = self._root
            for path in self.indexed_paths():
                if self._path_hash.get(str(path)) in self._blacklist:
                    continue
                folder = path.parent
                while True:
                    counts[folder] = counts.get(folder, 0) + 1
                    if folder == root or folder.parent == folder:
                        break
                    folder = folder.parent
            self._dir_counts = counts
            self._dir_counts_revision = self.revision
        return self._dir_counts

    def marker(self, path: Path, *, in_preset_list: bool = False) -> str:
        """Panel marker such as ``" [F] [L] [R:B]"``; empty when uncurated.

        *in_preset_list* adds ``[L]``: the layer's preset list holds this preset.
        """
        digest = self.hash_of(path)
        parts: list[str] = []
        if digest is not None and digest in self._favourites:
            parts.append("[F]")
        if digest is not None and digest in self._blacklist:
            parts.append("[B]")
        if in_preset_list:
            parts.append("[L]")
        role = self._roles.get(digest) if digest is not None else None
        if role is not None:
            parts.append(f"[R:{CUE_ROLE_MARKER_LETTER[role]}]")
        if not parts:
            return ""
        return " " + " ".join(parts)
