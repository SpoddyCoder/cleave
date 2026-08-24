"""Per-frame GL pipeline for stem layers."""

from __future__ import annotations

from pathlib import Path

from collections.abc import Callable

from cleave.config import CleaveConfig
from cleave.milk_textures import project_texture_search_paths
from cleave.effects.runtime import EffectRuntime
from cleave.gl_compositor import GlCompositor
from cleave.gl_masked_compositor import GlMaskedCompositor
from cleave.gl_post_process import GlPostProcess
from cleave.layer_composite import LayerCompositeRequest
from cleave.pattern_mask import PatternMaskParams
from cleave.preset_playlist import PresetPlaylist
from cleave.projectm import ProjectM, pcm_max_samples_per_channel
from cleave.projectm_health import (
    drain_projectm_log_notifications,
    drain_stem_layers_preset_failures,
)
from cleave.signals import Signals
from cleave.stem_pcm import StemPcmBank, fold_pcm_to_max_samples
from cleave.viz.layer import StemLayer
from cleave.viz.layer_preview_resolution import (
    preview_layer_size,
    preview_sizes_for_session,
    render_layer_size,
)
from cleave.viz.editor_mode_controls import (
    is_preset_curation_mode,
    projectm_notifications_active,
    render_sections_active,
)
from cleave.viz.post_fx import (
    chroma_boost_active,
    chroma_boost_variant_index,
    highlight_rolloff_active,
    highlight_rolloff_curve_index,
)
from cleave.viz.preset_switching import apply_preset_switching
from cleave.viz.session import (
    ChromaBoostRuntime,
    HighlightRolloffRuntime,
    LayerRuntime,
    TuningSession,
)
from OpenGL.GL import GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, glClear, glClearColor, glViewport


def _apply_curation_layer_modifiers(layers_by_slot: dict[str, StemLayer]) -> None:
    """Identity compositing for judging presets: full opacity, no effects, black-key."""
    for layer in layers_by_slot.values():
        if not layer.fbo.enabled:
            continue
        fbo = layer.fbo
        fbo.opacity = 1.0
        fbo.flash_alpha = 0.0
        fbo.bloom_strength = 0.0
        fbo.hue_rgb = (1.0, 1.0, 1.0)
        fbo.hue_mix = 0.0
        fbo.grit_strength = 0.0
        fbo.aberration_px = 0.0
        fbo.blend_mode = "black-key"


def apply_effect_modifiers(
    session: TuningSession,
    layers_by_slot: dict[str, StemLayer],
    effect_runtime: EffectRuntime,
    signals: Signals | None,
    t_sec: float,
    *,
    update: bool = True,
) -> None:
    if is_preset_curation_mode(session):
        _apply_curation_layer_modifiers(layers_by_slot)
        return
    if update:
        effect_runtime.update(session, signals, t_sec)
    modifiers = effect_runtime.modifiers(session)
    for slot, layer in layers_by_slot.items():
        if not layer.fbo.enabled:
            continue
        mod = modifiers[slot]
        layer.fbo.opacity = mod.opacity * layer.timeline_level * layer.limiter_gain
        layer.fbo.flash_alpha = mod.flash_alpha
        layer.fbo.bloom_strength = mod.bloom_strength
        layer.fbo.hue_rgb = mod.hue_rgb
        layer.fbo.hue_mix = mod.hue_mix
        layer.fbo.grit_strength = mod.grit_strength
        layer.fbo.aberration_px = mod.aberration_px


