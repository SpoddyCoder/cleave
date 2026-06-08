"""Visualizer main loop and runtime."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pygame

from cleave.config import CleaveConfig, load_config
from cleave.effects.runtime import EffectRuntime
from cleave.gl_compositor import GlCompositor
from cleave.gl_post_process import GlPostProcess
from cleave.paths import repo_root
from cleave.preset_playlist import PresetPlaylist
from cleave.signals import Signals
from cleave.stem_pcm import StemPcmBank, load_stem_pcm, samples_per_frame
from cleave.viz.bootstrap import STEM_DRUMS, load_stem_signals
from cleave.viz.controls import TuningControls, TuningSession
from cleave.viz.layer import (
    StemLayer,
    _apply_layer_bloom,
    _apply_layer_grit,
    _build_drums_layer,
    _build_layers,
    _composite_ordered,
    _destroy_layers,
    _draw_tuning_overlay,
    _render_layer_fbo,
    _session_for_drums,
    _session_from_cfg,
    apply_effect_modifiers,
)
from cleave.viz.overlay import TuningOverlay
from cleave.viz.playback import PlaybackState, current_sec, init_playback
from cleave.viz.wiring import make_tuning_controls


@dataclass
class VisualizerRuntime:
    project_dir: Path
    audio_path: Path
    width: int
    height: int
    fps: int
    window_title: str
    session: TuningSession
    cfg: CleaveConfig | None
    pcm_bank: StemPcmBank
    duration_sec: float
    n_pcm: int
    signals: Signals | None
    effect_runtime: EffectRuntime
    preset_root: Path
    mode: Literal["full", "drums"] = "full"
    playlists: dict[str, PresetPlaylist] = field(default_factory=dict)
    drums_playlist: PresetPlaylist | None = None
    drums_texture_paths: list[Path] = field(default_factory=list)
    drums_beat_sensitivity: float = 1.0
    drums_preset_anchor: Path | None = None
    layers: list[StemLayer] = field(default_factory=list)
    layers_by_name: dict[str, StemLayer] = field(default_factory=dict)
    compositor: GlCompositor | None = None
    post_process: GlPostProcess | None = None
    controls: TuningControls | None = None
    overlay: TuningOverlay | None = None
    overlay_surface: pygame.Surface | None = None
    playback: PlaybackState | None = None


def build_runtime_full(
    cfg: CleaveConfig,
    project_dir: Path,
    audio_path: Path,
    playlists: dict[str, PresetPlaylist],
) -> VisualizerRuntime:
    pcm_bank = load_stem_pcm(project_dir)
    fps = cfg.visualizer.fps
    return VisualizerRuntime(
        project_dir=project_dir,
        audio_path=audio_path,
        width=cfg.visualizer.width,
        height=cfg.visualizer.height,
        fps=fps,
        window_title=f"Cleave — {project_dir.name}",
        session=_session_from_cfg(cfg, playlists),
        cfg=cfg,
        pcm_bank=pcm_bank,
        duration_sec=pcm_bank.duration_sec,
        n_pcm=samples_per_frame(fps),
        signals=load_stem_signals(project_dir),
        effect_runtime=EffectRuntime(),
        preset_root=cfg.paths.preset_root,
        mode="full",
        playlists=playlists,
    )


def build_runtime_drums_only(
    project_dir: Path,
    audio_path: Path,
    playlist: PresetPlaylist,
    texture_paths: list[Path],
    beat_sensitivity: float,
    config_path: Path | None,
    preset_root: Path,
    preset_anchor: Path,
    width: int,
    height: int,
    fps: int,
) -> VisualizerRuntime:
    cfg: CleaveConfig | None = None
    try:
        cfg = load_config(config_path, repo_root())
    except (FileNotFoundError, ValueError):
        pass

    pcm_bank = load_stem_pcm(project_dir)
    drums_cfg = cfg.layers[STEM_DRUMS] if cfg is not None else None
    return VisualizerRuntime(
        project_dir=project_dir,
        audio_path=audio_path,
        width=width,
        height=height,
        fps=fps,
        window_title=f"Cleave (drums) — {project_dir.name}",
        session=_session_for_drums(
            playlist,
            preset_anchor,
            preset_root,
            beat_sensitivity,
            drums_cfg,
        ),
        cfg=cfg,
        pcm_bank=pcm_bank,
        duration_sec=pcm_bank.duration_sec,
        n_pcm=samples_per_frame(fps),
        signals=load_stem_signals(project_dir),
        effect_runtime=EffectRuntime(),
        preset_root=preset_root,
        mode="drums",
        drums_playlist=playlist,
        drums_texture_paths=texture_paths,
        drums_beat_sensitivity=beat_sensitivity,
        drums_preset_anchor=preset_anchor,
    )


def _init_gl_resources(runtime: VisualizerRuntime) -> None:
    compositor = GlCompositor(runtime.width, runtime.height)
    compositor.init()
    post_process = GlPostProcess()
    post_process.init()

    if runtime.mode == "full":
        assert runtime.cfg is not None
        layers = _build_layers(runtime.cfg, compositor, runtime.playlists)
    else:
        assert runtime.drums_playlist is not None
        layers = [
            _build_drums_layer(
                compositor,
                runtime.drums_playlist,
                runtime.drums_texture_paths,
                runtime.drums_beat_sensitivity,
                runtime.width,
                runtime.height,
                runtime.fps,
            )
        ]

    layers_by_name = {layer.name: layer for layer in layers}
    playback = init_playback()
    controls = make_tuning_controls(
        session=runtime.session,
        cfg=runtime.cfg,
        preset_root=runtime.preset_root,
        project_dir=runtime.project_dir,
        layers_by_name=layers_by_name,
        layers=layers,
        playback=playback,
        duration_sec=runtime.duration_sec,
        signals=runtime.signals,
        effect_runtime=runtime.effect_runtime,
    )

    runtime.compositor = compositor
    runtime.post_process = post_process
    runtime.layers = layers
    runtime.layers_by_name = layers_by_name
    runtime.controls = controls
    runtime.overlay = TuningOverlay()
    runtime.overlay_surface = pygame.Surface(
        (runtime.width, runtime.height), pygame.SRCALPHA
    )
    runtime.playback = playback


class VisualizerApp:
    def __init__(self, runtime: VisualizerRuntime) -> None:
        self._runtime = runtime
        self._overlay_dt = 0.0

    def tick_frame(self, t_sec: float, *, paused: bool) -> None:
        rt = self._runtime
        assert rt.compositor is not None
        assert rt.post_process is not None
        assert rt.controls is not None
        assert rt.overlay is not None
        assert rt.overlay_surface is not None

        if not paused:
            for layer in rt.layers:
                if not layer.fbo.enabled:
                    continue
                pcm = rt.pcm_bank.slice_pcm(layer.name, t_sec, rt.n_pcm)
                layer.pm.feed_pcm(pcm)
                layer.pm.set_frame_time(t_sec)

        apply_effect_modifiers(
            rt.session,
            rt.layers_by_name,
            rt.effect_runtime,
            rt.signals,
            t_sec,
        )

        if not paused:
            for layer in rt.layers:
                if layer.fbo.enabled:
                    _render_layer_fbo(layer, layer.pm)
                    _apply_layer_bloom(layer, rt.post_process)
                    _apply_layer_grit(layer, rt.post_process)

        _composite_ordered(rt.compositor, rt.layers_by_name, rt.session)

        view_state = rt.controls.build_view_state(
            paused=paused,
            position_sec=t_sec,
        )
        rt.overlay.update(self._overlay_dt)
        _draw_tuning_overlay(rt.compositor, rt.overlay, rt.overlay_surface, view_state)

    def run(self) -> None:
        rt = self._runtime

        pygame.init()
        pygame.mixer.init()

        try:
            pygame.display.set_mode(
                (rt.width, rt.height), pygame.OPENGL | pygame.DOUBLEBUF
            )
        except pygame.error as exc:
            print(f"error: failed to open OpenGL window: {exc}", file=sys.stderr)
            pygame.quit()
            sys.exit(1)

        pygame.display.set_caption(rt.window_title)
        clock = pygame.time.Clock()

        try:
            _init_gl_resources(rt)
            assert rt.controls is not None
            assert rt.playback is not None

            pygame.mixer.music.load(str(rt.audio_path))
            pygame.mixer.music.play()

            running = True
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN:
                        if rt.controls.handle_keydown(event) is False:
                            running = False
                        else:
                            assert rt.overlay is not None
                            rt.overlay.notify_input()
                    elif event.type == pygame.KEYUP:
                        rt.controls.handle_keyup(event)

                self._overlay_dt = clock.tick(rt.fps) / 1000.0
                rt.controls.tick(self._overlay_dt)

                t_sec = current_sec(rt.playback, rt.duration_sec)
                self.tick_frame(t_sec, paused=rt.playback.paused)

                pygame.display.flip()

                if not rt.playback.paused and not pygame.mixer.music.get_busy():
                    if t_sec >= rt.duration_sec - 0.05:
                        running = False

        finally:
            _destroy_layers(rt.layers)
            if rt.compositor is not None:
                rt.compositor.destroy()
            if rt.post_process is not None:
                rt.post_process.destroy()
            pygame.mixer.music.stop()
            pygame.quit()
