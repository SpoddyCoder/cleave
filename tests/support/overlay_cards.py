"""Overlay card config builders shared by overlay card and render tests."""

from __future__ import annotations

from cleave.config import (
    RenderOverlayAnimationConfig,
    RenderOverlayBackgroundConfig,
    RenderOverlayBorderConfig,
    RenderOverlayCardConfig,
    RenderOverlayClosingAnimationConfig,
    RenderOverlaysConfig,
    RenderOverlayTextBlockConfig,
)


def text_block(
    content: str,
    *,
    font: str = "monospace",
    font_size: int = 10,
    colour: tuple[int, int, int] = (255, 170, 0),
    background_colour: tuple[int, int, int] | None = None,
    margin_bottom: int = 0,
) -> RenderOverlayTextBlockConfig:
    return RenderOverlayTextBlockConfig(
        content=content,
        font=font,
        font_size=font_size,
        colour=colour,
        background_colour=background_colour,
        margin_bottom=margin_bottom,
    )


def opening_card_cfg(
    *,
    enabled: bool = True,
    appear_at: float = 10.0,
    display_time: float = 30.0,
    animation_type: str = "fade",
    slide_direction: str = "left",
    position: str = "bottom-left",
    margin: int = 10,
    padding: int = 10,
    title_font_size: int = 12,
    body_font_size: int = 10,
    opacity: float = 1.0,
    border_width: int = 2,
    title_background_colour: tuple[int, int, int] | None = None,
) -> RenderOverlayCardConfig:
    return RenderOverlayCardConfig(
        enabled=enabled,
        title=text_block(
            "Title",
            font_size=title_font_size,
            background_colour=title_background_colour,
        ),
        body=text_block("Line one\nLine two", font_size=body_font_size),
        animation=RenderOverlayAnimationConfig(
            type=animation_type,  # type: ignore[arg-type]
            slide_direction=slide_direction,  # type: ignore[arg-type]
            appear_at=appear_at,
            display_time=display_time,
        ),
        position=position,  # type: ignore[arg-type]
        background=RenderOverlayBackgroundConfig(
            margin=margin,
            padding=padding,
            colour=(34, 51, 68),
            opacity=opacity,
            border=RenderOverlayBorderConfig(colour=(200, 100, 50), width=border_width),
        ),
    )


def closing_card_cfg(
    *,
    enabled: bool = True,
    disappear_at: float = 0.0,
    display_time: float = 30.0,
    animation_type: str = "fade",
    slide_direction: str = "left",
    position: str = "bottom-left",
) -> RenderOverlayCardConfig:
    return RenderOverlayCardConfig(
        enabled=enabled,
        title=text_block("Title"),
        body=text_block("Line one\nLine two"),
        animation=RenderOverlayClosingAnimationConfig(
            type=animation_type,  # type: ignore[arg-type]
            slide_direction=slide_direction,  # type: ignore[arg-type]
            disappear_at=disappear_at,
            display_time=display_time,
        ),
        position=position,  # type: ignore[arg-type]
        background=RenderOverlayBackgroundConfig(
            margin=10,
            padding=10,
            colour=(34, 51, 68),
            opacity=1.0,
            border=RenderOverlayBorderConfig(colour=(200, 100, 50), width=2),
        ),
    )


def overlays_cfg(
    *,
    opening: RenderOverlayCardConfig | None = None,
    closing: RenderOverlayCardConfig | None = None,
    locked: bool = False,
) -> RenderOverlaysConfig:
    return RenderOverlaysConfig(
        opening_card=opening if opening is not None else opening_card_cfg(),
        closing_card=closing if closing is not None else closing_card_cfg(),
        locked=locked,
    )
