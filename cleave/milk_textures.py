"""Parse Milkdrop presets for texture sampler refs and sync project bundles."""

from __future__ import annotations

import filecmp
import re
import shutil
from collections.abc import Iterable, Sequence
from pathlib import Path

BUILTIN_SAMPLERS = {
    "main",
    "fw_main",
    "fc_main",
    "pw_main",
    "pc_main",
    "noise_lq",
    "noise_mq",
    "noise_hq",
    "noisevol_lq",
    "noisevol_hq",
    "pw_noise_lq",
}
RAND_PATTERN = re.compile(r"rand\d{2}")
SAMPLER_PATTERN = re.compile(r"sampler\s+sampler_(?:fw_|fc_|pw_|pc_)?(\w+)")
TEXTURE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tga", ".bmp", ".dds", ".dib")
PROJECT_TEXTURES_DIRNAME = "textures"


def extract_texture_names(milk_path: Path) -> set[str]:
    """Return texture basenames referenced by sampler declarations."""
    try:
        text = milk_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    names: set[str] = set()
    for match in SAMPLER_PATTERN.finditer(text):
        name = match.group(1)
        if name in BUILTIN_SAMPLERS:
            continue
        if RAND_PATTERN.match(name):
            continue
        names.add(name)
    return names


_TEXTURE_EXT_ORDER = {ext.lower(): index for index, ext in enumerate(TEXTURE_EXTENSIONS)}


def resolve_texture_file(name: str, search_paths: Sequence[Path]) -> Path | None:
    """Find first file matching name (without extension) in search paths."""
    name_lower = name.lower()
    for search_dir in search_paths:
        try:
            if not search_dir.is_dir():
                continue
        except OSError:
            continue
        try:
            files = sorted(
                (path for path in search_dir.rglob("*") if path.is_file()),
                key=lambda path: str(path).lower(),
            )
        except OSError:
            continue
        best: tuple[int, str, Path] | None = None
        for candidate in files:
            ext_lower = candidate.suffix.lower()
            ext_index = _TEXTURE_EXT_ORDER.get(ext_lower)
            if ext_index is None or candidate.stem.lower() != name_lower:
                continue
            sort_key = (ext_index, str(candidate).lower())
            if best is None or sort_key < (best[0], best[1]):
                best = (ext_index, str(candidate).lower(), candidate)
        if best is not None:
            return best[2]
    return None


def project_texture_search_paths(
    project_dir: Path,
    texture_paths: Sequence[Path],
) -> list[Path]:
    """Prepend project-local textures when the bundle directory exists."""
    project_textures = project_dir / PROJECT_TEXTURES_DIRNAME
    try:
        if project_textures.is_dir():
            return [project_textures, *texture_paths]
    except OSError:
        pass
    return list(texture_paths)


def sync_project_textures(
    project_dir: Path,
    milk_paths: Iterable[Path],
    search_paths: Sequence[Path],
) -> None:
    """Copy referenced textures into project_dir/textures/, remove orphans."""
    needed: set[str] = set()
    for milk_path in milk_paths:
        try:
            if milk_path.is_file():
                needed.update(extract_texture_names(milk_path))
        except OSError:
            continue

    textures_dir = project_dir / PROJECT_TEXTURES_DIRNAME
    textures_dir.mkdir(parents=True, exist_ok=True)
    local_search = [textures_dir, *search_paths]

    for name in needed:
        src = resolve_texture_file(name, search_paths)
        if src is None:
            src = resolve_texture_file(name, [textures_dir])
        if src is None:
            continue
        dest = textures_dir / src.name
        try:
            if src.resolve() == dest.resolve():
                continue
        except OSError:
            pass
        if not dest.exists() or not filecmp.cmp(src, dest, shallow=False):
            shutil.copy2(src, dest)

    try:
        for path in textures_dir.iterdir():
            if path.is_file() and path.stem not in needed:
                path.unlink()
    except OSError:
        pass
