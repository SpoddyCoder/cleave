"""Editor and project-editor YAML parse, serialize, and defaults."""

from __future__ import annotations

from typing import Any, Literal

from cleave.config_schema.descriptors import (
    FieldDescriptor,
    ParseCtx,
    PersistCtx,
    as_mapping,
    dump_fields,
    dump_scalar,
    parse_field,
    require_non_negative_number,
)

DEFAULT_EDITOR_WIDTH = 1280
DEFAULT_EDITOR_HEIGHT = 720
DEFAULT_EDITOR_UPSCALE = 1.0
UPSCALE_MIN = 1.0
DEFAULT_BEAT_SENSITIVITY = 2.0
BEAT_SENSITIVITY_MIN = 0.0
BEAT_SENSITIVITY_MAX = 5.0

EditorPreviewQuality = Literal[
    "full-quality", "balanced", "performance", "ultra-performance"
]

EDITOR_PREVIEW_QUALITIES: tuple[EditorPreviewQuality, ...] = (
    "full-quality",
    "balanced",
    "performance",
    "ultra-performance",
)

EDITOR_PREVIEW_QUALITY_HELP_ENTRIES: tuple[
    tuple[EditorPreviewQuality, str], ...
] = (
    ("full-quality", "every layer at configured resolution."),
    ("balanced", "top layer full size; lower layers step down."),
    ("performance", "more aggressive downscale from top."),
    ("ultra-performance", "lowest preview resolution for heaviest load reduction."),
)

DEFAULT_EDITOR_PREVIEW_QUALITY: EditorPreviewQuality = "balanced"
DEFAULT_UI_FADE_SEC = 10.0
DEFAULT_RESIDUAL_LATENCY_MS = 0
MAX_RESIDUAL_LATENCY_MS = 2000
UI_FADE_MAX_SEC = 60.0
DEFAULT_UI_WIDTH = 110
UI_WIDTH_MIN = 80
UI_WIDTH_MAX = 200

UiWidthMode = Literal["flexible", "fixed"]

UI_WIDTH_MODES: tuple[UiWidthMode, ...] = ("flexible", "fixed")
DEFAULT_UI_WIDTH_MODE: UiWidthMode = "flexible"


def clamp_upscale(value: float) -> float:
    return max(UPSCALE_MIN, float(value))


def clamp_beat_sensitivity(value: float) -> float:
    return max(BEAT_SENSITIVITY_MIN, min(BEAT_SENSITIVITY_MAX, float(value)))


def _parse_upscale(raw: Any, ctx: ParseCtx, label: str) -> float:
    try:
        upscale = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if upscale < UPSCALE_MIN:
        raise ValueError(f"{label} must be >= {UPSCALE_MIN}")
    return clamp_upscale(upscale)


def _parse_beat_sensitivity(raw: Any, ctx: ParseCtx, label: str) -> float:
    return clamp_beat_sensitivity(raw)


def clamp_ui_fade(value: float) -> float:
    return max(0.0, min(UI_FADE_MAX_SEC, float(value)))


def ui_fade_display(sec: float) -> str:
    if sec <= 0:
        return "disabled"
    if sec == int(sec):
        return f"{int(sec)}s"
    return f"{sec:.1f}s"


def clamp_ui_width(value: int | float) -> int:
    return max(UI_WIDTH_MIN, min(UI_WIDTH_MAX, int(round(value))))


def clamp_residual_latency_ms(value: int | float) -> int:
    return max(0, min(int(round(value)), MAX_RESIDUAL_LATENCY_MS))


def _parse_editor_preview_quality(
    value: Any, ctx: ParseCtx, label: str = "editor.preview_quality"
) -> EditorPreviewQuality:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in EDITOR_PREVIEW_QUALITIES:
        allowed = ", ".join(f"'{mode}'" for mode in EDITOR_PREVIEW_QUALITIES)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value


def _parse_ui_width_mode(
    value: Any, ctx: ParseCtx, label: str = "editor.ui_width_mode"
) -> UiWidthMode:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in UI_WIDTH_MODES:
        allowed = ", ".join(f"'{mode}'" for mode in UI_WIDTH_MODES)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value


EDITOR_PROJECT_FIELDS: tuple[FieldDescriptor, ...] = (
    FieldDescriptor(
        "width",
        DEFAULT_EDITOR_WIDTH,
        lambda raw, _ctx, _label: int(raw),
        dump_scalar,
    ),
    FieldDescriptor(
        "height",
        DEFAULT_EDITOR_HEIGHT,
        lambda raw, _ctx, _label: int(raw),
        dump_scalar,
    ),
    FieldDescriptor(
        "upscale",
        DEFAULT_EDITOR_UPSCALE,
        _parse_upscale,
        lambda value, _ctx: clamp_upscale(value),
    ),
    FieldDescriptor(
        "beat_sensitivity",
        DEFAULT_BEAT_SENSITIVITY,
        _parse_beat_sensitivity,
        lambda value, _ctx: clamp_beat_sensitivity(value),
    ),
)

