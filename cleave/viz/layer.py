"""Stem layer construction, rendering, and compositing."""

from __future__ import annotations

from dataclasses import dataclass

import pygame
from OpenGL.GL import GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, glClear, glClearColor, glViewport

from cleave.timeline import TimelineCue, layer_visible_at
from cleave.config import CleaveConfig
from cleave.effects.runtime import EffectRuntime
from cleave.gl_compositor import GlCompositor, LayerFbo
from cleave.gl_post_process import GlPostProcess
from cleave.preset_playlist import PresetPlaylist
from cleave.projectm import ProjectM
from cleave.signals import Signals
from cleave.stem_pcm import StemPcmBank
from cleave.viz.session import TuningSession
from cleave.viz.help_overlay import HelpOverlay
from cleave.viz.overlay import TuningOverlay, TuningViewState, row_kind
from cleave.viz.timeline_overlay import TimelineOverlay, TimelineViewState


@dataclass
class StemLayer:
    name: str
    pm: ProjectM
    fbo: LayerFbo
    playlist: PresetPlaylist


def timeline_defaults(session: TuningSession) -> dict[str, bool]:
    return {name: session.layers[name].enabled for name in session.layer_z_order}


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


def armed_recording_defaults(session: TuningSession) -> dict[str, bool]:
    defaults = timeline_defaults(session)
    defaults.update(session.timeline.record_baseline)
    return defaults


def armed_recording_visible(
    session: TuningSession,
    stem: str,
    t_sec: float,
) -> bool:
    """Visibility for an armed stem during an active record pass."""
    return layer_visible_at(
        session.timeline.record_buffer,
        armed_recording_defaults(session),
        stem,
        t_sec,
    )


def committed_visible_outside_punch(
    session: TuningSession,
    stem: str,
    record_start: float,
    record_stop: float,
) -> bool:
    """Committed visibility at *record_stop* ignoring armed-stem cues inside the punch."""
    kept = [
        cue
        for cue in session.timeline.cues
        if not (
            record_start <= cue.t <= record_stop
            and stem in cue.layers
        )
    ]
    return layer_visible_at(kept, timeline_defaults(session), stem, record_stop)


def build_record_punch_cues(
    session: TuningSession,
    record_start: float,
    record_stop: float,
) -> list[TimelineCue]:
    """Cues to punch on record stop: baseline, toggles, and committed restore at stop."""
    tl = session.timeline
    punch: list[TimelineCue] = []
    for stem in tl.armed_stems:
        baseline = tl.record_baseline.get(stem)
        if baseline is None:
            continue
        if baseline != timeline_committed_visible(session, stem, record_start):
            punch.append(
                TimelineCue(
                    t=record_start,
                    layers={stem: baseline},
                    show_tick=False,
                )
            )
    punch.extend(tl.record_buffer)
    for stem in tl.armed_stems:
        end_visible = armed_recording_visible(session, stem, record_stop)
        committed_at_stop = timeline_committed_visible(session, stem, record_stop)
        if end_visible != committed_at_stop:
            punch.append(
                TimelineCue(
                    t=record_stop,
                    layers={stem: committed_at_stop},
                    show_tick=False,
                )
            )
    return punch


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
            return armed_recording_visible(session, stem, t_sec)
        if stem in tl.override_stems:
            return tl.override_visible.get(stem, True)
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


def _warmup_layers(
    layers: list[StemLayer],
    pcm_bank: StemPcmBank,
    start_sec: float,
    frames: int,
    fps: int,
    n_pcm: int,
    *,
    session: TuningSession,
) -> None:
    """Pre-render projectM FBOs over a pre-roll that flows into *start_sec*.

    Frame time advances monotonically across the pre-roll, from
    ``start_sec - frames / fps`` up to ``start_sec - 1 / fps``, so projectM's
    time-driven equations and feedback buffers actually evolve (pinning the
    frame time leaves projectM in its white frame-0 state). The window ends one
    frame before *start_sec*, so the first real frame at *start_sec* continues
    the same ``+1 / fps`` step with no frame-time reset or visible cut.

    For a t=0 show start the pre-roll frame times are negative; that is fine for
    projectM and PCM is sampled from the show-start region
    (StemPcmBank.slice_pcm clamps the sample position to t>=0).
    """
    layers_by_name = {layer.name: layer for layer in layers}
    for i in range(frames):
        t_sec = start_sec - (frames - i) / fps
        apply_layer_visibility(session, layers_by_name, t_sec)
        for layer in layers:
            if not layer.fbo.enabled:
                continue
            pcm = pcm_bank.slice_pcm(layer.name, t_sec, n_pcm)
            layer.pm.feed_pcm(pcm)
            layer.pm.set_frame_time(t_sec)
            _render_layer_fbo(layer, layer.pm)


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
    *,
    timeline_panel_open: bool = False,
    help_overlay: HelpOverlay | None = None,
) -> None:
    overlay_surface.fill((0, 0, 0, 0))
    overlay.draw(
        overlay_surface, view_state, timeline_panel_open=timeline_panel_open
    )
    if help_overlay is not None and view_state.help_visible:
        help_overlay.draw(
            overlay_surface,
            row_kind(view_state, view_state.focus_index),
            timeline_enabled=view_state.render_timeline.enabled,
            timeline_submenu_focused=view_state.timeline_submenu_focused,
            paused=view_state.paused,
            timeline_recording=view_state.timeline_recording,
            timeline_override_active=view_state.timeline_override_active,
        )
    panel = overlay.panel_rect
    if panel is not None:
        px, py, pw, ph = panel
        panel_surface = overlay_surface.subsurface((px, py, pw, ph))
        tex_id = compositor.upload_overlay_texture(panel_surface)
        compositor.draw_overlay(tex_id, px, py, pw, ph)

    if help_overlay is not None and view_state.help_visible:
        help_panel = help_overlay.panel_rect
        if help_panel is not None:
            hx, hy, hw, hh = help_panel
            help_surface = overlay_surface.subsurface((hx, hy, hw, hh))
            help_tex_id = compositor.upload_overlay_texture(help_surface)
            compositor.draw_overlay(help_tex_id, hx, hy, hw, hh)


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
        cues=list(tl.cues),
        defaults=timeline_defaults(session),
        position_sec=position_sec,
        duration_sec=duration_sec,
        focus_row=tl.focus_row,
        monitor_visible=monitor_visible,
        timeline_visible=timeline_visible,
        override_stems=set(tl.override_stems),
        armed_stems=set(tl.armed_stems),
        recording=tl.recording,
        record_start_sec=tl.record_start_sec,
        record_baseline=dict(tl.record_baseline),
        record_buffer=list(tl.record_buffer),
        enabled=tl.enabled,
        submenu_focused=tl.submenu_focused,
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
    content_height: int,
    *,
    visibility: float = 1.0,
) -> None:
    overlay_surface.fill((0, 0, 0, 0))
    overlay.draw(overlay_surface, view_state, content_height=content_height)
    panel = overlay.panel_rect
    if panel is not None and visibility > 0.01:
        upload_rect = panel
        badge = overlay.header_badge_rect
        if badge is not None:
            upload_rect = _union_rect(panel, badge)
        px, py, pw, ph = upload_rect
        upload_surface = overlay_surface.subsurface((px, py, pw, ph))
        tex_id = compositor.upload_overlay_texture(upload_surface)
        compositor.draw_overlay(tex_id, px, py, pw, ph, visibility)
