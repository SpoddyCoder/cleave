"""Render-only text overlay for offline video export."""

from __future__ import annotations

import pygame

from cleave.config import (
    DEFAULT_RENDER_OVERLAY_BACKGROUND_COLOUR,
    DEFAULT_RENDER_OVERLAY_BACKGROUND_MARGIN,
    DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY,
    DEFAULT_RENDER_OVERLAY_BACKGROUND_PADDING,
    DEFAULT_RENDER_OVERLAY_BORDER_COLOUR,
    DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
    DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
    DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    DEFAULT_RENDER_OVERLAY_FONT,
    DEFAULT_RENDER_OVERLAY_POSITION,
    DEFAULT_RENDER_OVERLAY_START_DELAY,
    DEFAULT_RENDER_OVERLAY_TEXT_COLOUR,
    DEFAULT_RENDER_OVERLAY_TITLE,
    DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
    DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
    DEFAULT_RENDER_OVERLAY_BODY,
    RenderOverlayBackgroundConfig,
    RenderOverlayBorderConfig,
    RenderOverlayConfig,
    RenderOverlayTextBlockConfig,
)
from cleave.viz.controls import RenderOverlayRuntime
from cleave.easing import fade_alpha
from cleave.gl_compositor import GlCompositor
from cleave.viz.theme import FADE_DURATION_SEC

LINE_GAP = 3
_ALPHA_EPSILON = 0.01


