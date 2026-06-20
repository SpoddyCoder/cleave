"""Wire tuning controls to live layer state."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cleave.config import VIZ_CONFIG_FILENAME, CleaveConfig, LayerConfig, PathsConfig, VisualizerConfig
from cleave.config_snapshot import next_unnamed_path, write_session_snapshot
from cleave.effects.runtime import EffectRuntime
from cleave.config_schema import DEFAULT_STEM_FOR_SLOT, LAYER_SLOTS
from cleave.extract import STEM_NAMES, STEM_SOURCES
from cleave.paths import repo_root
from cleave.preset_playlist import PresetPlaylist
from cleave.signals import Signals
from cleave.viz.controls import TuningControls
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.modal import ModalHost
from cleave.viz.session import TuningSession
from cleave.viz.timeline_controls import TimelineControls
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import LayerFramePipeline, apply_effect_modifiers
from cleave.viz.layer_visibility import apply_layer_visibility, effective_layer_enabled
from cleave.viz.mix_player import MixPlayer
from cleave.stem_pcm import StemPcmBank
from cleave.viz.playback import current_sec, seek


def _solo_audio_source(session: TuningSession) -> str | None:
    if session.solo_slot is None:
        return None
    return session.layers[session.solo_slot].stem


def _stub_cfg_for_session(
    session: TuningSession,
    preset_root: Path,
    project_dir: Path,
) -> CleaveConfig:
    return CleaveConfig(
        paths=PathsConfig(preset_root=preset_root, texture_paths=()),
        layers={
            slot: LayerConfig(
                preset=preset_root / slot / "stub.milk",
                stem=DEFAULT_STEM_FOR_SLOT[slot],
            )
            for slot in LAYER_SLOTS
        },
        visualizer=VisualizerConfig(),
        config_path=project_dir / VIZ_CONFIG_FILENAME,
        layer_z_order=tuple(session.layer_z_order),
    )


def make_tuning_controls(
    *,
    session: TuningSession,
    cfg: CleaveConfig | None,
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
) -> TuningControls:
    def on_preset_change(stem: str, playlist: PresetPlaylist) -> None:
        layer = layers_by_slot[stem]
        layer.playlist = playlist
        if playlist.current is not None:
            playlist.load_into(layer.pm, smooth=False)
            layer.pm.lock_preset(True)

    def on_blend_change(stem: str, blend_mode) -> None:
        layers_by_slot[stem].fbo.blend_mode = blend_mode

    def on_stem_change(slot: str, stem) -> None:
        layers_by_slot[slot].stem = stem
        LayerFramePipeline.flush_pcm(layers)
        if mix_player is not None and session.solo_slot == slot:
            mix_player.set_solo_stem(_solo_audio_source(session))
        apply_effect_modifiers(
            session,
            layers_by_slot,
            effect_runtime,
            signals,
            current_sec(playback, duration_sec),
            update=False,
        )

    def on_opacity_change(stem: str, pct: int) -> None:
        apply_effect_modifiers(
            session,
            layers_by_slot,
            effect_runtime,
            signals,
            current_sec(playback, duration_sec),
            update=False,
        )

    def on_layer_enabled_change(stem: str, enabled: bool) -> None:
        t_sec = current_sec(playback, duration_sec)
        apply_layer_visibility(session, layers_by_slot, t_sec)
        LayerFramePipeline.flush_pcm(layers)
        if effective_layer_enabled(session, stem, t_sec):
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
            mix_player.set_solo_stem(_solo_audio_source(session))
        LayerFramePipeline.flush_pcm(layers)
        apply_effect_modifiers(
            session,
            layers_by_slot,
            effect_runtime,
            signals,
            current_sec(playback, duration_sec),
            update=False,
        )

    def on_beat_change(stem: str, beat: float) -> None:
        layers_by_slot[stem].pm.set_beat_sensitivity(beat)

    def on_seek(delta_sec: float) -> None:
        seek(playback, delta_sec, duration_sec)
        LayerFramePipeline.flush_pcm(layers)

    layer_bindings = LiveLayerBindings(
        on_preset_change=on_preset_change,
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
        "cfg": cfg if cfg is not None else _stub_cfg_for_session(
            session, preset_root, project_dir
        ),
        "preset_root": preset_root,
        "playback": playback,
        "duration_sec": duration_sec,
        "layer_bindings": layer_bindings,
    }
    if modal_host is not None:
        kwargs["modal_host"] = modal_host

    if cfg is not None:
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
    if pcm_bank is not None and mix_player is not None:
        mix_player.set_stem_pcm(
            {stem: pcm_bank.mono_pcm(stem) for stem in STEM_SOURCES}
        )
        apply_layer_visibility(
            session,
            layers_by_slot,
            current_sec(playback, duration_sec),
        )
        mix_player.set_solo_stem(_solo_audio_source(session))
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
    on_toast: Callable[[str], None] | None = None,
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
            session.timeline.submenu_focused = False

    def on_exit_submenu() -> None:
        if tuning_controls is not None:
            tuning_controls.exit_timeline_submenu()
        else:
            session.timeline.submenu_focused = False

    def on_seek(delta_sec: float) -> None:
        seek(playback, delta_sec, duration_sec)
        LayerFramePipeline.flush_pcm(layers)

    return TimelineControls(
        session,
        playback,
        duration_sec,
        on_visibility_change=on_visibility_change,
        on_close=on_close,
        on_exit_submenu=on_exit_submenu,
        on_seek=on_seek,
        on_toast=on_toast,
    )
