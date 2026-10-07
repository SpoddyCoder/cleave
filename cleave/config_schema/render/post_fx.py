"""Render post-FX YAML parse, serialize, and defaults."""

from __future__ import annotations

from typing import Any, Literal

from cleave.config_schema.descriptors import (
    FieldDescriptor,
    ParseCtx,
    PersistCtx,
    SchemaField,
    SectionDescriptor,
    dump_scalar,
    parse_section_fields,
    require_non_negative_number,
)

DEFAULT_RENDER_POST_FX_ENABLED = True
DEFAULT_RENDER_POST_FX_LOCKED = False

FadeCurve = Literal["linear", "smoothstep", "ease_out_cubic", "ease_out_expo"]

FADE_CURVES: tuple[FadeCurve, ...] = (
    "linear",
    "smoothstep",
    "ease_out_cubic",
    "ease_out_expo",
)

FADE_CURVE_HELP_ENTRIES: tuple[tuple[FadeCurve, str], ...] = (
    ("linear", "constant rate from start to end."),
    ("smoothstep", "smooth S-curve."),
    ("ease_out_cubic", "fast start, cubic settle."),
    ("ease_out_expo", "fast start, exponential settle."),
)

DEFAULT_FADE_IN_START = 0.0
DEFAULT_FADE_IN_END = 30.0
DEFAULT_FADE_OUT_START = 4.0
DEFAULT_FADE_OUT_END = 0.0
DEFAULT_FADE_CURVE: FadeCurve = "smoothstep"

HighlightRolloffApplyMode = Literal["off", "per_layer", "composite"]

HIGHLIGHT_ROLLOFF_APPLY_MODES: tuple[HighlightRolloffApplyMode, ...] = (
    "off",
    "per_layer",
    "composite",
)

HIGHLIGHT_ROLLOFF_APPLY_MODE_HELP_ENTRIES: tuple[
    tuple[HighlightRolloffApplyMode, str], ...
] = (
    ("off", "disabled."),
    ("per_layer", "on each active layer before compositing."),
    ("composite", "after all layers are stacked (default)."),
)

DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE: HighlightRolloffApplyMode = "composite"

HighlightRolloffCurve = Literal["rolloff", "smoothstep", "aces_fit"]

HIGHLIGHT_ROLLOFF_CURVES: tuple[HighlightRolloffCurve, ...] = (
    "rolloff",
    "smoothstep",
    "aces_fit",
)

HIGHLIGHT_ROLLOFF_CURVE_HELP_ENTRIES: tuple[tuple[HighlightRolloffCurve, str], ...] = (
    ("rolloff", "Reinhard-style filmic compression."),
    ("smoothstep", "gradual S-curve toward the ceiling."),
    ("aces_fit", "ACES tone-map fit scaled to the ceiling."),
)

DEFAULT_HIGHLIGHT_ROLLOFF_CURVE: HighlightRolloffCurve = "rolloff"

DEFAULT_HIGHLIGHT_ROLLOFF_THRESHOLD_PCT = 78
DEFAULT_HIGHLIGHT_ROLLOFF_CEILING_PCT = 65
DEFAULT_HIGHLIGHT_ROLLOFF_STRENGTH_PCT = 70
DEFAULT_HIGHLIGHT_ROLLOFF_SOFTNESS_PCT = 40
DEFAULT_HIGHLIGHT_ROLLOFF_DESATURATION_PCT = 30

ChromaBoostApplyMode = Literal["off", "per_layer", "composite"]

CHROMA_BOOST_APPLY_MODES: tuple[ChromaBoostApplyMode, ...] = (
    "off",
    "per_layer",
    "composite",
)

CHROMA_BOOST_APPLY_MODE_HELP_ENTRIES: tuple[
    tuple[ChromaBoostApplyMode, str], ...
] = (
    ("off", "disabled."),
    ("per_layer", "on each active layer before compositing."),
    ("composite", "after all layers are stacked."),
)

DEFAULT_CHROMA_BOOST_APPLY_MODE: ChromaBoostApplyMode = "off"

ChromaBoostVariant = Literal["saturation", "vibrance"]

CHROMA_BOOST_VARIANTS: tuple[ChromaBoostVariant, ...] = (
    "saturation",
    "vibrance",
)

