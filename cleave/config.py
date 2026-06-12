"""Load Cleave YAML configuration for Milkdrop preset and compositor settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TextIO

import yaml

# Avoid PyYAML folding long preset paths across lines (can corrupt mid-token paths).
_YAML_DUMP_WIDTH = 2**31 - 1

from cleave.blend_modes import BLEND_MODES, BlendMode
from cleave.effects.constants import clamp_effect_pct
from cleave.effects.registry import validate_effect_entry
from cleave.extract import STEM_NAMES

DEFAULT_VIZ_CONFIG_FILENAME = "cleave-viz-default.yaml"
PROJECT_VIZ_CONFIG_FILENAME = "cleave-viz.yaml"
GLOBAL_CONFIG_PATH = (
    Path.home() / ".config" / "cleave" / DEFAULT_VIZ_CONFIG_FILENAME
)

DEFAULT_LAYER_Z_ORDER = ("drums", "vocals", "bass", "other")

DEFAULT_BLEND_MODE: dict[str, BlendMode] = {
    "drums": "add",
    "other": "black-key",
    "bass": "black-key",
    "vocals": "black-key",
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
BEAT_SENSITIVITY_MAX = 5.0


def clamp_beat_sensitivity(value: float) -> float:
    """Beat sensitivity range for PCM scaling into projectM (0.0 to 5.0)."""
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
    effects: dict[str, dict[str, int]] = field(default_factory=dict)
    blend_mode: BlendMode = "black-key"
    locked: bool = False


@dataclass(frozen=True)
class VisualizerConfig:
    name: str = "render"
    width: int = DEFAULT_VISUALIZER_WIDTH
    height: int = DEFAULT_VISUALIZER_HEIGHT
    fps: int = DEFAULT_VISUALIZER_FPS
    beat_sensitivity: float = DEFAULT_BEAT_SENSITIVITY


RenderOverlayPosition = Literal[
    "top-left", "top-right", "centre", "bottom-left", "bottom-right"
]

RENDER_OVERLAY_POSITIONS: tuple[RenderOverlayPosition, ...] = (
    "top-left",
    "top-right",
    "centre",
    "bottom-left",
    "bottom-right",
)

DEFAULT_RENDER_OVERLAY_TITLE = "Cleave Final Render"
DEFAULT_RENDER_OVERLAY_BODY = (
    "Place anything you like here\n"
    "Like musician names, year of release etc.\n"
    "As many lines as you like\n"
)
DEFAULT_RENDER_OVERLAY_START_DELAY = 10.0
DEFAULT_RENDER_OVERLAY_DISPLAY_TIME = 30.0
DEFAULT_RENDER_OVERLAY_POSITION: RenderOverlayPosition = "bottom-left"
DEFAULT_RENDER_OVERLAY_FONT_SIZE = 10
DEFAULT_RENDER_OVERLAY_FONT_COLOUR = (255, 170, 0)
DEFAULT_RENDER_OVERLAY_BACKGROUND_MARGIN = 10
DEFAULT_RENDER_OVERLAY_BACKGROUND_PADDING = 10
DEFAULT_RENDER_OVERLAY_BACKGROUND_COLOUR = (34, 51, 68)
DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY = 1.0
DEFAULT_RENDER_OVERLAY_BORDER_WIDTH = 2

DEFAULT_RENDER_POST_FX_FADE_IN = 30.0
DEFAULT_RENDER_POST_FX_FADE_OUT = 4.0


@dataclass(frozen=True)
class RenderOverlayFontConfig:
    size: int
    colour: tuple[int, int, int]


@dataclass(frozen=True)
class RenderOverlayBorderConfig:
    colour: tuple[int, int, int]
    width: int


@dataclass(frozen=True)
class RenderOverlayBackgroundConfig:
    margin: int
    padding: int
    colour: tuple[int, int, int]
    opacity: float
    border: RenderOverlayBorderConfig


@dataclass(frozen=True)
class RenderOverlayConfig:
    enabled: bool
    title: str
    body: str
    start_delay: float
    display_time: float
    position: RenderOverlayPosition
    font: RenderOverlayFontConfig
    background: RenderOverlayBackgroundConfig


@dataclass(frozen=True)
class RenderPostFxConfig:
    enabled: bool
    fade_in: float
    fade_out: float


@dataclass(frozen=True)
class RenderConfig:
    overlay: RenderOverlayConfig | None
    post_fx: RenderPostFxConfig | None


@dataclass(frozen=True)
class CleaveConfig:
    paths: PathsConfig
    layers: dict[str, LayerConfig]
    visualizer: VisualizerConfig
    config_path: Path
    layer_z_order: tuple[str, ...] = DEFAULT_LAYER_Z_ORDER
    render: RenderConfig | None = None

    def layers_in_z_order(self) -> list[tuple[str, LayerConfig]]:
        """Return layers in compositor draw order (bottom-to-top)."""
        return [(name, self.layers[name]) for name in reversed(self.layer_z_order)]


def _expand_path(path: Path | str) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def project_viz_config_path(project_dir: Path) -> Path:
    """Return the default per-project visualizer config path."""
    return project_dir.resolve() / PROJECT_VIZ_CONFIG_FILENAME


def ensure_project_viz_config(project_dir: Path) -> Path:
    """Copy the repo template into *project_dir* when cleave-viz.yaml is missing."""
    from cleave.paths import repo_root

    dst = project_viz_config_path(project_dir)
    if dst.is_file():
        return dst

    src = repo_root() / DEFAULT_VIZ_CONFIG_FILENAME
    if not src.is_file():
        raise FileNotFoundError(f"config template not found: {src}")

    with src.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"config template root must be a mapping: {src}")

    visualizer = data.get("visualizer")
    if not isinstance(visualizer, dict):
        visualizer = {}
        data["visualizer"] = visualizer
    visualizer["name"] = project_dir.name

    project_dir.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as fh:
        dump_yaml(data, fh)
    return dst


def find_config_path(
    config_path: Path | None = None,
    project_root: Path | None = None,
) -> Path | None:
    """Locate config: CLI override, project cleave-viz.yaml, global, then repo template."""
    if config_path is not None:
        return _expand_path(config_path)

    root = project_root.resolve() if project_root is not None else Path.cwd()
    local_path = root / PROJECT_VIZ_CONFIG_FILENAME
    if local_path.is_file():
        return local_path.resolve()

    if GLOBAL_CONFIG_PATH.is_file():
        return GLOBAL_CONFIG_PATH.resolve()

    from cleave.paths import repo_root

    template = repo_root() / DEFAULT_VIZ_CONFIG_FILENAME
    if template.is_file():
        return template.resolve()

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


def _parse_effects(stem: str, layer_raw: dict[str, Any]) -> dict[str, dict[str, int]]:
    raw = layer_raw.get("effects")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"layers.{stem}.effects must be a mapping")

    effects: dict[str, dict[str, int]] = {}
    for effect_id, drivers_raw in raw.items():
        if not isinstance(effect_id, str):
            raise ValueError(f"layers.{stem}.effects keys must be strings")
        if not isinstance(drivers_raw, dict):
            raise ValueError(f"layers.{stem}.effects.{effect_id} must be a mapping")
        for driver_slug, value in drivers_raw.items():
            if not isinstance(driver_slug, str):
                raise ValueError(
                    f"layers.{stem}.effects.{effect_id} driver keys must be strings"
                )
            validate_effect_entry(stem, effect_id, driver_slug)
            pct = clamp_effect_pct(value)
            if pct == 0:
                continue
            effects.setdefault(effect_id, {})[driver_slug] = pct
    return effects


def _parse_hex_colour(value: Any, label: str) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    raw = value.strip()
    if not raw.startswith("#"):
        raise ValueError(f"{label} must be a hex colour starting with #")
    digits = raw[1:]
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    elif len(digits) != 6:
        raise ValueError(f"{label} must be #rgb or #rrggbb")
    try:
        return (
            int(digits[0:2], 16),
            int(digits[2:4], 16),
            int(digits[4:6], 16),
        )
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid hex colour") from exc


def _require_non_negative_number(
    value: Any, label: str, *, as_int: bool = False
) -> float | int:
    try:
        number = int(value) if as_int else float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if number < 0:
        raise ValueError(f"{label} must be non-negative")
    return number


def _parse_render_overlay_position(
    value: Any, label: str = "render.overlay.position"
) -> RenderOverlayPosition:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in RENDER_OVERLAY_POSITIONS:
        allowed = ", ".join(f"'{pos}'" for pos in RENDER_OVERLAY_POSITIONS)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value


def _parse_render_overlay_font(data: dict[str, Any]) -> RenderOverlayFontConfig:
    font = _as_mapping(data.get("font"), "render.overlay.font")
    size = _require_non_negative_number(
        font.get("size", DEFAULT_RENDER_OVERLAY_FONT_SIZE),
        "render.overlay.font.size",
        as_int=True,
    )
    colour_raw = font.get("colour", "#ffaa00")
    colour = _parse_hex_colour(
        "#ffaa00" if colour_raw is None else colour_raw,
        "render.overlay.font.colour",
    )
    return RenderOverlayFontConfig(size=int(size), colour=colour)


def _parse_render_overlay_border(data: dict[str, Any]) -> RenderOverlayBorderConfig:
    border = _as_mapping(data.get("border"), "render.overlay.background.border")
    border_colour_raw = border.get("colour", "#223344")
    colour = _parse_hex_colour(
        "#223344" if border_colour_raw is None else border_colour_raw,
        "render.overlay.background.border.colour",
    )
    width = _require_non_negative_number(
        border.get("width", DEFAULT_RENDER_OVERLAY_BORDER_WIDTH),
        "render.overlay.background.border.width",
        as_int=True,
    )
    return RenderOverlayBorderConfig(colour=colour, width=int(width))


def _parse_render_overlay_background(
    data: dict[str, Any],
) -> RenderOverlayBackgroundConfig:
    background = _as_mapping(data.get("background"), "render.overlay.background")
    margin = _require_non_negative_number(
        background.get("margin", DEFAULT_RENDER_OVERLAY_BACKGROUND_MARGIN),
        "render.overlay.background.margin",
        as_int=True,
    )
    padding = _require_non_negative_number(
        background.get("padding", DEFAULT_RENDER_OVERLAY_BACKGROUND_PADDING),
        "render.overlay.background.padding",
        as_int=True,
    )
    background_colour_raw = background.get("colour", "#223344")
    colour = _parse_hex_colour(
        "#223344" if background_colour_raw is None else background_colour_raw,
        "render.overlay.background.colour",
    )
    opacity = _require_non_negative_number(
        background.get("opacity", DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY),
        "render.overlay.background.opacity",
    )
    return RenderOverlayBackgroundConfig(
        margin=int(margin),
        padding=int(padding),
        colour=colour,
        opacity=float(opacity),
        border=_parse_render_overlay_border(background),
    )


def _parse_render_overlay_section(overlay_map: dict[str, Any]) -> RenderOverlayConfig:
    return RenderOverlayConfig(
        enabled=bool(overlay_map.get("enabled", True)),
        title=str(overlay_map.get("title", DEFAULT_RENDER_OVERLAY_TITLE)),
        body=str(overlay_map.get("body", DEFAULT_RENDER_OVERLAY_BODY)),
        start_delay=float(
            _require_non_negative_number(
                overlay_map.get("start_delay", DEFAULT_RENDER_OVERLAY_START_DELAY),
                "render.overlay.start_delay",
            )
        ),
        display_time=float(
            _require_non_negative_number(
                overlay_map.get("display_time", DEFAULT_RENDER_OVERLAY_DISPLAY_TIME),
                "render.overlay.display_time",
            )
        ),
        position=_parse_render_overlay_position(
            overlay_map.get("position", DEFAULT_RENDER_OVERLAY_POSITION)
        ),
        font=_parse_render_overlay_font(overlay_map),
        background=_parse_render_overlay_background(overlay_map),
    )


def _parse_render_post_fx_section(
    post_fx_map: dict[str, Any],
) -> RenderPostFxConfig:
    return RenderPostFxConfig(
        enabled=bool(post_fx_map.get("enabled", True)),
        fade_in=float(
            _require_non_negative_number(
                post_fx_map.get("fade_in", DEFAULT_RENDER_POST_FX_FADE_IN),
                "render.post_fx.fade_in",
            )
        ),
        fade_out=float(
            _require_non_negative_number(
                post_fx_map.get("fade_out", DEFAULT_RENDER_POST_FX_FADE_OUT),
                "render.post_fx.fade_out",
            )
        ),
    )


def _parse_render(data: dict[str, Any]) -> RenderConfig | None:
    render = data.get("render")
    if render is None:
        return None
    render_map = _as_mapping(render, "render")
    overlay_raw = render_map.get("overlay")
    post_fx_raw = render_map.get("post_fx")
    if overlay_raw is None and post_fx_raw is None:
        return None
    overlay = (
        _parse_render_overlay_section(_as_mapping(overlay_raw, "render.overlay"))
        if overlay_raw is not None
        else None
    )
    post_fx = (
        _parse_render_post_fx_section(_as_mapping(post_fx_raw, "render.post_fx"))
        if post_fx_raw is not None
        else None
    )
    return RenderConfig(overlay=overlay, post_fx=post_fx)


def _parse_visualizer(data: dict[str, Any]) -> VisualizerConfig:
    visualizer = _as_mapping(data.get("visualizer"), "visualizer")
    return VisualizerConfig(
        name=str(visualizer.get("name", "render")),
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
            effects=_parse_effects(name, layer_raw),
            blend_mode=_parse_blend_mode(name, layer_raw),
            locked=bool(layer_raw.get("locked", False)),
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
            f"no {PROJECT_VIZ_CONFIG_FILENAME} found; create one in the project "
            f"directory or at {GLOBAL_CONFIG_PATH}"
        )
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")

    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"config root must be a mapping: {path}")

    paths = _parse_paths(data)
    visualizer = _parse_visualizer(data)
    render = _parse_render(data)
    layer_z_order = _parse_layer_z_order(data)
    layers = _parse_layers(data, paths.preset_root)
    _validate_presets(layers)

    return CleaveConfig(
        paths=paths,
        layers=layers,
        visualizer=visualizer,
        config_path=path,
        layer_z_order=layer_z_order,
        render=render,
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
