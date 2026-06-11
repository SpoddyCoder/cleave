"""Visualizer main loop and runtime."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from cleave.config import CleaveConfig, RenderOverlayConfig
from cleave.effects.runtime import EffectRuntime
from cleave.gl_compositor import GlCompositor
from cleave.gl_post_process import GlPostProcess
from cleave.preset_playlist import PresetPlaylist
from cleave.signals import Signals
from cleave.pcm_io import load_mix_pcm
from cleave.stem_pcm import StemPcmBank, load_stem_pcm, samples_per_frame
from cleave.viz.bootstrap import load_stem_signals
from cleave.viz.controls import TuningControls, TuningSession
from cleave.viz.mix_player import MixPlayer
from cleave.viz.layer import (
    StemLayer,
    _apply_layer_bloom,
    _apply_layer_grit,
    _build_layers,
    _composite_ordered,
    _destroy_layers,
    _draw_tuning_overlay,
    _flush_all_pcm,
    _render_layer_fbo,
    _session_from_cfg,
    apply_effect_modifiers,
)
from cleave.viz.overlay import TuningOverlay
from cleave.viz.playback import PlaybackState, current_sec, init_playback
from cleave.viz.render_overlay import (
    build_live_overlay_config,
    build_panel_surface,
    composite_render_overlay_with_alpha,
    default_render_overlay_config,
    live_overlay_alpha,
    panel_surface_key,
)
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
    playlists: dict[str, PresetPlaylist] = field(default_factory=dict)
    layers: list[StemLayer] = field(default_factory=list)
    layers_by_name: dict[str, StemLayer] = field(default_factory=dict)
    compositor: GlCompositor | None = None
    post_process: GlPostProcess | None = None
    controls: TuningControls | None = None
    overlay: TuningOverlay | None = None
    overlay_surface: pygame.Surface | None = None
    render_overlay_panel: pygame.Surface | None = None
    render_overlay_panel_key: tuple | None = None
    mix_player: MixPlayer | None = None
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
        playlists=playlists,
    )


def _init_gl_resources(runtime: VisualizerRuntime) -> None:
    compositor = GlCompositor(runtime.width, runtime.height)
    compositor.init()
    post_process = GlPostProcess()
    post_process.init()

    assert runtime.cfg is not None
    layers = _build_layers(runtime.cfg, compositor, runtime.playlists)

    layers_by_name = {layer.name: layer for layer in layers}
    mix_pcm, sample_rate = load_mix_pcm(runtime.audio_path)
    mix_player = MixPlayer(mix_pcm, sample_rate)
    runtime.mix_player = mix_player
    playback = init_playback(mix_player)
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
        pcm_bank=runtime.pcm_bank,
        mix_player=mix_player,
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


def _init_gl_resources_render(runtime: VisualizerRuntime) -> None:
    compositor = GlCompositor(runtime.width, runtime.height)
    compositor.init()
    post_process = GlPostProcess()
    post_process.init()

    assert runtime.cfg is not None
    layers = _build_layers(runtime.cfg, compositor, runtime.playlists)
    layers_by_name = {layer.name: layer for layer in layers}

    runtime.compositor = compositor
    runtime.post_process = post_process
    runtime.layers = layers
    runtime.layers_by_name = layers_by_name


def _ensure_render_overlay_panel(
    runtime: VisualizerRuntime, cfg: RenderOverlayConfig
) -> pygame.Surface:
    key = panel_surface_key(cfg)
    if (
        runtime.render_overlay_panel is not None
        and runtime.render_overlay_panel_key == key
    ):
        return runtime.render_overlay_panel
    runtime.render_overlay_panel = build_panel_surface(cfg)
    runtime.render_overlay_panel_key = key
    return runtime.render_overlay_panel


def _composite_live_render_overlay(runtime: VisualizerRuntime, t_sec: float) -> None:
    assert runtime.compositor is not None
    assert runtime.cfg is not None
    base = (
        runtime.cfg.render
        if runtime.cfg.render is not None
        else default_render_overlay_config()
    )
    cfg = build_live_overlay_config(base, runtime.session.render_overlay)
    alpha = live_overlay_alpha(
        t_sec,
        cfg,
        enabled=runtime.session.render_overlay.enabled,
        solo=runtime.session.render_overlay_solo,
    )
    if alpha <= 0.01:
        return
    panel = _ensure_render_overlay_panel(runtime, cfg)
    composite_render_overlay_with_alpha(
        runtime.compositor,
        cfg,
        alpha,
        runtime.width,
        runtime.height,
        panel=panel,
    )


class VisualizerApp:
    def __init__(self, runtime: VisualizerRuntime) -> None:
        self._runtime = runtime
        self._overlay_dt = 0.0
        self._was_paused: bool | None = None

    def tick_frame(
        self, t_sec: float, *, paused: bool, draw_overlay: bool = True
    ) -> None:
        rt = self._runtime
        assert rt.compositor is not None
        assert rt.post_process is not None
        if draw_overlay:
            assert rt.controls is not None
            assert rt.overlay is not None
            assert rt.overlay_surface is not None

        if self._was_paused is not None and paused != self._was_paused:
            _flush_all_pcm(rt.layers)
        self._was_paused = paused

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

        if draw_overlay:
            _composite_live_render_overlay(rt, t_sec)
            view_state = rt.controls.build_view_state(
                paused=paused,
                position_sec=t_sec,
            )
            rt.overlay.update(self._overlay_dt)
            _draw_tuning_overlay(
                rt.compositor, rt.overlay, rt.overlay_surface, view_state
            )

    def run(self) -> None:
        rt = self._runtime

        pygame.init()

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
            assert rt.mix_player is not None
            rt.mix_player.start()

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

        finally:
            _destroy_layers(rt.layers)
            if rt.compositor is not None:
                rt.compositor.destroy()
            if rt.post_process is not None:
                rt.post_process.destroy()
            if rt.mix_player is not None:
                rt.mix_player.stop()
            pygame.quit()
