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
DEFAULT_BEAT_SENSITIVITY = 1.0
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

DEFAULT_EDITOR_PREVIEW_QUALITY: EditorPreviewQuality = "full-quality"
DEFAULT_RESIDUAL_LATENCY_MS = 0
MAX_RESIDUAL_LATENCY_MS = 2000
DEFAULT_NOTIFICATION_DISPLAY_SEC = 10
NOTIFICATION_DISPLAY_MAX_SEC = 20

# Half again the design mock's 330px column, so labels and stepped values fit.
# The navigator and the inspector share this stack width.
DEFAULT_INSPECTOR_WIDTH = 495
DEFAULT_HELP_WIDTH = 320
# Navigator height in the shared stack. 0 fits the navigator to its rows.
DEFAULT_NAVIGATOR_HEIGHT = 0
# Editor chrome scale in percent: text plus the spacing around it.
DEFAULT_UI_SCALE = 100
UI_SCALE_MIN = 80
UI_SCALE_MAX = 200
# Side columns stay at least this wide once the display can hold every open
# side column and a 1px visualiser. A narrower window skips the floor.
MIN_COLUMN_WIDTH = 60

ColumnSide = Literal["left", "right"]

COLUMN_SIDES: tuple[ColumnSide, ...] = ("left", "right")
DEFAULT_NAVIGATOR_SIDE: ColumnSide = "left"
DEFAULT_HELP_SIDE: ColumnSide = "right"


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


def clamp_shell_column_width(value: int | float) -> int:
    return max(MIN_COLUMN_WIDTH, int(round(value)))


def clamp_navigator_height(value: int | float) -> int:
    return max(0, int(round(value)))


def navigator_height_label(px: int) -> str:
    if px <= 0:
        return "fit to rows"
    return f"{px} px"


def clamp_ui_scale(value: int | float) -> int:
    return max(UI_SCALE_MIN, min(UI_SCALE_MAX, int(round(value))))


def ui_scale_label(percent: int) -> str:
    return f"{percent}%"


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


def _parse_column_side(
    value: Any, ctx: ParseCtx, label: str
) -> ColumnSide:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in COLUMN_SIDES:
        allowed = ", ".join(f"'{side}'" for side in COLUMN_SIDES)
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
    FieldDescriptor(
        "inspector_width",
        DEFAULT_INSPECTOR_WIDTH,
        lambda raw, ctx, label: clamp_shell_column_width(
            int(require_non_negative_number(raw, label, as_int=True))
        ),
        lambda value, _ctx: clamp_shell_column_width(value),
    ),
    FieldDescriptor(
        "help_width",
        DEFAULT_HELP_WIDTH,
        lambda raw, ctx, label: clamp_shell_column_width(
            int(require_non_negative_number(raw, label, as_int=True))
        ),
        lambda value, _ctx: clamp_shell_column_width(value),
    ),
    FieldDescriptor(
        "navigator_height",
        DEFAULT_NAVIGATOR_HEIGHT,
        lambda raw, ctx, label: clamp_navigator_height(
            int(require_non_negative_number(raw, label, as_int=True))
        ),
        lambda value, _ctx: clamp_navigator_height(value),
    ),
    FieldDescriptor(
        "ui_scale",
        DEFAULT_UI_SCALE,
        lambda raw, ctx, label: clamp_ui_scale(
            int(require_non_negative_number(raw, label, as_int=True))
        ),
        lambda value, _ctx: clamp_ui_scale(value),
    ),
    FieldDescriptor(
        "navigator_side",
        DEFAULT_NAVIGATOR_SIDE,
        lambda raw, ctx, label: _parse_column_side(raw, ctx, label),
        dump_scalar,
    ),
    FieldDescriptor(
        "help_side",
        DEFAULT_HELP_SIDE,
        lambda raw, ctx, label: _parse_column_side(raw, ctx, label),
        dump_scalar,
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
        notification_display_sec=parsed["notification_display_sec"],
        residual_latency_ms=parsed["residual_latency_ms"],
        inspector_width=parsed["inspector_width"],
        help_width=parsed["help_width"],
        navigator_height=parsed["navigator_height"],
        ui_scale=parsed["ui_scale"],
        navigator_side=parsed["navigator_side"],
        help_side=parsed["help_side"],
    )


def dump_editor_section(editor: Any) -> dict[str, Any]:
    values = {
        "width": editor.width,
        "height": editor.height,
        "upscale": editor.upscale,
        "preview_quality": editor.preview_quality,
        "notification_display_sec": editor.notification_display_sec,
        "residual_latency_ms": editor.residual_latency_ms,
        "inspector_width": editor.inspector_width,
        "help_width": editor.help_width,
        "navigator_height": editor.navigator_height,
        "ui_scale": editor.ui_scale,
        "navigator_side": editor.navigator_side,
        "help_side": editor.help_side,
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
        notification_display_sec=editor.notification_display_sec,
        residual_latency_ms=editor.residual_latency_ms,
        inspector_width=editor.inspector_width,
        help_width=editor.help_width,
        navigator_height=editor.navigator_height,
        ui_scale=editor.ui_scale,
        navigator_side=editor.navigator_side,
        help_side=editor.help_side,
    )