def _pattern_mask_live_slots(
    session: TuningSession,
    layers_by_slot: dict[str, StemLayer],
    masked_compositor: GlMaskedCompositor | None,
    song_time_sec: float,
) -> dict[str, bool] | None:
    if masked_compositor is None:
        return None
    if not render_sections_active(session):
        return None
    pm = session.render_pattern_mask
    if not pm.enabled:
        return None
    slot_names = list(session.layer_z_order)
    active_slots = tuple(
        bool(
            layers_by_slot[name].fbo.enabled and layers_by_slot[name].fbo.opacity > 0.0
        )
        for name in slot_names
    )
    transition = masked_compositor.transitions.peek(
        active_slots,
        song_time_sec=song_time_sec,
        duration=pm.transition,
        mask_type=pm.type,
    )
    flags = masked_compositor.live_slots(
        active_slots, song_time_sec, transition
    )
    return {name: flags[index] for index, name in enumerate(slot_names)}


def _slot_should_render(
    layer: StemLayer, live_by_slot: dict[str, bool] | None
) -> bool:
    if layer.fbo.enabled:
        return True
    if live_by_slot is None:
        return False
    return bool(live_by_slot.get(layer.slot, False))


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
        runtime: LayerRuntime,
        compositor: GlCompositor,
        playlist: PresetPlaylist,
        fps: int,
        texture_paths: list[Path],
        *,
        width: int,
        height: int,
        preset_root: Path,
    ) -> StemLayer:
        w, h = width, height

        pm = ProjectM()
        pm.set_window_size(w, h)
        if texture_paths:
            pm.set_texture_paths(texture_paths)
        playlist.load_into(pm)
        pm.set_fps(fps)
        pm.set_beat_sensitivity(runtime.beat_sensitivity)

        fbo = compositor.create_layer_fbo(
            slot,
            w,
            h,
            opacity=runtime.opacity_pct / 100.0,
            blend_mode=runtime.blend_mode,
        )
        fbo.enabled = runtime.enabled
        layer = StemLayer(
            slot=slot,
            pm=pm,
            fbo=fbo,
            playlist=playlist,
        )
        apply_preset_switching(
            layer,
            mode=runtime.preset_switching,
            trigger=runtime.preset_switching_trigger,
            preset_list=runtime.preset_list,
            preset_duration=runtime.preset_duration,
            soft_cut_duration=runtime.soft_cut_duration,
            easter_egg=runtime.easter_egg,
            preset_start_clean=runtime.preset_start_clean,
            hard_cut_enabled=runtime.hard_cut_enabled,
            hard_cut_duration=runtime.hard_cut_duration,
            hard_cut_sensitivity=runtime.hard_cut_sensitivity,
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
        session: TuningSession,
        *,
        projectm_fps: int,
        preview_resolutions: bool = True,
        viz_quality: bool = False,
        project_dir: Path | None = None,
    ) -> tuple[list[StemLayer], dict[str, StemLayer]]:
        texture_paths = list(cfg.paths.texture_paths)
        if project_dir is not None:
            texture_paths = project_texture_search_paths(project_dir, texture_paths)
        runtimes: list[StemLayer] = []
        z_order = session.layer_z_order

        if preview_resolutions:
            preview_quality = cfg.editor.preview_quality
            visualizer = cfg.editor

            def layer_size(slot: str) -> tuple[int, int]:
                z_index = z_order.index(slot)
                return preview_layer_size(preview_quality, z_index, visualizer)
        else:

            def layer_size(slot: str) -> tuple[int, int]:
                z_index = z_order.index(slot)
                return render_layer_size(cfg, z_index, viz_quality=viz_quality)

        preset_root = cfg.paths.preset_root
        for slot in z_order:
            runtime = session.layers[slot]
            width, height = layer_size(slot)
            runtimes.append(
                LayerFramePipeline.build_single(
                    slot,
                    runtime,
                    compositor,
                    playlists[slot],
                    projectm_fps,
                    texture_paths,
                    width=width,
                    height=height,
                    preset_root=preset_root,
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
        pm_time_sec: float,
        compositor: GlCompositor | None = None,
        masked_compositor: GlMaskedCompositor | None = None,
        on_panel_notification: Callable[[str], None] | None = None,
    ) -> None:
        notify = (
            on_panel_notification
            if projectm_notifications_active(session)
            else None
        )
        drain_stem_layers_preset_failures(
            layers,
            on_notification=notify,
            skip_notify_tracker=session.preset_skip_notify_tracker,
        )
        drain_projectm_log_notifications(
            on_notification=notify,
            log_notify_tracker=session.projectm_log_notify_tracker,
        )

        live_by_slot = _pattern_mask_live_slots(
            session, layers_by_slot, masked_compositor, t_sec
        )

        if not paused:
            for layer in layers:
                if not _slot_should_render(layer, live_by_slot):
                    continue
                stem = session.layers[layer.slot].stem
                pcm = pcm_bank.slice_pcm(stem, t_sec, n_pcm)
                ch = pcm_bank.channels(stem)
                max_pcm = pcm_max_samples_per_channel()
                if max_pcm > 0:
                    pcm = fold_pcm_to_max_samples(
                        pcm, channels=ch, max_samples=max_pcm
                    )
                layer.pm.feed_pcm(pcm, channels=ch)
                layer.pm.set_frame_time(pm_time_sec)

        apply_effect_modifiers(
            session,
            layers_by_slot,
            effect_runtime,
            signals,
            t_sec,
        )

        pp = session.render_post_fx
        sections_on = render_sections_active(session)
        hr = pp.highlight_rolloff
        cb = pp.chroma_boost
        per_layer_rolloff = (
            sections_on
            and highlight_rolloff_active(pp, solo=False)
            and hr.mode == "per_layer"
            and compositor is not None
        )
        per_layer_chroma = (
            sections_on
            and chroma_boost_active(pp, solo=False)
            and cb.mode == "per_layer"
            and compositor is not None
        )

        if not paused:
            for layer in layers:
                if _slot_should_render(layer, live_by_slot):
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
                    if _slot_should_render(layer, live_by_slot):
                        _apply_layer_highlight_rolloff(
                            layer, post_process, compositor, hr
                        )
            if per_layer_chroma:
                for layer in layers:
                    if _slot_should_render(layer, live_by_slot):
                        _apply_layer_chroma_boost(
                            layer, post_process, compositor, cb
                        )

    @staticmethod
    def composite(
        compositor: GlCompositor,
        layers_by_slot: dict[str, StemLayer],
        session: TuningSession,
        *,
        masked_compositor: GlMaskedCompositor | None = None,
        song_time_sec: float = 0.0,
    ) -> None:
        slot_names = list(session.layer_z_order)
        ordered = [layers_by_slot[name] for name in slot_names]
        fbos = [layer.fbo for layer in ordered]
        active_slots = tuple(
            bool(layer.fbo.enabled and layer.fbo.opacity > 0.0) for layer in ordered
        )
        pm = session.render_pattern_mask
        use_mask = (
            render_sections_active(session)
            and pm.enabled
            and masked_compositor is not None
        )
        mask = None
        transition = None
        if use_mask:
            assert masked_compositor is not None
            width = compositor.content_width
            height = compositor.content_height
            masked_compositor.set_content_size(width, height)
            mask = PatternMaskParams(
                mask_type=pm.type,
                feather_pct=pm.feather_pct,
                density=pm.density,
                invert=pm.invert,
                seed=pm.seed,
            )
            transition = masked_compositor.transitions.peek(
                active_slots,
                song_time_sec=song_time_sec,
                duration=pm.transition,
                mask_type=pm.type,
            )
        request = LayerCompositeRequest(
            target_fbo_id=compositor.content_fbo_id,
            layers=fbos,
            color_format=compositor.color_format,
            mask=mask,
            active_slots=active_slots,
            song_time_sec=song_time_sec,
            transition=transition,
        )
        if use_mask:
            assert masked_compositor is not None
            masked_compositor.composite(request)
            masked_compositor.transitions.commit(active_slots)
        else:
            compositor.composite(request)

    @staticmethod
    def destroy(layers: list[StemLayer]) -> None:
        for layer in layers:
            layer.pm.destroy()