EDITOR_FIELDS: tuple[FieldDescriptor, ...] = (
    FieldDescriptor(
        "preview_quality",
        DEFAULT_EDITOR_PREVIEW_QUALITY,
        _parse_editor_preview_quality,
        dump_scalar,
    ),
    FieldDescriptor(
        "ui_width_mode",
        DEFAULT_UI_WIDTH_MODE,
        _parse_ui_width_mode,
        dump_scalar,
    ),
    FieldDescriptor(
        "ui_width",
        DEFAULT_UI_WIDTH,
        lambda raw, ctx, label: clamp_ui_width(
            int(require_non_negative_number(raw, label, as_int=True))
        ),
        lambda value, _ctx: clamp_ui_width(value),
    ),
    FieldDescriptor(
        "ui_fade",
        DEFAULT_UI_FADE_SEC,
        lambda raw, ctx, label: clamp_ui_fade(
            float(require_non_negative_number(raw, label))
        ),
        lambda value, _ctx: clamp_ui_fade(value),
    ),
    FieldDescriptor(
        "residual_latency_ms",
        DEFAULT_RESIDUAL_LATENCY_MS,
        lambda raw, ctx, label: clamp_residual_latency_ms(
            int(require_non_negative_number(raw, label, as_int=True))
        ),
        lambda value, _ctx: clamp_residual_latency_ms(value),
    ),
)


def parse_editor_section(data: dict[str, Any]) -> Any:
    from cleave.user_config import EditorSettings

    editor = as_mapping(data.get("editor"), "editor")
    ctx = ParseCtx()
    parsed: dict[str, Any] = {}
    for field in EDITOR_FIELDS:
        parsed[field.yaml_key] = parse_field(editor, field, ctx, "editor")
    return EditorSettings(
        preview_quality=parsed["preview_quality"],
        ui_width_mode=parsed["ui_width_mode"],
        ui_width=parsed["ui_width"],
        ui_fade=parsed["ui_fade"],
        residual_latency_ms=parsed["residual_latency_ms"],
    )


def dump_editor_section(editor: Any) -> dict[str, Any]:
    values = {
        "preview_quality": editor.preview_quality,
        "ui_width_mode": editor.ui_width_mode,
        "ui_width": editor.ui_width,
        "ui_fade": editor.ui_fade,
        "residual_latency_ms": editor.residual_latency_ms,
    }
    ctx = PersistCtx(cfg=None, session=None)
    return dump_fields(EDITOR_FIELDS, values, ctx)


def parse_project_editor_section(
    data: dict[str, Any],
    *,
    editor: Any | None = None,
) -> Any:
    from cleave.config import EditorConfig
    from cleave.user_config import default_editor_settings

    if editor is None:
        editor = default_editor_settings()

    project_editor = as_mapping(data.get("editor"), "editor")
    ctx = ParseCtx()
    parsed: dict[str, Any] = {}
    for field in EDITOR_PROJECT_FIELDS:
        parsed[field.yaml_key] = parse_field(
            project_editor, field, ctx, "editor"
        )
    return EditorConfig(
        name=str(project_editor.get("name", "render")),
        width=parsed["width"],
        height=parsed["height"],
        upscale=parsed["upscale"],
        beat_sensitivity=parsed["beat_sensitivity"],
        preview_quality=editor.preview_quality,
        ui_width_mode=editor.ui_width_mode,
        ui_width=editor.ui_width,
        ui_fade=editor.ui_fade,
        residual_latency_ms=editor.residual_latency_ms,
    )


def persist_project_editor_section(ctx: PersistCtx) -> dict[str, Any]:
    vis = ctx.cfg.editor
    values = {
        "width": vis.width,
        "height": vis.height,
        "upscale": vis.upscale,
        "beat_sensitivity": vis.beat_sensitivity,
    }
    return dump_fields(EDITOR_PROJECT_FIELDS, values, ctx)


def template_project_editor_section(*, name: str = "cleave-viz-example") -> dict[str, Any]:
    ctx = PersistCtx(cfg=None, session=None)  # type: ignore[arg-type]
    out = dump_fields(
        EDITOR_PROJECT_FIELDS,
        {field.yaml_key: field.default for field in EDITOR_PROJECT_FIELDS},
        ctx,
    )
    out["name"] = name
    return out
