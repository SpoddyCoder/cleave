"""Render-only text overlay for offline video export."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from cleave.config import (
    RenderOverlayConfig,
    RenderOverlayTextBlockConfig,
)
from cleave.easing import (
    ease_out_back,
    ease_out_expo,
    fade_alpha,
)
from cleave.gl_compositor import GlCompositor
from cleave.viz.session import RenderOverlayRuntime
from cleave.viz.theme import FADE_DURATION_SEC

LINE_GAP = 3
_ALPHA_EPSILON = 0.01

OVERLAY_MOTION_DURATION_SEC = 0.35
OVERLAY_MOTION_STAGGER_SEC = 0.07
OVERLAY_BACK_OVERSHOOT = 1.525

OVERLAY_LAYER_ORDER = ("background", "title_bar", "title", "body")


@dataclass(frozen=True)
class OverlayLayerSurface:
    surface: pygame.Surface
    rect: pygame.Rect


@dataclass(frozen=True)
class OverlayLayerSet:
    panel_w: int
    panel_h: int
    background: OverlayLayerSurface
    title_bar: OverlayLayerSurface | None
    title: OverlayLayerSurface
    body: OverlayLayerSurface | None
    settled_panel: pygame.Surface

    def active_layer_names(self) -> tuple[str, ...]:
        names: list[str] = ["background"]
        if self.title_bar is not None:
            names.append("title_bar")
        names.append("title")
        if self.body is not None:
            names.append("body")
        return tuple(names)

    def layer(self, name: str) -> OverlayLayerSurface | None:
        if name == "background":
            return self.background
        if name == "title_bar":
            return self.title_bar
        if name == "title":
            return self.title
        if name == "body":
            return self.body
        return None


@dataclass(frozen=True)
class LayerAnimState:
    offset_x: float = 0.0
    offset_y: float = 0.0
    alpha: float = 1.0
    wipe_progress: float | None = None


@dataclass(frozen=True)
class OverlayAnimationState:
    """Per-frame animation evaluation for the render overlay."""

    visible: bool
    settled: bool
    panel_alpha: float
    panel_offset_x: float
    panel_offset_y: float
    layers: dict[str, LayerAnimState]


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
    from cleave.config import (
        RenderOverlayAnimationConfig,
        RenderOverlayBackgroundConfig,
        RenderOverlayBorderConfig,
    )

    anim = runtime.animation
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
        animation=RenderOverlayAnimationConfig(
            type=anim.type,
            slide_direction=anim.slide_direction,
            start_delay=anim.start_delay,
            display_time=anim.display_time,
        ),
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
        locked=runtime.locked,
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
    """Combined visibility multiplier for the render overlay at *t_sec*."""
    if not cfg.enabled:
        return 0.0
    anim = cfg.animation
    local_t = t_sec - anim.start_delay
    if local_t < 0.0 or local_t > anim.display_time:
        return 0.0
    if anim.type == "fade":
        return fade_alpha(
            local_t,
            anim.display_time,
            FADE_DURATION_SEC,
            FADE_DURATION_SEC,
        )
    return 1.0


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


def _slide_delta(
    direction: str, panel_w: int, panel_h: int, progress: float
) -> tuple[float, float]:
    """Offset from settled position; progress 0 = fully off-screen, 1 = settled."""
    remaining = 1.0 - progress
    if direction == "left":
        return (-panel_w * remaining, 0.0)
    if direction == "right":
        return (panel_w * remaining, 0.0)
    if direction == "top":
        return (0.0, -panel_h * remaining)
    assert direction == "bottom"
    return (0.0, panel_h * remaining)


def _wipe_source_rect(
    layer_w: int,
    layer_h: int,
    direction: str,
    progress: float,
) -> pygame.Rect | None:
    """Visible source rect for a directional wipe at *progress* in [0, 1]."""
    progress = max(0.0, min(1.0, progress))
    if progress <= 0.0:
        return None
    if progress >= 1.0:
        return pygame.Rect(0, 0, layer_w, layer_h)
    if direction == "left":
        return pygame.Rect(0, 0, max(1, int(round(layer_w * progress))), layer_h)
    if direction == "right":
        w = max(1, int(round(layer_w * progress)))
        return pygame.Rect(layer_w - w, 0, w, layer_h)
    if direction == "top":
        return pygame.Rect(0, 0, layer_w, max(1, int(round(layer_h * progress))))
    assert direction == "bottom"
    h = max(1, int(round(layer_h * progress)))
    return pygame.Rect(0, layer_h - h, layer_w, h)


def _motion_span(layer_count: int, *, staggered: bool) -> float:
    if not staggered or layer_count <= 1:
        return OVERLAY_MOTION_DURATION_SEC
    return (
        OVERLAY_MOTION_DURATION_SEC
        + OVERLAY_MOTION_STAGGER_SEC * (layer_count - 1)
    )


def _layer_unit(
    phase_t: float,
    layer_index: int,
    *,
    staggered: bool,
    use_back: bool,
) -> float:
    start = (OVERLAY_MOTION_STAGGER_SEC * layer_index) if staggered else 0.0
    local = phase_t - start
    if local <= 0.0:
        return 0.0
    u = min(1.0, local / OVERLAY_MOTION_DURATION_SEC)
    if use_back:
        return ease_out_back(u, overshoot=OVERLAY_BACK_OVERSHOOT)
    return ease_out_expo(u)


def overlay_animation_state(
    local_t: float,
    cfg: RenderOverlayConfig,
    *,
    panel_w: int,
    panel_h: int,
    layer_names: tuple[str, ...] = OVERLAY_LAYER_ORDER,
) -> OverlayAnimationState:
    """Evaluate per-layer offset/alpha/wipe for *local_t* within the display window."""
    anim = cfg.animation
    anim_type = anim.type
    direction = anim.slide_direction
    display_time = anim.display_time

    invisible = OverlayAnimationState(
        visible=False,
        settled=False,
        panel_alpha=0.0,
        panel_offset_x=0.0,
        panel_offset_y=0.0,
        layers={name: LayerAnimState(alpha=0.0) for name in layer_names},
    )
    if local_t < 0.0 or local_t > display_time:
        return invisible

    staggered = anim_type in ("cascade", "cascade-wipe")
    span = _motion_span(len(layer_names), staggered=staggered)
    if anim_type == "fade":
        span = FADE_DURATION_SEC

    settled_layers = {name: LayerAnimState() for name in layer_names}
    settled = OverlayAnimationState(
        visible=True,
        settled=True,
        panel_alpha=1.0,
        panel_offset_x=0.0,
        panel_offset_y=0.0,
        layers=settled_layers,
    )

    if anim_type == "fade":
        alpha = fade_alpha(local_t, display_time, FADE_DURATION_SEC, FADE_DURATION_SEC)
        return OverlayAnimationState(
            visible=alpha > _ALPHA_EPSILON,
            settled=alpha >= 1.0 - _ALPHA_EPSILON,
            panel_alpha=alpha,
            panel_offset_x=0.0,
            panel_offset_y=0.0,
            layers=settled_layers,
        )

    in_exit = local_t > display_time - span
    in_entrance = local_t < span
    if not in_entrance and not in_exit:
        return settled

    if in_entrance:
        phase_t = local_t
    else:
        phase_t = display_time - local_t

    if anim_type in ("slide", "slide-fade"):
        u = ease_out_expo(min(1.0, phase_t / OVERLAY_MOTION_DURATION_SEC))
        ox, oy = _slide_delta(direction, panel_w, panel_h, u)
        panel_alpha = u if anim_type == "slide-fade" else 1.0
        return OverlayAnimationState(
            visible=True,
            settled=False,
            panel_alpha=panel_alpha,
            panel_offset_x=ox,
            panel_offset_y=oy,
            layers=settled_layers,
        )

    if anim_type == "wipe":
        u = ease_out_expo(min(1.0, phase_t / OVERLAY_MOTION_DURATION_SEC))
        progress = u
        layers = {
            name: LayerAnimState(wipe_progress=progress) for name in layer_names
        }
        return OverlayAnimationState(
            visible=progress > _ALPHA_EPSILON,
            settled=False,
            panel_alpha=1.0,
            panel_offset_x=0.0,
            panel_offset_y=0.0,
            layers=layers,
        )

    # cascade / cascade-wipe
    layers: dict[str, LayerAnimState] = {}
    for index, name in enumerate(layer_names):
        use_back = name == "title_bar"
        u = _layer_unit(phase_t, index, staggered=True, use_back=use_back)
        if anim_type == "cascade-wipe":
            layers[name] = LayerAnimState(wipe_progress=u)
        else:
            ox, oy = _slide_delta(direction, panel_w, panel_h, u)
            layers[name] = LayerAnimState(offset_x=ox, offset_y=oy, alpha=1.0)
    return OverlayAnimationState(
        visible=True,
        settled=False,
        panel_alpha=1.0,
        panel_offset_x=0.0,
        panel_offset_y=0.0,
        layers=layers,
    )


def _blit_text_only(
    panel: pygame.Surface,
    surf: pygame.Surface,
    pos: tuple[int, int],
) -> None:
    panel.blit(surf, pos)


def build_overlay_layers(cfg: RenderOverlayConfig) -> OverlayLayerSet:
    """Build cached layer surfaces and a settled full-panel composite."""
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
    background = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    border_colour = (*cfg.background.border.colour, bg_alpha)

    if border_width > 0 and bg_alpha >= 1:
        pygame.draw.rect(background, border_colour, (0, 0, panel_w, border_width))
        pygame.draw.rect(
            background,
            border_colour,
            (0, panel_h - border_width, panel_w, border_width),
        )
        pygame.draw.rect(
            background, border_colour, (0, border_width, border_width, inner_h)
        )
        pygame.draw.rect(
            background,
            border_colour,
            (panel_w - border_width, border_width, border_width, inner_h),
        )

    if bg_alpha >= 1:
        bg_rect = pygame.Rect(border_width, border_width, inner_w, inner_h)
        background.fill((*cfg.background.colour, bg_alpha), bg_rect)

    content_x = border_width + padding
    title_y = border_width + padding
    title_rect = pygame.Rect(content_x, title_y, title_surf.get_width(), line_h_title)

    title_bar_layer: OverlayLayerSurface | None = None
    if cfg.title.background_colour is not None:
        bar = pygame.Surface(title_surf.get_size(), pygame.SRCALPHA)
        bar.fill((*cfg.title.background_colour, 255))
        title_bar_layer = OverlayLayerSurface(bar, title_rect.copy())

    title_layer = OverlayLayerSurface(title_surf, title_rect.copy())

    body_layer: OverlayLayerSurface | None = None
    if body_surfs:
        body_y = title_y + line_h_title + cfg.title.margin_bottom
        body_h = body_block_h
        body_w = max(surf.get_width() for surf in body_surfs)
        body_surface = pygame.Surface((body_w, body_h), pygame.SRCALPHA)
        y = 0
        for index, surf in enumerate(body_surfs):
            if cfg.body.background_colour is not None:
                bg = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
                bg.fill((*cfg.body.background_colour, 255))
                body_surface.blit(bg, (0, y))
            body_surface.blit(surf, (0, y))
            y += line_h_body
            if index < len(body_surfs) - 1:
                y += LINE_GAP
        body_layer = OverlayLayerSurface(
            body_surface, pygame.Rect(content_x, body_y, body_w, body_h)
        )

    settled = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    settled.blit(background, (0, 0))
    if title_bar_layer is not None:
        settled.blit(title_bar_layer.surface, title_bar_layer.rect.topleft)
    settled.blit(title_layer.surface, title_layer.rect.topleft)
    if body_layer is not None:
        settled.blit(body_layer.surface, body_layer.rect.topleft)

    return OverlayLayerSet(
        panel_w=panel_w,
        panel_h=panel_h,
        background=OverlayLayerSurface(
            background, pygame.Rect(0, 0, panel_w, panel_h)
        ),
        title_bar=title_bar_layer,
        title=title_layer,
        body=body_layer,
        settled_panel=settled,
    )


def build_panel_surface(cfg: RenderOverlayConfig) -> pygame.Surface:
    """Static SRCALPHA panel with background, border, title, and body text."""
    return build_overlay_layers(cfg).settled_panel


def compose_animated_panel(
    layers: OverlayLayerSet,
    state: OverlayAnimationState,
    *,
    direction: str,
) -> pygame.Surface:
    """Blit animated layers into a working SRCALPHA surface the size of the panel."""
    panel_w = layers.panel_w
    panel_h = layers.panel_h
    # Expand working surface to hold slide offsets so we can crop later if needed.
    # Keep panel-sized and clip; offsets that leave the panel are discarded.
    out = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    for name in layers.active_layer_names():
        layer = layers.layer(name)
        if layer is None:
            continue
        anim = state.layers.get(name, LayerAnimState())
        if anim.alpha <= _ALPHA_EPSILON:
            continue
        if anim.wipe_progress is not None and anim.wipe_progress <= _ALPHA_EPSILON:
            continue

        src = layer.surface
        dest_x = int(round(layer.rect.x + anim.offset_x + state.panel_offset_x))
        dest_y = int(round(layer.rect.y + anim.offset_y + state.panel_offset_y))

        if anim.wipe_progress is not None:
            wipe_rect = _wipe_source_rect(
                src.get_width(), src.get_height(), direction, anim.wipe_progress
            )
            if wipe_rect is None:
                continue
            src = src.subsurface(wipe_rect)
            if direction == "right":
                dest_x += wipe_rect.x
            elif direction == "bottom":
                dest_y += wipe_rect.y

        if anim.alpha < 1.0 - _ALPHA_EPSILON:
            tmp = src.copy()
            tmp.set_alpha(int(round(255 * anim.alpha)))
            out.blit(tmp, (dest_x, dest_y))
        else:
            out.blit(src, (dest_x, dest_y))
    return out


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
    layers: OverlayLayerSet | None = None,
    t_sec: float | None = None,
    solo: bool = False,
) -> None:
    """Upload and draw the render overlay at *alpha* visibility."""
    if alpha <= _ALPHA_EPSILON:
        return

    if layers is None:
        if panel is not None:
            # Settled-only path without layer metadata (tests / simple callers).
            panel_w, panel_h = panel.get_size()
            pos = panel_position(cfg, panel_w, panel_h, width, height)
            draw_alpha = alpha
            draw_surface = panel
            _upload_and_draw(
                compositor, draw_surface, pos, draw_alpha, width, height
            )
            return
        layers = build_overlay_layers(cfg)

    panel_w = layers.panel_w
    panel_h = layers.panel_h
    base_pos = panel_position(cfg, panel_w, panel_h, width, height)

    if solo or t_sec is None:
        _upload_and_draw(
            compositor, layers.settled_panel, base_pos, alpha, width, height
        )
        return

    local_t = t_sec - cfg.animation.start_delay
    anim_state = overlay_animation_state(
        local_t,
        cfg,
        panel_w=panel_w,
        panel_h=panel_h,
        layer_names=layers.active_layer_names(),
    )
    if not anim_state.visible:
        return

    if anim_state.settled or cfg.animation.type == "fade":
        draw_alpha = alpha * anim_state.panel_alpha
        if draw_alpha <= _ALPHA_EPSILON:
            return
        pos = (
            int(round(base_pos[0] + anim_state.panel_offset_x)),
            int(round(base_pos[1] + anim_state.panel_offset_y)),
        )
        _upload_and_draw(
            compositor, layers.settled_panel, pos, draw_alpha, width, height
        )
        return

    if cfg.animation.type in ("slide", "slide-fade"):
        draw_alpha = alpha * anim_state.panel_alpha
        if draw_alpha <= _ALPHA_EPSILON:
            return
        pos = (
            int(round(base_pos[0] + anim_state.panel_offset_x)),
            int(round(base_pos[1] + anim_state.panel_offset_y)),
        )
        _upload_and_draw(
            compositor, layers.settled_panel, pos, draw_alpha, width, height
        )
        return

    composed = compose_animated_panel(
        layers, anim_state, direction=cfg.animation.slide_direction
    )
    draw_alpha = alpha * anim_state.panel_alpha
    if draw_alpha <= _ALPHA_EPSILON:
        return
    _upload_and_draw(compositor, composed, base_pos, draw_alpha, width, height)


def _upload_and_draw(
    compositor: GlCompositor,
    panel: pygame.Surface,
    pos: tuple[int, int],
    alpha: float,
    width: int,
    height: int,
) -> None:
    panel_w, panel_h = panel.get_size()
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
    compositor.draw_content_overlay(
        texture_id, clip_x, clip_y, clip_w, clip_h, alpha=alpha
    )


def composite_render_overlay(
    compositor: GlCompositor,
    cfg: RenderOverlayConfig,
    t_sec: float,
    width: int,
    height: int,
    *,
    panel: pygame.Surface | None = None,
    layers: OverlayLayerSet | None = None,
) -> None:
    """Upload and draw the render overlay when visible at *t_sec*."""
    composite_render_overlay_with_alpha(
        compositor,
        cfg,
        overlay_visible_alpha(t_sec, cfg),
        width,
        height,
        panel=panel,
        layers=layers,
        t_sec=t_sec,
    )
