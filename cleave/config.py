"""Load Cleave YAML configuration for Milkdrop preset and compositor settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TextIO

if TYPE_CHECKING:
    from cleave.user_config import UserConfig

import yaml

# Avoid PyYAML folding long preset paths across lines (can corrupt mid-token paths).
_YAML_DUMP_WIDTH = 2**31 - 1

from cleave.blend_modes import BlendMode
from cleave.effects.constants import clamp_effect_pct
from cleave.extract import StemSource
from cleave.config_schema import (
    DEFAULT_BLEND_MODE,
    BEAT_SENSITIVITY_MAX,
    BEAT_SENSITIVITY_MIN,
    DEFAULT_BEAT_SENSITIVITY,
    DEFAULT_LAYER_Z_ORDER,
    DEFAULT_PRESET_SWITCHING,
    DEFAULT_PRESET_SWITCHING_ROTATION_SET,
    DEFAULT_PRESET_SWITCHING_SHUFFLE,
    DEFAULT_PRESET_SWITCHING_SHUFFLE_SALT,
    DEFAULT_PRESET_DURATION,
    DEFAULT_SOFT_CUT_DURATION,
    DEFAULT_HARD_CUT_DURATION,
    DEFAULT_HARD_CUT_SENSITIVITY,
    DEFAULT_HARD_CUT_ENABLED,
    DEFAULT_EASTER_EGG,
    DEFAULT_PRESET_START_CLEAN,
    DEFAULT_PRESET_ROOT,
    PresetSwitchingMode,
    PresetSwitchingRotationSet,
    DEFAULT_RENDER_OVERLAY_BACKGROUND_COLOUR,
    DEFAULT_RENDER_OVERLAY_BACKGROUND_MARGIN,
    DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY,
    DEFAULT_RENDER_OVERLAY_BACKGROUND_PADDING,
    DEFAULT_RENDER_OVERLAY_BODY,
    DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
    DEFAULT_RENDER_OVERLAY_BORDER_COLOUR,
    DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
    DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    DEFAULT_RENDER_OVERLAY_FONT,
    DEFAULT_RENDER_OVERLAY_POSITION,
    DEFAULT_RENDER_OVERLAY_SLIDE_DIRECTION,
    DEFAULT_RENDER_OVERLAY_START_DELAY,
    DEFAULT_RENDER_OVERLAY_TEXT_COLOUR,
    DEFAULT_RENDER_OVERLAY_TITLE,
    DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
    DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
    DEFAULT_RENDER_OVERLAY_ANIMATION_TYPE,
    DEFAULT_RENDER_POST_FX_FADE_IN,
    DEFAULT_RENDER_POST_FX_FADE_OUT,
    DEFAULT_TEXTURE_PATHS,
    DEFAULT_TIMELINE_ENABLED,
    DEFAULT_TIMELINE_FADES_ENABLED,
    DEFAULT_TIMELINE_FADE_IN,
    DEFAULT_TIMELINE_FADE_OUT,
    DEFAULT_TIMELINE_PLACEMENT_SNAP,
    TimelinePlacementSnap,
    DEFAULT_HDR_COMPOSITING,
    DEFAULT_RENDER_FPS,
    DEFAULT_RENDER_HEIGHT,
    DEFAULT_RENDER_WIDTH,
    DEFAULT_EDITOR_HEIGHT,
    DEFAULT_UI_FADE_SEC,
    DEFAULT_RESIDUAL_LATENCY_MS,
    DEFAULT_UI_WIDTH,
    DEFAULT_UI_WIDTH_MODE,
    DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE,
    DEFAULT_HIGHLIGHT_ROLLOFF_CURVE,
    DEFAULT_EDITOR_PREVIEW_QUALITY,
    DEFAULT_EDITOR_UPSCALE,
    DEFAULT_EDITOR_WIDTH,
    CHROMA_BOOST_APPLY_MODES,
    CHROMA_BOOST_VARIANTS,
    HIGHLIGHT_ROLLOFF_APPLY_MODES,
    HIGHLIGHT_ROLLOFF_CURVES,
    RENDER_OVERLAY_ANIMATION_TYPES,
    RENDER_OVERLAY_POSITIONS,
    RENDER_OVERLAY_SLIDE_DIRECTIONS,
    UPSCALE_MIN,
    EDITOR_PREVIEW_QUALITIES,
    ChromaBoostApplyMode,
    ChromaBoostVariant,
    HighlightRolloffApplyMode,
    HighlightRolloffCurve,
    RenderOverlayAnimationType,
    RenderOverlayPosition,
    RenderOverlaySlideDirection,
    UiWidthMode,
    EditorPreviewQuality,
    as_mapping,
    clamp_beat_sensitivity,
    clamp_upscale,
    parse_layer_z_order_section,
    parse_layers_section,
    parse_render_section,
    parse_timeline_section,
    parse_project_editor_section,
    require_non_negative_number,
)
from cleave.timeline import TimelineLane
from cleave.timeline_presets.characters import DEFAULT_TIMELINE_PRESET_KIND
from cleave.timeline_presets.crescendo import CrescendoTarget
from cleave.timeline_presets.density import (
    DEFAULT_TIMELINE_PRESET_DENSITY,
    TimelinePresetDensity,
)

VIZ_CONFIG_FILENAME = "cleave-viz.yaml"


@dataclass(frozen=True)
class PathsConfig:
    preset_root: Path
    texture_paths: tuple[Path, ...]


@dataclass(frozen=True)
class LayerConfig:
    preset: Path
    stem: StemSource
    enabled: bool = True
    opacity: float = 1.0
    beat_sensitivity: float | None = None
    effects: dict[str, dict[str, int]] = field(default_factory=dict)
    blend_mode: BlendMode = "black-key"
    locked: bool = False
    preset_switching: PresetSwitchingMode = DEFAULT_PRESET_SWITCHING
    preset_switching_rotation_set: PresetSwitchingRotationSet = DEFAULT_PRESET_SWITCHING_ROTATION_SET
    preset_switching_shuffle: bool = DEFAULT_PRESET_SWITCHING_SHUFFLE
    preset_switching_shuffle_salt: int = DEFAULT_PRESET_SWITCHING_SHUFFLE_SALT
    preset_duration: float = DEFAULT_PRESET_DURATION
    soft_cut_duration: float = DEFAULT_SOFT_CUT_DURATION
    hard_cut_duration: float = DEFAULT_HARD_CUT_DURATION
    hard_cut_sensitivity: float = DEFAULT_HARD_CUT_SENSITIVITY
    hard_cut_enabled: bool = DEFAULT_HARD_CUT_ENABLED
    easter_egg: float = DEFAULT_EASTER_EGG
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN
    preset_switching_presets: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class EditorConfig:
    name: str = "render"
    width: int = DEFAULT_EDITOR_WIDTH
    height: int = DEFAULT_EDITOR_HEIGHT
    upscale: float = DEFAULT_EDITOR_UPSCALE
    beat_sensitivity: float = DEFAULT_BEAT_SENSITIVITY
    preview_quality: EditorPreviewQuality = DEFAULT_EDITOR_PREVIEW_QUALITY
    ui_width_mode: UiWidthMode = DEFAULT_UI_WIDTH_MODE
    ui_width: int = DEFAULT_UI_WIDTH
    ui_fade: float = DEFAULT_UI_FADE_SEC
    residual_latency_ms: int = DEFAULT_RESIDUAL_LATENCY_MS
    @property
    def display_width(self) -> int:
        return max(1, round(self.width * self.upscale))

    @property
    def display_height(self) -> int:
        return max(1, round(self.height * self.upscale))


@dataclass(frozen=True)
class RenderOverlayTextBlockConfig:
    content: str
    font: str
    font_size: int
    colour: tuple[int, int, int]
    background_colour: tuple[int, int, int] | None = None
    margin_bottom: int = 0


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
class RenderOverlayAnimationConfig:
    type: RenderOverlayAnimationType
    slide_direction: RenderOverlaySlideDirection
    start_delay: float
    display_time: float


@dataclass(frozen=True)
class RenderOverlayConfig:
    enabled: bool
    title: RenderOverlayTextBlockConfig
    body: RenderOverlayTextBlockConfig
    animation: RenderOverlayAnimationConfig
    position: RenderOverlayPosition
    background: RenderOverlayBackgroundConfig
    locked: bool = False


@dataclass(frozen=True)
class HighlightRolloffConfig:
    mode: HighlightRolloffApplyMode
    curve: HighlightRolloffCurve
    threshold_pct: int
    ceiling_pct: int
    strength_pct: int
    softness_pct: int
    desaturation_pct: int


@dataclass(frozen=True)
class ChromaBoostConfig:
    mode: ChromaBoostApplyMode
    variant: ChromaBoostVariant
    amount_pct: int


@dataclass(frozen=True)
class RenderPostFxConfig:
    enabled: bool
    fade_in: float
    fade_out: float
    highlight_rolloff: HighlightRolloffConfig
    chroma_boost: ChromaBoostConfig
    locked: bool = False


@dataclass(frozen=True)
class RenderConfig:
    fps: int = DEFAULT_RENDER_FPS
    width: int = DEFAULT_RENDER_WIDTH
    height: int = DEFAULT_RENDER_HEIGHT
    hdr_compositing: bool = DEFAULT_HDR_COMPOSITING
    overlay: RenderOverlayConfig | None = None
    post_fx: RenderPostFxConfig | None = None


@dataclass(frozen=True)
class TimelineFadeGroupConfig:
    enabled: bool = DEFAULT_TIMELINE_FADES_ENABLED
    fade_in: float = DEFAULT_TIMELINE_FADE_IN
    fade_out: float = DEFAULT_TIMELINE_FADE_OUT


@dataclass(frozen=True)
class TimelineFadesConfig:
    song_markers: TimelineFadeGroupConfig = field(
        default_factory=TimelineFadeGroupConfig
    )
    standard: TimelineFadeGroupConfig = field(default_factory=TimelineFadeGroupConfig)


@dataclass(frozen=True)
class TimelinePresetConfig:
    """Staged character / crescendo / density for the timeline preset action."""

    character: str = DEFAULT_TIMELINE_PRESET_KIND
    crescendo: CrescendoTarget | None = None
    density: TimelinePresetDensity = DEFAULT_TIMELINE_PRESET_DENSITY


@dataclass(frozen=True)
class TimelineConfig:
    enabled: bool
    lanes: dict[str, TimelineLane]
    locked: bool = False
    fades: TimelineFadesConfig = field(default_factory=TimelineFadesConfig)
    placement_snap: TimelinePlacementSnap = DEFAULT_TIMELINE_PLACEMENT_SNAP
    preset: TimelinePresetConfig = field(default_factory=TimelinePresetConfig)


@dataclass
class CleaveConfig:
    paths: PathsConfig
    layers: dict[str, LayerConfig]
    editor: EditorConfig
    config_path: Path
    user_config_path: Path
    layer_z_order: list[str] = field(default_factory=lambda: list(DEFAULT_LAYER_Z_ORDER))
    render: RenderConfig | None = None
    timeline: TimelineConfig | None = None

    def layers_in_z_order(self) -> list[tuple[str, LayerConfig]]:
        """Return layers in compositor draw order (bottom-to-top)."""
        return [(name, self.layers[name]) for name in reversed(self.layer_z_order)]


def render_fps(cfg: CleaveConfig) -> int:
    """Offline render output frame rate from config."""
    if cfg.render is not None:
        return cfg.render.fps
    return DEFAULT_RENDER_FPS


def render_output_size(cfg: CleaveConfig) -> tuple[int, int]:
    """Offline render output resolution from config."""
    if cfg.render is not None:
        return cfg.render.width, cfg.render.height
    return DEFAULT_RENDER_WIDTH, DEFAULT_RENDER_HEIGHT


def render_hdr_compositing(cfg: CleaveConfig) -> bool:
    """Whether layer and content FBOs use float HDR compositing."""
    if cfg.render is None:
        return False
    return cfg.render.hdr_compositing


def _expand_path(path: Path | str) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def project_viz_config_path(project_dir: Path) -> Path:
    """Return the default per-project visualizer config path."""
    return project_dir.resolve() / VIZ_CONFIG_FILENAME


def ensure_project_viz_config(project_dir: Path) -> Path:
    """Copy the repo template into *project_dir* when cleave-viz.yaml is missing."""
    from cleave.paths import repo_root

    dst = project_viz_config_path(project_dir)
    if dst.is_file():
        return dst

    src = repo_root() / VIZ_CONFIG_FILENAME
    if not src.is_file():
        raise FileNotFoundError(f"config template not found: {src}")

    with src.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"config template root must be a mapping: {src}")

    editor_section = data.get("editor")
    if not isinstance(editor_section, dict):
        editor_section = {}
        data["editor"] = editor_section
    editor_section["name"] = project_dir.name

    project_dir.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as fh:
        dump_yaml(data, fh)
    return dst


def find_config_path(
    config_path: Path | None = None,
    project_root: Path | None = None,
) -> Path | None:
    """Locate config: CLI override, project cleave-viz.yaml, then repo template."""
    if config_path is not None:
        return _expand_path(config_path)

    root = project_root.resolve() if project_root is not None else Path.cwd()
    local_path = root / VIZ_CONFIG_FILENAME
    if local_path.is_file():
        return local_path.resolve()

    from cleave.paths import repo_root

    template = repo_root() / VIZ_CONFIG_FILENAME
    if template.is_file():
        return template.resolve()

    return None


def _parse_paths(data: dict[str, Any], user_cfg: UserConfig) -> PathsConfig:
    raw_paths = data.get("paths")
    if raw_paths is None:
        paths: dict[str, Any] = {}
    else:
        paths = as_mapping(raw_paths, "paths")

    if "preset_root" in paths:
        preset_root = _expand_path(paths["preset_root"])
    elif user_cfg.preset_root is not None:
        preset_root = user_cfg.preset_root
    else:
        preset_root = _expand_path(DEFAULT_PRESET_ROOT)

    if "texture_paths" in paths:
        raw_texture_paths = paths["texture_paths"]
        if not isinstance(raw_texture_paths, list):
            raise ValueError("paths.texture_paths must be a list")
        if not raw_texture_paths:
            raise ValueError("paths.texture_paths must not be empty")
        texture_paths = tuple(_expand_path(path) for path in raw_texture_paths)
    elif user_cfg.texture_paths is not None:
        texture_paths = user_cfg.texture_paths
    else:
        texture_paths = tuple(_expand_path(path) for path in DEFAULT_TEXTURE_PATHS)

    return PathsConfig(preset_root=preset_root, texture_paths=texture_paths)


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


def _parse_layers(
    data: dict[str, Any], preset_root: Path, cfg_dir: Path | None = None
) -> tuple[dict[str, LayerConfig], "ParseCtx"]:
    from cleave.config_schema import ParseCtx

    ctx = ParseCtx(preset_root=preset_root, cfg_dir=cfg_dir)
    layers = parse_layers_section(data, ctx)
    return layers, ctx


def load_config(
    config_path: Path | None = None,
    project_root: Path | None = None,
    user_config_path: Path | None = None,
) -> CleaveConfig:
    """Load, parse, and validate Cleave YAML configuration."""
    from cleave.user_config import load_user_config

    user_cfg = load_user_config(user_config_path)
    path = find_config_path(config_path, project_root)
    if path is None:
        raise FileNotFoundError(
            f"no {VIZ_CONFIG_FILENAME} found; create one in the project directory"
        )
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")

    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"config root must be a mapping: {path}")

    paths = _parse_paths(data, user_cfg)
    editor = parse_project_editor_section(data, editor=user_cfg.editor)
    render = parse_render_section(data)
    layers, parse_ctx = _parse_layers(data, paths.preset_root, path.parent)
    layer_z_order = parse_layer_z_order_section(data, parse_ctx)
    timeline = parse_timeline_section(data, parse_ctx)
    _validate_presets(layers)

    return CleaveConfig(
        paths=paths,
        layers=layers,
        editor=editor,
        config_path=path,
        user_config_path=user_cfg.path,
        layer_z_order=layer_z_order,
        render=render,
        timeline=timeline,
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
