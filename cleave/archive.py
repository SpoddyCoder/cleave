"""Backup and restore Cleave project directories as gzip tar archives."""

from __future__ import annotations

import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from cleave.paths import project_dir, projects_dir, validate_project_slug
from cleave.project import load_manifest, rewrite_manifest_slug

_ARCHIVE_SUFFIXES = (".cleave-tar.gz", ".tar.gz")


def _is_archive_file_path(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(suffix) for suffix in _ARCHIVE_SUFFIXES)


def resolve_backup_output(dest: Path, slug: str) -> Path:
    """Resolve a backup destination to the output archive path."""
    dest = Path(dest)
    if dest.is_dir():
        return dest / f"{slug}.cleave-tar.gz"
    if _is_archive_file_path(dest):
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    return dest / f"{slug}.cleave-tar.gz"


def confirm_overwrite(message: str, *, force: bool) -> bool:
    """Prompt ``[y/N]`` on a TTY; auto-yes with *force*, auto-no when not a TTY."""
    if force:
        return True
    if not sys.stdin.isatty():
        return False
    try:
        answer = input(f"{message} [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def _archive_top_level_dir(members: list[tarfile.TarInfo]) -> str:
    top_levels: set[str] = set()
    for member in members:
        parts = PurePosixPath(member.name).parts
        if not parts or parts[0] in ("", "."):
            continue
        top_levels.add(parts[0])
    if len(top_levels) != 1:
        names = ", ".join(sorted(top_levels)) or "(none)"
        raise ValueError(
            f"archive must contain exactly one top-level directory, found: {names}"
        )
    return next(iter(top_levels))


def _safe_extract(
    tar: tarfile.TarFile,
    destination: Path,
    members: list[tarfile.TarInfo],
) -> None:
    dest = destination.resolve()
    dest_prefix = os.fspath(dest)
    if not dest_prefix.endswith(os.sep):
        dest_prefix = f"{dest_prefix}{os.sep}"

    for member in members:
        member_path = (dest / member.name).resolve()
        member_prefix = os.fspath(member_path)
        if member_path != dest and not member_prefix.startswith(dest_prefix):
            raise ValueError(f"unsafe path in archive: {member.name!r}")

    tar.extractall(dest)


def backup_project(project_dir: Path, dest: Path, *, force: bool) -> Path:
    """Write *project_dir* to a ``.cleave-tar.gz`` archive at *dest*."""
    project_dir = Path(project_dir).resolve()
    manifest = load_manifest(project_dir)
    output = resolve_backup_output(dest, manifest.slug)

    if output.is_file():
        if not confirm_overwrite(f"overwrite {output}?", force=force):
            raise FileExistsError(f"backup already exists: {output}")

    output.parent.mkdir(parents=True, exist_ok=True)
    print("Backing up project, please wait...", file=sys.stderr)
    with tarfile.open(output, "w:gz") as tar:
        tar.add(project_dir, arcname=manifest.slug)
    return output.resolve()


def restore_project(
    archive: Path,
    *,
    as_slug: str | None = None,
    force: bool = False,
) -> Path:
    """Extract a project archive into :func:`~cleave.paths.projects_dir`."""
    archive = Path(archive).resolve()
    if not archive.is_file():
        raise FileNotFoundError(f"archive not found: {archive}")

    with tarfile.open(archive, "r:gz") as tar:
        print("Reading archive, please wait...", file=sys.stderr)
        members = tar.getmembers()
        top_level = _archive_top_level_dir(members)

        with tempfile.TemporaryDirectory(prefix="cleave-restore-") as tmp:
            extract_root = Path(tmp)
            print("Unpacking project files, please wait...", file=sys.stderr)
            _safe_extract(tar, extract_root, members)
            extracted = extract_root / top_level
            if not extracted.is_dir():
                raise ValueError(
                    f"archive top-level entry is not a directory: {top_level!r}"
                )

            manifest = load_manifest(extracted)
            if manifest.slug != top_level:
                raise ValueError(
                    "archive top-level directory "
                    f"{top_level!r} does not match manifest slug {manifest.slug!r}"
                )

            target_slug = manifest.slug
            if as_slug is not None:
                validate_project_slug(as_slug)
                rewrite_manifest_slug(
                    extracted,
                    as_slug,
                    restored_from=manifest.slug,
                )
                target_slug = as_slug

            target = project_dir(target_slug).resolve()
            projects_dir().mkdir(parents=True, exist_ok=True)

            if target.exists():
                if not confirm_overwrite(f"replace existing project {target}?", force=force):
                    raise FileExistsError(f"project already exists: {target}")
                shutil.rmtree(target)

            print("Restoring project...", file=sys.stderr)
            shutil.move(os.fspath(extracted), os.fspath(target))

    return target
