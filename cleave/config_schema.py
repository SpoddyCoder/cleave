"""Single source of truth for Cleave YAML parse, serialize, and defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, TypeVar

from cleave.blend_modes import BLEND_MODES, BlendMode
from cleave.effects.constants import clamp_effect_pct
from cleave.effects.registry import validate_effect_entry
from cleave.extract import STEM_NAMES
from cleave.timeline import TimelineCue

# --- Visualizer defaults ---

DEFAULT_VISUALIZER_WIDTH = 1280
DEFAULT_VISUALIZER_HEIGHT = 720
DEFAULT_VISUALIZER_FPS = 30
DEFAULT_VISUALIZER_WARMUP_SEC = 3.0
DEFAULT_VISUALIZER_UPSCALE = 1.0
UPSCALE_MIN = 1.0
DEFAULT_BEAT_SENSITIVITY = 1.0
BEAT_SENSITIVITY_MIN = 0.0
BEAT_SENSITIVITY_MAX = 5.0

# --- Layer defaults ---

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

# --- Render overlay defaults ---

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
    "Edit the cleave-viz.yaml to modify this message, colours etc."
)
DEFAULT_RENDER_OVERLAY_START_DELAY = 10.0
DEFAULT_RENDER_OVERLAY_DISPLAY_TIME = 30.0
DEFAULT_RENDER_OVERLAY_POSITION: RenderOverlayPosition = "bottom-left"
DEFAULT_RENDER_OVERLAY_FONT = "monospace"
DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE = 24
DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM = 10
DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE = 18
DEFAULT_RENDER_OVERLAY_TEXT_COLOUR = (255, 255, 255)
DEFAULT_RENDER_OVERLAY_BACKGROUND_MARGIN = 40
DEFAULT_RENDER_OVERLAY_BACKGROUND_PADDING = 20
DEFAULT_RENDER_OVERLAY_BACKGROUND_COLOUR = (0, 0, 0)
DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY = 0.7
DEFAULT_RENDER_OVERLAY_BORDER_COLOUR = (255, 255, 255)
DEFAULT_RENDER_OVERLAY_BORDER_WIDTH = 4

# --- Render post-FX defaults ---

DEFAULT_RENDER_POST_FX_FADE_IN = 30.0
DEFAULT_RENDER_POST_FX_FADE_OUT = 4.0

# --- Timeline defaults ---

DEFAULT_TIMELINE_ENABLED = True

FieldSource = Literal["cfg", "session", "both"]
T = TypeVar("T")


def clamp_upscale(value: float) -> float:
    return max(UPSCALE_MIN, float(value))


def clamp_beat_sensitivity(value: float) -> float:
    return max(BEAT_SENSITIVITY_MIN, min(BEAT_SENSITIVITY_MAX, float(value)))


@dataclass(frozen=True)
class FieldDescriptor:
    """Leaf field: YAML key, default, parse/dump, and persistence source."""

    yaml_key: str
    default: Any
    source: FieldSource
    parse: Callable[[Any, "ParseCtx", str], Any]
    dump: Callable[[Any, "PersistCtx"], Any]
    yaml_alt_keys: tuple[str, ...] = ()


@dataclass
class ParseCtx:
    preset_root: Path | None = None


@dataclass
class PersistCtx:
    cfg: Any
    session: Any


def _expand_path(path: Path | str) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def as_mapping(data: Any, label: str) -> dict[str, Any]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a mapping")
    return data


def parse_hex_colour(value: Any, label: str) -> tuple[int, int, int]:
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


def require_non_negative_number(
    value: Any, label: str, *, as_int: bool = False
) -> float | int:
    try:
        number = int(value) if as_int else float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if number < 0:
        raise ValueError(f"{label} must be non-negative")
    return number


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _resolve_preset(preset: str | Path, preset_root: Path) -> Path:
    path = Path(os.path.expanduser(str(preset)))
    if path.is_absolute():
        return path.resolve()
    return (preset_root / path).resolve()


def _parse_scalar(raw: Any, ctx: ParseCtx, label: str) -> Any:
    return raw


def _dump_scalar(value: Any, ctx: PersistCtx) -> Any:
    return value


def _parse_upscale(raw: Any, ctx: ParseCtx, label: str) -> float:
    try:
        upscale = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if upscale < UPSCALE_MIN:
        raise ValueError(f"{label} must be >= {UPSCALE_MIN}")
    return clamp_upscale(upscale)


def _parse_warmup_sec(raw: Any, ctx: ParseCtx, label: str) -> float:
    try:
        warmup_sec = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if warmup_sec < 0:
        raise ValueError(f"{label} must be >= 0")
    return warmup_sec


def _parse_beat_sensitivity(raw: Any, ctx: ParseCtx, label: str) -> float:
    return clamp_beat_sensitivity(raw)


def _parse_render_overlay_position(
    value: Any, ctx: ParseCtx, label: str = "render.overlay.position"
) -> RenderOverlayPosition:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in RENDER_OVERLAY_POSITIONS:
        allowed = ", ".join(f"'{pos}'" for pos in RENDER_OVERLAY_POSITIONS)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value


VISUALIZER_FIELDS: tuple[FieldDescriptor, ...] = (
    FieldDescriptor(
        "width",
        DEFAULT_VISUALIZER_WIDTH,
        "cfg",
        lambda raw, _ctx, _label: int(raw),
        _dump_scalar,
    ),
    FieldDescriptor(
        "height",
        DEFAULT_VISUALIZER_HEIGHT,
        "cfg",
        lambda raw, _ctx, _label: int(raw),
        _dump_scalar,
    ),
    FieldDescriptor(
        "upscale",
        DEFAULT_VISUALIZER_UPSCALE,
        "cfg",
        _parse_upscale,
        lambda value, _ctx: clamp_upscale(value),
    ),
    FieldDescriptor(
        "fps",
        DEFAULT_VISUALIZER_FPS,
        "cfg",
        lambda raw, _ctx, _label: int(raw),
        _dump_scalar,
    ),
    FieldDescriptor(
        "warmup_sec",
        DEFAULT_VISUALIZER_WARMUP_SEC,
        "cfg",
        _parse_warmup_sec,
        _dump_scalar,
    ),
    FieldDescriptor(
        "beat_sensitivity",
        DEFAULT_BEAT_SENSITIVITY,
        "cfg",
        _parse_beat_sensitivity,
        lambda value, _ctx: clamp_beat_sensitivity(value),
    ),
)

RENDER_POST_FX_FIELDS: tuple[FieldDescriptor, ...] = (
    FieldDescriptor(
        "enabled",
        True,
        "session",
        lambda raw, _ctx, _label: bool(raw),
        _dump_scalar,
    ),
    FieldDescriptor(
        "fade_in",
        DEFAULT_RENDER_POST_FX_FADE_IN,
        "session",
        lambda raw, ctx, label: float(require_non_negative_number(raw, label)),
        _dump_scalar,
    ),
    FieldDescriptor(
        "fade_out",
        DEFAULT_RENDER_POST_FX_FADE_OUT,
        "session",
        lambda raw, ctx, label: float(require_non_negative_number(raw, label)),
        _dump_scalar,
    ),
)


def _parse_field(
    parent: dict[str, Any],
    field: FieldDescriptor,
    ctx: ParseCtx,
    label: str,
) -> Any:
    raw = parent.get(field.yaml_key)
    if raw is None:
        for alt in field.yaml_alt_keys:
            raw = parent.get(alt)
            if raw is not None:
                break
    if raw is None:
        return field.default
    return field.parse(raw, ctx, f"{label}.{field.yaml_key}")


def _dump_fields(
    fields: tuple[FieldDescriptor, ...],
    values: dict[str, Any],
    ctx: PersistCtx,
) -> dict[str, Any]:
    return {field.yaml_key: field.dump(values[field.yaml_key], ctx) for field in fields}


def parse_visualizer_section(data: dict[str, Any]) -> Any:
    from cleave.config import VisualizerConfig

    visualizer = as_mapping(data.get("visualizer"), "visualizer")
    ctx = ParseCtx()
    parsed: dict[str, Any] = {}
    for field in VISUALIZER_FIELDS:
        parsed[field.yaml_key] = _parse_field(
            visualizer, field, ctx, "visualizer"
        )
    return VisualizerConfig(
        name=str(visualizer.get("name", "render")),
        width=parsed["width"],
        height=parsed["height"],
        upscale=parsed["upscale"],
        fps=parsed["fps"],
        warmup_sec=parsed["warmup_sec"],
        beat_sensitivity=parsed["beat_sensitivity"],
    )


def persist_visualizer(ctx: PersistCtx) -> dict[str, Any]:
    vis = ctx.cfg.visualizer
    values = {
        "width": vis.width,
        "height": vis.height,
        "upscale": vis.upscale,
        "fps": vis.fps,
        "warmup_sec": vis.warmup_sec,
        "beat_sensitivity": vis.beat_sensitivity,
    }
    return _dump_fields(VISUALIZER_FIELDS, values, ctx)


def parse_layer_z_order_section(data: dict[str, Any]) -> tuple[str, ...]:
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


def persist_layer_z_order(ctx: PersistCtx) -> list[str]:
    from cleave.extract import STEM_NAMES

    order = ctx.session.layer_z_order
    cfg_order = list(ctx.cfg.layer_z_order)
    if len(order) == len(cfg_order) and set(order) == set(cfg_order):
        return list(order)
    if len(order) == len(STEM_NAMES) and set(order) == set(STEM_NAMES):
        return list(order)
    return cfg_order


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


def sparse_effects(
    effects: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]] | None:
    out: dict[str, dict[str, int]] = {}
    for effect_id, drivers in effects.items():
        sparse_drivers: dict[str, int] = {}
        for driver_slug, pct in drivers.items():
            clamped = clamp_effect_pct(pct)
            if clamped != 0:
                sparse_drivers[driver_slug] = clamped
        if sparse_drivers:
            out[effect_id] = sparse_drivers
    return out or None


def parse_layers_section(data: dict[str, Any], ctx: ParseCtx) -> dict[str, Any]:
    from cleave.config import LayerConfig

    if ctx.preset_root is None:
        raise ValueError("preset_root required to parse layers")
    preset_root = ctx.preset_root

    layers_raw = as_mapping(data.get("layers"), "layers")
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
        layer_raw = as_mapping(layers_raw[name], f"layers.{name}")
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


def persist_layers(ctx: PersistCtx) -> dict[str, dict[str, Any]]:
    from cleave.preset_playlist import to_config_relative

    preset_root = ctx.cfg.paths.preset_root
    layers_out: dict[str, dict[str, Any]] = {}
    global_beat = ctx.cfg.visualizer.beat_sensitivity

    for name in STEM_NAMES:
        layer_cfg = ctx.cfg.layers[name]
        if name in ctx.session.layers:
            runtime = ctx.session.layers[name]
            preset = runtime.playlist.config_preset_path(preset_root)
            opacity = runtime.opacity_pct / 100.0
            enabled = runtime.enabled
            blend_mode = runtime.blend_mode
            beat = runtime.beat_sensitivity
            effects = runtime.effects
            locked = runtime.locked
        else:
            preset = to_config_relative(layer_cfg.preset, preset_root)
            opacity = layer_cfg.opacity
            enabled = layer_cfg.enabled
            blend_mode = layer_cfg.blend_mode
            locked = layer_cfg.locked
            effects = layer_cfg.effects
            beat = (
                layer_cfg.beat_sensitivity
                if layer_cfg.beat_sensitivity is not None
                else global_beat
            )

        layer_out: dict[str, Any] = {
            "preset": preset,
            "enabled": enabled,
            "opacity": opacity,
            "width": layer_cfg.width,
            "height": layer_cfg.height,
            "blend_mode": blend_mode,
            "locked": locked,
        }
        beat = clamp_beat_sensitivity(beat)
        if beat != global_beat:
            layer_out["beat_sensitivity"] = beat
        sparse = sparse_effects(effects)
        if sparse is not None:
            layer_out["effects"] = sparse
        layers_out[name] = layer_out

    return layers_out


def _default_render_overlay_title_block() -> Any:
    from cleave.config import RenderOverlayTextBlockConfig

    return RenderOverlayTextBlockConfig(
        content=DEFAULT_RENDER_OVERLAY_TITLE,
        font=DEFAULT_RENDER_OVERLAY_FONT,
        font_size=DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
        colour=DEFAULT_RENDER_OVERLAY_TEXT_COLOUR,
        margin_bottom=DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
    )


def _default_render_overlay_body_block() -> Any:
    from cleave.config import RenderOverlayTextBlockConfig

    return RenderOverlayTextBlockConfig(
        content=DEFAULT_RENDER_OVERLAY_BODY,
        font=DEFAULT_RENDER_OVERLAY_FONT,
        font_size=DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
        colour=DEFAULT_RENDER_OVERLAY_TEXT_COLOUR,
    )


def _parse_render_overlay_text_block_colour(
    block: dict[str, Any], label_prefix: str
) -> tuple[int, int, int]:
    colour_raw = block.get("font-colour")
    if colour_raw is None:
        colour_raw = block.get("colour")
    if colour_raw is None:
        return DEFAULT_RENDER_OVERLAY_TEXT_COLOUR
    return parse_hex_colour(colour_raw, f"{label_prefix}.font-colour")


def _parse_render_overlay_text_block_background_colour(
    block: dict[str, Any], label_prefix: str
) -> tuple[int, int, int] | None:
    if "background-colour" not in block:
        return None
    raw = block.get("background-colour")
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip() == "":
        return None
    return parse_hex_colour(raw, f"{label_prefix}.background-colour")


def _parse_render_overlay_text_block(
    overlay_map: dict[str, Any],
    key: str,
    label_prefix: str,
    *,
    default_font_size: int,
    default_margin_bottom: int = 0,
) -> Any:
    from cleave.config import RenderOverlayTextBlockConfig

    block = as_mapping(overlay_map.get(key), label_prefix)
    content_raw = block.get("content", "")
    content = str(content_raw)
    if content.endswith("\n"):
        content = content[:-1]
    font_raw = block.get("font", DEFAULT_RENDER_OVERLAY_FONT)
    if not isinstance(font_raw, str) or not font_raw.strip():
        raise ValueError(f"{label_prefix}.font must be a non-empty string")
    font = font_raw.strip()
    font_size = require_non_negative_number(
        block.get("font-size", default_font_size),
        f"{label_prefix}.font-size",
        as_int=True,
    )
    colour = _parse_render_overlay_text_block_colour(block, label_prefix)
    background_colour = _parse_render_overlay_text_block_background_colour(
        block, label_prefix
    )
    margin_bottom = require_non_negative_number(
        block.get("margin-bottom", default_margin_bottom),
        f"{label_prefix}.margin-bottom",
        as_int=True,
    )
    return RenderOverlayTextBlockConfig(
        content=content,
        font=font,
        font_size=int(font_size),
        colour=colour,
        background_colour=background_colour,
        margin_bottom=int(margin_bottom),
    )


def _parse_render_overlay_border(data: dict[str, Any]) -> Any:
    from cleave.config import RenderOverlayBorderConfig

    border = as_mapping(data.get("border"), "render.overlay.background.border")
    border_colour_raw = border.get("colour", "#ffffff")
    colour = parse_hex_colour(
        "#ffffff" if border_colour_raw is None else border_colour_raw,
        "render.overlay.background.border.colour",
    )
    width = require_non_negative_number(
        border.get("width", DEFAULT_RENDER_OVERLAY_BORDER_WIDTH),
        "render.overlay.background.border.width",
        as_int=True,
    )
    return RenderOverlayBorderConfig(colour=colour, width=int(width))


def _parse_render_overlay_background(data: dict[str, Any]) -> Any:
    from cleave.config import RenderOverlayBackgroundConfig

    background = as_mapping(data.get("background"), "render.overlay.background")
    margin = require_non_negative_number(
        background.get("margin", DEFAULT_RENDER_OVERLAY_BACKGROUND_MARGIN),
        "render.overlay.background.margin",
        as_int=True,
    )
    padding = require_non_negative_number(
        background.get("padding", DEFAULT_RENDER_OVERLAY_BACKGROUND_PADDING),
        "render.overlay.background.padding",
        as_int=True,
    )
    background_colour_raw = background.get("colour", "#000000")
    colour = parse_hex_colour(
        "#000000" if background_colour_raw is None else background_colour_raw,
        "render.overlay.background.colour",
    )
    opacity = require_non_negative_number(
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


def _parse_render_overlay_section(overlay_map: dict[str, Any]) -> Any:
    from cleave.config import RenderOverlayConfig

    title = (
        _parse_render_overlay_text_block(
            overlay_map,
            "title",
            "render.overlay.title",
            default_font_size=DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
            default_margin_bottom=DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        )
        if overlay_map.get("title") is not None
        else _default_render_overlay_title_block()
    )
    body = (
        _parse_render_overlay_text_block(
            overlay_map,
            "body",
            "render.overlay.body",
            default_font_size=DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
        )
        if overlay_map.get("body") is not None
        else _default_render_overlay_body_block()
    )
    return RenderOverlayConfig(
        enabled=bool(overlay_map.get("enabled", True)),
        title=title,
        body=body,
        start_delay=float(
            require_non_negative_number(
                overlay_map.get("start_delay", DEFAULT_RENDER_OVERLAY_START_DELAY),
                "render.overlay.start_delay",
            )
        ),
        display_time=float(
            require_non_negative_number(
                overlay_map.get("display_time", DEFAULT_RENDER_OVERLAY_DISPLAY_TIME),
                "render.overlay.display_time",
            )
        ),
        position=_parse_render_overlay_position(
            overlay_map.get("position", DEFAULT_RENDER_OVERLAY_POSITION),
            ParseCtx(),
            "render.overlay.position",
        ),
        background=_parse_render_overlay_background(overlay_map),
    )


def _parse_render_post_fx_section(post_fx_map: dict[str, Any]) -> Any:
    from cleave.config import RenderPostFxConfig

    ctx = ParseCtx()
    parsed: dict[str, Any] = {}
    for field in RENDER_POST_FX_FIELDS:
        parsed[field.yaml_key] = _parse_field(
            post_fx_map, field, ctx, "render.post_fx"
        )
    return RenderPostFxConfig(
        enabled=parsed["enabled"],
        fade_in=parsed["fade_in"],
        fade_out=parsed["fade_out"],
    )


def parse_render_section(data: dict[str, Any]) -> Any | None:
    from cleave.config import RenderConfig

    render = data.get("render")
    if render is None:
        return None
    render_map = as_mapping(render, "render")
    overlay_raw = render_map.get("overlay")
    post_fx_raw = render_map.get("post_fx")
    if overlay_raw is None and post_fx_raw is None:
        return None
    overlay = (
        _parse_render_overlay_section(as_mapping(overlay_raw, "render.overlay"))
        if overlay_raw is not None
        else None
    )
    post_fx = (
        _parse_render_post_fx_section(as_mapping(post_fx_raw, "render.post_fx"))
        if post_fx_raw is not None
        else None
    )
    return RenderConfig(overlay=overlay, post_fx=post_fx)


def default_render_overlay_config() -> Any:
    from cleave.config import (
        RenderOverlayBackgroundConfig,
        RenderOverlayBorderConfig,
        RenderOverlayConfig,
    )

    return RenderOverlayConfig(
        enabled=True,
        title=_default_render_overlay_title_block(),
        body=_default_render_overlay_body_block(),
        start_delay=DEFAULT_RENDER_OVERLAY_START_DELAY,
        display_time=DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
        position=DEFAULT_RENDER_OVERLAY_POSITION,
        background=RenderOverlayBackgroundConfig(
            margin=DEFAULT_RENDER_OVERLAY_BACKGROUND_MARGIN,
            padding=DEFAULT_RENDER_OVERLAY_BACKGROUND_PADDING,
            colour=DEFAULT_RENDER_OVERLAY_BACKGROUND_COLOUR,
            opacity=DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY,
            border=RenderOverlayBorderConfig(
                colour=DEFAULT_RENDER_OVERLAY_BORDER_COLOUR,
                width=DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
            ),
        ),
    )


def render_overlay_base(cfg: Any) -> Any:
    if cfg.render is not None and cfg.render.overlay is not None:
        return cfg.render.overlay
    return default_render_overlay_config()


def _text_block_to_yaml(
    block: Any,
    *,
    font: str,
    font_size: int,
    colour_key: str,
    margin_bottom: int | None = None,
) -> dict[str, Any]:
    content = block.content
    if "\n" in content:
        content = content + "\n"
    out: dict[str, Any] = {
        "content": content,
        "font": font,
        "font-size": font_size,
        colour_key: rgb_to_hex(block.colour),
    }
    if block.background_colour is not None:
        out["background-colour"] = rgb_to_hex(block.background_colour)
    if margin_bottom is not None:
        out["margin-bottom"] = margin_bottom
    return out


def persist_render(ctx: PersistCtx) -> dict[str, Any]:
    runtime = ctx.session.render_overlay
    base = render_overlay_base(ctx.cfg)
    bg = base.background
    runtime_pp = ctx.session.render_post_fx
    overlay: dict[str, Any] = {
        "enabled": runtime.enabled,
        "title": _text_block_to_yaml(
            base.title,
            font=runtime.title_font,
            font_size=runtime.title_font_size,
            colour_key="font-colour",
            margin_bottom=runtime.title_margin_bottom,
        ),
        "body": _text_block_to_yaml(
            base.body,
            font=runtime.body_font,
            font_size=runtime.body_font_size,
            colour_key="colour",
        ),
        "start_delay": runtime.start_delay,
        "display_time": runtime.display_time,
        "position": runtime.position,
        "background": {
            "margin": bg.margin,
            "padding": bg.padding,
            "colour": rgb_to_hex(bg.colour),
            "opacity": runtime.opacity_pct / 100.0,
            "border": {
                "colour": rgb_to_hex(bg.border.colour),
                "width": runtime.border_width,
            },
        },
    }
    post_fx_values = {
        "enabled": runtime_pp.enabled,
        "fade_in": runtime_pp.fade_in,
        "fade_out": runtime_pp.fade_out,
    }
    post_fx = _dump_fields(RENDER_POST_FX_FIELDS, post_fx_values, ctx)
    return {"overlay": overlay, "post_fx": post_fx}


def parse_timeline_section(data: dict[str, Any]) -> Any | None:
    from cleave.config import TimelineConfig

    timeline = data.get("timeline")
    if timeline is None:
        return None
    timeline_map = as_mapping(timeline, "timeline")
    enabled = bool(timeline_map.get("enabled", DEFAULT_TIMELINE_ENABLED))
    cues_raw = timeline_map.get("cues", [])
    if cues_raw is None:
        cues_raw = []
    if not isinstance(cues_raw, list):
        raise ValueError("timeline.cues must be a list")
    cues: list[TimelineCue] = []
    for index, item in enumerate(cues_raw):
        cue_map = as_mapping(item, f"timeline.cues[{index}]")
        t = float(
            require_non_negative_number(
                cue_map.get("t"),
                f"timeline.cues[{index}].t",
            )
        )
        layers_raw = as_mapping(
            cue_map.get("layers"),
            f"timeline.cues[{index}].layers",
        )
        unknown = sorted(set(layers_raw) - set(STEM_NAMES))
        if unknown:
            raise ValueError(
                f"unknown layer keys in timeline.cues[{index}].layers "
                f"(expected {', '.join(STEM_NAMES)}): "
                + ", ".join(unknown)
            )
        layers = {stem: bool(layers_raw[stem]) for stem in layers_raw}
        cues.append(TimelineCue(t=t, layers=layers))
    cues.sort(key=lambda cue: cue.t)
    return TimelineConfig(enabled=enabled, cues=tuple(cues))


def persist_timeline(ctx: PersistCtx) -> dict[str, Any]:
    runtime = ctx.session.timeline
    out: dict[str, Any] = {"enabled": runtime.enabled}
    if runtime.cues:
        out["cues"] = [
            {"t": cue.t, "layers": dict(cue.layers)}
            for cue in sorted(runtime.cues, key=lambda cue: cue.t)
        ]
    return out


def persisted_session_payload(cfg: Any, session: Any) -> dict[str, Any]:
    ctx = PersistCtx(cfg=cfg, session=session)
    return {
        "visualizer": persist_visualizer(ctx),
        "layer_z_order": persist_layer_z_order(ctx),
        "layers": persist_layers(ctx),
        "render": persist_render(ctx),
        "timeline": persist_timeline(ctx),
    }


def default_render_overlay_runtime_values() -> dict[str, Any]:
    return {
        "enabled": True,
        "expanded": False,
        "position": DEFAULT_RENDER_OVERLAY_POSITION,
        "title_expanded": False,
        "body_expanded": False,
        "title_font_size": DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
        "title_font": DEFAULT_RENDER_OVERLAY_FONT,
        "title_margin_bottom": DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        "body_font_size": DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
        "body_font": DEFAULT_RENDER_OVERLAY_FONT,
        "opacity_pct": int(round(DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY * 100)),
        "border_width": DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
        "start_delay": DEFAULT_RENDER_OVERLAY_START_DELAY,
        "display_time": DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    }


def default_render_post_fx_runtime_values() -> dict[str, Any]:
    return {
        "enabled": True,
        "expanded": False,
        "fade_in": DEFAULT_RENDER_POST_FX_FADE_IN,
        "fade_out": DEFAULT_RENDER_POST_FX_FADE_OUT,
    }


def template_visualizer_section(*, name: str = "cleave-viz-example") -> dict[str, Any]:
    ctx = PersistCtx(cfg=None, session=None)  # type: ignore[arg-type]
    out = _dump_fields(
        VISUALIZER_FIELDS,
        {field.yaml_key: field.default for field in VISUALIZER_FIELDS},
        ctx,
    )
    out["name"] = name
    return out


def template_layer_entry(stem: str) -> dict[str, Any]:
    width, height = LAYER_DEFAULT_SIZE[stem]
    return {
        "preset": f"presets/{stem}/",
        "enabled": True,
        "opacity": 1.0,
        "width": width,
        "height": height,
        "blend_mode": DEFAULT_BLEND_MODE[stem],
    }
