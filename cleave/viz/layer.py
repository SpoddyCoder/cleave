"""Stem layer construction, rendering, and compositing."""

from __future__ import annotations

from dataclasses import dataclass

import pygame
from OpenGL.GL import GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, glClear, glClearColor, glViewport

from cleave.extract import STEM_NAMES
from cleave.timeline import TimelineCue, layer_visible_at
from cleave.config import (
    DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY,
    DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
    DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
    DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    DEFAULT_RENDER_OVERLAY_FONT,
    DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
    DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
    DEFAULT_RENDER_OVERLAY_POSITION,
    DEFAULT_RENDER_OVERLAY_START_DELAY,
    DEFAULT_RENDER_POST_FX_FADE_IN,
    DEFAULT_RENDER_POST_FX_FADE_OUT,
    CleaveConfig,
)
from cleave.effects.runtime import EffectRuntime
from cleave.gl_compositor import GlCompositor, LayerFbo
from cleave.gl_post_process import GlPostProcess
from cleave.preset_playlist import PresetPlaylist, preset_browse_floor
from cleave.projectm import ProjectM
from cleave.signals import Signals
from cleave.viz.controls import (
    LayerRuntime,
    RenderOverlayRuntime,
    RenderPostFxRuntime,
    TimelineRuntime,
    TuningSession,
)
from cleave.viz.overlay import TuningOverlay, TuningViewState
from cleave.viz.timeline_overlay import TimelineOverlay, TimelineViewState


@dataclass
class StemLayer:
    name: str
    pm: ProjectM
    fbo: LayerFbo
    playlist: PresetPlaylist


def timeline_defaults(session: TuningSession) -> dict[str, bool]:
    return {name: session.layers[name].enabled for name in STEM_NAMES}


def timeline_cues_for_eval(session: TuningSession) -> list[TimelineCue]:
    tl = session.timeline
    if tl.recording:
        return tl.cues + tl.record_buffer
    return tl.cues


def timeline_committed_visible(
    session: TuningSession,
    stem: str,
    t_sec: float,
) -> bool:
    return layer_visible_at(
        session.timeline.cues,
        timeline_defaults(session),
        stem,
        t_sec,
    )


def snapshot_monitor_from_timeline(
    session: TuningSession,
    t_sec: float,
) -> dict[str, bool]:
    defaults = timeline_defaults(session)
    return {
        stem: layer_visible_at(session.timeline.cues, defaults, stem, t_sec)
        for stem in session.layer_z_order
    }


def snapshot_monitor_from_output(
    session: TuningSession,
    t_sec: float,
) -> dict[str, bool]:
    return {
        stem: effective_layer_enabled(session, stem, t_sec)
        for stem in session.layer_z_order
    }


def effective_layer_enabled(
    session: TuningSession,
    stem: str,
    t_sec: float,
) -> bool:
    if session.solo_stem is not None:
        return stem == session.solo_stem
    if not session.timeline.enabled:
        return session.layers[stem].enabled
    tl = session.timeline
    defaults = timeline_defaults(session)
    if tl.recording:
        if stem in tl.armed_stems:
            return layer_visible_at(
                tl.cues + tl.record_buffer,
                defaults,
                stem,
                t_sec,
            )
        return layer_visible_at(tl.cues, defaults, stem, t_sec)
    if tl.preview_active:
        return tl.monitor[stem]
    if stem in tl.override_stems:
        return tl.override_visible.get(stem, True)
    return layer_visible_at(tl.cues, defaults, stem, t_sec)


def apply_layer_visibility(
    session: TuningSession,
    layers_by_name: dict[str, StemLayer],
    t_sec: float,
) -> None:
    for stem, layer in layers_by_name.items():
        layer.fbo.enabled = effective_layer_enabled(session, stem, t_sec)


def apply_effect_modifiers(
    session: TuningSession,
    layers_by_name: dict[str, StemLayer],
    effect_runtime: EffectRuntime,
    signals: Signals | None,
    t_sec: float,
    *,
    update: bool = True,
) -> None:
    if update:
        effect_runtime.update(session, signals, t_sec)
    modifiers = effect_runtime.modifiers(session)
    for stem, layer in layers_by_name.items():
        if not effective_layer_enabled(session, stem, t_sec):
            continue
        mod = modifiers[stem]
        layer.fbo.opacity = mod.opacity
        layer.fbo.flash_alpha = mod.flash_alpha
        layer.fbo.bloom_strength = mod.bloom_strength
        layer.fbo.hue_rgb = mod.hue_rgb
        layer.fbo.hue_mix = mod.hue_mix
        layer.fbo.grit_strength = mod.grit_strength
        layer.fbo.aberration_px = mod.aberration_px


