"""Stem layer construction, rendering, and compositing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame
from OpenGL.GL import GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, glClear, glClearColor, glViewport

from cleave.config import CleaveConfig, LayerConfig
from cleave.effects.runtime import EffectRuntime
from cleave.gl_compositor import GlCompositor, LayerFbo
from cleave.gl_post_process import GlPostProcess
from cleave.preset_playlist import PresetPlaylist, preset_browse_floor
from cleave.projectm import ProjectM
from cleave.signals import Signals
from cleave.viz.controls import LayerRuntime, TuningSession
from cleave.viz.overlay import TuningOverlay, TuningViewState


@dataclass
class StemLayer:
    name: str
    pm: ProjectM
    fbo: LayerFbo
    playlist: PresetPlaylist


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
        if not session.layers[stem].enabled:
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


def _build_drums_layer(
    compositor: GlCompositor,
    playlist: PresetPlaylist,
    texture_paths: list[Path],
    beat_sensitivity: float,
    width: int,
    height: int,
    fps: int,
    *,
    blend_mode: str = "add",
) -> StemLayer:
    from cleave.viz.bootstrap import STEM_DRUMS

    pm = ProjectM()
    pm.set_window_size(width, height)
    if texture_paths:
        pm.set_texture_paths(texture_paths)
    playlist.load_into(pm)
    pm.lock_preset(True)
    pm.set_hard_cut_enabled(False)
    pm.set_fps(fps)
    pm.set_beat_sensitivity(beat_sensitivity)

    fbo = compositor.create_layer_fbo(STEM_DRUMS, width, height, blend_mode=blend_mode)
    return StemLayer(name=STEM_DRUMS, pm=pm, fbo=fbo, playlist=playlist)


def _session_for_drums(
    playlist: PresetPlaylist,
    preset_anchor: Path,
    preset_root: Path,
    beat_sensitivity: float,
    drums_cfg: LayerConfig | None,
) -> TuningSession:
    from cleave.viz.bootstrap import STEM_DRUMS

    return TuningSession(
        layer_z_order=[STEM_DRUMS],
        layers={
            STEM_DRUMS: LayerRuntime(
                playlist=playlist,
                browse_floor=preset_browse_floor(preset_anchor, preset_root),
                opacity_pct=int((drums_cfg.opacity if drums_cfg else 1.0) * 100),
                effects={
                    effect_id: dict(drivers)
                    for effect_id, drivers in (
                        drums_cfg.effects if drums_cfg else {}
                    ).items()
                },
                blend_mode="add",
                beat_sensitivity=beat_sensitivity,
            ),
        },
    )


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


def _session_from_cfg(
    cfg: CleaveConfig,
    playlists: dict[str, PresetPlaylist],
) -> TuningSession:
    preset_root = cfg.paths.preset_root
    return TuningSession(
        layer_z_order=list(cfg.layer_z_order),
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
