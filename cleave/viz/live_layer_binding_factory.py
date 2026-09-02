"""Build live layer and post-FX bindings from an explicit context."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cleave.config import CleaveConfig
from cleave.config_snapshot import next_unnamed_path, write_session_snapshot
from cleave.effects.runtime import EffectRuntime
from cleave.stems import StemSource
from cleave.gl_compositor import GlCompositor
from cleave.gl_post_process import GlPostProcess
from cleave.milk_textures import sync_project_textures
from cleave.preset_playlist import PresetPlaylist
from cleave.signals import Signals
from cleave.viz.editor_mode_controls import preset_switching_active
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import LayerFramePipeline, apply_effect_modifiers
from cleave.viz.layer_visibility import apply_layer_visibility, effective_layer_enabled
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.mix_player import MixPlayer
from cleave.viz.playback import PlaybackState, current_sec, seek
from cleave.viz.preset_switching import (
    EMPTY_PRESET_LIST_NOTIFICATION,
    apply_preset_switching,
    load_manual_preset_clean,
    reanchor_list_preset_after_browse,
    reapply_projectm_preset_switching,
    resync_timeline_preset_switching,
    sync_manual_browse_with_list,
)
from cleave.viz.render_post_fx_bindings import RenderPostFxBindings
from cleave.viz.session import TuningSession
from cleave.viz.user_presets import USER_PRESETS_DIRNAME


@dataclass
class LiveLayerBindingContext:
    session: TuningSession
    cfg: CleaveConfig
    preset_root: Path
    project_dir: Path
    layers_by_slot: dict[str, StemLayer]
    layers: list[StemLayer]
    playback: PlaybackState
    duration_sec: float
    signals: Signals | None
    effect_runtime: EffectRuntime
    mix_player: MixPlayer | None = None
    compositor: GlCompositor | None = None
    post_process: GlPostProcess | None = None
    notification_sink: Callable[[str], None] | None = None


def solo_audio_source(session: TuningSession) -> str | None:
    if session.solo_slot is None:
        return None
    return session.layers[session.solo_slot].stem


def sync_mix_player_solo(session: TuningSession, mix_player: MixPlayer) -> None:
    mix_player.set_solo_source(solo_audio_source(session))


class LiveLayerBindingsFactory:
    """Handlers for LiveLayerBindings, RenderPostFxBindings, and config save."""

    def __init__(self, ctx: LiveLayerBindingContext) -> None:
        self.ctx = ctx

    def layer_bindings(self) -> LiveLayerBindings:
        return LiveLayerBindings(
            on_preset_change=self.on_preset_change,
            on_preset_switching_change=self.on_preset_switching_change,
            lock_preset_for_modal=self.lock_preset_for_modal,
            unlock_preset_after_modal=self.unlock_preset_after_modal,
            on_stem_change=self.on_stem_change,
            on_opacity_change=self.on_opacity_change,
            on_layer_enabled_change=self.on_layer_enabled_change,
            on_timeline_enabled_change=self.on_timeline_enabled_change,
            on_solo_change=self.on_solo_change,
            on_beat_change=self.on_beat_change,
            on_seek=self.on_seek,
        )

    def render_post_fx_bindings(self) -> RenderPostFxBindings:
        return RenderPostFxBindings(
            on_highlight_rolloff_apply_mode_change=(
                self.on_highlight_rolloff_apply_mode_change
            ),
            on_chroma_boost_apply_mode_change=self.on_chroma_boost_apply_mode_change,
            is_paused=self.is_paused,
        )

    def is_paused(self) -> bool:
        return self.ctx.playback.paused

    def on_preset_change(self, slot: str, playlist: PresetPlaylist) -> None:
        ctx = self.ctx
        layer = ctx.layers_by_slot[slot]
        layer.playlist = playlist
        runtime = ctx.session.layers[slot]
        mode = self._effective_preset_switching(slot)
        projectm_trigger = (
            mode == "on" and runtime.preset_switching_trigger == "projectm"
        )
        if projectm_trigger:
            current = playlist.current
            if current is not None:
                layer.auto_preset_path = current.resolve()
            self._apply_preset_switching(slot)
            return
        if playlist.current is None:
            return
        load_manual_preset_clean(
            layer, preset_start_clean=runtime.preset_start_clean
        )
        if mode != "on":
            layer.pm.lock_preset(True)
            return
        if runtime.preset_switching_trigger in ("timer", "timeline"):
            reanchor_list_preset_after_browse(
                layer,
                ctx.session,
                self._song_time(),
                preset_list=runtime.preset_list,
            )
            return
        layer.pm.lock_preset(False)
        sync_manual_browse_with_list(layer)

    def on_preset_switching_change(self, slot: str) -> None:
        self._apply_preset_switching(slot)

    def lock_preset_for_modal(self, slot: str) -> None:
        self.ctx.layers_by_slot[slot].pm.lock_preset(True)

    def unlock_preset_after_modal(self, slot: str) -> None:
        mode = self._effective_preset_switching(slot)
        runtime = self.ctx.session.layers[slot]
        projectm_trigger = (
            mode == "on" and runtime.preset_switching_trigger == "projectm"
        )
        if projectm_trigger:
            self.ctx.layers_by_slot[slot].pm.lock_preset(False)
        else:
            self.ctx.layers_by_slot[slot].pm.lock_preset(True)

    def on_stem_change(self, slot: str, stem: StemSource) -> None:
        ctx = self.ctx
        LayerFramePipeline.flush_pcm(ctx.layers)
        if ctx.mix_player is not None:
            sync_mix_player_solo(ctx.session, ctx.mix_player)
        self._apply_effect_modifiers()

    def on_opacity_change(self, slot: str, pct: int) -> None:
        self._apply_effect_modifiers()

    def on_layer_enabled_change(self, slot: str, enabled: bool) -> None:
        ctx = self.ctx
        t_sec = self._song_time()
        apply_layer_visibility(ctx.session, ctx.layers_by_slot, t_sec)
        LayerFramePipeline.flush_pcm(ctx.layers)
        if effective_layer_enabled(ctx.session, slot, t_sec):
            self._apply_effect_modifiers()

    def on_timeline_enabled_change(self) -> None:
        ctx = self.ctx
        t_sec = self._song_time()
        apply_layer_visibility(ctx.session, ctx.layers_by_slot, t_sec)
        LayerFramePipeline.flush_pcm(ctx.layers)
        self._apply_effect_modifiers()

    def on_solo_change(self) -> None:
        ctx = self.ctx
        t_sec = self._song_time()
        apply_layer_visibility(ctx.session, ctx.layers_by_slot, t_sec)
        if ctx.mix_player is not None:
            sync_mix_player_solo(ctx.session, ctx.mix_player)
        LayerFramePipeline.flush_pcm(ctx.layers)
        self._apply_effect_modifiers()

    def on_beat_change(self, slot: str, beat: float) -> None:
        self.ctx.layers_by_slot[slot].pm.set_beat_sensitivity(beat)

    def on_seek(self, delta_sec: float) -> None:
        ctx = self.ctx
        seek(ctx.playback, delta_sec, ctx.duration_sec)
        LayerFramePipeline.flush_pcm(ctx.layers)
        reapply_projectm_preset_switching(
            ctx.session,
            ctx.layers_by_slot,
            preset_root=ctx.preset_root,
            delta_sec=delta_sec,
        )
        resync_timeline_preset_switching(
            ctx.session,
            ctx.layers_by_slot,
            self._song_time(),
        )

    def on_highlight_rolloff_apply_mode_change(
        self, old_mode: str, new_mode: str
    ) -> None:
        ctx = self.ctx
        if ctx.compositor is None or ctx.post_process is None:
            return
        if ctx.session.render_post_fx_solo:
            return
        hr = ctx.session.render_post_fx.highlight_rolloff
        for layer in ctx.layers:
            if not layer.fbo.enabled:
                continue
            fbo = layer.fbo
            if new_mode == "per_layer" and old_mode in ("composite", "off"):
                ctx.compositor.copy_layer_to_rolloff_source(
                    ctx.post_process,
                    layer.slot,
                    fbo.texture_id,
                    fbo.width,
                    fbo.height,
                )
                LayerFramePipeline.apply_layer_highlight_rolloff(
                    layer, ctx.post_process, ctx.compositor, hr
                )
            elif old_mode == "per_layer" and new_mode in ("composite", "off"):
                ctx.compositor.restore_layer_from_rolloff_source(
                    ctx.post_process,
                    layer.slot,
                    fbo.texture_id,
                    fbo.width,
                    fbo.height,
                )

    def on_chroma_boost_apply_mode_change(
        self, old_mode: str, new_mode: str
    ) -> None:
        ctx = self.ctx
        if ctx.compositor is None or ctx.post_process is None:
            return
        if ctx.session.render_post_fx_solo:
            return
        cb = ctx.session.render_post_fx.chroma_boost
        for layer in ctx.layers:
            if not layer.fbo.enabled:
                continue
            fbo = layer.fbo
            if new_mode == "per_layer" and old_mode in ("composite", "off"):
                ctx.compositor.copy_layer_to_chroma_source(
                    ctx.post_process,
                    layer.slot,
                    fbo.texture_id,
                    fbo.width,
                    fbo.height,
                )
                LayerFramePipeline.apply_layer_chroma_boost(
                    layer, ctx.post_process, ctx.compositor, cb
                )
            elif old_mode == "per_layer" and new_mode in ("composite", "off"):
                ctx.compositor.restore_layer_from_chroma_source(
                    ctx.post_process,
                    layer.slot,
                    fbo.texture_id,
                    fbo.width,
                    fbo.height,
                )

    def on_save_new_config(self) -> Path:
        ctx = self.ctx
        out_path = next_unnamed_path(ctx.project_dir)
        write_session_snapshot(out_path, cfg=ctx.cfg, session=ctx.session)
        self._sync_project_textures()
        return out_path

    def on_overwrite_config(self, path: Path) -> str:
        ctx = self.ctx
        write_session_snapshot(path, cfg=ctx.cfg, session=ctx.session)
        self._sync_project_textures()
        return path.name

    def _effective_preset_switching(self, slot: str) -> str:
        if not preset_switching_active(self.ctx.session.settings.editor_mode):
            return "off"
        return self.ctx.session.layers[slot].preset_switching

    def _notify_empty_preset_list(self) -> None:
        if not preset_switching_active(self.ctx.session.settings.editor_mode):
            return
        notify = self.ctx.notification_sink
        if notify is not None:
            notify(EMPTY_PRESET_LIST_NOTIFICATION)

    def _apply_preset_switching(self, slot: str) -> None:
        ctx = self.ctx
        layer = ctx.layers_by_slot[slot]
        runtime = ctx.session.layers[slot]
        apply_preset_switching(
            layer,
            mode=self._effective_preset_switching(slot),
            trigger=runtime.preset_switching_trigger,
            preset_list=runtime.preset_list,
            preset_duration=runtime.preset_duration,
            soft_cut_duration=runtime.soft_cut_duration,
            easter_egg=runtime.easter_egg,
            preset_start_clean=runtime.preset_start_clean,
            hard_cut_enabled=runtime.hard_cut_enabled,
            hard_cut_duration=runtime.hard_cut_duration,
            hard_cut_sensitivity=runtime.hard_cut_sensitivity,
            on_empty=self._notify_empty_preset_list,
            session=ctx.session,
        )

    def _apply_effect_modifiers(self) -> None:
        ctx = self.ctx
        apply_effect_modifiers(
            ctx.session,
            ctx.layers_by_slot,
            ctx.effect_runtime,
            ctx.signals,
            self._song_time(),
            update=False,
        )

    def _song_time(self) -> float:
        return current_sec(self.ctx.playback, self.ctx.duration_sec)

    def _sync_project_textures(self) -> None:
        ctx = self.ctx
        presets_dir = ctx.project_dir / USER_PRESETS_DIRNAME
        milk_paths = (
            sorted(presets_dir.glob("*.milk")) if presets_dir.is_dir() else []
        )
        sync_project_textures(ctx.project_dir, milk_paths, ctx.cfg.paths.texture_paths)
