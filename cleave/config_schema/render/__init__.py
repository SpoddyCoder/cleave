"""Render YAML parse, serialize, and defaults (overlays, post-FX, pattern mask)."""

from __future__ import annotations

from typing import Any

from cleave.config_schema.descriptors import PersistCtx, as_mapping, dump_section_fields
from cleave.config_schema.render.overlays import (
    DEFAULT_RENDER_OVERLAY_ANIMATION_TYPE,
    DEFAULT_RENDER_OVERLAY_APPEAR_AT,
    DEFAULT_RENDER_OVERLAY_BACKGROUND_COLOUR,
    DEFAULT_RENDER_OVERLAY_BACKGROUND_MARGIN,
    DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY,
    DEFAULT_RENDER_OVERLAY_BACKGROUND_PADDING,
    DEFAULT_RENDER_OVERLAY_BODY,
    DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
    DEFAULT_RENDER_OVERLAY_BORDER_COLOUR,
    DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
    DEFAULT_RENDER_OVERLAY_CARD_ENABLED,
    DEFAULT_RENDER_OVERLAY_DISAPPEAR_AT,
    DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    DEFAULT_RENDER_OVERLAY_FONT,
    DEFAULT_RENDER_OVERLAY_POSITION,
    DEFAULT_RENDER_OVERLAY_SLIDE_DIRECTION,
    DEFAULT_RENDER_OVERLAY_TEXT_COLOUR,
    DEFAULT_RENDER_OVERLAY_TITLE,
    DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
    DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
    DEFAULT_RENDER_OVERLAYS_LOCKED,
    RENDER_OVERLAY_ANIMATION_TYPE_HELP_ENTRIES,
    RENDER_OVERLAY_ANIMATION_TYPES,
    RENDER_OVERLAY_POSITIONS,
    RENDER_OVERLAY_SLIDE_DIRECTION_HELP_ENTRIES,
    RENDER_OVERLAY_SLIDE_DIRECTIONS,
    RENDER_OVERLAYS_FIELDS,
    RenderOverlayAnimationType,
    RenderOverlayPosition,
    RenderOverlaySlideDirection,
    default_render_overlay_animation_runtime_values,
    default_render_overlay_card_runtime_values,
    default_render_overlay_closing_animation_runtime_values,
    default_render_overlays_config,
    default_render_overlays_runtime_values,
    overlays_persist_values,
    parse_render_overlays_section,
    render_overlays_base,
)
from cleave.config_schema.render.pattern_mask import (
    DEFAULT_RENDER_PATTERN_MASK_DENSITY,
    DEFAULT_RENDER_PATTERN_MASK_ENABLED,
    DEFAULT_RENDER_PATTERN_MASK_FEATHER_PCT,
    DEFAULT_RENDER_PATTERN_MASK_INVERT,
    DEFAULT_RENDER_PATTERN_MASK_LOCKED,
    DEFAULT_RENDER_PATTERN_MASK_SEED,
    DEFAULT_RENDER_PATTERN_MASK_TRANSITION,
    DEFAULT_RENDER_PATTERN_MASK_TYPE,
    PATTERN_MASK_DENSITY_MAX,
    PATTERN_MASK_DENSITY_MIN,
    PATTERN_MASK_DENSITY_STEP,
    PATTERN_MASK_DENSITY_STEP_LARGE,
    PATTERN_MASK_FEATHER_PCT_MAX,
    PATTERN_MASK_FEATHER_PCT_MIN,
    PATTERN_MASK_FEATHER_PCT_STEP,
    PATTERN_MASK_FEATHER_PCT_STEP_LARGE,
    PATTERN_MASK_TRANSITION_MAX,
    PATTERN_MASK_TRANSITION_MIN,
    PATTERN_MASK_TRANSITION_STEP,
    PATTERN_MASK_TRANSITION_STEP_LARGE,
    PATTERN_MASK_TYPES,
    RENDER_PATTERN_MASK_FIELDS,
    PatternMaskType,
    clamp_pattern_mask_density,
    clamp_pattern_mask_feather_pct,
    clamp_pattern_mask_transition,
    default_render_pattern_mask_runtime_values,
    parse_render_pattern_mask_section,
    pattern_mask_persist_values,
)
from cleave.config_schema.render.post_fx import (
    CHROMA_BOOST_AMOUNT_PCT_MAX,
    CHROMA_BOOST_AMOUNT_PCT_MIN,
    CHROMA_BOOST_APPLY_MODE_HELP_ENTRIES,
    CHROMA_BOOST_APPLY_MODES,
    CHROMA_BOOST_VARIANT_HELP_ENTRIES,
    CHROMA_BOOST_VARIANTS,
    DEFAULT_CHROMA_BOOST_AMOUNT_PCT,
    DEFAULT_CHROMA_BOOST_APPLY_MODE,
    DEFAULT_CHROMA_BOOST_VARIANT,
    DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE,
    DEFAULT_HIGHLIGHT_ROLLOFF_CEILING_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_CURVE,
    DEFAULT_HIGHLIGHT_ROLLOFF_DESATURATION_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_SOFTNESS_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_STRENGTH_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_THRESHOLD_PCT,
    DEFAULT_RENDER_POST_FX_ENABLED,
    DEFAULT_RENDER_POST_FX_FADE_IN,
    DEFAULT_RENDER_POST_FX_FADE_OUT,
    DEFAULT_RENDER_POST_FX_LOCKED,
    HIGHLIGHT_ROLLOFF_APPLY_MODE_HELP_ENTRIES,
    HIGHLIGHT_ROLLOFF_APPLY_MODES,
    HIGHLIGHT_ROLLOFF_CURVE_HELP_ENTRIES,
    HIGHLIGHT_ROLLOFF_CURVES,
    HIGHLIGHT_ROLLOFF_STRENGTH_PCT_MAX,
    HIGHLIGHT_ROLLOFF_THRESHOLD_PCT_MAX,
    HIGHLIGHT_ROLLOFF_THRESHOLD_PCT_MIN,
    RENDER_POST_FX_FIELDS,
    ChromaBoostApplyMode,
    ChromaBoostVariant,
    HighlightRolloffApplyMode,
    HighlightRolloffCurve,
    clamp_chroma_boost_amount_pct,
    clamp_highlight_rolloff_ceiling_pct,
    clamp_highlight_rolloff_desaturation_pct,
    clamp_highlight_rolloff_softness_pct,
    clamp_highlight_rolloff_strength_pct,
    clamp_highlight_rolloff_threshold_pct,
    default_chroma_boost_runtime_values,
    default_highlight_rolloff_runtime_values,
    default_render_post_fx_runtime_values,
    parse_render_post_fx_section,
    post_fx_persist_values,
)

