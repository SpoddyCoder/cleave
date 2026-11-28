"""Render pattern-mask YAML parse, serialize, and defaults."""

from __future__ import annotations

from typing import Any, Literal

from cleave.config_schema.descriptors import (
    FieldDescriptor,
    ParseCtx,
    PersistCtx,
    SchemaField,
    dump_scalar,
    parse_section_fields,
    require_non_negative_number,
)

PatternMaskType = Literal["strips", "bars", "radial", "checker", "plasma"]

# What the transition is counted in: beats or bars of the song, or seconds.
PatternMaskTransitionUnit = Literal["beats", "bars", "seconds"]

PATTERN_MASK_TRANSITION_UNITS: tuple[PatternMaskTransitionUnit, ...] = (
    "beats",
    "bars",
    "seconds",
)

PATTERN_MASK_TYPES: tuple[PatternMaskType, ...] = (
    "strips",
    "bars",
    "radial",
    "checker",
    "plasma",
)

DEFAULT_RENDER_PATTERN_MASK_ENABLED = False
DEFAULT_RENDER_PATTERN_MASK_TYPE: PatternMaskType = "strips"
DEFAULT_RENDER_PATTERN_MASK_FEATHER_PCT = 0
DEFAULT_RENDER_PATTERN_MASK_DENSITY = 1.0
DEFAULT_RENDER_PATTERN_MASK_INVERT = False
DEFAULT_RENDER_PATTERN_MASK_SEED = 0
DEFAULT_RENDER_PATTERN_MASK_TRANSITION = 1.0
DEFAULT_RENDER_PATTERN_MASK_TRANSITION_UNIT: PatternMaskTransitionUnit = "beats"
DEFAULT_RENDER_PATTERN_MASK_LOCKED = False
PATTERN_MASK_DENSITY_MIN = 1.0
PATTERN_MASK_DENSITY_MAX = 10.0
PATTERN_MASK_DENSITY_STEP = 0.1
PATTERN_MASK_DENSITY_STEP_LARGE = 1.0
PATTERN_MASK_TRANSITION_MIN = 0.0
PATTERN_MASK_TRANSITION_MAX = 5.0
PATTERN_MASK_TRANSITION_STEP = 0.1
PATTERN_MASK_TRANSITION_STEP_LARGE = 1.0
# The lengths a transition counted in beats or bars can take.
PATTERN_MASK_TRANSITION_BEATS: tuple[float, ...] = (0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0)
PATTERN_MASK_TRANSITION_BARS: tuple[float, ...] = (0.0, 0.5, 1.0, 2.0)
PATTERN_MASK_FEATHER_PCT_MIN = 0
PATTERN_MASK_FEATHER_PCT_MAX = 100
PATTERN_MASK_FEATHER_PCT_STEP = 1
PATTERN_MASK_FEATHER_PCT_STEP_LARGE = 10


def clamp_pattern_mask_density(value: float) -> float:
    return round(
        max(PATTERN_MASK_DENSITY_MIN, min(PATTERN_MASK_DENSITY_MAX, float(value))),
        1,
    )


def pattern_mask_transition_steps(
    unit: PatternMaskTransitionUnit,
) -> tuple[float, ...] | None:
    """The lengths a beats or bars transition can take; None for seconds."""
    if unit == "beats":
        return PATTERN_MASK_TRANSITION_BEATS
    if unit == "bars":
        return PATTERN_MASK_TRANSITION_BARS
    return None


def clamp_pattern_mask_transition(
    value: float, unit: PatternMaskTransitionUnit = "seconds"
) -> float:
    """*value* as a length *unit* allows: the nearest step for beats or bars."""
    steps = pattern_mask_transition_steps(unit)
    if steps is not None:
        return min(steps, key=lambda step: abs(step - float(value)))
    return round(
        max(
            PATTERN_MASK_TRANSITION_MIN,
            min(PATTERN_MASK_TRANSITION_MAX, float(value)),
        ),
        1,
    )


def clamp_pattern_mask_feather_pct(value: int) -> int:
    return max(
        PATTERN_MASK_FEATHER_PCT_MIN,
        min(PATTERN_MASK_FEATHER_PCT_MAX, int(value)),
    )


def _parse_pattern_mask_type(
    value: Any,
    _ctx: ParseCtx,
    label: str = "render.pattern_mask.type",
) -> PatternMaskType:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in PATTERN_MASK_TYPES:
        allowed = ", ".join(f"'{item}'" for item in PATTERN_MASK_TYPES)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value  # type: ignore[return-value]


