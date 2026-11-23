"""Helpers for per-layer preset switching lists (project presets copies)."""

from __future__ import annotations

import filecmp
import hashlib
import os
import shutil
from collections.abc import Sequence
from pathlib import Path

import yaml

from cleave.config_schema.layers import resolve_user_preset
from cleave.preset_list_entry import PresetListEntry
from cleave.project import PROJECT_FILENAME

USER_PRESETS_DIRNAME = "presets"


def path_list_digest(paths: Sequence[str]) -> str:
    """Stable digest for ordered path strings (empty list -> empty digest)."""
    if not paths:
        return ""
    return hashlib.sha1("\0".join(paths).encode()).hexdigest()


def path_list_identity(paths: Sequence[str]) -> dict[str, int | str]:
    """Compact structure-signature identity for an ordered path list."""
    return {"len": len(paths), "digest": path_list_digest(paths)}


def preset_list_identity(entries: Sequence[PresetListEntry]) -> dict[str, int | str]:
    """Structure-signature identity for a preset list, covering each entry's source."""
    return path_list_identity(
        [f"{entry.path}\x01{entry.source or ''}" for entry in entries]
    )


def preset_list_display_names(entries: Sequence[PresetListEntry]) -> list[str]:
    """Format preset-list row labels, numbering entries that share a copy.

    An entry reads as its original file name, so a deduplicated copy such as
    ``foo_2.milk`` still shows as ``foo.milk``.
    """
    if not entries:
        return []
    resolved = [entry.file.resolve() for entry in entries]
    by_resolved: dict[Path, list[int]] = {}
    for index, path in enumerate(resolved):
        by_resolved.setdefault(path, []).append(index)
    labels = [""] * len(entries)
    for indices in by_resolved.values():
        if len(indices) == 1:
            index = indices[0]
            labels[index] = entries[index].display_name
            continue
        for instance, index in enumerate(indices, start=1):
            labels[index] = f"{entries[index].display_name} ({instance})"
    return labels


def preset_list_item_display_name(
    entries: Sequence[PresetListEntry], index: int
) -> str:
    """Format a preset-list row label, numbering entries that share a copy."""
    return preset_list_display_names(entries)[index]


def copy_with_dedup(dest_dir: Path, src_path: Path) -> PresetListEntry:
    """Copy ``src_path`` into ``dest_dir`` with dedup; return the list entry.

    The entry remembers ``src_path`` as its source unless the preset already
    lived in ``dest_dir``.
    """
    dest_path, needs_copy = resolve_user_preset_dest(dest_dir, src_path)
    if needs_copy:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)
    resolved_src = src_path.resolve()
    try:
        resolved_src.relative_to(dest_dir.resolve())
        source = None
    except ValueError:
        source = str(resolved_src)
    return PresetListEntry(path=str(dest_path.resolve()), source=source)


def preview_anchor(entry: PresetListEntry) -> Path:
    """The file to browse when previewing ``entry``.

    The original, so the preset rows show the folder it came from, while it
    still exists and matches the copy; otherwise the project copy.
    """
    copy = entry.file
    if entry.source is None:
        return copy
    source = Path(entry.source)
    try:
        if source.is_file() and _same_preset_file(source, copy):
            return source
    except OSError:
        pass
    return copy


def resolve_user_preset_dest(dest_dir: Path, src_path: Path) -> tuple[Path, bool]:
    """Return destination path and whether the source file must be copied."""
    resolved_src = src_path.resolve()
    presets_dir = dest_dir.resolve()

    try:
        resolved_src.relative_to(presets_dir)
        return resolved_src, False
    except ValueError:
        pass

    canonical = presets_dir / src_path.name
    if canonical.exists():
        if _same_preset_file(src_path, canonical):
            return canonical, False
        return _unique_copy_dest(dest_dir, src_path.name), True

    return canonical, True


def iter_project_viz_config_paths(project_dir: Path) -> list[Path]:
    """Return project-dir ``*.yaml`` files that look like visualizer configs."""
    try:
        candidates = sorted(project_dir.glob("*.yaml"))
    except OSError:
        return []
    out: list[Path] = []
    for path in candidates:
        if path.name == PROJECT_FILENAME or not path.is_file():
            continue
        if _is_viz_config_yaml(path):
            out.append(path)
    return out


def referenced_user_preset_paths(project_dir: Path) -> set[Path]:
    """Resolved preset paths cited by any visualizer YAML in ``project_dir``."""
    refs: set[Path] = set()
    for config_path in iter_project_viz_config_paths(project_dir):
        refs.update(_preset_refs_from_viz_yaml(config_path))
    return refs


def user_preset_referenced_on_disk(
    project_dir: Path,
    path: Path,
    *,
    skip_config: Path | None = None,
) -> bool:
    """True if ``path`` appears in any project viz YAML (optionally skipping one)."""
    target = path.resolve()
    skip = skip_config.resolve() if skip_config is not None else None
    for config_path in iter_project_viz_config_paths(project_dir):
        if skip is not None and config_path.resolve() == skip:
            continue
        if target in _preset_refs_from_viz_yaml(config_path):
            return True
    return False


def cleanup_unreferenced_user_presets(project_dir: Path) -> list[Path]:
    """Remove ``*.milk`` under ``presets/`` not referenced by any viz YAML.

    Returns resolved paths that were unlinked. Failures are ignored.
    """
    presets_dir = project_dir / USER_PRESETS_DIRNAME
    try:
        if not presets_dir.is_dir():
            return []
        candidates = list(presets_dir.glob("*.milk"))
    except OSError:
        return []

    referenced = referenced_user_preset_paths(project_dir)
    removed: list[Path] = []
    for milk in candidates:
        try:
            resolved = milk.resolve()
        except OSError:
            continue
        if resolved in referenced:
            continue
        try:
            milk.unlink()
        except OSError:
            continue
        removed.append(resolved)
    return removed


def _is_viz_config_yaml(path: Path) -> bool:
    data = _load_yaml_mapping(path)
    return data is not None and "layers" in data


def _preset_refs_from_viz_yaml(path: Path) -> set[Path]:
    data = _load_yaml_mapping(path)
    if data is None:
        return set()
    layers = data.get("layers")
    if not isinstance(layers, dict):
        return set()
    cfg_dir = path.parent
    entries: list[object] = []
    for layer_raw in layers.values():
        if not isinstance(layer_raw, dict):
            continue
        raw = layer_raw.get("preset_switching_list")
        if isinstance(raw, list):
            entries.extend(raw)
    entries.extend(_clip_preset_refs(data.get("timeline")))
    return {
        resolve_user_preset(entry["path"], cfg_dir)
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }


def _clip_preset_refs(timeline: object) -> list[object]:
    """The ``preset`` mappings on every timeline clip in a viz YAML."""
    if not isinstance(timeline, dict):
        return []
    lanes = timeline.get("lanes")
    if not isinstance(lanes, dict):
        return []
    out: list[object] = []
    for lane in lanes.values():
        cues = lane.get("cues") if isinstance(lane, dict) else None
        if not isinstance(cues, list):
            continue
        out.extend(cue.get("preset") for cue in cues if isinstance(cue, dict))
    return out


def _load_yaml_mapping(path: Path) -> dict | None:
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except OSError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _same_preset_file(left: Path, right: Path) -> bool:
    try:
        if os.path.samefile(left, right):
            return True
    except OSError:
        pass
    return filecmp.cmp(left, right, shallow=False)


def _unique_copy_dest(dest_dir: Path, filename: str) -> Path:
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    index = 2
    while True:
        candidate = dest_dir / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1
