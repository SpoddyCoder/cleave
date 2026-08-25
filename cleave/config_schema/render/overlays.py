"""Render overlay YAML parse, serialize, and defaults."""

from __future__ import annotations

from typing import Any, Literal

from cleave.config_schema.descriptors import (
    FieldDescriptor,
    ParseCtx,
    PersistCtx,
    SchemaField,
    SectionDescriptor,
    dump_hex_colour,
    dump_scalar,
    parse_hex_colour,
    parse_non_negative_float,
    parse_non_negative_int,
    parse_section_fields,
    section_field_defaults,
)

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
DEFAULT_RENDER_OVERLAY_APPEAR_AT = 10.0
DEFAULT_RENDER_OVERLAY_DISAPPEAR_AT = 0.0
DEFAULT_RENDER_OVERLAY_DISPLAY_TIME = 30.0

RenderOverlayAnimationType = Literal[
    "fade", "slide", "slide-fade", "cascade", "wipe", "cascade-wipe"
]

RENDER_OVERLAY_ANIMATION_TYPES: tuple[RenderOverlayAnimationType, ...] = (
    "fade",
    "slide",
    "slide-fade",
    "cascade",
    "wipe",
    "cascade-wipe",
)

RENDER_OVERLAY_ANIMATION_TYPE_HELP_ENTRIES: tuple[
    tuple[RenderOverlayAnimationType, str], ...
] = (
    ("fade", "Smooth fade in and out"),
    ("slide", "Panel slides in from an edge"),
    ("slide-fade", "Slide plus fade"),
    ("cascade", "Staggered slide of panel elements"),
    ("wipe", "Directional wipe reveal in place"),
    ("cascade-wipe", "Staggered wipe of panel elements"),
)

DEFAULT_RENDER_OVERLAY_ANIMATION_TYPE: RenderOverlayAnimationType = "fade"

RenderOverlaySlideDirection = Literal["left", "right", "top", "bottom"]

RENDER_OVERLAY_SLIDE_DIRECTIONS: tuple[RenderOverlaySlideDirection, ...] = (
    "left",
    "right",
    "top",
    "bottom",
)

RENDER_OVERLAY_SLIDE_DIRECTION_HELP_ENTRIES: tuple[
    tuple[RenderOverlaySlideDirection, str], ...
] = (
    ("left", "Enter from the left"),
    ("right", "Enter from the right"),
    ("top", "Enter from the top"),
    ("bottom", "Enter from the bottom"),
)

DEFAULT_RENDER_OVERLAY_SLIDE_DIRECTION: RenderOverlaySlideDirection = "left"

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


def _parse_render_overlay_position(
    value: Any, ctx: ParseCtx, label: str = "render.overlays.position"
) -> RenderOverlayPosition:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in RENDER_OVERLAY_POSITIONS:
        allowed = ", ".join(f"'{pos}'" for pos in RENDER_OVERLAY_POSITIONS)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value


def _parse_render_overlay_animation_type(
    value: Any,
    ctx: ParseCtx,
    label: str = "render.overlays.animation.type",
) -> RenderOverlayAnimationType:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in RENDER_OVERLAY_ANIMATION_TYPES:
        allowed = ", ".join(f"'{item}'" for item in RENDER_OVERLAY_ANIMATION_TYPES)
        raise ValueError(f"{label} must be one of: {allowed}")
    return value


def _parse_render_overlay_slide_direction(
    value: Any,
    ctx: ParseCtx,
    label: str = "render.overlays.animation.slide-direction",
) -> RenderOverlaySlideDirection:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if value not in RENDER_OVERLAY_SLIDE_DIRECTIONS:
        allowed = ", ".join(f"'{item}'" for item in RENDER_OVERLAY_SLIDE_DIRECTIONS)
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


def _build_render_overlay_animation_config(parsed: dict[str, Any]) -> Any:
    from cleave.config import RenderOverlayAnimationConfig

    return RenderOverlayAnimationConfig(
        type=parsed["type"],
        slide_direction=parsed["slide_direction"],
        appear_at=parsed["appear_at"],
        display_time=parsed["display_time"],
    )


