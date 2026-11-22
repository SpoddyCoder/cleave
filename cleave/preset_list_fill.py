"""Fill a new project's preset lists so switching has presets from the start.

Pygame-free: ``separate`` calls this once, right after the template becomes a
project, and the editor's Populate list shares :func:`needed_preset_count`.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import yaml

from cleave.config import dump_yaml, load_config, project_viz_config_path
from cleave.paths import config_relative_path, library_db_path
from cleave.preset_library import (
    UNFILTERED_CATALOG,
    PresetCatalog,
    PresetLibrary,
    PresetLibraryError,
)
from cleave.preset_playlist import milk_files_in_dir
from cleave.viz.user_presets import USER_PRESETS_DIRNAME, copy_with_dedup

_FILLED_TRIGGERS = ("timer", "projectm")


def needed_preset_count(
    *,
    song_duration_sec: float,
    preset_duration: float,
    trigger: str,
) -> int:
    """How many presets to populate for timer/projectm over the song."""
    duration = max(1e-6, float(preset_duration))
    base = math.ceil(float(song_duration_sec) / duration)
    if trigger == "projectm":
        return max(1, base + 2)
    return max(1, base)


def _song_duration_sec(project_dir: Path) -> float | None:
    path = project_dir / "signals.json"
    try:
        with path.open(encoding="utf-8") as fh:
            return float(json.load(fh)["duration_sec"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _open_catalog(preset_root: Path) -> tuple[PresetCatalog, PresetLibrary | None]:
    """The preset library, so blacklisted presets stay out, when it is indexed."""
    try:
        library = PresetLibrary.open(library_db_path())
    except (PresetLibraryError, OSError):
        return UNFILTERED_CATALOG, None
    if library.load_index(preset_root):
        return library, library
    library.close()
    return UNFILTERED_CATALOG, None


def _pool(folder: Path, catalog: PresetCatalog) -> list[Path]:
    return list(catalog.visible(milk_files_in_dir(folder)))


def fill_new_project_preset_lists(
    project_dir: Path, *, rng: random.Random | None = None
) -> list[str]:
    """Fill every empty timer/projectm preset list in a new project.

    Each list gets as many presets as the song needs at the layer's preset
    duration, shuffled from the layer's preset folder, as Populate list does.
    Presets are copied into the project like any list preset. Returns the
    slots filled.
    """
    duration = _song_duration_sec(project_dir)
    if duration is None:
        return []
    cfg = load_config(project_root=project_dir)
    preset_root = cfg.paths.preset_root
    rng = rng or random.Random()
    catalog, library = _open_catalog(preset_root)
    filled: dict[str, list[dict[str, str]]] = {}
    try:
        for slot, layer in cfg.layers.items():
            if layer.preset_switching != "on" or layer.preset_switching_list:
                continue
            if layer.preset_switching_trigger not in _FILLED_TRIGGERS:
                continue
            folder = (
                layer.preset.parent
                if layer.preset.suffix.lower() == ".milk"
                else layer.preset
            )
            pool = _pool(folder, catalog)
            if not pool:
                continue
            count = needed_preset_count(
                song_duration_sec=duration,
                preset_duration=layer.preset_duration,
                trigger=layer.preset_switching_trigger,
            )
            sources = rng.sample(pool, min(count, len(pool)))
            dest_dir = project_dir / USER_PRESETS_DIRNAME
            entries = [copy_with_dedup(dest_dir, src) for src in sources]
            filled[slot] = [
                {"path": config_relative_path(entry.file, project_dir)}
                | ({"source": entry.source} if entry.source is not None else {})
                for entry in entries
            ]
    finally:
        if library is not None:
            library.close()
    if not filled:
        return []
    path = project_viz_config_path(project_dir)
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    for slot, entries in filled.items():
        data["layers"][slot]["preset_switching_list"] = entries
    with path.open("w", encoding="utf-8") as fh:
        dump_yaml(data, fh)
    return list(filled)
