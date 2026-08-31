"""Wire tuning controls to live layer state."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cleave.config import CleaveConfig, VIZ_CONFIG_FILENAME
from cleave.config_schema.layers import (
    MAX_LAYER_COUNT,
    MIN_LAYER_COUNT,
    next_layer_slot,
)
from cleave.effects.runtime import EffectRuntime
from cleave.extract import STEM_SOURCES
from cleave.gl_compositor import GlCompositor
from cleave.gl_masked_compositor import GlMaskedCompositor
from cleave.gl_post_process import GlPostProcess
from cleave.paths import repo_root
from cleave.preset_playlist import PresetPlaylist, scan_single_layer
from cleave.signals import Signals
from cleave.viz.controls import TuningControls
from cleave.viz.layer_preview_resolution import preview_layer_size
from cleave.viz.live_layer_binding_factory import (
    LiveLayerBindingContext,
    LiveLayerBindingsFactory,
    sync_mix_player_solo,
)
from cleave.viz.modal import ModalHost
from cleave.viz.session import (
    TuningSession,
    add_layer_to_session,
    new_layer_runtime,
    remove_layer_from_session,
)
from cleave.viz.timeline_controls import TimelineControls
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import LayerFramePipeline, apply_effect_modifiers
from cleave.viz.layer_visibility import apply_layer_visibility
from cleave.viz.mix_player import MixPlayer
from cleave.viz.preset_switching import (
    reapply_projectm_preset_switching,
    resync_timeline_preset_switching,
)
from cleave.stem_pcm import StemPcmBank
from cleave.viz.playback import PlaybackState, current_sec, seek


def _discard_timeline_slot(session: TuningSession, slot: str) -> None:
    timeline = session.timeline
    timeline.armed_slots.discard(slot)
    timeline.override_slots.discard(slot)
    timeline.record_baseline.pop(slot, None)
    timeline.record_slot_start_sec.pop(slot, None)
    timeline.monitor.pop(slot, None)
    timeline.override_visible.pop(slot, None)
    timeline.arm_flash_start_ms.pop(slot, None)
    timeline.selected_cue_t.pop(slot, None)
    timeline.record_buffer.pop(slot, None)


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
        runtime = new_layer_runtime(
            slot,
            playlist,
            self.preset_root,
            self.cfg.editor.beat_sensitivity,
        )
        z_index = len(self.session.layer_z_order)
        width, height = preview_layer_size(
            self.cfg.editor.preview_quality,
            z_index,
            self.cfg.editor,
        )
        stem_layer = LayerFramePipeline.build_single(
            slot,
            runtime,
            self.compositor,
            playlist,
            self.projectm_fps,
            self.texture_paths,
            width=width,
            height=height,
            preset_root=self.preset_root,
        )
        self.layers.append(stem_layer)
        self.layers_by_slot[slot] = stem_layer
        self.playlists[slot] = playlist
        add_layer_to_session(self.session, slot, runtime)
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
        del self.playlists[slot]
        remove_layer_from_session(self.session, slot)


def make_tuning_controls(
    *,
    session: TuningSession,
    cfg: CleaveConfig,
    preset_root: Path,
    project_dir: Path,
    layers_by_slot: dict[str, StemLayer],
    layers: list[StemLayer],
    playback: PlaybackState,
    duration_sec: float,
    signals: Signals | None,
    effect_runtime: EffectRuntime,
    pcm_bank: StemPcmBank | None = None,
    mix_player: MixPlayer | None = None,
    modal_host: ModalHost | None = None,
    layer_manager: LayerManager | None = None,
    compositor: GlCompositor | None = None,
    post_process: GlPostProcess | None = None,
    masked_compositor: GlMaskedCompositor | None = None,
) -> TuningControls:
    ctx = LiveLayerBindingContext(
        session=session,
        cfg=cfg,
        preset_root=preset_root,
        project_dir=project_dir,
        layers_by_slot=layers_by_slot,
        layers=layers,
        playback=playback,
        duration_sec=duration_sec,
        signals=signals,
        effect_runtime=effect_runtime,
        mix_player=mix_player,
        compositor=compositor,
        post_process=post_process,
    )
    factory = LiveLayerBindingsFactory(ctx)

    beat_times: list[float] = []
    bar_times: list[float] = []
    if signals is not None:
        beat_times = list(signals.beat_times)
        bar_times = list(signals.downbeat_times)

    kwargs: dict = {
        "session": session,
        "cfg": cfg,
        "preset_root": preset_root,
        "project_dir": project_dir,
        "playback": playback,
        "duration_sec": duration_sec,
        "layer_bindings": factory.layer_bindings(),
        "render_post_fx_bindings": factory.render_post_fx_bindings(),
        "layer_manager": layer_manager,
        "compositor": compositor,
        "post_process": post_process,
        "masked_compositor": masked_compositor,
        "beat_times": beat_times,
        "bar_times": bar_times,
        "signals": signals,
        "on_save_new_config": factory.on_save_new_config,
        "on_overwrite_config": factory.on_overwrite_config,
        "launch_config_path": cfg.config_path,
        "repo_root_example": repo_root() / VIZ_CONFIG_FILENAME,
    }
    if modal_host is not None:
        kwargs["modal_host"] = modal_host

    controls = TuningControls(**kwargs)
    ctx.notification_sink = controls.show_notification
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
        sync_mix_player_solo(session, mix_player)
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
    preset_root: Path,
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
            preset_root=preset_root,
            delta_sec=delta_sec,
        )
        resync_timeline_preset_switching(
            session,
            layers_by_slot,
            current_sec(playback, duration_sec),
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
        beat_times=list(signals.beat_times) if signals is not None else (),
        bar_times=list(signals.downbeat_times) if signals is not None else (),
    )