def _build_render_overlay_closing_animation_config(parsed: dict[str, Any]) -> Any:
    from cleave.config import RenderOverlayClosingAnimationConfig

    return RenderOverlayClosingAnimationConfig(
        type=parsed["type"],
        slide_direction=parsed["slide_direction"],
        disappear_at=parsed["disappear_at"],
        display_time=parsed["display_time"],
    )


def _build_render_overlay_card_config(parsed: dict[str, Any]) -> Any:
    from cleave.config import RenderOverlayCardConfig

    return RenderOverlayCardConfig(
        enabled=parsed["enabled"],
        title=parsed["title"],
        body=parsed["body"],
        animation=parsed["animation"],
        position=parsed["position"],
        background=parsed["background"],
    )


def _build_render_overlays_config(parsed: dict[str, Any]) -> Any:
    from cleave.config import RenderOverlaysConfig

    return RenderOverlaysConfig(
        opening_card=parsed["opening_card"],
        closing_card=parsed["closing_card"],
        locked=parsed["locked"],
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
            _parse_overlay_content,
            _dump_overlay_content,
        ),
        FieldDescriptor(
            "font",
            DEFAULT_RENDER_OVERLAY_FONT,
            _parse_overlay_font,
            dump_scalar,
        ),
        FieldDescriptor(
            "font-size",
            font_size_default,
            parse_non_negative_int,
            dump_scalar,
            attr_key="font_size",
        ),
        FieldDescriptor(
            colour_yaml_key,
            DEFAULT_RENDER_OVERLAY_TEXT_COLOUR,
            lambda raw, ctx, label: parse_hex_colour(raw, label),
            dump_hex_colour,
            yaml_alt_keys=colour_alt_keys,
            attr_key="colour",
        ),
        FieldDescriptor(
            "background-colour",
            None,
            _parse_optional_background_colour,
            dump_hex_colour,
            attr_key="background_colour",
            omit_when=lambda value: value is None,
        ),
        FieldDescriptor(
            "margin-bottom",
            margin_bottom_default,
            parse_non_negative_int,
            dump_scalar,
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
        section_field_defaults(RENDER_OVERLAY_TITLE_SECTION)
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
        section_field_defaults(RENDER_OVERLAY_BODY_SECTION)
    ),
)

RENDER_OVERLAY_BORDER_SECTION = SectionDescriptor(
    yaml_key="border",
    fields=(
        FieldDescriptor(
            "colour",
            DEFAULT_RENDER_OVERLAY_BORDER_COLOUR,
            lambda raw, ctx, label: parse_hex_colour(
                "#ffffff" if raw is None else raw, label
            ),
            dump_hex_colour,
        ),
        FieldDescriptor(
            "width",
            DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
            parse_non_negative_int,
            dump_scalar,
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
            parse_non_negative_int,
            dump_scalar,
        ),
        FieldDescriptor(
            "padding",
            DEFAULT_RENDER_OVERLAY_BACKGROUND_PADDING,
            parse_non_negative_int,
            dump_scalar,
        ),
        FieldDescriptor(
            "colour",
            DEFAULT_RENDER_OVERLAY_BACKGROUND_COLOUR,
            lambda raw, ctx, label: parse_hex_colour(
                "#000000" if raw is None else raw, label
            ),
            dump_hex_colour,
        ),
        FieldDescriptor(
            "opacity",
            DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY,
            parse_non_negative_float,
            dump_scalar,
        ),
        RENDER_OVERLAY_BORDER_SECTION,
    ),
    build=_build_render_overlay_background,
)


def _render_overlay_animation_shared_fields() -> tuple[FieldDescriptor, ...]:
    return (
        FieldDescriptor(
            "type",
            DEFAULT_RENDER_OVERLAY_ANIMATION_TYPE,
            _parse_render_overlay_animation_type,
            dump_scalar,
        ),
        FieldDescriptor(
            "slide-direction",
            DEFAULT_RENDER_OVERLAY_SLIDE_DIRECTION,
            _parse_render_overlay_slide_direction,
            dump_scalar,
            attr_key="slide_direction",
        ),
    )


