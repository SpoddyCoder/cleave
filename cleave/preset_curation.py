"""Back up and restore preset curation (favourites, blacklist, roles) as JSON.

Curation is keyed by each preset's content hash, so a backup works on another
machine, another OS, and before the matching presets are installed. The file
index (machine paths) is not included; a fresh install rebuilds it.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cleave import __version__
from cleave.cue_roles import CUE_ROLES
from cleave.preset_library import CurationEntry, PresetLibrary

FORMAT = "cleave-preset-curation"
FORMAT_VERSION = 1
BACKUP_SUFFIX = ".json"
_FILENAME_PREFIX = "cleave-curation"
_HASH_RE = re.compile(r"^[0-9a-f]{32}$")


class CurationBackupError(ValueError):
    """A curation backup cannot be read or written."""


@dataclass(frozen=True)
class CurationCounts:
    """How many presets a set of entries curates, by kind."""

    presets: int
    favourites: int
    roles: int
    blacklisted: int

    def summary(self) -> str:
        """Such as ``312 presets: 40 favourites, 242 roles, 30 blacklisted``."""
        return (
            f"{_plural(self.presets, 'preset')}: "
            f"{_plural(self.favourites, 'favourite')}, "
            f"{_plural(self.roles, 'role')}, "
            f"{self.blacklisted:,} blacklisted"
        )


def _plural(count: int, noun: str) -> str:
    return f"{count:,} {noun}" if count == 1 else f"{count:,} {noun}s"


def count_entries(entries: tuple[CurationEntry, ...]) -> CurationCounts:
    return CurationCounts(
        presets=len(entries),
        favourites=sum(entry.favourite for entry in entries),
        roles=sum(entry.role is not None for entry in entries),
        blacklisted=sum(entry.blacklisted for entry in entries),
    )


@dataclass(frozen=True)
class RestorePreview:
    """What restoring a backup into a library would do, before it runs."""

    counts: CurationCounts
    installed: int
    """Entries whose preset is in the library's current index."""
    role_changes: int
    """Presets whose current role a merge would replace with a different one."""
    current: CurationCounts
    """The library's curation now (what Replace clears)."""


def backup_filename(now: datetime) -> str:
    return f"{_FILENAME_PREFIX}-{now:%Y-%m-%d-%H%M%S}{BACKUP_SUFFIX}"


def is_backup_candidate(path: Path) -> bool:
    """True when *path* is a file that may be a curation backup (by suffix)."""
    try:
        return path.suffix.lower() == BACKUP_SUFFIX and path.is_file()
    except OSError:
        return False


def _entry_json(entry: CurationEntry) -> dict[str, object]:
    return {
        "hash": entry.hash,
        "name": entry.name,
        "favourite": entry.favourite,
        "blacklisted": entry.blacklisted,
        "role": entry.role,
    }


def write_backup(
    entries: tuple[CurationEntry, ...],
    dest: Path,
    *,
    now: datetime | None = None,
) -> Path:
    """Write *entries* to *dest* and return the file written.

    *dest* is a ``.json`` file path, or a folder that gets a dated file name.
    An existing file is never overwritten. Raises :class:`CurationBackupError`.
    """
    stamp = now or datetime.now()
    if dest.suffix.lower() == BACKUP_SUFFIX:
        path = dest
        if path.exists():
            raise CurationBackupError(f"{path} already exists")
    else:
        path = dest / backup_filename(stamp)
        n = 2
        while path.exists():
            path = dest / f"{path.stem.split('~')[0]}~{n}{BACKUP_SUFFIX}"
            n += 1
    payload = {
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "created": stamp.isoformat(timespec="seconds"),
        "cleave_version": __version__,
        "presets": [_entry_json(entry) for entry in entries],
    }
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise CurationBackupError(f"could not write {path}: {exc}") from exc
    return path


def back_up_library(
    library: PresetLibrary, dest: Path, *, now: datetime | None = None
) -> tuple[Path, CurationCounts]:
    """Write *library*'s curation to *dest* (see :func:`write_backup`)."""
    entries = library.curation_entries()
    return write_backup(entries, dest, now=now), count_entries(entries)


def _parse_entry(index: int, raw: object) -> CurationEntry:
    where = f"preset {index + 1}"
    if not isinstance(raw, dict):
        raise CurationBackupError(f"{where} is not an object")
    digest = raw.get("hash")
    if not isinstance(digest, str) or not _HASH_RE.match(digest):
        raise CurationBackupError(f"{where} has no valid hash")
    name = raw.get("name", "")
    if not isinstance(name, str):
        raise CurationBackupError(f"{where} has a name that is not text")
    favourite = raw.get("favourite", False)
    blacklisted = raw.get("blacklisted", False)
    if not isinstance(favourite, bool) or not isinstance(blacklisted, bool):
        raise CurationBackupError(f"{where} has a favourite or blacklisted value that is not true/false")
    role = raw.get("role")
    if role is not None and role not in CUE_ROLES:
        raise CurationBackupError(f"{where} has an unknown role {role!r}")
    return CurationEntry(
        hash=digest,
        name=name or digest,
        favourite=favourite,
        blacklisted=blacklisted,
        role=role,
    )


def read_backup(path: Path) -> tuple[CurationEntry, ...]:
    """Read and validate a backup. Raises :class:`CurationBackupError`."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CurationBackupError(f"could not read {path.name}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CurationBackupError(f"{path.name} is not a preset curation backup") from exc
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise CurationBackupError(f"{path.name} is not a preset curation backup")
    version = payload.get("version")
    if not isinstance(version, int) or version < 1:
        raise CurationBackupError(f"{path.name} has no valid version")
    if version > FORMAT_VERSION:
        raise CurationBackupError(
            f"{path.name} was made by a newer Cleave; update Cleave to restore it"
        )
    presets = payload.get("presets")
    if not isinstance(presets, list):
        raise CurationBackupError(f"{path.name} has no preset list")
    by_hash: dict[str, CurationEntry] = {}
    for index, raw in enumerate(presets):
        entry = _parse_entry(index, raw)
        by_hash[entry.hash] = entry
    return tuple(by_hash.values())


def preview_restore(
    library: PresetLibrary, entries: tuple[CurationEntry, ...]
) -> RestorePreview:
    installed = library.indexed_hashes()
    current = library.curation_entries()
    current_roles = {entry.hash: entry.role for entry in current if entry.role}
    return RestorePreview(
        counts=count_entries(entries),
        installed=sum(entry.hash in installed for entry in entries),
        role_changes=sum(
            entry.role is not None
            and current_roles.get(entry.hash) not in (None, entry.role)
            for entry in entries
        ),
        current=count_entries(current),
    )


def restore_into(
    library: PresetLibrary,
    entries: tuple[CurationEntry, ...],
    *,
    replace: bool,
    safety_dir: Path,
    now: datetime | None = None,
) -> Path | None:
    """Save the library's current curation to *safety_dir*, then apply *entries*.

    Returns the safety backup, or None when there was nothing to save. Raises
    :class:`CurationBackupError` when the safety backup fails; nothing is
    applied then.
    """
    safety: Path | None = None
    current = library.curation_entries()
    if current:
        safety = write_backup(current, safety_dir, now=now)
    library.apply_curation(entries, replace=replace)
    return safety
