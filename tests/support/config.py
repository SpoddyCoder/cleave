"""Shared config helpers for unit tests."""

from __future__ import annotations

from pathlib import Path

from cleave.config import VIZ_CONFIG_FILENAME, dump_yaml
from cleave.config_schema import (
    DEFAULT_LAYER_Z_ORDER,
    template_layer_entry,
    template_visualizer_section,
)
from cleave.extract import STEM_NAMES
from cleave.paths import repo_root


def repo_root_template_path() -> Path:
    return repo_root() / VIZ_CONFIG_FILENAME


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
            stem: {
                **template_layer_entry(stem),
                "preset": f"{stem}/{stem}.milk",
            }
            for stem in STEM_NAMES
        },
    }
    data.update(overrides)

    config_path = project_dir / VIZ_CONFIG_FILENAME
    with config_path.open("w", encoding="utf-8") as handle:
        dump_yaml(data, handle)

    return config_path
