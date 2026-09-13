"""Editor user-config YAML parse, serialize, and defaults."""

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

DEFAULT_EDITOR_WIDTH = 1920
DEFAULT_EDITOR_HEIGHT = 1080
DEFAULT_EDITOR_UPSCALE = 1.0
EDITOR_WIDTH_MIN = 320
EDITOR_HEIGHT_MIN = 240
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
DEFAULT_NOTIFICATION_DISPLAY_SEC = 5
NOTIFICATION_DISPLAY_MAX_SEC = 20

UiWidthMode = Literal["flexible", "fixed"]

UI_WIDTH_MODES: tuple[UiWidthMode, ...] = ("flexible", "fixed")
DEFAULT_UI_WIDTH_MODE: UiWidthMode = "flexible"


def editor_display_size(
    width: int = DEFAULT_EDITOR_WIDTH,
    height: int = DEFAULT_EDITOR_HEIGHT,
    *,
    upscale: float = DEFAULT_EDITOR_UPSCALE,
) -> tuple[int, int]:
    """Window size from editor content size and upscale (same as ``EditorConfig``)."""
    return (
        max(1, round(width * upscale)),
        max(1, round(height * upscale)),
    )


def clamp_upscale(value: float) -> float:
    return max(UPSCALE_MIN, float(value))


def clamp_editor_width(value: int | float) -> int:
    return max(EDITOR_WIDTH_MIN, int(round(value)))


def clamp_editor_height(value: int | float) -> int:
    return max(EDITOR_HEIGHT_MIN, int(round(value)))


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


def clamp_notification_display_sec(value: int | float) -> int:
    return max(0, min(NOTIFICATION_DISPLAY_MAX_SEC, int(round(value))))


def notification_display_label(sec: int) -> str:
    if sec <= 0:
        return "until dismissed"
    return f"{sec}s"


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


EDITOR_FIELDS: tuple[FieldDescriptor, ...] = (
    FieldDescriptor(
        "width",
        DEFAULT_EDITOR_WIDTH,
        lambda raw, ctx, label: clamp_editor_width(
            int(require_non_negative_number(raw, label, as_int=True))
        ),
        lambda value, _ctx: clamp_editor_width(value),
    ),
    FieldDescriptor(
        "height",
        DEFAULT_EDITOR_HEIGHT,
        lambda raw, ctx, label: clamp_editor_height(
            int(require_non_negative_number(raw, label, as_int=True))
        ),
        lambda value, _ctx: clamp_editor_height(value),
    ),
    FieldDescriptor(
        "upscale",
        DEFAULT_EDITOR_UPSCALE,
        _parse_upscale,
        lambda value, _ctx: clamp_upscale(value),
    ),
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
        "notification_display_sec",
        DEFAULT_NOTIFICATION_DISPLAY_SEC,
        lambda raw, ctx, label: clamp_notification_display_sec(
            int(require_non_negative_number(raw, label, as_int=True))
        ),
        lambda value, _ctx: clamp_notification_display_sec(value),
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
        width=parsed["width"],
        height=parsed["height"],
        upscale=parsed["upscale"],
        preview_quality=parsed["preview_quality"],
        ui_width_mode=parsed["ui_width_mode"],
        ui_width=parsed["ui_width"],
        ui_fade=parsed["ui_fade"],
        notification_display_sec=parsed["notification_display_sec"],
        residual_latency_ms=parsed["residual_latency_ms"],
    )


def dump_editor_section(editor: Any) -> dict[str, Any]:
    values = {
        "width": editor.width,
        "height": editor.height,
        "upscale": editor.upscale,
        "preview_quality": editor.preview_quality,
        "ui_width_mode": editor.ui_width_mode,
        "ui_width": editor.ui_width,
        "ui_fade": editor.ui_fade,
        "notification_display_sec": editor.notification_display_sec,
        "residual_latency_ms": editor.residual_latency_ms,
    }
    ctx = PersistCtx(cfg=None, session=None)
    return dump_fields(EDITOR_FIELDS, values, ctx)


def editor_config_from_settings(editor: Any | None = None) -> Any:
    """Build ``EditorConfig`` from user-config settings only."""
    from cleave.config import EditorConfig
    from cleave.user_config import default_editor_settings

    if editor is None:
        editor = default_editor_settings()
    return EditorConfig(
        width=editor.width,
        height=editor.height,
        upscale=editor.upscale,
        preview_quality=editor.preview_quality,
        ui_width_mode=editor.ui_width_mode,
        ui_width=editor.ui_width,
        ui_fade=editor.ui_fade,
        notification_display_sec=editor.notification_display_sec,
        residual_latency_ms=editor.residual_latency_ms,
    )
