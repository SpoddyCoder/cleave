"""Shared config helpers for unit tests."""

from __future__ import annotations

from pathlib import Path

from cleave.config import LayerConfig, VIZ_CONFIG_FILENAME, dump_yaml
from cleave.config_schema import (
    DEFAULT_LAYER_Z_ORDER,
    DEFAULT_STEM_FOR_SLOT,
    LAYER_SLOTS,
    template_layer_entry,
    template_visualizer_section,
)
from cleave.extract import STEM_NAMES
from cleave.paths import repo_root
from cleave.preset_playlist import playlist_at_dir
from cleave.viz.session import LayerRuntime


def repo_root_template_path() -> Path:
    return repo_root() / VIZ_CONFIG_FILENAME


def slot_for_stem(stem: str) -> str:
    for slot, assigned in DEFAULT_STEM_FOR_SLOT.items():
        if assigned == stem:
            return slot
    raise KeyError(stem)


def make_preset_dirs(preset_root: Path) -> None:
    for stem in STEM_NAMES:
        stem_dir = preset_root / stem
        stem_dir.mkdir(parents=True, exist_ok=True)
        (stem_dir / "anchor.milk").write_text("milk", encoding="utf-8")


def layer_configs(preset_root: Path) -> dict[str, LayerConfig]:
    return {
        slot: LayerConfig(
            preset=preset_root / DEFAULT_STEM_FOR_SLOT[slot] / "anchor.milk",
            stem=DEFAULT_STEM_FOR_SLOT[slot],
        )
        for slot in LAYER_SLOTS
    }


def layer_runtimes(
    preset_root: Path,
    **per_slot: dict,
) -> dict[str, LayerRuntime]:
    runtimes: dict[str, LayerRuntime] = {}
    for slot in LAYER_SLOTS:
        stem = DEFAULT_STEM_FOR_SLOT[slot]
        stem_dir = preset_root / stem
        kwargs = per_slot.get(slot, {})
        runtimes[slot] = LayerRuntime(
            playlist=playlist_at_dir(stem_dir, index=0),
            browse_floor=stem_dir,
            **kwargs,
        )
    return runtimes


def write_minimal_config(project_dir: Path, preset_root: Path, **overrides) -> Path:
    project_dir.mkdir(parents=True, exist_ok=True)
    preset_root.mkdir(parents=True, exist_ok=True)

    for stem in STEM_NAMES:
        milk = preset_root / stem / f"{stem}.milk"
        milk.parent.mkdir(parents=True, exist_ok=True)
        milk.write_text(f"; minimal test preset for {stem}\n", encoding="utf-8")

    texture_root = preset_root / "textures"
    texture_root.mkdir(parents=True, exist_ok=True)

    data: dict = {
        "visualizer": template_visualizer_section(name="cleave-test"),
        "paths": {
            "preset_root": str(preset_root),
            "texture_paths": [str(texture_root)],
        },
        "layer_z_order": list(DEFAULT_LAYER_Z_ORDER),
        "layers": {
            slot: {
                **template_layer_entry(slot),
                "preset": (
                    f"{DEFAULT_STEM_FOR_SLOT[slot]}/{DEFAULT_STEM_FOR_SLOT[slot]}.milk"
                ),
            }
            for slot in LAYER_SLOTS
        },
    }
    data.update(overrides)

    config_path = project_dir / VIZ_CONFIG_FILENAME
    with config_path.open("w", encoding="utf-8") as handle:
        dump_yaml(data, handle)

    return config_path
