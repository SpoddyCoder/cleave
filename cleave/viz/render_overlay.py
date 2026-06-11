"""Render-only text overlay for offline video export."""

from __future__ import annotations

import pygame

from cleave.config import RenderOverlayConfig
from cleave.easing import fade_alpha
from cleave.gl_compositor import GlCompositor
from cleave.viz.theme import FADE_DURATION_SEC

LINE_GAP = 3
_ALPHA_EPSILON = 0.01


def overlay_visible_alpha(t_sec: float, cfg: RenderOverlayConfig) -> float:
    """Combined fade multiplier for the render overlay at *t_sec*."""
    if not cfg.enabled:
        return 0.0
    local_t = t_sec - cfg.start
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
    return pygame.font.SysFont("monospace", cfg.font.size)


def _title_font(cfg: RenderOverlayConfig) -> pygame.font.Font:
    return pygame.font.SysFont("monospace", round(cfg.font.size * 1.2), bold=True)


def _background_pixel_alpha(cfg: RenderOverlayConfig) -> int:
    return int(round(255 * cfg.background.opacity))


def build_panel_surface(cfg: RenderOverlayConfig) -> pygame.Surface:
    """Static SRCALPHA panel with background, border, title, and body text."""
    body_font = _body_font(cfg)
    title_font = _title_font(cfg)
    padding = cfg.background.padding

    title_surf = title_font.render(cfg.title, True, cfg.font.colour)
    body_lines = cfg.body.splitlines() or [""]
    body_surfs = [body_font.render(line, True, cfg.font.colour) for line in body_lines]

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
        content_h += LINE_GAP + body_block_h

    panel_w = content_w + padding * 2
    panel_h = content_h + padding * 2

    bg_alpha = _background_pixel_alpha(cfg)
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    if bg_alpha >= 1:
        panel.fill((*cfg.background.colour, bg_alpha))

    border_width = cfg.background.border.width
    if border_width > 0 and bg_alpha >= 1:
        pygame.draw.rect(
            panel,
            (*cfg.background.border.colour, bg_alpha),
            panel.get_rect(),
            width=border_width,
        )

    y = padding
    panel.blit(title_surf, (padding, y))
    y += line_h_title
    if body_surfs:
        y += LINE_GAP
        for index, surf in enumerate(body_surfs):
            panel.blit(surf, (padding, y))
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
    alpha = overlay_visible_alpha(t_sec, cfg)
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