def default_render_overlay_config() -> RenderOverlayConfig:
    """Static overlay fields when ``cfg.render`` is absent."""
    return RenderOverlayConfig(
        enabled=True,
        title=RenderOverlayTextBlockConfig(
            content=DEFAULT_RENDER_OVERLAY_TITLE,
            font=DEFAULT_RENDER_OVERLAY_FONT,
            font_size=DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
            colour=DEFAULT_RENDER_OVERLAY_TEXT_COLOUR,
            margin_bottom=DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        ),
        body=RenderOverlayTextBlockConfig(
            content=DEFAULT_RENDER_OVERLAY_BODY,
            font=DEFAULT_RENDER_OVERLAY_FONT,
            font_size=DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
            colour=DEFAULT_RENDER_OVERLAY_TEXT_COLOUR,
        ),
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


def _text_block_surface_key(block: RenderOverlayTextBlockConfig) -> tuple:
    return (
        block.content,
        block.font,
        block.font_size,
        block.colour,
        block.background_colour,
        block.margin_bottom,
    )


def panel_surface_key(cfg: RenderOverlayConfig) -> tuple:
    """Hashable key for cached panel surfaces (appearance only, not placement)."""
    bg = cfg.background
    return (
        _text_block_surface_key(cfg.title),
        _text_block_surface_key(cfg.body),
        bg.margin,
        bg.padding,
        bg.colour,
        bg.opacity,
        bg.border.colour,
        bg.border.width,
    )


def build_live_overlay_config(
    base: RenderOverlayConfig, runtime: RenderOverlayRuntime
) -> RenderOverlayConfig:
    """Merge static YAML fields with live-tuned runtime overrides."""
    return RenderOverlayConfig(
        enabled=runtime.enabled,
        title=RenderOverlayTextBlockConfig(
            content=base.title.content,
            font=runtime.title_font,
            font_size=runtime.title_font_size,
            colour=base.title.colour,
            background_colour=base.title.background_colour,
            margin_bottom=runtime.title_margin_bottom,
        ),
        body=RenderOverlayTextBlockConfig(
            content=base.body.content,
            font=runtime.body_font,
            font_size=runtime.body_font_size,
            colour=base.body.colour,
            background_colour=base.body.background_colour,
        ),
        start_delay=runtime.start_delay,
        display_time=runtime.display_time,
        position=runtime.position,
        background=RenderOverlayBackgroundConfig(
            margin=base.background.margin,
            padding=base.background.padding,
            colour=base.background.colour,
            opacity=runtime.opacity_pct / 100.0,
            border=RenderOverlayBorderConfig(
                colour=base.background.border.colour,
                width=runtime.border_width,
            ),
        ),
    )


def live_overlay_alpha(
    t_sec: float,
    cfg: RenderOverlayConfig,
    *,
    enabled: bool,
    solo: bool,
) -> float:
    """Visibility multiplier for the live render overlay at *t_sec*."""
    if not enabled:
        return 0.0
    if solo:
        return 1.0
    return overlay_visible_alpha(t_sec, cfg)


def overlay_visible_alpha(t_sec: float, cfg: RenderOverlayConfig) -> float:
    """Combined fade multiplier for the render overlay at *t_sec*."""
    if not cfg.enabled:
        return 0.0
    local_t = t_sec - cfg.start_delay
    if local_t < 0.0 or local_t > cfg.display_time:
        return 0.0
    return fade_alpha(
        local_t,
        cfg.display_time,
        FADE_DURATION_SEC,
        FADE_DURATION_SEC,
    )


def panel_position(
    cfg: RenderOverlayConfig,
    panel_w: int,
    panel_h: int,
    screen_w: int,
    screen_h: int,
) -> tuple[int, int]:
    """Top-left pixel position for a panel of *panel_w* x *panel_h*."""
    margin = cfg.background.margin
    position = cfg.position

    if position == "centre":
        return ((screen_w - panel_w) // 2, (screen_h - panel_h) // 2)
    if position == "top-left":
        return (margin, margin)
    if position == "top-right":
        return (screen_w - panel_w - margin, margin)
    if position == "bottom-left":
        return (margin, screen_h - panel_h - margin)
    assert position == "bottom-right"
    return (screen_w - panel_w - margin, screen_h - panel_h - margin)


def _body_font(cfg: RenderOverlayConfig) -> pygame.font.Font:
    return pygame.font.SysFont(cfg.body.font, cfg.body.font_size)


def _title_font(cfg: RenderOverlayConfig) -> pygame.font.Font:
    return pygame.font.SysFont(cfg.title.font, cfg.title.font_size, bold=True)


def _background_pixel_alpha(cfg: RenderOverlayConfig) -> int:
    return int(round(255 * cfg.background.opacity))


def _blit_text(
    panel: pygame.Surface,
    surf: pygame.Surface,
    pos: tuple[int, int],
    background_colour: tuple[int, int, int] | None,
) -> None:
    x, y = pos
    if background_colour is not None:
        bg = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        bg.fill((*background_colour, 255))
        panel.blit(bg, (x, y))
    panel.blit(surf, (x, y))


def build_panel_surface(cfg: RenderOverlayConfig) -> pygame.Surface:
    """Static SRCALPHA panel with background, border, title, and body text."""
    body_font = _body_font(cfg)
    title_font = _title_font(cfg)
    padding = cfg.background.padding

    title_surf = title_font.render(cfg.title.content, True, cfg.title.colour)
    body_lines = cfg.body.content.splitlines() or [""]
    body_surfs = [
        body_font.render(line, True, cfg.body.colour) for line in body_lines
    ]

    line_h_body = body_font.get_linesize()
    line_h_title = title_font.get_linesize()
    content_w = max([title_surf.get_width(), *[surf.get_width() for surf in body_surfs]])
    body_block_h = 0
    if body_surfs:
        body_block_h = (
            len(body_surfs) * line_h_body + max(0, len(body_surfs) - 1) * LINE_GAP
        )
    content_h = line_h_title
    if body_surfs:
        content_h += cfg.title.margin_bottom + body_block_h

    border_width = cfg.background.border.width
    inner_w = content_w + padding * 2
    inner_h = content_h + padding * 2
    panel_w = inner_w + border_width * 2
    panel_h = inner_h + border_width * 2

    bg_alpha = _background_pixel_alpha(cfg)
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    border_colour = (*cfg.background.border.colour, bg_alpha)

    if border_width > 0 and bg_alpha >= 1:
        pygame.draw.rect(panel, border_colour, (0, 0, panel_w, border_width))
        pygame.draw.rect(
            panel,
            border_colour,
            (0, panel_h - border_width, panel_w, border_width),
        )
        pygame.draw.rect(
            panel, border_colour, (0, border_width, border_width, inner_h)
        )
        pygame.draw.rect(
            panel,
            border_colour,
            (panel_w - border_width, border_width, border_width, inner_h),
        )

    if bg_alpha >= 1:
        bg_rect = pygame.Rect(border_width, border_width, inner_w, inner_h)
        panel.fill((*cfg.background.colour, bg_alpha), bg_rect)

    content_x = border_width + padding
    y = border_width + padding
    _blit_text(
        panel, title_surf, (content_x, y), cfg.title.background_colour
    )
    y += line_h_title
    if body_surfs:
        y += cfg.title.margin_bottom
        for index, surf in enumerate(body_surfs):
            _blit_text(
                panel, surf, (content_x, y), cfg.body.background_colour
            )
            y += line_h_body
            if index < len(body_surfs) - 1:
                y += LINE_GAP

    return panel


def _clip_rect_to_bounds(
    rect: tuple[int, int, int, int],
    bounds_w: int,
    bounds_h: int,
) -> tuple[int, int, int, int] | None:
    """Intersection of *rect* with ``(0, 0, bounds_w, bounds_h)``."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return None
    left = max(x, 0)
    top = max(y, 0)
    right = min(x + w, bounds_w)
    bottom = min(y + h, bounds_h)
    clip_w = right - left
    clip_h = bottom - top
    if clip_w <= 0 or clip_h <= 0:
        return None
    return (left, top, clip_w, clip_h)


def composite_render_overlay_with_alpha(
    compositor: GlCompositor,
    cfg: RenderOverlayConfig,
    alpha: float,
    width: int,
    height: int,
    *,
    panel: pygame.Surface | None = None,
) -> None:
    """Upload and draw the render overlay at *alpha* visibility."""
    if alpha <= _ALPHA_EPSILON:
        return

    if panel is None:
        panel = build_panel_surface(cfg)
    panel_w, panel_h = panel.get_size()
    pos = panel_position(cfg, panel_w, panel_h, width, height)
    clip = _clip_rect_to_bounds((pos[0], pos[1], panel_w, panel_h), width, height)
    if clip is None:
        return

    clip_x, clip_y, clip_w, clip_h = clip
    src_x = clip_x - pos[0]
    src_y = clip_y - pos[1]
    if src_x == 0 and src_y == 0 and clip_w == panel_w and clip_h == panel_h:
        draw_surface = panel
    else:
        draw_surface = panel.subsurface((src_x, src_y, clip_w, clip_h))

    texture_id = compositor.upload_overlay_texture(draw_surface)
    compositor.draw_overlay(texture_id, clip_x, clip_y, clip_w, clip_h, alpha=alpha)


def composite_render_overlay(
    compositor: GlCompositor,
    cfg: RenderOverlayConfig,
    t_sec: float,
    width: int,
    height: int,
    *,
    panel: pygame.Surface | None = None,
) -> None:
    """Upload and draw the render overlay when visible at *t_sec*."""
    composite_render_overlay_with_alpha(
        compositor,
        cfg,
        overlay_visible_alpha(t_sec, cfg),
        width,
        height,
        panel=panel,
    )