CHROMA_BOOST_VARIANT_HELP_ENTRIES: tuple[tuple[ChromaBoostVariant, str], ...] = (
    ("saturation", "uniform chroma boost around Rec.709 luma."),
    ("vibrance", "boosts muted colors more; spares already-saturated pixels."),
)

DEFAULT_CHROMA_BOOST_VARIANT: ChromaBoostVariant = "vibrance"

DEFAULT_CHROMA_BOOST_AMOUNT_PCT = 25

CHROMA_BOOST_AMOUNT_PCT_MIN = 0
CHROMA_BOOST_AMOUNT_PCT_MAX = 100

HIGHLIGHT_ROLLOFF_THRESHOLD_PCT_MIN = 0
HIGHLIGHT_ROLLOFF_THRESHOLD_PCT_MAX = 95
HIGHLIGHT_ROLLOFF_STRENGTH_PCT_MAX = 200


def clamp_highlight_rolloff_threshold_pct(value: int) -> int:
    return max(
        HIGHLIGHT_ROLLOFF_THRESHOLD_PCT_MIN,
        min(HIGHLIGHT_ROLLOFF_THRESHOLD_PCT_MAX, int(value)),
    )


def clamp_highlight_rolloff_ceiling_pct(
    value: int, *, threshold_pct: int | None = None
) -> int:
    clamped = max(0, min(100, int(value)))
    if threshold_pct is not None:
        clamped = min(clamped, int(threshold_pct))
    return clamped


def clamp_highlight_rolloff_strength_pct(value: int) -> int:
    return max(0, min(HIGHLIGHT_ROLLOFF_STRENGTH_PCT_MAX, int(value)))


def clamp_highlight_rolloff_softness_pct(value: int) -> int:
    return max(0, min(100, int(value)))


def clamp_highlight_rolloff_desaturation_pct(value: int) -> int:
    return max(0, min(100, int(value)))


def clamp_chroma_boost_amount_pct(value: int) -> int:
    return max(
        CHROMA_BOOST_AMOUNT_PCT_MIN,
        min(CHROMA_BOOST_AMOUNT_PCT_MAX, int(value)),
    )


def clamp_fade_seconds(value: float) -> float:
    return max(0.0, float(value))


def clamp_fade_in_end(end: float, *, start: float) -> float:
    return max(clamp_fade_seconds(end), clamp_fade_seconds(start))


def clamp_fade_out_start(start: float, *, end: float) -> float:
    return max(clamp_fade_seconds(start), clamp_fade_seconds(end))


def _parse_chroma_boost_apply_mode(
    value: object,
    _ctx: ParseCtx,
    label: str = "render.post_fx.chroma_boost.mode",
) -> ChromaBoostApplyMode:
    if value is False:
        value = "off"
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in CHROMA_BOOST_APPLY_MODES:
        allowed = ", ".join(f"'{mode}'" for mode in CHROMA_BOOST_APPLY_MODES)
        raise ValueError(f"{label} must be one of {allowed}, got {value!r}")
    return value  # type: ignore[return-value]


def _parse_chroma_boost_variant(
    value: object,
    _ctx: ParseCtx,
    label: str = "render.post_fx.chroma_boost.variant",
) -> ChromaBoostVariant:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in CHROMA_BOOST_VARIANTS:
        allowed = ", ".join(f"'{variant}'" for variant in CHROMA_BOOST_VARIANTS)
        raise ValueError(f"{label} must be one of {allowed}, got {value!r}")
    return value  # type: ignore[return-value]


def _parse_highlight_rolloff_apply_mode(
    value: Any,
    ctx: ParseCtx,
    label: str = "render.post_fx.highlight_rolloff.mode",
) -> HighlightRolloffApplyMode:
    if value is False:
        value = "off"
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in HIGHLIGHT_ROLLOFF_APPLY_MODES:
        allowed = ", ".join(f"'{mode}'" for mode in HIGHLIGHT_ROLLOFF_APPLY_MODES)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value


def _parse_fade_curve(
    value: Any,
    ctx: ParseCtx,
    label: str = "render.post_fx.fade.type",
) -> FadeCurve:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in FADE_CURVES:
        allowed = ", ".join(f"'{curve}'" for curve in FADE_CURVES)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value


