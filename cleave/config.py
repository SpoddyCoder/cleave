"""Load Cleave YAML configuration for Milkdrop preset and compositor settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

import yaml

# Avoid PyYAML folding long preset paths across lines (can corrupt mid-token paths).
_YAML_DUMP_WIDTH = 2**31 - 1

from cleave.extract import STEM_NAMES
from cleave.gl_compositor import BLEND_MODES, BlendMode

CONFIG_FILENAME = "cleave.config.yaml"
GLOBAL_CONFIG_PATH = Path.home() / ".config" / "cleave" / CONFIG_FILENAME

DEFAULT_LAYER_Z_ORDER = ("drums", "vocals", "bass", "other")

DEFAULT_BLEND_MODE: dict[str, BlendMode] = {
    "drums": "add",
    "other": "alpha",
    "bass": "alpha",
    "vocals": "alpha",
}

LAYER_DEFAULT_SIZE: dict[str, tuple[int, int]] = {
    "other": (640, 360),
    "bass": (960, 540),
    "vocals": (960, 540),
    "drums": (1280, 720),
}

DEFAULT_PRESET_ROOT = Path("~/.local/share/cleave/presets")
DEFAULT_TEXTURE_PATHS = (Path("~/.local/share/cleave/textures"),)

DEFAULT_VISUALIZER_WIDTH = 1280
DEFAULT_VISUALIZER_HEIGHT = 720
DEFAULT_VISUALIZER_FPS = 30
DEFAULT_BEAT_SENSITIVITY = 1.0
BEAT_SENSITIVITY_MIN = 0.0
BEAT_SENSITIVITY_MAX = 2.0


def clamp_beat_sensitivity(value: float) -> float:
    """Match libprojectM beat sensitivity range (0.0 to 2.0)."""
    return max(BEAT_SENSITIVITY_MIN, min(BEAT_SENSITIVITY_MAX, float(value)))


@dataclass(frozen=True)
class PathsConfig:
    preset_root: Path
    texture_paths: tuple[Path, ...]


@dataclass(frozen=True)
class LayerConfig:
    preset: Path
    enabled: bool = True
    opacity: float = 1.0
    width: int = 1280
    height: int = 720
    beat_sensitivity: float | None = None
    blend_mode: BlendMode = "alpha"


@dataclass(frozen=True)
class VisualizerConfig:
    width: int = DEFAULT_VISUALIZER_WIDTH
    height: int = DEFAULT_VISUALIZER_HEIGHT
    fps: int = DEFAULT_VISUALIZER_FPS
    beat_sensitivity: float = DEFAULT_BEAT_SENSITIVITY


@dataclass(frozen=True)
class CleaveConfig:
    paths: PathsConfig
    layers: dict[str, LayerConfig]
    visualizer: VisualizerConfig
    config_path: Path
    layer_z_order: tuple[str, ...] = DEFAULT_LAYER_Z_ORDER

    def layers_in_z_order(self) -> list[tuple[str, LayerConfig]]:
        """Return layers in compositor draw order (bottom-to-top)."""
        return [(name, self.layers[name]) for name in reversed(self.layer_z_order)]


def _expand_path(path: Path | str) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def find_config_path(
    config_path: Path | None = None,
    project_root: Path | None = None,
) -> Path | None:
    """Locate cleave.config.yaml using CLI override, project root, then global path."""
    if config_path is not None:
        return _expand_path(config_path)

    root = project_root.resolve() if project_root is not None else Path.cwd()
    local_path = root / CONFIG_FILENAME
    if local_path.is_file():
        return local_path.resolve()

    if GLOBAL_CONFIG_PATH.is_file():
        return GLOBAL_CONFIG_PATH.resolve()

    return None


def _resolve_preset(preset: str | Path, preset_root: Path) -> Path:
    path = Path(os.path.expanduser(str(preset)))
    if path.is_absolute():
        return path.resolve()
    return (preset_root / path).resolve()


def _as_mapping(data: Any, label: str) -> dict[str, Any]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a mapping")
    return data


def _parse_paths(data: dict[str, Any]) -> PathsConfig:
    paths = _as_mapping(data.get("paths"), "paths")
    preset_root = _expand_path(paths.get("preset_root", DEFAULT_PRESET_ROOT))

    raw_texture_paths = paths.get("texture_paths", DEFAULT_TEXTURE_PATHS)
    if not isinstance(raw_texture_paths, list):
        raise ValueError("paths.texture_paths must be a list")
    if not raw_texture_paths:
        raise ValueError("paths.texture_paths must not be empty")

    texture_paths = tuple(_expand_path(path) for path in raw_texture_paths)
    return PathsConfig(preset_root=preset_root, texture_paths=texture_paths)


def _parse_layer_z_order(data: dict[str, Any]) -> tuple[str, ...]:
    raw = data.get("layer_z_order")
    if raw is None:
        return DEFAULT_LAYER_Z_ORDER
    if not isinstance(raw, list):
        raise ValueError("layer_z_order must be a list")
    if len(raw) != len(STEM_NAMES):
        raise ValueError(
            f"layer_z_order must contain exactly {len(STEM_NAMES)} entries"
        )
    if set(raw) != set(STEM_NAMES):
        raise ValueError(
            f"layer_z_order must contain each of {', '.join(STEM_NAMES)} exactly once"
        )
    return tuple(raw)


def _parse_blend_mode(name: str, layer_raw: dict[str, Any]) -> BlendMode:
    raw = layer_raw.get("blend_mode")
    if raw is None:
        return DEFAULT_BLEND_MODE[name]
    if raw not in BLEND_MODES:
        allowed = ", ".join(f"'{mode}'" for mode in BLEND_MODES)
        raise ValueError(f"layers.{name}.blend_mode must be one of: {allowed}")
    return raw


def _parse_visualizer(data: dict[str, Any]) -> VisualizerConfig:
    visualizer = _as_mapping(data.get("visualizer"), "visualizer")
    return VisualizerConfig(
        width=int(visualizer.get("width", DEFAULT_VISUALIZER_WIDTH)),
        height=int(visualizer.get("height", DEFAULT_VISUALIZER_HEIGHT)),
        fps=int(visualizer.get("fps", DEFAULT_VISUALIZER_FPS)),
        beat_sensitivity=clamp_beat_sensitivity(
            visualizer.get("beat_sensitivity", DEFAULT_BEAT_SENSITIVITY)
        ),
    )


def _parse_layers(data: dict[str, Any], preset_root: Path) -> dict[str, LayerConfig]:
    layers_raw = _as_mapping(data.get("layers"), "layers")
    unknown = sorted(set(layers_raw) - set(STEM_NAMES))
    if unknown:
        raise ValueError(
            f"unknown layer keys in config (expected {', '.join(STEM_NAMES)}): "
            + ", ".join(unknown)
        )

    missing = [name for name in STEM_NAMES if name not in layers_raw]
    if missing:
        raise ValueError(f"missing layer config for: {', '.join(missing)}")

    layers: dict[str, LayerConfig] = {}
    for name in STEM_NAMES:
        layer_raw = _as_mapping(layers_raw[name], f"layers.{name}")
        preset_raw = layer_raw.get("preset")
        if not preset_raw:
            raise ValueError(f"layers.{name}.preset is required")

        default_width, default_height = LAYER_DEFAULT_SIZE[name]
        beat_raw = layer_raw.get("beat_sensitivity")
        layers[name] = LayerConfig(
            preset=_resolve_preset(preset_raw, preset_root),
            enabled=bool(layer_raw.get("enabled", True)),
            opacity=float(layer_raw.get("opacity", 1.0)),
            width=int(layer_raw.get("width", default_width)),
            height=int(layer_raw.get("height", default_height)),
            beat_sensitivity=clamp_beat_sensitivity(beat_raw)
            if beat_raw is not None
            else None,
            blend_mode=_parse_blend_mode(name, layer_raw),
        )
    return layers


def _validate_presets(layers: dict[str, LayerConfig]) -> None:
    missing: list[str] = []
    invalid: list[str] = []

    for name, layer in layers.items():
        preset = layer.preset
        if not preset.exists():
            missing.append(f"{name}: {preset}")
            continue
        if preset.is_dir():
            continue
        if preset.is_file():
            if preset.suffix.lower() != ".milk":
                invalid.append(f"{name}: {preset}")
            continue
        invalid.append(f"{name}: {preset}")

    if missing:
        raise FileNotFoundError(
            "missing preset anchor(s):\n  " + "\n  ".join(missing)
        )
    if invalid:
        raise ValueError(
            "preset must be a .milk file or directory:\n  "
            + "\n  ".join(invalid)
        )


def load_config(
    config_path: Path | None = None,
    project_root: Path | None = None,
) -> CleaveConfig:
    """Load, parse, and validate Cleave YAML configuration."""
    path = find_config_path(config_path, project_root)
    if path is None:
        raise FileNotFoundError(
            f"no {CONFIG_FILENAME} found; create one in the project root or at "
            f"{GLOBAL_CONFIG_PATH}"
        )
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")

    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"config root must be a mapping: {path}")

    paths = _parse_paths(data)
    visualizer = _parse_visualizer(data)
    layer_z_order = _parse_layer_z_order(data)
    layers = _parse_layers(data, paths.preset_root)
    _validate_presets(layers)

    return CleaveConfig(
        paths=paths,
        layers=layers,
        visualizer=visualizer,
        config_path=path,
        layer_z_order=layer_z_order,
    )


def dump_yaml(data: Any, fh: TextIO) -> None:
    """Write Cleave config YAML without folding long scalar values."""
    yaml.safe_dump(
        data,
        fh,
        default_flow_style=False,
        sort_keys=False,
        width=_YAML_DUMP_WIDTH,
    )
