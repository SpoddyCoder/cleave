"""Wire tuning controls to live layer state."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cleave.config import CleaveConfig
from cleave.config_schema import (
    MAX_LAYER_COUNT,
    MIN_LAYER_COUNT,
    DEFAULT_NEW_LAYER_STEM,
    new_layer_config,
    next_layer_slot,
)
from cleave.config_snapshot import next_unnamed_path, write_session_snapshot
from cleave.effects.runtime import EffectRuntime
from cleave.extract import STEM_NAMES, STEM_SOURCES
from cleave.gl_compositor import GlCompositor
from cleave.gl_post_process import GlPostProcess
from cleave.paths import repo_root
from cleave.preset_playlist import PresetPlaylist, preset_browse_floor, scan_single_layer
from cleave.signals import Signals
from cleave.viz.controls import TuningControls
from cleave.viz.layer_preview_resolution import preview_layer_size
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.render_post_fx_bindings import RenderPostFxBindings
from cleave.viz.modal import ModalHost
from cleave.viz.session import (
    LayerRuntime,
    TuningSession,
    add_layer_to_session,
    remove_layer_from_session,
)
from cleave.viz.timeline_controls import TimelineControls
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import LayerFramePipeline, apply_effect_modifiers
from cleave.viz.layer_visibility import apply_layer_visibility, effective_layer_enabled
from cleave.viz.mix_player import MixPlayer
from cleave.viz.preset_switching import (
    EMPTY_ROTATION_NOTIFICATION,
    EMPTY_USER_PRESETS_NOTIFICATION,
    apply_preset_switching,
    load_manual_preset_clean,
    reapply_projectm_preset_switching,
    sync_manual_browse_with_user_defined_rotation,
)
from cleave.stem_pcm import StemPcmBank
from cleave.viz.playback import current_sec, seek
from cleave.config import VIZ_CONFIG_FILENAME


def _discard_timeline_slot(session: TuningSession, slot: str) -> None:
    timeline = session.timeline
    timeline.armed_slots.discard(slot)
    timeline.override_slots.discard(slot)
    timeline.record_baseline.pop(slot, None)
    timeline.monitor.pop(slot, None)
    timeline.override_visible.pop(slot, None)
    timeline.arm_flash_start_ms.pop(slot, None)
    for cue in timeline.record_buffer:
        cue.layers.pop(slot, None)
    timeline.record_buffer = [cue for cue in timeline.record_buffer if cue.layers]


class LayerManager:
    def __init__(
        self,
        cfg: CleaveConfig,
        session: TuningSession,
        compositor: GlCompositor,
        layers: list[StemLayer],
        layers_by_slot: dict[str, StemLayer],
        playlists: dict[str, PresetPlaylist],
        preset_root: Path,
        project_dir: Path,
        projectm_fps: int,
        texture_paths: list[Path],
    ) -> None:
        self.cfg = cfg
        self.session = session
        self.compositor = compositor
        self.layers = layers
        self.layers_by_slot = layers_by_slot
        self.playlists = playlists
        self.preset_root = preset_root
        self.project_dir = project_dir
        self.projectm_fps = projectm_fps
        self.texture_paths = texture_paths

    def can_add(self) -> bool:
        return len(self.session.layer_z_order) < MAX_LAYER_COUNT

    def can_remove(self) -> bool:
        return len(self.session.layer_z_order) > MIN_LAYER_COUNT

    def add_layer(self) -> str:
        slot = next_layer_slot(self.session.layer_z_order)
        playlist = scan_single_layer(slot, self.preset_root, self.project_dir)
        preset = playlist.current if playlist.current is not None else self.preset_root
        layer_cfg = new_layer_config(slot, preset, self.preset_root)
        self.cfg.layers[slot] = layer_cfg
        z_index = len(self.session.layer_z_order)
        width, height = preview_layer_size(
            self.cfg.editor.preview_quality,
            z_index,
            self.cfg.editor,
        )
        stem_layer = LayerFramePipeline.build_single(
            slot,
            layer_cfg,
            self.compositor,
            playlist,
            self.projectm_fps,
            self.texture_paths,
            beat_sensitivity=self.cfg.editor.beat_sensitivity,
            width=width,
            height=height,
        )
        self.layers.append(stem_layer)
        self.layers_by_slot[slot] = stem_layer
        self.playlists[slot] = playlist
        runtime = LayerRuntime(
            playlist=playlist,
            browse_floor=preset_browse_floor(layer_cfg.preset, self.preset_root),
            stem=DEFAULT_NEW_LAYER_STEM,
            beat_sensitivity=self.cfg.editor.beat_sensitivity,
        )
        add_layer_to_session(self.session, slot, runtime)
        self.cfg.layer_z_order.append(slot)
        self.apply_preview_resolutions()
        return slot

    def apply_preview_resolutions(self) -> None:
        LayerFramePipeline.apply_preview_resolutions(
            self.cfg,
            self.session,
            self.layers_by_slot,
            self.compositor,
        )

    def remove_layer(self, slot: str) -> None:
        _discard_timeline_slot(self.session, slot)
        LayerFramePipeline.destroy_single(
            slot, self.layers, self.layers_by_slot, self.compositor
        )
        del self.cfg.layers[slot]
        self.cfg.layer_z_order.remove(slot)
        del self.playlists[slot]
        remove_layer_from_session(self.session, slot)


def _solo_audio_source(session: TuningSession) -> str | None:
    if session.solo_slot is None:
        return None
    return session.layers[session.solo_slot].stem


def _sync_mix_player_solo(session: TuningSession, mix_player: MixPlayer) -> None:
    mix_player.set_solo_source(_solo_audio_source(session))


def make_tuning_controls(
    *,
    session: TuningSession,
    cfg: CleaveConfig,
    preset_root: Path,
    project_dir: Path,
    layers_by_slot: dict[str, StemLayer],
    layers: list[StemLayer],
    playback,
    duration_sec: float,
    signals: Signals | None,
    effect_runtime: EffectRuntime,
    pcm_bank: StemPcmBank | None = None,
    mix_player: MixPlayer | None = None,
    modal_host: ModalHost | None = None,
    layer_manager: LayerManager | None = None,
    compositor: GlCompositor | None = None,
    post_process: GlPostProcess | None = None,
) -> TuningControls:
    def _empty_rotation_notify(slot: str) -> Callable[[], None]:
        runtime = session.layers[slot]

        def on_empty() -> None:
            notify = notification_sink.get("fn")
            if notify is not None:
                if runtime.preset_switching == "user_defined":
                    notify(EMPTY_USER_PRESETS_NOTIFICATION)
                else:
                    notify(EMPTY_ROTATION_NOTIFICATION)

        return on_empty

    def on_preset_change(slot: str, playlist: PresetPlaylist) -> None:
        layer = layers_by_slot[slot]
        layer.playlist = playlist
        runtime = session.layers[slot]
        mode = runtime.preset_switching
        if mode == "projectm":
            current = playlist.current
            if current is not None:
                layer.auto_preset_path = current.resolve()
            apply_preset_switching(
                layer,
                mode=runtime.preset_switching,
                scope=runtime.preset_switching_scope,
                user_presets=runtime.user_presets,
                preset_duration=runtime.preset_duration,
                soft_cut_duration=runtime.soft_cut_duration,
                easter_egg=runtime.easter_egg,
                preset_start_clean=runtime.preset_start_clean,
                hard_cut_enabled=runtime.hard_cut_enabled,
                hard_cut_duration=runtime.hard_cut_duration,
                hard_cut_sensitivity=runtime.hard_cut_sensitivity,
                shuffle=runtime.preset_switching_shuffle,
                on_empty=_empty_rotation_notify(slot),
            )
            return
        if playlist.current is None:
            return
        load_manual_preset_clean(
            layer, preset_start_clean=runtime.preset_start_clean
        )
        if mode == "none":
            layer.pm.lock_preset(True)
            return
        layer.pm.lock_preset(False)
        sync_manual_browse_with_user_defined_rotation(layer)

    def on_preset_switching_change(slot: str) -> None:
        layer = layers_by_slot[slot]
        runtime = session.layers[slot]
        apply_preset_switching(
            layer,
            mode=runtime.preset_switching,
            scope=runtime.preset_switching_scope,
            user_presets=runtime.user_presets,
            preset_duration=runtime.preset_duration,
            soft_cut_duration=runtime.soft_cut_duration,
            easter_egg=runtime.easter_egg,
            preset_start_clean=runtime.preset_start_clean,
            hard_cut_enabled=runtime.hard_cut_enabled,
            hard_cut_duration=runtime.hard_cut_duration,
            hard_cut_sensitivity=runtime.hard_cut_sensitivity,
            shuffle=runtime.preset_switching_shuffle,
            on_empty=_empty_rotation_notify(slot),
        )

    def lock_preset_for_modal(slot: str) -> None:
        layers_by_slot[slot].pm.lock_preset(True)

    def unlock_preset_after_modal(slot: str) -> None:
        runtime = session.layers[slot]
        if runtime.preset_switching == "none":
            layers_by_slot[slot].pm.lock_preset(True)
        else:
            layers_by_slot[slot].pm.lock_preset(False)

    notification_sink: dict[str, Callable[[str], None] | None] = {"fn": None}

    def on_blend_change(slot: str, blend_mode) -> None:
        layers_by_slot[slot].fbo.blend_mode = blend_mode

    def on_stem_change(slot: str, stem) -> None:
        LayerFramePipeline.flush_pcm(layers)
        if mix_player is not None:
            _sync_mix_player_solo(session, mix_player)
        apply_effect_modifiers(
            session,
            layers_by_slot,
            effect_runtime,
            signals,
            current_sec(playback, duration_sec),
            update=False,
        )

    def on_opacity_change(slot: str, pct: int) -> None:
        apply_effect_modifiers(
            session,
            layers_by_slot,
            effect_runtime,
            signals,
            current_sec(playback, duration_sec),
            update=False,
        )

    def on_layer_enabled_change(slot: str, enabled: bool) -> None:
        t_sec = current_sec(playback, duration_sec)
        apply_layer_visibility(session, layers_by_slot, t_sec)
        LayerFramePipeline.flush_pcm(layers)
        if effective_layer_enabled(session, slot, t_sec):
            apply_effect_modifiers(
                session,
                layers_by_slot,
                effect_runtime,
                signals,
                current_sec(playback, duration_sec),
                update=False,
            )

    def on_timeline_enabled_change() -> None:
        t_sec = current_sec(playback, duration_sec)
        apply_layer_visibility(session, layers_by_slot, t_sec)
        LayerFramePipeline.flush_pcm(layers)
        apply_effect_modifiers(
            session,
            layers_by_slot,
            effect_runtime,
            signals,
            current_sec(playback, duration_sec),
            update=False,
        )

    def on_solo_change() -> None:
        t_sec = current_sec(playback, duration_sec)
        apply_layer_visibility(session, layers_by_slot, t_sec)
        if mix_player is not None:
            _sync_mix_player_solo(session, mix_player)
        LayerFramePipeline.flush_pcm(layers)
        apply_effect_modifiers(
            session,
            layers_by_slot,
            effect_runtime,
            signals,
            current_sec(playback, duration_sec),
            update=False,
        )

    def on_beat_change(slot: str, beat: float) -> None:
        layers_by_slot[slot].pm.set_beat_sensitivity(beat)

    def on_seek(delta_sec: float) -> None:
        seek(playback, delta_sec, duration_sec)
        LayerFramePipeline.flush_pcm(layers)
        reapply_projectm_preset_switching(
            session,
            layers_by_slot,
            delta_sec=delta_sec,
        )

    def on_highlight_rolloff_apply_mode_change(old_mode: str, new_mode: str) -> None:
        if compositor is None or post_process is None:
            return
        if session.render_post_fx_solo:
            return
        hr = session.render_post_fx.highlight_rolloff
        for layer in layers:
            if not layer.fbo.enabled:
                continue
            fbo = layer.fbo
            if new_mode == "per_layer" and old_mode in ("composite", "off"):
                compositor.copy_layer_to_rolloff_source(
                    post_process,
                    layer.slot,
                    fbo.texture_id,
                    fbo.width,
                    fbo.height,
                )
                LayerFramePipeline.apply_layer_highlight_rolloff(
                    layer, post_process, compositor, hr
                )
            elif old_mode == "per_layer" and new_mode in ("composite", "off"):
                compositor.restore_layer_from_rolloff_source(
                    post_process,
                    layer.slot,
                    fbo.texture_id,
                    fbo.width,
                    fbo.height,
                )

    def on_chroma_boost_apply_mode_change(old_mode: str, new_mode: str) -> None:
        if compositor is None or post_process is None:
            return
        if session.render_post_fx_solo:
            return
        cb = session.render_post_fx.chroma_boost
        for layer in layers:
            if not layer.fbo.enabled:
                continue
            fbo = layer.fbo
            if new_mode == "per_layer" and old_mode in ("composite", "off"):
                compositor.copy_layer_to_chroma_source(
                    post_process,
                    layer.slot,
                    fbo.texture_id,
                    fbo.width,
                    fbo.height,
                )
                LayerFramePipeline.apply_layer_chroma_boost(
                    layer, post_process, compositor, cb
                )
            elif old_mode == "per_layer" and new_mode in ("composite", "off"):
                compositor.restore_layer_from_chroma_source(
                    post_process,
                    layer.slot,
                    fbo.texture_id,
                    fbo.width,
                    fbo.height,
                )

    render_post_fx_bindings = RenderPostFxBindings(
        on_highlight_rolloff_apply_mode_change=on_highlight_rolloff_apply_mode_change,
        on_chroma_boost_apply_mode_change=on_chroma_boost_apply_mode_change,
        is_paused=lambda: playback.paused,
    )

    layer_bindings = LiveLayerBindings(
        on_preset_change=on_preset_change,
        on_preset_switching_change=on_preset_switching_change,
        lock_preset_for_modal=lock_preset_for_modal,
        unlock_preset_after_modal=unlock_preset_after_modal,
        on_blend_change=on_blend_change,
        on_stem_change=on_stem_change,
        on_opacity_change=on_opacity_change,
        on_layer_enabled_change=on_layer_enabled_change,
        on_timeline_enabled_change=on_timeline_enabled_change,
        on_solo_change=on_solo_change,
        on_beat_change=on_beat_change,
        on_seek=on_seek,
    )

    kwargs: dict = {
        "session": session,
        "cfg": cfg,
        "preset_root": preset_root,
        "project_dir": project_dir,
        "playback": playback,
        "duration_sec": duration_sec,
        "layer_bindings": layer_bindings,
        "render_post_fx_bindings": render_post_fx_bindings,
        "layer_manager": layer_manager,
    }
    if modal_host is not None:
        kwargs["modal_host"] = modal_host

    def on_save_new_config() -> Path:
        out_path = next_unnamed_path(project_dir)
        write_session_snapshot(out_path, cfg=cfg, session=session)
        return out_path

    def on_overwrite_config(path: Path) -> str:
        write_session_snapshot(path, cfg=cfg, session=session)
        return path.name

    kwargs.update(
        on_save_new_config=on_save_new_config,
        on_overwrite_config=on_overwrite_config,
        launch_config_path=cfg.config_path,
        repo_root_example=repo_root() / VIZ_CONFIG_FILENAME,
    )

    controls = TuningControls(**kwargs)
    notification_sink["fn"] = controls.show_notification
    if pcm_bank is not None and mix_player is not None:
        mix_player.set_stem_pcm(
            {
                stem: (pcm_bank.pcm(stem), pcm_bank.channels(stem))
                for stem in STEM_SOURCES
            }
        )
        apply_layer_visibility(
            session,
            layers_by_slot,
            current_sec(playback, duration_sec),
        )
        _sync_mix_player_solo(session, mix_player)
    return controls


def make_timeline_controls(
    *,
    session: TuningSession,
    playback,
    duration_sec: float,
    layers_by_slot: dict[str, StemLayer],
    layers: list[StemLayer],
    signals: Signals | None,
    effect_runtime: EffectRuntime,
    mix_player: MixPlayer | None = None,
    on_notification: Callable[[str], None] | None = None,
    tuning_controls: TuningControls | None = None,
) -> TimelineControls:
    def on_visibility_change() -> None:
        t_sec = current_sec(playback, duration_sec)
        apply_layer_visibility(session, layers_by_slot, t_sec)
        LayerFramePipeline.flush_pcm(layers)
        apply_effect_modifiers(
            session,
            layers_by_slot,
            effect_runtime,
            signals,
            current_sec(playback, duration_sec),
            update=False,
        )

    def on_close() -> None:
        if tuning_controls is not None:
            tuning_controls.close_timeline_panel()
        else:
            session.timeline.panel_open = False

    def on_exit_submenu() -> None:
        if tuning_controls is not None:
            tuning_controls.exit_timeline_submenu()

    def on_seek(delta_sec: float) -> None:
        seek(playback, delta_sec, duration_sec)
        LayerFramePipeline.flush_pcm(layers)
        reapply_projectm_preset_switching(
            session,
            layers_by_slot,
            delta_sec=delta_sec,
        )

    return TimelineControls(
        session,
        playback,
        duration_sec,
        on_visibility_change=on_visibility_change,
        on_close=on_close,
        on_exit_submenu=on_exit_submenu,
        on_seek=on_seek,
        on_notification=on_notification,
    )