def _parse_highlight_rolloff_curve(
    value: Any,
    ctx: ParseCtx,
    label: str = "render.post_fx.highlight_rolloff.curve",
) -> HighlightRolloffCurve:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in HIGHLIGHT_ROLLOFF_CURVES:
        allowed = ", ".join(f"'{curve}'" for curve in HIGHLIGHT_ROLLOFF_CURVES)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value


def _build_highlight_rolloff_config(parsed: dict[str, Any]) -> Any:
    from cleave.config import HighlightRolloffConfig

    threshold_pct = parsed["threshold_pct"]
    return HighlightRolloffConfig(
        mode=parsed["mode"],
        curve=parsed["curve"],
        threshold_pct=threshold_pct,
        ceiling_pct=clamp_highlight_rolloff_ceiling_pct(
            parsed["ceiling_pct"], threshold_pct=threshold_pct
        ),
        strength_pct=parsed["strength_pct"],
        softness_pct=parsed["softness_pct"],
        desaturation_pct=parsed["desaturation_pct"],
    )


def _build_chroma_boost_config(parsed: dict[str, Any]) -> Any:
    from cleave.config import ChromaBoostConfig

    return ChromaBoostConfig(
        mode=parsed["mode"],
        variant=parsed["variant"],
        amount_pct=parsed["amount_pct"],
    )


CHROMA_BOOST_SECTION = SectionDescriptor(
    yaml_key="chroma_boost",
    fields=(
        FieldDescriptor(
            "mode",
            DEFAULT_CHROMA_BOOST_APPLY_MODE,
            _parse_chroma_boost_apply_mode,
            dump_scalar,
        ),
        FieldDescriptor(
            "variant",
            DEFAULT_CHROMA_BOOST_VARIANT,
            _parse_chroma_boost_variant,
            dump_scalar,
        ),
        FieldDescriptor(
            "amount_pct",
            DEFAULT_CHROMA_BOOST_AMOUNT_PCT,
            lambda raw, _ctx, _label: clamp_chroma_boost_amount_pct(int(float(raw))),
            dump_scalar,
        ),
    ),
    build=_build_chroma_boost_config,
    optional=True,
    default_factory=lambda: _build_chroma_boost_config(
        {
            "mode": DEFAULT_CHROMA_BOOST_APPLY_MODE,
            "variant": DEFAULT_CHROMA_BOOST_VARIANT,
            "amount_pct": DEFAULT_CHROMA_BOOST_AMOUNT_PCT,
        }
    ),
)

HIGHLIGHT_ROLLOFF_SECTION = SectionDescriptor(
    yaml_key="highlight_rolloff",
    fields=(
        FieldDescriptor(
            "mode",
            DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE,
            _parse_highlight_rolloff_apply_mode,
            dump_scalar,
        ),
        FieldDescriptor(
            "curve",
            DEFAULT_HIGHLIGHT_ROLLOFF_CURVE,
            _parse_highlight_rolloff_curve,
            dump_scalar,
        ),
        FieldDescriptor(
            "threshold_pct",
            DEFAULT_HIGHLIGHT_ROLLOFF_THRESHOLD_PCT,
            lambda raw, _ctx, _label: clamp_highlight_rolloff_threshold_pct(
                int(float(raw))
            ),
            dump_scalar,
        ),
        FieldDescriptor(
            "ceiling_pct",
            DEFAULT_HIGHLIGHT_ROLLOFF_CEILING_PCT,
            lambda raw, _ctx, _label: clamp_highlight_rolloff_ceiling_pct(
                int(float(raw))
            ),
            dump_scalar,
        ),
        FieldDescriptor(
            "strength_pct",
            DEFAULT_HIGHLIGHT_ROLLOFF_STRENGTH_PCT,
            lambda raw, _ctx, _label: clamp_highlight_rolloff_strength_pct(
                int(float(raw))
            ),
            dump_scalar,
        ),
        FieldDescriptor(
            "softness_pct",
            DEFAULT_HIGHLIGHT_ROLLOFF_SOFTNESS_PCT,
            lambda raw, _ctx, _label: clamp_highlight_rolloff_softness_pct(
                int(float(raw))
            ),
            dump_scalar,
        ),
        FieldDescriptor(
            "desaturation_pct",
            DEFAULT_HIGHLIGHT_ROLLOFF_DESATURATION_PCT,
            lambda raw, _ctx, _label: clamp_highlight_rolloff_desaturation_pct(
                int(float(raw))
            ),
            dump_scalar,
        ),
    ),
    build=_build_highlight_rolloff_config,
    optional=True,
    default_factory=lambda: _build_highlight_rolloff_config(
        {
            "mode": DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE,
            "curve": DEFAULT_HIGHLIGHT_ROLLOFF_CURVE,
            "threshold_pct": DEFAULT_HIGHLIGHT_ROLLOFF_THRESHOLD_PCT,
            "ceiling_pct": DEFAULT_HIGHLIGHT_ROLLOFF_CEILING_PCT,
            "strength_pct": DEFAULT_HIGHLIGHT_ROLLOFF_STRENGTH_PCT,
            "softness_pct": DEFAULT_HIGHLIGHT_ROLLOFF_SOFTNESS_PCT,
            "desaturation_pct": DEFAULT_HIGHLIGHT_ROLLOFF_DESATURATION_PCT,
        }
    ),
)

