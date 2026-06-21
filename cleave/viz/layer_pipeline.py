"""Per-frame GL pipeline for stem layers."""

from __future__ import annotations

from pathlib import Path

from cleave.config import CleaveConfig, LayerConfig
from cleave.effects.runtime import EffectRuntime
from cleave.gl_compositor import GlCompositor
from cleave.gl_post_process import GlPostProcess
from cleave.preset_playlist import PresetPlaylist
from cleave.projectm import ProjectM
from cleave.signals import Signals
from cleave.stem_pcm import StemPcmBank
from cleave.viz.layer import StemLayer
from cleave.viz.layer_visibility import apply_layer_visibility, effective_layer_enabled
from cleave.viz.session import TuningSession
from OpenGL.GL import GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, glClear, glClearColor, glViewport


def apply_effect_modifiers(
    session: TuningSession,
    layers_by_slot: dict[str, StemLayer],
    effect_runtime: EffectRuntime,
    signals: Signals | None,
    t_sec: float,
    *,
    update: bool = True,
) -> None:
    if update:
        effect_runtime.update(session, signals, t_sec)
    modifiers = effect_runtime.modifiers(session)
    for slot, layer in layers_by_slot.items():
        if not effective_layer_enabled(session, slot, t_sec):
            continue
        mod = modifiers[slot]
        layer.fbo.opacity = mod.opacity
        layer.fbo.flash_alpha = mod.flash_alpha
        layer.fbo.bloom_strength = mod.bloom_strength
        layer.fbo.hue_rgb = mod.hue_rgb
        layer.fbo.hue_mix = mod.hue_mix
        layer.fbo.grit_strength = mod.grit_strength
        layer.fbo.aberration_px = mod.aberration_px


def _beat_sensitivity(cfg: CleaveConfig, slot: str) -> float:
    layer = cfg.layers[slot]
    if layer.beat_sensitivity is not None:
        return layer.beat_sensitivity
    return cfg.visualizer.beat_sensitivity


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


class LayerFramePipeline:
    """Per-frame GL path for stem layers."""

    @staticmethod
    def build_single(
        slot: str,
        layer_cfg: LayerConfig,
        compositor: GlCompositor,
        playlist: PresetPlaylist,
        fps: int,
        texture_paths: list[Path],
        beat_sensitivity: float,
    ) -> StemLayer:
        w, h = layer_cfg.width, layer_cfg.height

        pm = ProjectM()
        pm.set_window_size(w, h)
        if texture_paths:
            pm.set_texture_paths(texture_paths)
        playlist.load_into(pm)
        pm.lock_preset(True)
        pm.set_hard_cut_enabled(False)
        pm.set_fps(fps)
        pm.set_beat_sensitivity(beat_sensitivity)

        fbo = compositor.create_layer_fbo(
            slot,
            w,
            h,
            opacity=layer_cfg.opacity,
            blend_mode=layer_cfg.blend_mode,
        )
        fbo.enabled = layer_cfg.enabled
        return StemLayer(
            slot=slot,
            pm=pm,
            fbo=fbo,
            playlist=playlist,
        )

    @staticmethod
    def destroy_single(
        slot: str,
        layers: list[StemLayer],
        layers_by_slot: dict[str, StemLayer],
        compositor: GlCompositor,
    ) -> None:
        layer = layers_by_slot.pop(slot)
        layers.remove(layer)
        layer.pm.destroy()
        compositor.remove_layer_fbo(slot)

    @staticmethod
    def build(
        cfg: CleaveConfig,
        compositor: GlCompositor,
        playlists: dict[str, PresetPlaylist],
    ) -> tuple[list[StemLayer], dict[str, StemLayer]]:
        texture_paths = list(cfg.paths.texture_paths)
        fps = cfg.visualizer.fps
        runtimes: list[StemLayer] = []

        for slot, layer_cfg in cfg.layers_in_z_order():
            runtimes.append(
                LayerFramePipeline.build_single(
                    slot,
                    layer_cfg,
                    compositor,
                    playlists[slot],
                    fps,
                    texture_paths,
                    _beat_sensitivity(cfg, slot),
                )
            )

        layers_by_slot = {layer.slot: layer for layer in runtimes}
        return runtimes, layers_by_slot

    @staticmethod
    def warmup(
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
        layers_by_slot = {layer.slot: layer for layer in layers}
        for i in range(frames):
            t_sec = start_sec - (frames - i) / fps
            apply_layer_visibility(session, layers_by_slot, t_sec)
            for layer in layers:
                if not layer.fbo.enabled:
                    continue
                stem = session.layers[layer.slot].stem
                pcm = pcm_bank.slice_pcm(stem, t_sec, n_pcm)
                layer.pm.feed_pcm(pcm, channels=pcm_bank.channels(stem))
                layer.pm.set_frame_time(t_sec)
                _render_layer_fbo(layer, layer.pm)

    @staticmethod
    def flush_pcm(layers: list[StemLayer]) -> None:
        for layer in layers:
            layer.pm.flush_pcm()

    @staticmethod
    def render_frame(
        session: TuningSession,
        layers: list[StemLayer],
        layers_by_slot: dict[str, StemLayer],
        pcm_bank: StemPcmBank,
        n_pcm: int,
        post_process: GlPostProcess,
        effect_runtime: EffectRuntime,
        signals: Signals | None,
        t_sec: float,
        *,
        paused: bool,
    ) -> None:
        if not paused:
            for layer in layers:
                if not layer.fbo.enabled:
                    continue
                stem = session.layers[layer.slot].stem
                pcm = pcm_bank.slice_pcm(stem, t_sec, n_pcm)
                layer.pm.feed_pcm(pcm, channels=pcm_bank.channels(stem))
                layer.pm.set_frame_time(t_sec)

        apply_effect_modifiers(
            session,
            layers_by_slot,
            effect_runtime,
            signals,
            t_sec,
        )

        if not paused:
            for layer in layers:
                if layer.fbo.enabled:
                    _render_layer_fbo(layer, layer.pm)
                    _apply_layer_bloom(layer, post_process)
                    _apply_layer_grit(layer, post_process)

    @staticmethod
    def composite(
        compositor: GlCompositor,
        layers_by_slot: dict[str, StemLayer],
        session: TuningSession,
    ) -> None:
        ordered = [layers_by_slot[name] for name in reversed(session.layer_z_order)]
        compositor.composite([layer.fbo for layer in ordered])

    @staticmethod
    def destroy(layers: list[StemLayer]) -> None:
        for layer in layers:
            layer.pm.destroy()
