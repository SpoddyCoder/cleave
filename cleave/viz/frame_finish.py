"""Shared content-frame finish for live play and offline render.

After layer compositing, both paths run the same sequence: HDR display
shoulder (when ``render.hdr_compositing`` is enabled and not in preset
curation), visual-limiter busyness sample, optional user highlight rolloff,
chroma boost, post-FX fade, render overlay composite, then present to the
display framebuffer.

When ``cfg.render`` is absent, overlay resolution matches live WYSIWYG:
``render_overlays_base(cfg)`` falls back to ``default_render_overlays_config()``,
merged with session bootstrap values from ``session_from_cfg`` (same as config
snapshot overlay persistence). Offline render uses the frozen bootstrap session;
live play may mutate ``session.render_overlays`` at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import pygame

from cleave.config import CleaveConfig, RenderOverlayCardConfig
from cleave.config_schema.render import render_overlays_base

if TYPE_CHECKING:
    from cleave.viz.app import VisualizerCore
from cleave.viz.post_fx import (
    apply_hdr_display_shoulder,
    chroma_boost_active,
    chroma_boost_variant_index,
    hdr_display_shoulder_active,
    highlight_rolloff_active,
    highlight_rolloff_curve_index,
    live_frame_fade_alpha,
)
from cleave.viz.editor_mode_controls import render_sections_active
from cleave.viz.render_overlay import (
    OverlayLayerSet,
    build_live_overlay_config,
    build_overlay_layers,
    composite_render_overlay_with_alpha,
    live_overlay_alpha,
    panel_surface_key,
)
from cleave.viz.session import TuningSession
from cleave.viz.visual_limiter import LimiterFrameState, observe_frame_busyness

OverlayCardName = Literal["opening", "closing"]


@dataclass
class RenderOverlayPanelCache:
    panel: pygame.Surface | None = None
    layers: OverlayLayerSet | None = None
    key: tuple | None = None


@dataclass
class RenderOverlaysPanelCache:
    opening: RenderOverlayPanelCache = field(default_factory=RenderOverlayPanelCache)
    closing: RenderOverlayPanelCache = field(default_factory=RenderOverlayPanelCache)


def ensure_render_overlay_layers(
    cache: RenderOverlayPanelCache, cfg: RenderOverlayCardConfig
) -> OverlayLayerSet:
    key = panel_surface_key(cfg)
    if cache.layers is not None and cache.key == key:
        return cache.layers
    layers = build_overlay_layers(cfg)
    cache.layers = layers
    cache.panel = layers.settled_panel
    cache.key = key
    return layers


def ensure_render_overlay_panel(
    cache: RenderOverlayPanelCache, cfg: RenderOverlayCardConfig
) -> pygame.Surface:
    return ensure_render_overlay_layers(cache, cfg).settled_panel


def resolve_overlay_card_config(
    cfg: CleaveConfig,
    session: TuningSession,
    card: OverlayCardName,
) -> RenderOverlayCardConfig:
    base = render_overlays_base(cfg)
    if card == "opening":
        return build_live_overlay_config(
            base.opening_card, session.render_overlays.opening_card
        )
    return build_live_overlay_config(
        base.closing_card, session.render_overlays.closing_card
    )


def resolve_overlay_configs(
    cfg: CleaveConfig, session: TuningSession
) -> tuple[RenderOverlayCardConfig, RenderOverlayCardConfig]:
    return (
        resolve_overlay_card_config(cfg, session, "opening"),
        resolve_overlay_card_config(cfg, session, "closing"),
    )


def _composite_one_overlay_card(
    core: VisualizerCore,  # noqa: F821 — TYPE_CHECKING import
    t_sec: float,
    *,
    card_cfg: RenderOverlayCardConfig,
    enabled: bool,
    overlay_solo: bool,
    panel_cache: RenderOverlayPanelCache | None,
    song_duration: float | None,
) -> None:
    alpha = live_overlay_alpha(
        t_sec,
        card_cfg,
        enabled=enabled,
        solo=overlay_solo,
        song_duration=song_duration,
    )
    if alpha <= 0.01:
        return
    layers = None
    if panel_cache is not None:
        layers = ensure_render_overlay_layers(panel_cache, card_cfg)
    composite_render_overlay_with_alpha(
        core.compositor,
        card_cfg,
        alpha,
        core.seed.width,
        core.seed.height,
        layers=layers,
        t_sec=t_sec,
        solo=overlay_solo,
        song_duration=song_duration,
    )


def _composite_render_overlay(
    core: VisualizerCore,  # noqa: F821 — TYPE_CHECKING import
    t_sec: float,
    session: TuningSession,
    *,
    overlay_solo: bool,
    panel_cache: RenderOverlaysPanelCache | None,
    song_duration: float | None,
) -> None:
    opening_cfg, closing_cfg = resolve_overlay_configs(core.seed.cfg, session)
    sections_on = render_sections_active(session.settings.editor_mode)
    overlays = session.render_overlays
    opening_cache = None if panel_cache is None else panel_cache.opening
    closing_cache = None if panel_cache is None else panel_cache.closing
    _composite_one_overlay_card(
        core,
        t_sec,
        card_cfg=opening_cfg,
        enabled=overlays.opening_card.enabled and sections_on,
        overlay_solo=overlay_solo,
        panel_cache=opening_cache,
        song_duration=song_duration,
    )
    _composite_one_overlay_card(
        core,
        t_sec,
        card_cfg=closing_cfg,
        enabled=overlays.closing_card.enabled and sections_on,
        overlay_solo=overlay_solo,
        panel_cache=closing_cache,
        song_duration=song_duration,
    )


def finish_content_frame(
    core: VisualizerCore,  # noqa: F821 — TYPE_CHECKING import
    t_sec: float,
    *,
    duration_sec: float | None = None,
    session: TuningSession | None = None,
    post_fx_solo: bool = False,
    overlay_solo: bool = False,
    panel_cache: RenderOverlaysPanelCache | None = None,
) -> None:
    """Apply post-FX fade, render overlay, and present content."""
    session = core.seed.session if session is None else session
    duration_sec = core.seed.duration_sec if duration_sec is None else duration_sec

    compositor = core.compositor
    editor_mode = session.settings.editor_mode
    if hdr_display_shoulder_active(core.seed.cfg, editor_mode):
        apply_hdr_display_shoulder(
            core.post_process,
            compositor.content_texture_id,
            compositor.content_width,
            compositor.content_height,
        )

    observe_frame_busyness(core, t_sec, LimiterFrameState.from_session(session))

    pp = session.render_post_fx
    sections_on = render_sections_active(session.settings.editor_mode)
    hr = pp.highlight_rolloff
    if (
        sections_on
        and highlight_rolloff_active(pp, solo=post_fx_solo)
        and hr.mode == "composite"
    ):
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
    cb = pp.chroma_boost
    if (
        sections_on
        and chroma_boost_active(pp, solo=post_fx_solo)
        and cb.mode == "composite"
    ):
        core.post_process.apply_chroma_boost(
            compositor.content_texture_id,
            compositor.content_width,
            compositor.content_height,
            cb.amount_pct,
            chroma_boost_variant_index(cb.variant),
        )
    frame_fade_alpha = live_frame_fade_alpha(
        t_sec,
        duration_sec,
        pp.fade_in,
        pp.fade_out,
        enabled=pp.enabled and sections_on,
        solo=post_fx_solo,
    )
    core.compositor.apply_frame_fade(frame_fade_alpha)
    _composite_render_overlay(
        core,
        t_sec,
        session,
        overlay_solo=overlay_solo,
        panel_cache=panel_cache,
        song_duration=duration_sec,
    )
    core.compositor.present_content()