def _beat_sensitivity(cfg: CleaveConfig, layer_name: str) -> float:
    layer = cfg.layers[layer_name]
    if layer.beat_sensitivity is not None:
        return layer.beat_sensitivity
    return cfg.visualizer.beat_sensitivity


def _build_layers(
    cfg: CleaveConfig,
    compositor: GlCompositor,
    playlists: dict[str, PresetPlaylist],
) -> list[StemLayer]:
    texture_paths = list(cfg.paths.texture_paths)
    fps = cfg.visualizer.fps
    runtimes: list[StemLayer] = []

    for name, layer_cfg in cfg.layers_in_z_order():
        w, h = layer_cfg.width, layer_cfg.height
        playlist = playlists[name]

        pm = ProjectM()
        pm.set_window_size(w, h)
        if texture_paths:
            pm.set_texture_paths(texture_paths)
        playlist.load_into(pm)
        pm.lock_preset(True)
        pm.set_hard_cut_enabled(False)
        pm.set_fps(fps)
        pm.set_beat_sensitivity(_beat_sensitivity(cfg, name))

        fbo = compositor.create_layer_fbo(
            name,
            w,
            h,
            opacity=layer_cfg.opacity,
            blend_mode=layer_cfg.blend_mode,
        )
        fbo.enabled = layer_cfg.enabled
        runtimes.append(
            StemLayer(name=name, pm=pm, fbo=fbo, playlist=playlist)
        )

    return runtimes


def _render_layer_fbo(layer: StemLayer, pm: ProjectM) -> None:
    fbo = layer.fbo
    with fbo:
        glViewport(0, 0, fbo.width, fbo.height)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        GlCompositor.reset_blend_for_external_render()
        pm.render_to_fbo(fbo.fbo_id)


def _apply_layer_bloom(layer: StemLayer, post_process: GlPostProcess | None) -> None:
    if post_process is None:
        return
    fbo = layer.fbo
    if fbo.bloom_strength <= 0.0:
        return
    post_process.apply_bloom(
        fbo.texture_id,
        fbo.width,
        fbo.height,
        fbo.bloom_strength,
    )


def _apply_layer_grit(layer: StemLayer, post_process: GlPostProcess | None) -> None:
    if post_process is None:
        return
    fbo = layer.fbo
    if fbo.grit_strength <= 0.0 and fbo.aberration_px <= 0.0:
        return
    post_process.apply_grit(
        fbo.texture_id,
        fbo.width,
        fbo.height,
        fbo.grit_strength,
        fbo.aberration_px,
    )


def _flush_all_pcm(layers: list[StemLayer]) -> None:
    for layer in layers:
        layer.pm.flush_pcm()


def _destroy_layers(layers: list[StemLayer]) -> None:
    for layer in layers:
        layer.pm.destroy()


def _render_overlay_runtime_from_cfg(cfg: CleaveConfig) -> RenderOverlayRuntime:
    overlay = cfg.render.overlay if cfg.render is not None else None
    if overlay is not None:
        return RenderOverlayRuntime(
            enabled=overlay.enabled,
            expanded=False,
            position=overlay.position,
            title_expanded=False,
            body_expanded=False,
            title_font_size=overlay.title.font_size,
            title_font=overlay.title.font,
            title_margin_bottom=overlay.title.margin_bottom,
            body_font_size=overlay.body.font_size,
            body_font=overlay.body.font,
            opacity_pct=int(round(overlay.background.opacity * 100)),
            border_width=overlay.background.border.width,
            start_delay=overlay.start_delay,
            display_time=overlay.display_time,
        )
    return RenderOverlayRuntime(
        enabled=True,
        expanded=False,
        position=DEFAULT_RENDER_OVERLAY_POSITION,
        title_expanded=False,
        body_expanded=False,
        title_font_size=DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
        title_font=DEFAULT_RENDER_OVERLAY_FONT,
        title_margin_bottom=DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        body_font_size=DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
        body_font=DEFAULT_RENDER_OVERLAY_FONT,
        opacity_pct=int(round(DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY * 100)),
        border_width=DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
        start_delay=DEFAULT_RENDER_OVERLAY_START_DELAY,
        display_time=DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    )