def _fade_side_section(
    yaml_key: str,
    *,
    default_start: float,
    default_end: float,
    fade_in: bool,
) -> SectionDescriptor:
    def build(parsed: dict[str, Any]) -> Any:
        from cleave.config import FadeSideConfig

        if fade_in:
            start = clamp_fade_seconds(parsed["start"])
            end = clamp_fade_in_end(parsed["end"], start=start)
        else:
            end = clamp_fade_seconds(parsed["end"])
            start = clamp_fade_out_start(parsed["start"], end=end)
        return FadeSideConfig(start=start, end=end, type=parsed["type"])

    def default_factory() -> Any:
        return build(
            {
                "start": default_start,
                "end": default_end,
                "type": DEFAULT_FADE_CURVE,
            }
        )

    return SectionDescriptor(
        yaml_key=yaml_key,
        fields=(
            FieldDescriptor(
                "start",
                default_start,
                lambda raw, ctx, label: float(require_non_negative_number(raw, label)),
                dump_scalar,
            ),
            FieldDescriptor(
                "end",
                default_end,
                lambda raw, ctx, label: float(require_non_negative_number(raw, label)),
                dump_scalar,
            ),
            FieldDescriptor(
                "type",
                DEFAULT_FADE_CURVE,
                _parse_fade_curve,
                dump_scalar,
            ),
        ),
        build=build,
        optional=True,
        default_factory=default_factory,
    )


FADE_IN_SECTION = _fade_side_section(
    "fade_in",
    default_start=DEFAULT_FADE_IN_START,
    default_end=DEFAULT_FADE_IN_END,
    fade_in=True,
)
FADE_OUT_SECTION = _fade_side_section(
    "fade_out",
    default_start=DEFAULT_FADE_OUT_START,
    default_end=DEFAULT_FADE_OUT_END,
    fade_in=False,
)


def _build_fade_config(parsed: dict[str, Any]) -> Any:
    from cleave.config import FadeConfig

    return FadeConfig(fade_in=parsed["fade_in"], fade_out=parsed["fade_out"])


def _default_fade_config() -> Any:
    fade_in_factory = FADE_IN_SECTION.default_factory
    fade_out_factory = FADE_OUT_SECTION.default_factory
    if fade_in_factory is None or fade_out_factory is None:
        raise RuntimeError("fade side sections require default_factory")
    return _build_fade_config(
        {
            "fade_in": fade_in_factory(),
            "fade_out": fade_out_factory(),
        }
    )


FADE_SECTION = SectionDescriptor(
    yaml_key="fade",
    fields=(FADE_IN_SECTION, FADE_OUT_SECTION),
    build=_build_fade_config,
    optional=True,
    default_factory=_default_fade_config,
)

RENDER_POST_FX_FIELDS: tuple[SchemaField, ...] = (
    FieldDescriptor(
        "enabled",
        DEFAULT_RENDER_POST_FX_ENABLED,
        lambda raw, _ctx, _label: bool(raw),
        dump_scalar,
    ),
    FieldDescriptor(
        "locked",
        DEFAULT_RENDER_POST_FX_LOCKED,
        lambda raw, _ctx, _label: bool(raw),
        dump_scalar,
    ),
    FADE_SECTION,
    HIGHLIGHT_ROLLOFF_SECTION,
    CHROMA_BOOST_SECTION,
)