def _render_overlay_display_time_field() -> FieldDescriptor:
    return FieldDescriptor(
        "display-time",
        DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
        parse_non_negative_float,
        dump_scalar,
        attr_key="display_time",
    )


RENDER_OVERLAY_OPENING_ANIMATION_SECTION = SectionDescriptor(
    yaml_key="animation",
    fields=(
        *_render_overlay_animation_shared_fields(),
        FieldDescriptor(
            "appear-at",
            DEFAULT_RENDER_OVERLAY_APPEAR_AT,
            parse_non_negative_float,
            dump_scalar,
            attr_key="appear_at",
        ),
        _render_overlay_display_time_field(),
    ),
    build=_build_render_overlay_animation_config,
    optional=True,
    default_factory=lambda: _build_render_overlay_animation_config(
        section_field_defaults(RENDER_OVERLAY_OPENING_ANIMATION_SECTION)
    ),
)

RENDER_OVERLAY_CLOSING_ANIMATION_SECTION = SectionDescriptor(
    yaml_key="animation",
    fields=(
        *_render_overlay_animation_shared_fields(),
        FieldDescriptor(
            "disappear-at",
            DEFAULT_RENDER_OVERLAY_DISAPPEAR_AT,
            parse_non_negative_float,
            dump_scalar,
            attr_key="disappear_at",
        ),
        _render_overlay_display_time_field(),
    ),
    build=_build_render_overlay_closing_animation_config,
    optional=True,
    default_factory=lambda: _build_render_overlay_closing_animation_config(
        section_field_defaults(RENDER_OVERLAY_CLOSING_ANIMATION_SECTION)
    ),
)


def _render_overlay_card_fields(
    animation_section: SectionDescriptor,
) -> tuple[SchemaField, ...]:
    return (
        FieldDescriptor(
            "enabled",
            True,
            lambda raw, _ctx, _label: bool(raw),
            dump_scalar,
        ),
        RENDER_OVERLAY_TITLE_SECTION,
        RENDER_OVERLAY_BODY_SECTION,
        animation_section,
        FieldDescriptor(
            "position",
            DEFAULT_RENDER_OVERLAY_POSITION,
            _parse_render_overlay_position,
            dump_scalar,
        ),
        RENDER_OVERLAY_BACKGROUND_SECTION,
    )


RENDER_OVERLAY_OPENING_CARD_FIELDS: tuple[SchemaField, ...] = (
    _render_overlay_card_fields(RENDER_OVERLAY_OPENING_ANIMATION_SECTION)
)

RENDER_OVERLAY_CLOSING_CARD_FIELDS: tuple[SchemaField, ...] = (
    _render_overlay_card_fields(RENDER_OVERLAY_CLOSING_ANIMATION_SECTION)
)

RENDER_OVERLAY_OPENING_CARD_SECTION = SectionDescriptor(
    yaml_key="opening-card",
    fields=RENDER_OVERLAY_OPENING_CARD_FIELDS,
    build=_build_render_overlay_card_config,
    optional=True,
    default_factory=lambda: _build_render_overlay_card_config(
        parse_section_fields(
            {},
            RENDER_OVERLAY_OPENING_CARD_FIELDS,
            ParseCtx(),
            "render.overlays.opening-card",
        )
    ),
    attr_key="opening_card",
)

RENDER_OVERLAY_CLOSING_CARD_SECTION = SectionDescriptor(
    yaml_key="closing-card",
    fields=RENDER_OVERLAY_CLOSING_CARD_FIELDS,
    build=_build_render_overlay_card_config,
    optional=True,
    default_factory=lambda: _build_render_overlay_card_config(
        parse_section_fields(
            {},
            RENDER_OVERLAY_CLOSING_CARD_FIELDS,
            ParseCtx(),
            "render.overlays.closing-card",
        )
    ),
    attr_key="closing_card",
)