def _render_post_fx_runtime_from_cfg(
    cfg: CleaveConfig,
) -> RenderPostFxRuntime:
    post_fx = cfg.render.post_fx if cfg.render is not None else None
    if post_fx is not None:
        return RenderPostFxRuntime(
            enabled=post_fx.enabled,
            expanded=False,
            fade_in=post_fx.fade_in,
            fade_out=post_fx.fade_out,
        )
    return RenderPostFxRuntime(
        enabled=True,
        expanded=False,
        fade_in=DEFAULT_RENDER_POST_FX_FADE_IN,
        fade_out=DEFAULT_RENDER_POST_FX_FADE_OUT,
    )


def _timeline_runtime_from_cfg(cfg: CleaveConfig) -> TimelineRuntime:
    timeline = cfg.timeline
    if timeline is None:
        return TimelineRuntime()
    return TimelineRuntime(
        enabled=timeline.enabled,
        expanded=False,
        cues=list(timeline.cues),
    )


def _session_from_cfg(
    cfg: CleaveConfig,
    playlists: dict[str, PresetPlaylist],
) -> TuningSession:
    preset_root = cfg.paths.preset_root
    return TuningSession(
        layer_z_order=list(cfg.layer_z_order),
        render_overlay=_render_overlay_runtime_from_cfg(cfg),
        render_post_fx=_render_post_fx_runtime_from_cfg(cfg),
        timeline=_timeline_runtime_from_cfg(cfg),
        layers={
            name: LayerRuntime(
                playlist=playlists[name],
                browse_floor=preset_browse_floor(
                    cfg.layers[name].preset, preset_root
                ),
                opacity_pct=int(layer_cfg.opacity * 100),
                effects={
                    effect_id: dict(drivers)
                    for effect_id, drivers in layer_cfg.effects.items()
                },
                blend_mode=layer_cfg.blend_mode,
                beat_sensitivity=_beat_sensitivity(cfg, name),
                enabled=layer_cfg.enabled,
                locked=layer_cfg.locked,
            )
            for name, layer_cfg in cfg.layers.items()
        },
    )


def _composite_ordered(
    compositor: GlCompositor,
    layers_by_name: dict[str, StemLayer],
    session: TuningSession,
) -> None:
    ordered = [layers_by_name[name] for name in reversed(session.layer_z_order)]
    compositor.composite([layer.fbo for layer in ordered])


def _draw_tuning_overlay(
    compositor: GlCompositor,
    overlay: TuningOverlay,
    overlay_surface: pygame.Surface,
    view_state: TuningViewState,
) -> None:
    overlay_surface.fill((0, 0, 0, 0))
    overlay.draw(overlay_surface, view_state)
    panel = overlay.panel_rect
    if panel is not None:
        px, py, pw, ph = panel
        panel_surface = overlay_surface.subsurface((px, py, pw, ph))
        tex_id = compositor.upload_overlay_texture(panel_surface)
        compositor.draw_overlay(tex_id, px, py, pw, ph)


def _build_timeline_view_state(
    session: TuningSession,
    position_sec: float,
    duration_sec: float,
) -> TimelineViewState:
    tl = session.timeline
    monitor_visible = {
        stem: effective_layer_enabled(session, stem, position_sec)
        for stem in session.layer_z_order
    }
    timeline_visible = {
        stem: timeline_committed_visible(session, stem, position_sec)
        for stem in session.layer_z_order
    }
    return TimelineViewState(
        layer_z_order=list(session.layer_z_order),
        cues=list(timeline_cues_for_eval(session)),
        defaults=timeline_defaults(session),
        position_sec=position_sec,
        duration_sec=duration_sec,
        focus_row=tl.focus_row,
        monitor_visible=monitor_visible,
        timeline_visible=timeline_visible,
        override_stems=set(tl.override_stems),
        armed_stems=set(tl.armed_stems),
        recording=tl.recording,
        enabled=tl.enabled,
    )


def _union_rect(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0 = min(ax, bx)
    y0 = min(ay, by)
    x1 = max(ax + aw, bx + bw)
    y1 = max(ay + ah, by + bh)
    return (x0, y0, x1 - x0, y1 - y0)


def _draw_timeline_overlay(
    compositor: GlCompositor,
    overlay: TimelineOverlay,
    overlay_surface: pygame.Surface,
    view_state: TimelineViewState,
) -> None:
    overlay_surface.fill((0, 0, 0, 0))
    overlay.draw(overlay_surface, view_state)
    panel = overlay.panel_rect
    if panel is not None:
        upload_rect = panel
        badge = overlay.header_badge_rect
        if badge is not None:
            upload_rect = _union_rect(panel, badge)
        px, py, pw, ph = upload_rect
        upload_surface = overlay_surface.subsurface((px, py, pw, ph))
        tex_id = compositor.upload_overlay_texture(upload_surface)
        compositor.draw_overlay(tex_id, px, py, pw, ph)
