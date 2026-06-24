"""Single source of truth for Cleave YAML parse, serialize, and defaults."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, TypeVar

from cleave.blend_modes import BLEND_MODES, BlendMode
from cleave.effects.constants import clamp_effect_pct
from cleave.effects.registry import validate_effect_entry
from cleave.extract import STEM_SOURCES, StemSource
from cleave.timeline import TimelineCue

# --- Visualizer defaults ---

DEFAULT_VISUALIZER_WIDTH = 1280
DEFAULT_VISUALIZER_HEIGHT = 720
DEFAULT_RENDER_FPS = 30
DEFAULT_RENDER_WIDTH = 1280
DEFAULT_RENDER_HEIGHT = 720
DEFAULT_VISUALIZER_WARMUP_SEC = 3.0
DEFAULT_VISUALIZER_UPSCALE = 1.0
UPSCALE_MIN = 1.0
DEFAULT_BEAT_SENSITIVITY = 2.0
BEAT_SENSITIVITY_MIN = 0.0
BEAT_SENSITIVITY_MAX = 5.0

PresetSwitchingMode = Literal["none", "projectm"]
PresetSwitchingScope = Literal["directory"]
PRESET_SWITCHING_MODES: tuple[PresetSwitchingMode, ...] = ("none", "projectm")
PRESET_SWITCHING_SCOPES: tuple[PresetSwitchingScope, ...] = ("directory",)
DEFAULT_PRESET_SWITCHING: PresetSwitchingMode = "none"
DEFAULT_PRESET_SWITCHING_SCOPE: PresetSwitchingScope = "directory"

VisualizerRenderMode = Literal[
    "full-quality", "balanced", "performance", "ultra-performance"
]

VISUALIZER_RENDER_MODES: tuple[VisualizerRenderMode, ...] = (
    "full-quality",
    "balanced",
    "performance",
    "ultra-performance",
)

DEFAULT_VISUALIZER_RENDER_MODE: VisualizerRenderMode = "balanced"

# --- Layer defaults ---

MAX_LAYER_COUNT = 8
MIN_LAYER_COUNT = 1
DEFAULT_LAYER_SLOTS = ("layer_1", "layer_2", "layer_3", "layer_4")
DEFAULT_LAYER_Z_ORDER: list[str] = list(DEFAULT_LAYER_SLOTS)
DEFAULT_NEW_LAYER_STEM: StemSource = "full_mix"

_SLOT_RE = re.compile(r"^layer_(\d+)$")


def _valid_slot(key: str) -> int | None:
    m = _SLOT_RE.match(key)
    if m:
        n = int(m.group(1))
        if 1 <= n <= MAX_LAYER_COUNT:
            return n
    return None


def next_layer_slot(existing_slots: list[str]) -> str:
    used = set(existing_slots)
    for i in range(1, MAX_LAYER_COUNT + 1):
        candidate = f"layer_{i}"
        if candidate not in used:
            return candidate
    raise ValueError(f"Maximum {MAX_LAYER_COUNT} layers already present")


def new_layer_config(slot: str, preset: Path, preset_root: Path) -> Any:
    from cleave.config import LayerConfig

    w, h = LAYER_DEFAULT_SIZE[DEFAULT_NEW_LAYER_STEM]
    return LayerConfig(
        preset=preset,
        stem=DEFAULT_NEW_LAYER_STEM,
        enabled=True,
        opacity=1.0,
        width=w,
        height=h,
        blend_mode=DEFAULT_BLEND_MODE[DEFAULT_NEW_LAYER_STEM],
        locked=False,
        preset_switching=DEFAULT_PRESET_SWITCHING,
        preset_switching_scope=DEFAULT_PRESET_SWITCHING_SCOPE,
    )

DEFAULT_BLEND_MODE: dict[StemSource, BlendMode] = {
    "drums": "add",
    "other": "black-key",
    "bass": "black-key",
    "vocals": "black-key",
    "full_mix": "black-key",
}

LAYER_DEFAULT_SIZE: dict[StemSource, tuple[int, int]] = {
    "other": (640, 360),
    "bass": (960, 540),
    "vocals": (960, 540),
    "drums": (1280, 720),
    "full_mix": (1280, 720),
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


def _parse_preset_switching(raw: Any, label: str) -> PresetSwitchingMode:
    mode = str(raw)
    if mode not in PRESET_SWITCHING_MODES:
        allowed = ", ".join(PRESET_SWITCHING_MODES)
        raise ValueError(f"{label} must be one of: {allowed}")
    return mode


def _parse_preset_switching_scope(raw: Any, label: str) -> PresetSwitchingScope:
    scope = str(raw)
    if scope not in PRESET_SWITCHING_SCOPES:
        allowed = ", ".join(PRESET_SWITCHING_SCOPES)
        raise ValueError(f"{label} must be one of: {allowed}")
    return scope


def preset_switching_display(mode: PresetSwitchingMode) -> str:
    return "projectM" if mode == "projectm" else "none"


@dataclass(frozen=True)
class FieldDescriptor:
    """Leaf field: YAML key, default, parse/dump, and persistence source."""

    yaml_key: str
    default: Any
    source: FieldSource
    parse: Callable[[Any, "ParseCtx", str], Any]
    dump: Callable[[Any, "PersistCtx"], Any]
    yaml_alt_keys: tuple[str, ...] = ()
    attr_key: str | None = None
    omit_when: Callable[[Any], bool] | None = None

    @property
    def key(self) -> str:
        if self.attr_key is not None:
            return self.attr_key
        return self.yaml_key.replace("-", "_")


@dataclass(frozen=True)
class SectionDescriptor:
    """Nested YAML section built from child field and section descriptors."""

    yaml_key: str
    fields: tuple["SchemaField", ...]
    build: Callable[[dict[str, Any]], Any]
    optional: bool = False
    default_factory: Callable[[], Any] | None = None
    attr_key: str | None = None

    @property
    def key(self) -> str:
        if self.attr_key is not None:
            return self.attr_key
        return self.yaml_key.replace("-", "_")


SchemaField = FieldDescriptor | SectionDescriptor


@dataclass
class ParseCtx:
    preset_root: Path | None = None
    layer_slots: tuple[str, ...] | None = None


@dataclass
class PersistCtx:
    cfg: Any
    session: Any


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


def _parse_visualizer_render_mode(
    value: Any, ctx: ParseCtx, label: str = "visualizer.render_mode"
) -> VisualizerRenderMode:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in VISUALIZER_RENDER_MODES:
        allowed = ", ".join(f"'{mode}'" for mode in VISUALIZER_RENDER_MODES)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value


def _parse_overlay_content(raw: Any, ctx: ParseCtx, label: str) -> str:
    content = str(raw if raw is not None else "")
    if content.endswith("\n"):
        content = content[:-1]
    return content


def _dump_overlay_content(value: str, ctx: PersistCtx) -> str:
    if "\n" in value:
        return value + "\n"
    return value


def _parse_overlay_font(raw: Any, ctx: ParseCtx, label: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return raw.strip()


def _parse_optional_background_colour(
    raw: Any, ctx: ParseCtx, label: str
) -> tuple[int, int, int] | None:
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip() == "":
        return None
    return parse_hex_colour(raw, label)


def _dump_hex_colour(value: tuple[int, int, int], ctx: PersistCtx) -> str:
    return rgb_to_hex(value)


def _parse_non_negative_int(raw: Any, ctx: ParseCtx, label: str) -> int:
    return int(require_non_negative_number(raw, label, as_int=True))


def _parse_non_negative_float(raw: Any, ctx: ParseCtx, label: str) -> float:
    return float(require_non_negative_number(raw, label))


def _build_render_overlay_text_block(parsed: dict[str, Any]) -> Any:
    from cleave.config import RenderOverlayTextBlockConfig

    return RenderOverlayTextBlockConfig(
        content=parsed["content"],
        font=parsed["font"],
        font_size=parsed["font_size"],
        colour=parsed["colour"],
        background_colour=parsed["background_colour"],
        margin_bottom=parsed["margin_bottom"],
    )


def _build_render_overlay_border(parsed: dict[str, Any]) -> Any:
    from cleave.config import RenderOverlayBorderConfig

    return RenderOverlayBorderConfig(
        colour=parsed["colour"],
        width=parsed["width"],
    )


def _build_render_overlay_background(parsed: dict[str, Any]) -> Any:
    from cleave.config import RenderOverlayBackgroundConfig

    return RenderOverlayBackgroundConfig(
        margin=parsed["margin"],
        padding=parsed["padding"],
        colour=parsed["colour"],
        opacity=parsed["opacity"],
        border=parsed["border"],
    )


def _build_render_overlay_config(parsed: dict[str, Any]) -> Any:
    from cleave.config import RenderOverlayConfig

    return RenderOverlayConfig(
        enabled=parsed["enabled"],
        title=parsed["title"],
        body=parsed["body"],
        start_delay=parsed["start_delay"],
        display_time=parsed["display_time"],
        position=parsed["position"],
        background=parsed["background"],
    )


def _overlay_text_block_fields(
    *,
    content_default: str,
    font_size_default: int,
    colour_yaml_key: str,
    colour_alt_keys: tuple[str, ...],
    margin_bottom_default: int,
    include_margin_bottom_in_dump: bool,
) -> tuple[FieldDescriptor, ...]:
    return (
        FieldDescriptor(
            "content",
            content_default,
            "cfg",
            _parse_overlay_content,
            _dump_overlay_content,
        ),
        FieldDescriptor(
            "font",
            DEFAULT_RENDER_OVERLAY_FONT,
            "cfg",
            _parse_overlay_font,
            _dump_scalar,
        ),
        FieldDescriptor(
            "font-size",
            font_size_default,
            "session",
            _parse_non_negative_int,
            _dump_scalar,
            attr_key="font_size",
        ),
        FieldDescriptor(
            colour_yaml_key,
            DEFAULT_RENDER_OVERLAY_TEXT_COLOUR,
            "cfg",
            lambda raw, ctx, label: parse_hex_colour(raw, label),
            _dump_hex_colour,
            yaml_alt_keys=colour_alt_keys,
            attr_key="colour",
        ),
        FieldDescriptor(
            "background-colour",
            None,
            "cfg",
            _parse_optional_background_colour,
            _dump_hex_colour,
            attr_key="background_colour",
            omit_when=lambda value: value is None,
        ),
        FieldDescriptor(
            "margin-bottom",
            margin_bottom_default,
            "cfg",
            _parse_non_negative_int,
            _dump_scalar,
            attr_key="margin_bottom",
            omit_when=(lambda value: value == 0)
            if not include_margin_bottom_in_dump
            else None,
        ),
    )


RENDER_OVERLAY_TITLE_SECTION = SectionDescriptor(
    yaml_key="title",
    fields=_overlay_text_block_fields(
        content_default=DEFAULT_RENDER_OVERLAY_TITLE,
        font_size_default=DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
        colour_yaml_key="font-colour",
        colour_alt_keys=("colour",),
        margin_bottom_default=DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        include_margin_bottom_in_dump=True,
    ),
    build=_build_render_overlay_text_block,
    optional=True,
    default_factory=lambda: _build_render_overlay_text_block(
        _section_field_defaults(RENDER_OVERLAY_TITLE_SECTION)
    ),
)

RENDER_OVERLAY_BODY_SECTION = SectionDescriptor(
    yaml_key="body",
    fields=_overlay_text_block_fields(
        content_default=DEFAULT_RENDER_OVERLAY_BODY,
        font_size_default=DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
        colour_yaml_key="colour",
        colour_alt_keys=("font-colour",),
        margin_bottom_default=0,
        include_margin_bottom_in_dump=False,
    ),
    build=_build_render_overlay_text_block,
    optional=True,
    default_factory=lambda: _build_render_overlay_text_block(
        _section_field_defaults(RENDER_OVERLAY_BODY_SECTION)
    ),
)

RENDER_OVERLAY_BORDER_SECTION = SectionDescriptor(
    yaml_key="border",
    fields=(
        FieldDescriptor(
            "colour",
            DEFAULT_RENDER_OVERLAY_BORDER_COLOUR,
            "cfg",
            lambda raw, ctx, label: parse_hex_colour(
                "#ffffff" if raw is None else raw, label
            ),
            _dump_hex_colour,
        ),
        FieldDescriptor(
            "width",
            DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
            "session",
            _parse_non_negative_int,
            _dump_scalar,
        ),
    ),
    build=_build_render_overlay_border,
)

RENDER_OVERLAY_BACKGROUND_SECTION = SectionDescriptor(
    yaml_key="background",
    fields=(
        FieldDescriptor(
            "margin",
            DEFAULT_RENDER_OVERLAY_BACKGROUND_MARGIN,
            "cfg",
            _parse_non_negative_int,
            _dump_scalar,
        ),
        FieldDescriptor(
            "padding",
            DEFAULT_RENDER_OVERLAY_BACKGROUND_PADDING,
            "cfg",
            _parse_non_negative_int,
            _dump_scalar,
        ),
        FieldDescriptor(
            "colour",
            DEFAULT_RENDER_OVERLAY_BACKGROUND_COLOUR,
            "cfg",
            lambda raw, ctx, label: parse_hex_colour(
                "#000000" if raw is None else raw, label
            ),
            _dump_hex_colour,
        ),
        FieldDescriptor(
            "opacity",
            DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY,
            "session",
            _parse_non_negative_float,
            _dump_scalar,
        ),
        RENDER_OVERLAY_BORDER_SECTION,
    ),
    build=_build_render_overlay_background,
)

RENDER_OVERLAY_FIELDS: tuple[SchemaField, ...] = (
    FieldDescriptor(
        "enabled",
        True,
        "session",
        lambda raw, _ctx, _label: bool(raw),
        _dump_scalar,
    ),
    RENDER_OVERLAY_TITLE_SECTION,
    RENDER_OVERLAY_BODY_SECTION,
    FieldDescriptor(
        "start_delay",
        DEFAULT_RENDER_OVERLAY_START_DELAY,
        "session",
        _parse_non_negative_float,
        _dump_scalar,
    ),
    FieldDescriptor(
        "display_time",
        DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
        "session",
        _parse_non_negative_float,
        _dump_scalar,
    ),
    FieldDescriptor(
        "position",
        DEFAULT_RENDER_OVERLAY_POSITION,
        "session",
        _parse_render_overlay_position,
        _dump_scalar,
    ),
    RENDER_OVERLAY_BACKGROUND_SECTION,
)


def _parse_overlay_fields(
    parent: dict[str, Any],
    fields: tuple[SchemaField, ...],
    ctx: ParseCtx,
    label: str,
) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for field in fields:
        if isinstance(field, SectionDescriptor):
            parsed[field.key] = _parse_section(parent, field, ctx, label)
        else:
            parsed[field.key] = _parse_field(parent, field, ctx, label)
    return parsed


def _dump_overlay_fields(
    fields: tuple[SchemaField, ...],
    values: dict[str, Any],
    ctx: PersistCtx,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in fields:
        if isinstance(field, SectionDescriptor):
            out[field.yaml_key] = _dump_section(field, values, ctx)
        else:
            out.update(_dump_field(field, values, ctx))
    return out


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
    FieldDescriptor(
        "render_mode",
        DEFAULT_VISUALIZER_RENDER_MODE,
        "cfg",
        _parse_visualizer_render_mode,
        _dump_scalar,
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


def _dump_field(
    field: FieldDescriptor,
    values: dict[str, Any],
    ctx: PersistCtx,
) -> dict[str, Any]:
    value = values[field.key]
    if field.omit_when is not None and field.omit_when(value):
        return {}
    return {field.yaml_key: field.dump(value, ctx)}


def _dump_fields(
    fields: tuple[FieldDescriptor, ...],
    values: dict[str, Any],
    ctx: PersistCtx,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in fields:
        out.update(_dump_field(field, values, ctx))
    return out


def _parse_section(
    parent: dict[str, Any],
    section: SectionDescriptor,
    ctx: ParseCtx,
    label: str,
) -> Any:
    if section.optional and parent.get(section.yaml_key) is None:
        if section.default_factory is None:
            raise ValueError(f"{label}.{section.yaml_key} missing default_factory")
        return section.default_factory()
    section_map = as_mapping(
        parent.get(section.yaml_key),
        f"{label}.{section.yaml_key}",
    )
    parsed: dict[str, Any] = {}
    for field in section.fields:
        if isinstance(field, SectionDescriptor):
            parsed[field.key] = _parse_section(
                section_map, field, ctx, f"{label}.{section.yaml_key}"
            )
        else:
            parsed[field.key] = _parse_field(
                section_map, field, ctx, f"{label}.{section.yaml_key}"
            )
    return section.build(parsed)


def _dump_section(
    section: SectionDescriptor,
    values: dict[str, Any],
    ctx: PersistCtx,
) -> dict[str, Any]:
    section_values = values[section.key]
    out: dict[str, Any] = {}
    for field in section.fields:
        if isinstance(field, SectionDescriptor):
            out[field.yaml_key] = _dump_section(field, section_values, ctx)
        else:
            out.update(_dump_field(field, section_values, ctx))
    return out


def _section_field_defaults(section: SectionDescriptor) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in section.fields:
        if isinstance(field, SectionDescriptor):
            out[field.key] = _section_field_defaults(field)
        else:
            out[field.key] = field.default
    return out


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
        warmup_sec=parsed["warmup_sec"],
        beat_sensitivity=parsed["beat_sensitivity"],
        render_mode=parsed["render_mode"],
    )


def persist_visualizer(ctx: PersistCtx) -> dict[str, Any]:
    vis = ctx.cfg.visualizer
    values = {
        "width": vis.width,
        "height": vis.height,
        "upscale": vis.upscale,
        "warmup_sec": vis.warmup_sec,
        "beat_sensitivity": vis.beat_sensitivity,
        "render_mode": vis.render_mode,
    }
    return _dump_fields(VISUALIZER_FIELDS, values, ctx)


def parse_layer_z_order_section(data: dict[str, Any], ctx: ParseCtx) -> list[str]:
    if ctx.layer_slots is None:
        raise ValueError("layer_slots required to parse layer_z_order")
    layer_slots = ctx.layer_slots
    raw = data.get("layer_z_order")
    if raw is None:
        return list(layer_slots)
    if not isinstance(raw, list):
        raise ValueError("layer_z_order must be a list")
    if len(raw) != len(layer_slots):
        raise ValueError(
            f"layer_z_order must contain exactly {len(layer_slots)} entries"
        )
    if set(raw) != set(layer_slots):
        raise ValueError(
            f"layer_z_order must contain each of {', '.join(layer_slots)} exactly once"
        )
    return list(raw)


def persist_layer_z_order(ctx: PersistCtx) -> list[str]:
    order = ctx.session.layer_z_order
    cfg_order = list(ctx.cfg.layer_z_order)
    if len(order) == len(cfg_order) and set(order) == set(cfg_order):
        return list(order)
    return cfg_order


def parse_blend_mode(slot: str, stem: StemSource, layer_raw: dict[str, Any]) -> BlendMode:
    raw = layer_raw.get("blend_mode")
    if raw is None:
        return DEFAULT_BLEND_MODE[stem]
    if raw not in BLEND_MODES:
        allowed = ", ".join(f"'{mode}'" for mode in BLEND_MODES)
        raise ValueError(f"layers.{slot}.blend_mode must be one of: {allowed}")
    return raw


def _parse_stem(slot: str, layer_raw: dict[str, Any]) -> StemSource:
    raw = layer_raw.get("stem")
    if raw is None:
        return DEFAULT_NEW_LAYER_STEM
    if raw not in STEM_SOURCES:
        allowed = ", ".join(STEM_SOURCES)
        raise ValueError(f"layers.{slot}.stem must be one of: {allowed}")
    return raw


def _parse_effects(
    slot: str,
    stem: StemSource,
    layer_raw: dict[str, Any],
) -> dict[str, dict[str, int]]:
    raw = layer_raw.get("effects")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"layers.{slot}.effects must be a mapping")

    effects: dict[str, dict[str, int]] = {}
    for effect_id, drivers_raw in raw.items():
        if not isinstance(effect_id, str):
            raise ValueError(f"layers.{slot}.effects keys must be strings")
        if not isinstance(drivers_raw, dict):
            raise ValueError(f"layers.{slot}.effects.{effect_id} must be a mapping")
        for driver_slug, value in drivers_raw.items():
            if not isinstance(driver_slug, str):
                raise ValueError(
                    f"layers.{slot}.effects.{effect_id} driver keys must be strings"
                )
            validate_effect_entry(slot, stem, effect_id, driver_slug)
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
    if not layers_raw:
        raise ValueError("layers section must contain at least one layer")
    for key in layers_raw:
        if _valid_slot(key) is None:
            raise ValueError(
                f"invalid layer key '{key}': must be layer_1 .. layer_{MAX_LAYER_COUNT}"
            )
    if len(layers_raw) < MIN_LAYER_COUNT:
        raise ValueError("layers section must contain at least one layer")
    if len(layers_raw) > MAX_LAYER_COUNT:
        raise ValueError(f"layers section must contain at most {MAX_LAYER_COUNT} layers")

    layer_keys = sorted(layers_raw, key=lambda k: _valid_slot(k) or 0)
    ctx.layer_slots = tuple(layer_keys)

    layers: dict[str, LayerConfig] = {}
    for slot in layer_keys:
        layer_raw = as_mapping(layers_raw[slot], f"layers.{slot}")
        preset_raw = layer_raw.get("preset")
        if not preset_raw:
            raise ValueError(f"layers.{slot}.preset is required")

        stem = _parse_stem(slot, layer_raw)
        default_width, default_height = LAYER_DEFAULT_SIZE[stem]
        beat_raw = layer_raw.get("beat_sensitivity")
        preset_switching = _parse_preset_switching(
            layer_raw.get("preset_switching", DEFAULT_PRESET_SWITCHING),
            f"layers.{slot}.preset_switching",
        )
        preset_switching_scope = _parse_preset_switching_scope(
            layer_raw.get("preset_switching_scope", DEFAULT_PRESET_SWITCHING_SCOPE),
            f"layers.{slot}.preset_switching_scope",
        )
        layers[slot] = LayerConfig(
            preset=_resolve_preset(preset_raw, preset_root),
            stem=stem,
            enabled=bool(layer_raw.get("enabled", True)),
            opacity=float(layer_raw.get("opacity", 1.0)),
            width=int(layer_raw.get("width", default_width)),
            height=int(layer_raw.get("height", default_height)),
            beat_sensitivity=clamp_beat_sensitivity(beat_raw)
            if beat_raw is not None
            else None,
            effects=_parse_effects(slot, stem, layer_raw),
            blend_mode=parse_blend_mode(slot, stem, layer_raw),
            locked=bool(layer_raw.get("locked", False)),
            preset_switching=preset_switching,
            preset_switching_scope=preset_switching_scope,
        )
    return layers


def persist_layers(ctx: PersistCtx) -> dict[str, dict[str, Any]]:
    from cleave.preset_playlist import to_config_relative

    preset_root = ctx.cfg.paths.preset_root
    layers_out: dict[str, dict[str, Any]] = {}
    global_beat = ctx.cfg.visualizer.beat_sensitivity

    for slot in ctx.session.layer_z_order:
        layer_cfg = ctx.cfg.layers[slot]
        stem = layer_cfg.stem
        if slot in ctx.session.layers:
            runtime = ctx.session.layers[slot]
            preset = runtime.playlist.config_preset_path(preset_root)
            opacity = runtime.opacity_pct / 100.0
            enabled = runtime.enabled
            blend_mode = runtime.blend_mode
            beat = runtime.beat_sensitivity
            effects = runtime.effects
            locked = runtime.locked
            preset_switching = runtime.preset_switching
            preset_switching_scope = runtime.preset_switching_scope
            stem = getattr(runtime, "stem", stem)
        else:
            preset = to_config_relative(layer_cfg.preset, preset_root)
            opacity = layer_cfg.opacity
            enabled = layer_cfg.enabled
            blend_mode = layer_cfg.blend_mode
            locked = layer_cfg.locked
            preset_switching = layer_cfg.preset_switching
            preset_switching_scope = layer_cfg.preset_switching_scope
            effects = layer_cfg.effects
            beat = (
                layer_cfg.beat_sensitivity
                if layer_cfg.beat_sensitivity is not None
                else global_beat
            )

        layer_out: dict[str, Any] = {
            "stem": stem,
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
        if preset_switching != DEFAULT_PRESET_SWITCHING:
            layer_out["preset_switching"] = preset_switching
        if preset_switching_scope != DEFAULT_PRESET_SWITCHING_SCOPE:
            layer_out["preset_switching_scope"] = preset_switching_scope
        layers_out[slot] = layer_out

    return layers_out


def _parse_render_overlay_section(overlay_map: dict[str, Any]) -> Any:
    parsed = _parse_overlay_fields(
        overlay_map,
        RENDER_OVERLAY_FIELDS,
        ParseCtx(),
        "render.overlay",
    )
    return _build_render_overlay_config(parsed)


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
    fps_raw = render_map.get("fps")
    fps = DEFAULT_RENDER_FPS if fps_raw is None else int(fps_raw)
    width_raw = render_map.get("width")
    width = DEFAULT_RENDER_WIDTH if width_raw is None else int(width_raw)
    height_raw = render_map.get("height")
    height = DEFAULT_RENDER_HEIGHT if height_raw is None else int(height_raw)
    overlay_raw = render_map.get("overlay")
    post_fx_raw = render_map.get("post_fx")
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
    return RenderConfig(
        fps=fps, width=width, height=height, overlay=overlay, post_fx=post_fx
    )


def default_render_overlay_config() -> Any:
    return _parse_render_overlay_section({})


def render_overlay_base(cfg: Any) -> Any:
    if cfg.render is not None and cfg.render.overlay is not None:
        return cfg.render.overlay
    return default_render_overlay_config()


def _overlay_persist_values(ctx: PersistCtx) -> dict[str, Any]:
    runtime = ctx.session.render_overlay
    base = render_overlay_base(ctx.cfg)
    bg = base.background
    return {
        "enabled": runtime.enabled,
        "title": {
            "content": base.title.content,
            "font": runtime.title_font,
            "font_size": runtime.title_font_size,
            "colour": base.title.colour,
            "background_colour": base.title.background_colour,
            "margin_bottom": runtime.title_margin_bottom,
        },
        "body": {
            "content": base.body.content,
            "font": runtime.body_font,
            "font_size": runtime.body_font_size,
            "colour": base.body.colour,
            "background_colour": base.body.background_colour,
            "margin_bottom": 0,
        },
        "start_delay": runtime.start_delay,
        "display_time": runtime.display_time,
        "position": runtime.position,
        "background": {
            "margin": bg.margin,
            "padding": bg.padding,
            "colour": bg.colour,
            "opacity": runtime.opacity_pct / 100.0,
            "border": {
                "colour": bg.border.colour,
                "width": runtime.border_width,
            },
        },
    }


def persist_render(ctx: PersistCtx) -> dict[str, Any]:
    runtime_pp = ctx.session.render_post_fx
    overlay = _dump_overlay_fields(
        RENDER_OVERLAY_FIELDS,
        _overlay_persist_values(ctx),
        ctx,
    )
    post_fx_values = {
        "enabled": runtime_pp.enabled,
        "fade_in": runtime_pp.fade_in,
        "fade_out": runtime_pp.fade_out,
    }
    post_fx = _dump_fields(RENDER_POST_FX_FIELDS, post_fx_values, ctx)
    from cleave.config import render_fps, render_output_size

    width, height = render_output_size(ctx.cfg)
    return {
        "fps": render_fps(ctx.cfg),
        "width": width,
        "height": height,
        "overlay": overlay,
        "post_fx": post_fx,
    }


def parse_timeline_section(data: dict[str, Any], ctx: ParseCtx) -> Any | None:
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
        if ctx.layer_slots is None:
            raise ValueError("layer_slots required to parse timeline")
        allowed_slots = ctx.layer_slots
        unknown = sorted(set(layers_raw) - set(allowed_slots))
        if unknown:
            raise ValueError(
                f"unknown layer keys in timeline.cues[{index}].layers "
                f"(expected {', '.join(allowed_slots)}): "
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


def template_layer_entry(
    slot: str, stem: StemSource = DEFAULT_NEW_LAYER_STEM
) -> dict[str, Any]:
    width, height = LAYER_DEFAULT_SIZE[stem]
    return {
        "stem": stem,
        "preset": f"presets/{stem}/",
        "enabled": True,
        "opacity": 1.0,
        "width": width,
        "height": height,
        "blend_mode": DEFAULT_BLEND_MODE[stem],
    }