RENDER_OVERLAYS_FIELDS: tuple[SchemaField, ...] = (
    FieldDescriptor(
        "locked",
        False,
        lambda raw, _ctx, _label: bool(raw),
        dump_scalar,
    ),
    RENDER_OVERLAY_OPENING_CARD_SECTION,
    RENDER_OVERLAY_CLOSING_CARD_SECTION,
)


def parse_render_overlays_section(overlays_map: dict[str, Any]) -> Any:
    parsed = parse_section_fields(
        overlays_map,
        RENDER_OVERLAYS_FIELDS,
        ParseCtx(),
        "render.overlays",
    )
    return _build_render_overlays_config(parsed)


def default_render_overlays_config() -> Any:
    return parse_render_overlays_section({})


def render_overlays_base(cfg: Any) -> Any:
    if cfg.render is not None and cfg.render.overlays is not None:
        return cfg.render.overlays
    return default_render_overlays_config()


def _overlay_card_persist_values(
    runtime: Any,
    base_card: Any,
) -> dict[str, Any]:
    bg = base_card.background
    anim = runtime.animation
    animation_values: dict[str, Any] = {
        "type": anim.type,
        "slide_direction": anim.slide_direction,
        "display_time": anim.display_time,
    }
    if hasattr(anim, "appear_at"):
        animation_values["appear_at"] = anim.appear_at
    else:
        animation_values["disappear_at"] = anim.disappear_at
    return {
        "enabled": runtime.enabled,
        "title": {
            "content": base_card.title.content,
            "font": runtime.title_font,
            "font_size": runtime.title_font_size,
            "colour": base_card.title.colour,
            "background_colour": base_card.title.background_colour,
            "margin_bottom": runtime.title_margin_bottom,
        },
        "body": {
            "content": base_card.body.content,
            "font": runtime.body_font,
            "font_size": runtime.body_font_size,
            "colour": base_card.body.colour,
            "background_colour": base_card.body.background_colour,
            "margin_bottom": 0,
        },
        "animation": animation_values,
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


def overlays_persist_values(ctx: PersistCtx) -> dict[str, Any]:
    runtime = ctx.session.render_overlays
    base = render_overlays_base(ctx.cfg)
    return {
        "locked": runtime.locked,
        "opening_card": _overlay_card_persist_values(
            runtime.opening_card, base.opening_card
        ),
        "closing_card": _overlay_card_persist_values(
            runtime.closing_card, base.closing_card
        ),
    }


def default_render_overlay_animation_runtime_values() -> dict[str, Any]:
    return {
        "type": DEFAULT_RENDER_OVERLAY_ANIMATION_TYPE,
        "slide_direction": DEFAULT_RENDER_OVERLAY_SLIDE_DIRECTION,
        "appear_at": DEFAULT_RENDER_OVERLAY_APPEAR_AT,
        "display_time": DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    }


def default_render_overlay_closing_animation_runtime_values() -> dict[str, Any]:
    return {
        "type": DEFAULT_RENDER_OVERLAY_ANIMATION_TYPE,
        "slide_direction": DEFAULT_RENDER_OVERLAY_SLIDE_DIRECTION,
        "disappear_at": DEFAULT_RENDER_OVERLAY_DISAPPEAR_AT,
        "display_time": DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    }


def default_render_overlay_card_runtime_values(
    *,
    closing: bool = False,
) -> dict[str, Any]:
    animation = (
        default_render_overlay_closing_animation_runtime_values()
        if closing
        else default_render_overlay_animation_runtime_values()
    )
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
        "animation": animation,
        "animation_expanded": False,
    }


def default_render_overlays_runtime_values() -> dict[str, Any]:
    return {
        "expanded": False,
        "opening_card": default_render_overlay_card_runtime_values(closing=False),
        "closing_card": default_render_overlay_card_runtime_values(closing=True),
        "locked": False,
    }
