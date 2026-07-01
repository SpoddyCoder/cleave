"""Shared content-frame finish for live play and offline render.

After layer compositing, both paths run the same sequence: post-FX fade,
render overlay composite, then present to the display framebuffer.

When ``cfg.render`` is absent, overlay resolution matches live WYSIWYG:
``render_overlay_base(cfg)`` falls back to ``default_render_overlay_config()``,
merged with session bootstrap values from ``session_from_cfg`` (same as config
snapshot overlay persistence). Offline render uses the frozen bootstrap session;
live play may mutate ``session.render_overlay`` at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from cleave.config import CleaveConfig, RenderOverlayConfig
from cleave.config_schema import render_overlay_base

if TYPE_CHECKING:
    from cleave.viz.app import VisualizerCore
from cleave.viz.post_fx import (
    highlight_rolloff_active,
    highlight_rolloff_curve_index,
    live_frame_fade_alpha,
)
from cleave.viz.render_overlay import (
    build_live_overlay_config,
    build_panel_surface,
    composite_render_overlay_with_alpha,
    live_overlay_alpha,
    panel_surface_key,
)
from cleave.viz.session import TuningSession


@dataclass
class RenderOverlayPanelCache:
    panel: pygame.Surface | None = None
    key: tuple | None = None


def ensure_render_overlay_panel(
    cache: RenderOverlayPanelCache, cfg: RenderOverlayConfig
) -> pygame.Surface:
    key = panel_surface_key(cfg)
    if cache.panel is not None and cache.key == key:
        return cache.panel
    cache.panel = build_panel_surface(cfg)
    cache.key = key
    return cache.panel


def resolve_overlay_config(
    cfg: CleaveConfig, session: TuningSession
) -> RenderOverlayConfig:
    base = render_overlay_base(cfg)
    return build_live_overlay_config(base, session.render_overlay)


def _composite_render_overlay(
    core: VisualizerCore,  # noqa: F821 — TYPE_CHECKING import
    t_sec: float,
    session: TuningSession,
    *,
    overlay_solo: bool,
    panel_cache: RenderOverlayPanelCache | None,
) -> None:
    cfg = resolve_overlay_config(core.seed.cfg, session)
    alpha = live_overlay_alpha(
        t_sec,
        cfg,
        enabled=session.render_overlay.enabled,
        solo=overlay_solo,
    )
    if alpha <= 0.01:
        return
    panel = None
    if panel_cache is not None:
        panel = ensure_render_overlay_panel(panel_cache, cfg)
    composite_render_overlay_with_alpha(
        core.compositor,
        cfg,
        alpha,
        core.seed.width,
        core.seed.height,
        panel=panel,
    )


def finish_content_frame(
    core: VisualizerCore,  # noqa: F821 — TYPE_CHECKING import
    t_sec: float,
    *,
    duration_sec: float | None = None,
    session: TuningSession | None = None,
    post_fx_solo: bool = False,
    overlay_solo: bool = False,
    panel_cache: RenderOverlayPanelCache | None = None,
) -> None:
    """Apply post-FX fade, render overlay, and present content."""
    session = core.seed.session if session is None else session
    duration_sec = core.seed.duration_sec if duration_sec is None else duration_sec

    pp = session.render_post_fx
    hr = pp.highlight_rolloff
    if highlight_rolloff_active(pp, solo=post_fx_solo) and hr.mode == "composite":
        compositor = core.compositor
        core.post_process.apply_highlight_rolloff(
            compositor.content_texture_id,
            compositor.content_width,
            compositor.content_height,
            hr.threshold_pct / 100.0,
            hr.ceiling_pct / 100.0,
            hr.strength_pct / 100.0,
            hr.softness_pct / 100.0,
            hr.desaturation_pct / 100.0,
            highlight_rolloff_curve_index(hr.curve),
        )
    frame_fade_alpha = live_frame_fade_alpha(
        t_sec,
        duration_sec,
        pp.fade_in,
        pp.fade_out,
        enabled=pp.enabled,
        solo=post_fx_solo,
    )
    core.compositor.apply_frame_fade(frame_fade_alpha)
    _composite_render_overlay(
        core,
        t_sec,
        session,
        overlay_solo=overlay_solo,
        panel_cache=panel_cache,
    )
    core.compositor.present_content()