def _build_render_post_fx_config(parsed: dict[str, Any]) -> Any:
    from cleave.config import RenderPostFxConfig

    return RenderPostFxConfig(**parsed)


def parse_render_post_fx_section(post_fx_map: dict[str, Any]) -> Any:
    parsed = parse_section_fields(
        post_fx_map,
        RENDER_POST_FX_FIELDS,
        ParseCtx(),
        "render.post_fx",
    )
    return _build_render_post_fx_config(parsed)


def post_fx_persist_values(ctx: PersistCtx) -> dict[str, Any]:
    runtime = ctx.session.render_post_fx
    return {
        "enabled": runtime.enabled,
        "locked": runtime.locked,
        "fade": {
            "fade_in": {
                "start": runtime.fade.fade_in.start,
                "end": runtime.fade.fade_in.end,
                "type": runtime.fade.fade_in.type,
            },
            "fade_out": {
                "start": runtime.fade.fade_out.start,
                "end": runtime.fade.fade_out.end,
                "type": runtime.fade.fade_out.type,
            },
        },
        "highlight_rolloff": {
            "mode": runtime.highlight_rolloff.mode,
            "curve": runtime.highlight_rolloff.curve,
            "threshold_pct": runtime.highlight_rolloff.threshold_pct,
            "ceiling_pct": runtime.highlight_rolloff.ceiling_pct,
            "strength_pct": runtime.highlight_rolloff.strength_pct,
            "softness_pct": runtime.highlight_rolloff.softness_pct,
            "desaturation_pct": runtime.highlight_rolloff.desaturation_pct,
        },
        "chroma_boost": {
            "mode": runtime.chroma_boost.mode,
            "variant": runtime.chroma_boost.variant,
            "amount_pct": runtime.chroma_boost.amount_pct,
        },
    }


def default_highlight_rolloff_runtime_values() -> dict[str, Any]:
    return {
        "mode": DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE,
        "curve": DEFAULT_HIGHLIGHT_ROLLOFF_CURVE,
        "threshold_pct": DEFAULT_HIGHLIGHT_ROLLOFF_THRESHOLD_PCT,
        "ceiling_pct": DEFAULT_HIGHLIGHT_ROLLOFF_CEILING_PCT,
        "strength_pct": DEFAULT_HIGHLIGHT_ROLLOFF_STRENGTH_PCT,
        "softness_pct": DEFAULT_HIGHLIGHT_ROLLOFF_SOFTNESS_PCT,
        "desaturation_pct": DEFAULT_HIGHLIGHT_ROLLOFF_DESATURATION_PCT,
    }


def default_chroma_boost_runtime_values() -> dict[str, Any]:
    return {
        "mode": DEFAULT_CHROMA_BOOST_APPLY_MODE,
        "variant": DEFAULT_CHROMA_BOOST_VARIANT,
        "amount_pct": DEFAULT_CHROMA_BOOST_AMOUNT_PCT,
    }


def default_fade_side_runtime_values(start: float, end: float) -> dict[str, Any]:
    return {
        "start": start,
        "end": end,
        "type": DEFAULT_FADE_CURVE,
        "expanded": False,
    }


def default_fade_runtime_values() -> dict[str, Any]:
    return {
        "expanded": False,
        "fade_in": default_fade_side_runtime_values(
            DEFAULT_FADE_IN_START, DEFAULT_FADE_IN_END
        ),
        "fade_out": default_fade_side_runtime_values(
            DEFAULT_FADE_OUT_START, DEFAULT_FADE_OUT_END
        ),
    }


def default_render_post_fx_runtime_values() -> dict[str, Any]:
    return {
        "enabled": DEFAULT_RENDER_POST_FX_ENABLED,
        "expanded": False,
        "fade": default_fade_runtime_values(),
        "highlight_rolloff": default_highlight_rolloff_runtime_values(),
        "highlight_rolloff_expanded": False,
        "chroma_boost": default_chroma_boost_runtime_values(),
        "chroma_boost_expanded": False,
        "locked": DEFAULT_RENDER_POST_FX_LOCKED,
    }