DEFAULT_RENDER_FPS = 30
DEFAULT_RENDER_WIDTH = 1280
DEFAULT_RENDER_HEIGHT = 720
DEFAULT_HDR_COMPOSITING = True


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
    overlays_raw = render_map.get("overlays")
    post_fx_raw = render_map.get("post_fx")
    pattern_mask_raw = render_map.get("pattern_mask")
    overlays = (
        parse_render_overlays_section(as_mapping(overlays_raw, "render.overlays"))
        if overlays_raw is not None
        else None
    )
    post_fx = (
        parse_render_post_fx_section(as_mapping(post_fx_raw, "render.post_fx"))
        if post_fx_raw is not None
        else None
    )
    pattern_mask = (
        parse_render_pattern_mask_section(
            as_mapping(pattern_mask_raw, "render.pattern_mask")
        )
        if pattern_mask_raw is not None
        else None
    )
    hdr_raw = render_map.get("hdr_compositing")
    hdr_compositing = (
        DEFAULT_HDR_COMPOSITING if hdr_raw is None else bool(hdr_raw)
    )
    return RenderConfig(
        fps=fps,
        width=width,
        height=height,
        hdr_compositing=hdr_compositing,
        overlays=overlays,
        post_fx=post_fx,
        pattern_mask=pattern_mask,
    )


def persist_render(ctx: PersistCtx) -> dict[str, Any]:
    overlays = dump_section_fields(
        RENDER_OVERLAYS_FIELDS,
        overlays_persist_values(ctx),
        ctx,
    )
    post_fx = dump_section_fields(
        RENDER_POST_FX_FIELDS, post_fx_persist_values(ctx), ctx
    )
    pattern_mask = dump_section_fields(
        RENDER_PATTERN_MASK_FIELDS, pattern_mask_persist_values(ctx), ctx
    )
    from cleave.config import render_fps, render_hdr_compositing, render_output_size

    width, height = render_output_size(ctx.cfg)
    return {
        "fps": render_fps(ctx.cfg),
        "width": width,
        "height": height,
        "hdr_compositing": render_hdr_compositing(ctx.cfg),
        "overlays": overlays,
        "post_fx": post_fx,
        "pattern_mask": pattern_mask,
    }
