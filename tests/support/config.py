"""Shared config helpers for unit tests."""

from __future__ import annotations

from pathlib import Path

from cleave.config import (
    DEFAULT_VIZ_CONFIG_FILENAME,
    PROJECT_VIZ_CONFIG_FILENAME,
    DEFAULT_BEAT_SENSITIVITY,
    DEFAULT_BLEND_MODE,
    DEFAULT_LAYER_Z_ORDER,
    DEFAULT_VISUALIZER_FPS,
    DEFAULT_VISUALIZER_HEIGHT,
    DEFAULT_VISUALIZER_WIDTH,
    LAYER_DEFAULT_SIZE,
    dump_yaml,
)
from cleave.extract import STEM_NAMES
from cleave.paths import repo_root


def repo_root_template_path() -> Path:
    return repo_root() / DEFAULT_VIZ_CONFIG_FILENAME


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
        "visualizer": {
            "name": "cleave-test",
            "width": DEFAULT_VISUALIZER_WIDTH,
            "height": DEFAULT_VISUALIZER_HEIGHT,
            "fps": DEFAULT_VISUALIZER_FPS,
            "beat_sensitivity": DEFAULT_BEAT_SENSITIVITY,
        },
        "paths": {
            "preset_root": str(preset_root),
            "texture_paths": [str(texture_root)],
        },
        "layer_z_order": list(DEFAULT_LAYER_Z_ORDER),
        "layers": {
            stem: {
                "preset": f"{stem}/{stem}.milk",
                "enabled": True,
                "opacity": 1.0,
                "width": LAYER_DEFAULT_SIZE[stem][0],
                "height": LAYER_DEFAULT_SIZE[stem][1],
                "blend_mode": DEFAULT_BLEND_MODE[stem],
            }
            for stem in STEM_NAMES
        },
    }
    data.update(overrides)

    config_path = project_dir / PROJECT_VIZ_CONFIG_FILENAME
    with config_path.open("w", encoding="utf-8") as handle:
        dump_yaml(data, handle)

    return config_path
