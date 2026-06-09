"""Wire tuning controls to live layer state."""

from __future__ import annotations

from pathlib import Path

from cleave.config import DEFAULT_VIZ_CONFIG_FILENAME, CleaveConfig
from cleave.config_snapshot import next_unnamed_path, write_session_snapshot
from cleave.effects.runtime import EffectRuntime
from cleave.paths import repo_root
from cleave.preset_playlist import PresetPlaylist
from cleave.signals import Signals
from cleave.viz.controls import TuningControls, TuningSession
from cleave.viz.layer import (
    StemLayer,
    _flush_all_pcm,
    apply_effect_modifiers,
    apply_layer_visibility,
    effective_layer_enabled,
)
from cleave.viz.mix_player import MixPlayer
from cleave.stem_pcm import StemPcmBank
from cleave.viz.playback import current_sec, seek


def make_tuning_controls(
    *,
    session: TuningSession,
    cfg: CleaveConfig | None,
    preset_root: Path,
    project_dir: Path,
    layers_by_name: dict[str, StemLayer],
    layers: list[StemLayer],
    playback,
    duration_sec: float,
    signals: Signals | None,
    effect_runtime: EffectRuntime,
    pcm_bank: StemPcmBank | None = None,
    mix_player: MixPlayer | None = None,
) -> TuningControls:
    def on_preset_change(stem: str, playlist: PresetPlaylist) -> None:
        layer = layers_by_name[stem]
        layer.playlist = playlist
        if playlist.current is not None:
            playlist.load_into(layer.pm, smooth=False)
            layer.pm.lock_preset(True)

    def on_blend_change(stem: str, blend_mode) -> None:
        layers_by_name[stem].fbo.blend_mode = blend_mode

    def on_opacity_change(stem: str, pct: int) -> None:
        apply_effect_modifiers(
            session,
            layers_by_name,
            effect_runtime,
            signals,
            current_sec(playback, duration_sec),
            update=False,
        )

    def on_layer_enabled_change(stem: str, enabled: bool) -> None:
        apply_layer_visibility(session, layers_by_name)
        if effective_layer_enabled(session, stem):
            apply_effect_modifiers(
                session,
                layers_by_name,
                effect_runtime,
                signals,
                current_sec(playback, duration_sec),
                update=False,
            )

    def on_solo_change() -> None:
        apply_layer_visibility(session, layers_by_name)
        if mix_player is not None:
            mix_player.set_solo_stem(session.solo_stem)
        apply_effect_modifiers(
            session,
            layers_by_name,
            effect_runtime,
            signals,
            current_sec(playback, duration_sec),
            update=False,
        )

    def on_beat_change(stem: str, beat: float) -> None:
        layers_by_name[stem].pm.set_beat_sensitivity(beat)

    def on_seek(delta_sec: float) -> None:
        seek(playback, delta_sec, duration_sec)
        _flush_all_pcm(layers)

    kwargs: dict = {
        "session": session,
        "preset_root": preset_root,
        "playback": playback,
        "duration_sec": duration_sec,
        "on_preset_change": on_preset_change,
        "on_blend_change": on_blend_change,
        "on_opacity_change": on_opacity_change,
        "on_layer_enabled_change": on_layer_enabled_change,
        "on_solo_change": on_solo_change,
        "on_beat_change": on_beat_change,
        "on_seek": on_seek,
    }

    if cfg is not None:
        def on_save_new_config() -> Path:
            out_path = next_unnamed_path(project_dir)
            write_session_snapshot(out_path, cfg=cfg, session=session)
            return out_path

        def on_overwrite_config(path: Path) -> str:
            write_session_snapshot(path, cfg=cfg, session=session)
            return path.name

        kwargs.update(
            on_z_order_change=lambda _order: None,
            on_save_new_config=on_save_new_config,
            on_overwrite_config=on_overwrite_config,
            launch_config_path=cfg.config_path,
            repo_root_example=repo_root() / DEFAULT_VIZ_CONFIG_FILENAME,
        )

    controls = TuningControls(**kwargs)
    if pcm_bank is not None and mix_player is not None:
        mix_player.set_stem_pcm(
            {stem: pcm_bank.mono_pcm(stem) for stem in session.layer_z_order}
        )
        apply_layer_visibility(session, layers_by_name)
        mix_player.set_solo_stem(session.solo_stem)
    return controls
