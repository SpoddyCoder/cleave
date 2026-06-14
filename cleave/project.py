"""Project manifest (project.yaml) for Cleave projects."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

PROJECT_FILENAME = "project.yaml"


@dataclass(frozen=True)
class ProjectManifest:
    version: int
    slug: str
    mix_filename: str
    original_path: str
    separated_at: str
    demucs_model: str
    restored_from: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> ProjectManifest:
        mix = data.get("mix")
        ingest = data.get("ingest")
        if not isinstance(mix, dict) or not isinstance(ingest, dict):
            raise ValueError("invalid project manifest: missing mix or ingest")
        filename = mix.get("filename")
        if not isinstance(filename, str) or not filename:
            raise ValueError("invalid project manifest: mix.filename")
        restored = data.get("restored-from")
        restored_from = None if restored is None else str(restored)
        return cls(
            version=int(data["version"]),
            slug=str(data["slug"]),
            mix_filename=filename,
            original_path=str(ingest["original_path"]),
            separated_at=str(ingest["separated_at"]),
            demucs_model=str(ingest["demucs_model"]),
            restored_from=restored_from,
        )

    def to_dict(self) -> dict:
        data = {
            "version": self.version,
            "slug": self.slug,
            "mix": {"filename": self.mix_filename},
            "ingest": {
                "original_path": self.original_path,
                "separated_at": self.separated_at,
                "demucs_model": self.demucs_model,
            },
        }
        if self.restored_from is not None:
            data["restored-from"] = self.restored_from
        return data


def manifest_path(project_dir: Path) -> Path:
    return project_dir / PROJECT_FILENAME


def rewrite_manifest_slug(
    project_dir: Path,
    slug: str,
    *,
    restored_from: str | None = None,
) -> Path:
    """Update ``project.yaml`` *slug* and optional ``restored-from`` provenance."""
    manifest = load_manifest(project_dir)
    updated = ProjectManifest(
        version=manifest.version,
        slug=slug,
        mix_filename=manifest.mix_filename,
        original_path=manifest.original_path,
        separated_at=manifest.separated_at,
        demucs_model=manifest.demucs_model,
        restored_from=restored_from,
    )
    path = manifest_path(project_dir)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(updated.to_dict(), handle, sort_keys=False)
    return path


def load_manifest(project_dir: Path) -> ProjectManifest:
    path = manifest_path(project_dir)
    if not path.is_file():
        raise FileNotFoundError(f"project manifest not found: {path}")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"invalid project manifest: {path}")
    return ProjectManifest.from_dict(data)


def write_manifest(
    project_dir: Path,
    *,
    slug: str,
    mix_filename: str,
    original_path: Path,
    demucs_model: str,
    separated_at: datetime | None = None,
) -> Path:
    when = separated_at or datetime.now(timezone.utc)
    manifest = ProjectManifest(
        version=1,
        slug=slug,
        mix_filename=mix_filename,
        original_path=str(original_path.resolve()),
        separated_at=when.isoformat(),
        demucs_model=demucs_model,
    )
    path = manifest_path(project_dir)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest.to_dict(), handle, sort_keys=False)
    return path


def mix_path(project_dir: Path) -> Path:
    manifest = load_manifest(project_dir)
    return project_dir / manifest.mix_filename


def resolve_mix_path(project_dir: Path) -> Path:
    if not manifest_path(project_dir).is_file():
        print(
            "error: no project mix; run separate first",
            file=sys.stderr,
        )
        sys.exit(1)

    path = mix_path(project_dir)
    if not path.is_file():
        print(f"error: audio not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path
