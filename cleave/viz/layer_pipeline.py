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
from cleave.viz.layer_preview_resolution import (
    preview_layer_size,
    preview_sizes_for_session,
    render_layer_size,
)
from cleave.viz.layer_visibility import effective_layer_enabled
from cleave.viz.post_fx import (
    chroma_boost_active,
    chroma_boost_variant_index,
    highlight_rolloff_active,
    highlight_rolloff_curve_index,
)
from cleave.viz.preset_switching import apply_preset_switching
from cleave.viz.session import ChromaBoostRuntime, HighlightRolloffRuntime, TuningSession
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


def _apply_layer_highlight_rolloff(
    layer: StemLayer,
    post_process: GlPostProcess,
    compositor: GlCompositor,
    hr: HighlightRolloffRuntime,
) -> None:
    LayerFramePipeline.apply_layer_highlight_rolloff(
        layer, post_process, compositor, hr
    )


def _apply_layer_chroma_boost(
    layer: StemLayer,
    post_process: GlPostProcess,
    compositor: GlCompositor,
    cb: ChromaBoostRuntime,
) -> None:
    LayerFramePipeline.apply_layer_chroma_boost(
        layer, post_process, compositor, cb
    )


class LayerFramePipeline:
    """Per-frame GL path for stem layers."""

    @staticmethod
    def resize_layer(
        layer: StemLayer,
        compositor: GlCompositor,
        width: int,
        height: int,
    ) -> None:
        layer.pm.set_window_size(width, height)
        compositor.resize_layer_fbo(layer.slot, width, height)

    @staticmethod
    def apply_preview_resolutions(
        cfg: CleaveConfig,
        session: TuningSession,
        layers_by_slot: dict[str, StemLayer],
        compositor: GlCompositor,
    ) -> None:
        sizes = preview_sizes_for_session(cfg, session)
        for slot, (width, height) in sizes.items():
            layer = layers_by_slot[slot]
            fbo = layer.fbo
            if fbo.width == width and fbo.height == height:
                continue
            LayerFramePipeline.resize_layer(layer, compositor, width, height)

    @staticmethod
    def set_projectm_fps(layers: list[StemLayer], fps: int) -> None:
        for layer in layers:
            layer.pm.set_fps(fps)

    @staticmethod
    def build_single(
        slot: str,
        layer_cfg: LayerConfig,
        compositor: GlCompositor,
        playlist: PresetPlaylist,
        fps: int,
        texture_paths: list[Path],
        beat_sensitivity: float,
        *,
        width: int,
        height: int,
    ) -> StemLayer:
        w, h = width, height

        pm = ProjectM()
        pm.set_window_size(w, h)
        if texture_paths:
            pm.set_texture_paths(texture_paths)
        playlist.load_into(pm)
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
        layer = StemLayer(
            slot=slot,
            pm=pm,
            fbo=fbo,
            playlist=playlist,
        )
        apply_preset_switching(
            layer,
            mode=layer_cfg.preset_switching,
            scope=layer_cfg.preset_switching_scope,
            user_presets=[
                str(path) for path in layer_cfg.preset_switching_presets
            ],
            preset_duration=layer_cfg.preset_duration,
            soft_cut_duration=layer_cfg.soft_cut_duration,
            easter_egg=layer_cfg.easter_egg,
            preset_start_clean=layer_cfg.preset_start_clean,
            hard_cut_enabled=layer_cfg.hard_cut_enabled,
            hard_cut_duration=layer_cfg.hard_cut_duration,
            hard_cut_sensitivity=layer_cfg.hard_cut_sensitivity,
        )
        return layer

    @staticmethod
    def destroy_single(
        slot: str,
        layers: list[StemLayer],
        layers_by_slot: dict[str, StemLayer],
        compositor: GlCompositor,
    ) -> None:
        layer = layers_by_slot.pop(slot)
        layers.remove(layer)
        if layer.projectm_playlist is not None:
            layer.projectm_playlist.destroy()
        layer.pm.destroy()
        compositor.remove_layer_fbo(slot)

    @staticmethod
    def build(
        cfg: CleaveConfig,
        compositor: GlCompositor,
        playlists: dict[str, PresetPlaylist],
        *,
        projectm_fps: int,
        preview_resolutions: bool = True,
        session: TuningSession | None = None,
        viz_quality: bool = False,
    ) -> tuple[list[StemLayer], dict[str, StemLayer]]:
        texture_paths = list(cfg.paths.texture_paths)
        runtimes: list[StemLayer] = []

        if preview_resolutions:
            if session is None:
                raise ValueError("session is required when preview_resolutions=True")
            z_order = session.layer_z_order
            preview_quality = cfg.visualizer.preview_quality
            visualizer = cfg.visualizer

            def layer_size(slot: str) -> tuple[int, int]:
                z_index = z_order.index(slot)
                return preview_layer_size(preview_quality, z_index, visualizer)
        else:
            z_order = cfg.layer_z_order

            def layer_size(slot: str) -> tuple[int, int]:
                z_index = z_order.index(slot)
                return render_layer_size(cfg, z_index, viz_quality=viz_quality)

        for slot, layer_cfg in cfg.layers_in_z_order():
            width, height = layer_size(slot)
            runtimes.append(
                LayerFramePipeline.build_single(
                    slot,
                    layer_cfg,
                    compositor,
                    playlists[slot],
                    projectm_fps,
                    texture_paths,
                    _beat_sensitivity(cfg, slot),
                    width=width,
                    height=height,
                )
            )

        layers_by_slot = {layer.slot: layer for layer in runtimes}
        if preview_resolutions:
            LayerFramePipeline.apply_preview_resolutions(
                cfg, session, layers_by_slot, compositor
            )
        return runtimes, layers_by_slot

    @staticmethod
    def flush_pcm(layers: list[StemLayer]) -> None:
        for layer in layers:
            layer.pm.flush_pcm()

    @staticmethod
    def apply_layer_highlight_rolloff(
        layer: StemLayer,
        post_process: GlPostProcess,
        compositor: GlCompositor,
        hr: HighlightRolloffRuntime,
    ) -> None:
        fbo = layer.fbo
        source_id = compositor.rolloff_source_texture_id(layer.slot)
        if source_id == 0:
            return
        post_process.apply_highlight_rolloff(
            fbo.texture_id,
            fbo.width,
            fbo.height,
            hr.threshold_pct / 100.0,
            hr.ceiling_pct / 100.0,
            hr.strength_pct / 100.0,
            hr.softness_pct / 100.0,
            hr.desaturation_pct / 100.0,
            highlight_rolloff_curve_index(hr.curve),
            source_texture_id=source_id,
        )

    @staticmethod
    def apply_layer_chroma_boost(
        layer: StemLayer,
        post_process: GlPostProcess,
        compositor: GlCompositor,
        cb: ChromaBoostRuntime,
    ) -> None:
        fbo = layer.fbo
        source_id = compositor.chroma_source_texture_id(layer.slot)
        if source_id == 0:
            return
        post_process.apply_chroma_boost(
            fbo.texture_id,
            fbo.width,
            fbo.height,
            cb.amount_pct,
            chroma_boost_variant_index(cb.variant),
            source_texture_id=source_id,
        )

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
        compositor: GlCompositor | None = None,
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

        pp = session.render_post_fx
        hr = pp.highlight_rolloff
        cb = pp.chroma_boost
        per_layer_rolloff = (
            highlight_rolloff_active(pp, solo=False)
            and hr.mode == "per_layer"
            and compositor is not None
        )
        per_layer_chroma = (
            chroma_boost_active(pp, solo=False)
            and cb.mode == "per_layer"
            and compositor is not None
        )

        if not paused:
            for layer in layers:
                if layer.fbo.enabled:
                    _render_layer_fbo(layer, layer.pm)
                    _apply_layer_bloom(layer, post_process)
                    _apply_layer_grit(layer, post_process)
                    if per_layer_rolloff:
                        compositor.copy_layer_to_rolloff_source(
                            post_process,
                            layer.slot,
                            layer.fbo.texture_id,
                            layer.fbo.width,
                            layer.fbo.height,
                        )
                        _apply_layer_highlight_rolloff(
                            layer, post_process, compositor, hr
                        )
                    if per_layer_chroma:
                        compositor.copy_layer_to_chroma_source(
                            post_process,
                            layer.slot,
                            layer.fbo.texture_id,
                            layer.fbo.width,
                            layer.fbo.height,
                        )
                        _apply_layer_chroma_boost(
                            layer, post_process, compositor, cb
                        )
        else:
            if per_layer_rolloff:
                for layer in layers:
                    if layer.fbo.enabled:
                        _apply_layer_highlight_rolloff(
                            layer, post_process, compositor, hr
                        )
            if per_layer_chroma:
                for layer in layers:
                    if layer.fbo.enabled:
                        _apply_layer_chroma_boost(
                            layer, post_process, compositor, cb
                        )

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
