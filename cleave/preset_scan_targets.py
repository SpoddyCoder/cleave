"""Derive preset scan sets for project and bulk ``cleave scan`` modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cleave.config import CleaveConfig
from cleave.preset_playlist import milk_files_in_dir, scan_preset_playlist


@dataclass(frozen=True)
class PresetTarget:
    """One deduplicated preset path and the layer slots that reference it."""

    path: Path
    layers: tuple[str, ...]


@dataclass(frozen=True)
class ScanTargets:
    """Preset paths to probe plus project-mode attribution metadata."""

    presets: tuple[PresetTarget, ...]
    preset_root: Path | None = None
    texture_paths: tuple[Path, ...] = ()
    presets_dir: Path | None = None
    layer_sources: dict[str, tuple[Path, ...]] = field(default_factory=dict)


def build_project_targets(cfg: CleaveConfig) -> ScanTargets:
    """Collect presets from on-disk config, matching live rotation set rules."""
    by_path: dict[Path, list[str]] = {}
    layer_sources: dict[str, tuple[Path, ...]] = {}

    for slot in cfg.layer_z_order:
        layer = cfg.layers.get(slot)
        if layer is None:
            continue

        playlist = scan_preset_playlist(layer.preset)
        anchor_dir = playlist.current_dir
        sources: list[Path] = [anchor_dir]

        for preset_path in milk_files_in_dir(anchor_dir):
            _register_preset(by_path, preset_path, slot)

        if layer.preset_switching_rotation_set == "user_defined":
            for preset_path in layer.preset_switching_presets:
                sources.append(preset_path)
                _register_preset(by_path, preset_path, slot)

        layer_sources[slot] = tuple(sources)

    presets = _finalize_presets(by_path)
    return ScanTargets(
        presets=presets,
        preset_root=cfg.paths.preset_root.resolve(),
        texture_paths=tuple(p.resolve() for p in cfg.paths.texture_paths),
        layer_sources=layer_sources,
    )


def build_bulk_targets(presets_dir: Path, *, recursive: bool = False) -> ScanTargets:
    """Collect presets from a directory for bulk scan mode."""
    resolved_dir = presets_dir.resolve()
    if recursive:
        paths = tuple(sorted(p.resolve() for p in resolved_dir.rglob("*.milk")))
    else:
        paths = milk_files_in_dir(resolved_dir)

    presets = tuple(PresetTarget(path=path, layers=()) for path in paths)
    return ScanTargets(presets=presets, presets_dir=resolved_dir)


def _register_preset(
    by_path: dict[Path, list[str]],
    path: Path,
    slot: str,
) -> None:
    resolved = path.resolve()
    slots = by_path.setdefault(resolved, [])
    if slot not in slots:
        slots.append(slot)


def _finalize_presets(by_path: dict[Path, list[str]]) -> tuple[PresetTarget, ...]:
    return tuple(
        PresetTarget(path=path, layers=tuple(slots))
        for path, slots in sorted(by_path.items(), key=lambda item: str(item[0]))
    )