def _parse_pattern_mask_transition_unit(
    value: Any,
    _ctx: ParseCtx,
    label: str = "render.pattern_mask.transition_unit",
) -> PatternMaskTransitionUnit:
    if value not in PATTERN_MASK_TRANSITION_UNITS:
        allowed = ", ".join(f"'{item}'" for item in PATTERN_MASK_TRANSITION_UNITS)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value  # type: ignore[return-value]


def _parse_pattern_mask_seed(
    value: Any,
    _ctx: ParseCtx,
    label: str = "render.pattern_mask.seed",
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc


RENDER_PATTERN_MASK_FIELDS: tuple[SchemaField, ...] = (
    FieldDescriptor(
        "enabled",
        DEFAULT_RENDER_PATTERN_MASK_ENABLED,
        lambda raw, _ctx, _label: bool(raw),
        dump_scalar,
    ),
    FieldDescriptor(
        "locked",
        DEFAULT_RENDER_PATTERN_MASK_LOCKED,
        lambda raw, _ctx, _label: bool(raw),
        dump_scalar,
    ),
    FieldDescriptor(
        "type",
        DEFAULT_RENDER_PATTERN_MASK_TYPE,
        _parse_pattern_mask_type,
        dump_scalar,
    ),
    FieldDescriptor(
        "density",
        DEFAULT_RENDER_PATTERN_MASK_DENSITY,
        lambda raw, _ctx, label: clamp_pattern_mask_density(
            float(require_non_negative_number(raw, label))
        ),
        dump_scalar,
    ),
    FieldDescriptor(
        "feather_pct",
        DEFAULT_RENDER_PATTERN_MASK_FEATHER_PCT,
        lambda raw, _ctx, _label: clamp_pattern_mask_feather_pct(int(float(raw))),
        dump_scalar,
    ),
    FieldDescriptor(
        "invert",
        DEFAULT_RENDER_PATTERN_MASK_INVERT,
        lambda raw, _ctx, _label: bool(raw),
        dump_scalar,
    ),
    FieldDescriptor(
        "transition_unit",
        DEFAULT_RENDER_PATTERN_MASK_TRANSITION_UNIT,
        _parse_pattern_mask_transition_unit,
        dump_scalar,
    ),
    FieldDescriptor(
        "transition",
        DEFAULT_RENDER_PATTERN_MASK_TRANSITION,
        lambda raw, _ctx, label: float(require_non_negative_number(raw, label)),
        dump_scalar,
    ),
    FieldDescriptor(
        "seed",
        DEFAULT_RENDER_PATTERN_MASK_SEED,
        _parse_pattern_mask_seed,
        dump_scalar,
    ),
)


def _build_render_pattern_mask_config(parsed: dict[str, Any]) -> Any:
    from cleave.config import RenderPatternMaskConfig

    # The transition's steps depend on its unit, so it is clamped once both are read.
    parsed["transition"] = clamp_pattern_mask_transition(
        parsed["transition"], parsed["transition_unit"]
    )
    return RenderPatternMaskConfig(**parsed)


def parse_render_pattern_mask_section(pattern_mask_map: dict[str, Any]) -> Any:
    parsed = parse_section_fields(
        pattern_mask_map,
        RENDER_PATTERN_MASK_FIELDS,
        ParseCtx(),
        "render.pattern_mask",
    )
    return _build_render_pattern_mask_config(parsed)


def pattern_mask_persist_values(ctx: PersistCtx) -> dict[str, Any]:
    runtime = ctx.session.pattern_mask
    return {
        "enabled": runtime.enabled,
        "locked": runtime.locked,
        "type": runtime.type,
        "density": runtime.density,
        "feather_pct": runtime.feather_pct,
        "invert": runtime.invert,
        "transition_unit": runtime.transition_unit,
        "transition": runtime.transition,
        "seed": runtime.seed,
    }


def default_render_pattern_mask_runtime_values() -> dict[str, Any]:
    return {
        "enabled": DEFAULT_RENDER_PATTERN_MASK_ENABLED,
        "type": DEFAULT_RENDER_PATTERN_MASK_TYPE,
        "density": DEFAULT_RENDER_PATTERN_MASK_DENSITY,
        "feather_pct": DEFAULT_RENDER_PATTERN_MASK_FEATHER_PCT,
        "invert": DEFAULT_RENDER_PATTERN_MASK_INVERT,
        "transition_unit": DEFAULT_RENDER_PATTERN_MASK_TRANSITION_UNIT,
        "transition": DEFAULT_RENDER_PATTERN_MASK_TRANSITION,
        "seed": DEFAULT_RENDER_PATTERN_MASK_SEED,
        "locked": DEFAULT_RENDER_PATTERN_MASK_LOCKED,
    }
