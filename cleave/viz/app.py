"""Visualizer main loop and runtime."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from cleave.config import CleaveConfig
from cleave.effects.runtime import EffectRuntime
from cleave.gl_compositor import GlCompositor
from cleave.gl_post_process import GlPostProcess
from cleave.preset_playlist import PresetPlaylist
from cleave.signals import Signals
from cleave.pcm_io import load_mix_pcm
from cleave.stem_pcm import StemPcmBank, load_stem_pcm, samples_per_frame
from cleave.viz.bootstrap import load_stem_signals
from cleave.viz.controls import TuningControls
from cleave.viz.session import TimelineRuntime, TuningSession, session_from_cfg
from cleave.viz.mix_player import MixPlayer
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import LayerFramePipeline
from cleave.viz.layer_visibility import apply_layer_visibility, build_timeline_view_state
from cleave.viz.overlay_draw import OverlayDrawer
from cleave.viz.loading import draw_loading_screen
from cleave.viz.help_overlay import HelpOverlay
from cleave.viz.overlay import TuningOverlay
from cleave.viz.timeline_controls import TimelineControls
from cleave.viz.timeline_overlay import TimelineOverlay
from cleave.viz.playback import PlaybackState, current_sec, init_playback
from cleave.viz.frame_finish import RenderOverlayPanelCache, finish_content_frame
from cleave.viz.input_dispatch import (
    dispatch_keydown,
    dispatch_keyup,
    dispatch_should_notify_overlay,
    key_handler_for_runtime,
)
from cleave.viz.wiring import make_timeline_controls, make_tuning_controls


@dataclass
class VisualizerSeed:
    """Pre-GL runtime state produced by build_runtime_base."""

    project_dir: Path
    audio_path: Path
    width: int
    height: int
    upscale: float
    display_width: int
    display_height: int
    fps: int
    window_title: str
    session: TuningSession
    cfg: CleaveConfig
    pcm_bank: StemPcmBank
    duration_sec: float
    n_pcm: int
    signals: Signals | None
    effect_runtime: EffectRuntime
    preset_root: Path
    playlists: dict[str, PresetPlaylist] = field(default_factory=dict)


@dataclass
class VisualizerCore:
    """GL-initialized state shared by live and offline render paths."""

    seed: VisualizerSeed
    layers: list[StemLayer]
    layers_by_name: dict[str, StemLayer]
    compositor: GlCompositor
    post_process: GlPostProcess


@dataclass
class LiveVisualizerRuntime(VisualizerCore):
    """Fully initialized live visualizer runtime."""

    controls: TuningControls
    timeline_controls: TimelineControls
    mix_player: MixPlayer
    playback: PlaybackState
    overlay: TuningOverlay
    help_overlay: HelpOverlay
    timeline_overlay: TimelineOverlay
    overlay_surface: pygame.Surface
    render_overlay_panel_cache: RenderOverlayPanelCache = field(
        default_factory=RenderOverlayPanelCache
    )


@dataclass
class RenderVisualizerRuntime(VisualizerCore):
    """Fully initialized offline render runtime."""


def build_runtime_base(
    cfg: CleaveConfig,
    project_dir: Path,
    audio_path: Path,
    playlists: dict[str, PresetPlaylist],
) -> VisualizerSeed:
    pcm_bank = load_stem_pcm(project_dir)
    fps = cfg.visualizer.fps
    return VisualizerSeed(
        project_dir=project_dir,
        audio_path=audio_path,
        width=cfg.visualizer.width,
        height=cfg.visualizer.height,
        upscale=cfg.visualizer.upscale,
        display_width=cfg.visualizer.display_width,
        display_height=cfg.visualizer.display_height,
        fps=fps,
        window_title=f"Cleave — {project_dir.name}",
        session=session_from_cfg(cfg, playlists),
        cfg=cfg,
        pcm_bank=pcm_bank,
        duration_sec=pcm_bank.duration_sec,
        n_pcm=samples_per_frame(fps),
        signals=load_stem_signals(project_dir),
        effect_runtime=EffectRuntime(),
        preset_root=cfg.paths.preset_root,
        playlists=playlists,
    )


def _make_compositor(seed: VisualizerSeed) -> GlCompositor:
    c = GlCompositor(
        seed.width,
        seed.height,
        display_width=seed.display_width,
        display_height=seed.display_height,
    )
    c.init()
    return c


def _init_compositor_and_post(
    seed: VisualizerSeed,
) -> tuple[GlCompositor, GlPostProcess]:
    compositor = _make_compositor(seed)
    post_process = GlPostProcess()
    post_process.init()
    return compositor, post_process


def _init_gl_resources_cheap(seed: VisualizerSeed) -> tuple[GlCompositor, GlPostProcess, pygame.Surface]:
    compositor, post_process = _init_compositor_and_post(seed)
    overlay_surface = pygame.Surface(
        (seed.display_width, seed.display_height), pygame.SRCALPHA
    )
    return compositor, post_process, overlay_surface


def _init_gl_resources_heavy(
    seed: VisualizerSeed,
    compositor: GlCompositor,
    post_process: GlPostProcess,
    overlay_surface: pygame.Surface,
    on_progress: Callable[[str], None] | None = None,
) -> LiveVisualizerRuntime:
    def report(message: str) -> None:
        if on_progress is not None:
            on_progress(message)

    report("Building layers...")
    layers, layers_by_name = LayerFramePipeline.build(
        seed.cfg, compositor, seed.playlists
    )

    mix_pcm, sample_rate = load_mix_pcm(seed.audio_path)
    mix_player = MixPlayer(mix_pcm, sample_rate)
    playback = init_playback(mix_player)

    controls = make_tuning_controls(
        session=seed.session,
        cfg=seed.cfg,
        preset_root=seed.preset_root,
        project_dir=seed.project_dir,
        layers_by_name=layers_by_name,
        layers=layers,
        playback=playback,
        duration_sec=seed.duration_sec,
        signals=seed.signals,
        effect_runtime=seed.effect_runtime,
        pcm_bank=seed.pcm_bank,
        mix_player=mix_player,
    )
    timeline_controls = make_timeline_controls(
        session=seed.session,
        playback=playback,
        duration_sec=seed.duration_sec,
        layers_by_name=layers_by_name,
        layers=layers,
        signals=seed.signals,
        effect_runtime=seed.effect_runtime,
        mix_player=mix_player,
        on_toast=controls.show_toast,
        tuning_controls=controls,
    )

    return LiveVisualizerRuntime(
        seed=seed,
        layers=layers,
        layers_by_name=layers_by_name,
        compositor=compositor,
        post_process=post_process,
        controls=controls,
        timeline_controls=timeline_controls,
        mix_player=mix_player,
        playback=playback,
        overlay=TuningOverlay(),
        help_overlay=HelpOverlay(),
        timeline_overlay=TimelineOverlay(),
        overlay_surface=overlay_surface,
    )


def _init_gl_resources_render(seed: VisualizerSeed) -> RenderVisualizerRuntime:
    compositor, post_process = _init_compositor_and_post(seed)
    layers, layers_by_name = LayerFramePipeline.build(
        seed.cfg, compositor, seed.playlists
    )

    return RenderVisualizerRuntime(
        seed=seed,
        layers=layers,
        layers_by_name=layers_by_name,
        compositor=compositor,
        post_process=post_process,
    )


def _timeline_strip_visible(tl: TimelineRuntime, *, overlay_visibility: float) -> bool:
    """Show the bottom timeline strip while the main panel is visible or a row is focused."""
    return tl.enabled and tl.panel_open and (
        tl.submenu_focused or overlay_visibility > 0.01
    )


def _timeline_strip_fade(tl: TimelineRuntime, *, overlay_visibility: float) -> float:
    if tl.submenu_focused:
        return 1.0
    return overlay_visibility


def tick_frame_core(
    runtime: VisualizerCore,
    t_sec: float,
    *,
    paused: bool,
    was_paused: bool | None,
) -> bool | None:
    """Shared frame tick for live and render. Returns updated was_paused."""
    if was_paused is not None and paused != was_paused:
        LayerFramePipeline.flush_pcm(runtime.layers)
    was_paused = paused

    apply_layer_visibility(runtime.seed.session, runtime.layers_by_name, t_sec)

    LayerFramePipeline.render_frame(
        runtime.seed.session,
        runtime.layers,
        runtime.layers_by_name,
        runtime.seed.pcm_bank,
        runtime.seed.n_pcm,
        runtime.post_process,
        runtime.seed.effect_runtime,
        runtime.seed.signals,
        t_sec,
        paused=paused,
    )

    LayerFramePipeline.composite(
        runtime.compositor, runtime.layers_by_name, runtime.seed.session
    )
    return was_paused


def _tick_frame_live_overlay(
    runtime: LiveVisualizerRuntime,
    t_sec: float,
    *,
    paused: bool,
    overlay_dt: float,
) -> None:
    finish_content_frame(
        runtime,
        t_sec,
        post_fx_solo=runtime.seed.session.render_post_fx_solo,
        overlay_solo=runtime.seed.session.render_overlay_solo,
        panel_cache=runtime.render_overlay_panel_cache,
    )
    view_state = runtime.controls.build_view_state(
        paused=paused,
        position_sec=t_sec,
    )
    tl = runtime.seed.session.timeline
    runtime.overlay.update(overlay_dt)
    overlay_visibility = runtime.overlay.visibility
    timeline_strip_visible = _timeline_strip_visible(
        tl, overlay_visibility=overlay_visibility
    )
    timeline_panel_open = tl.enabled and tl.panel_open and overlay_visibility > 0.01
    OverlayDrawer.draw_tuning(
        runtime.compositor,
        runtime.overlay,
        runtime.overlay_surface,
        view_state,
        timeline_panel_open=timeline_panel_open,
        help_overlay=runtime.help_overlay,
    )

    if timeline_strip_visible:
        timeline_state = build_timeline_view_state(
            runtime.seed.session, t_sec, runtime.seed.duration_sec
        )
        OverlayDrawer.draw_timeline(
            runtime.compositor,
            runtime.timeline_overlay,
            runtime.overlay_surface,
            timeline_state,
            runtime.seed.height,
            visibility=_timeline_strip_fade(tl, overlay_visibility=overlay_visibility),
        )


class VisualizerApp:
    def __init__(self, runtime: VisualizerSeed | VisualizerCore) -> None:
        self._runtime = runtime
        self._overlay_dt = 0.0
        self._was_paused: bool | None = None

    def tick_frame(
        self, t_sec: float, *, paused: bool, draw_overlay: bool = True
    ) -> None:
        self._was_paused = tick_frame_core(
            self._runtime,
            t_sec,
            paused=paused,
            was_paused=self._was_paused,
        )
        if draw_overlay:
            if not isinstance(self._runtime, LiveVisualizerRuntime):
                raise TypeError(
                    "draw_overlay=True requires LiveVisualizerRuntime"
                )
            _tick_frame_live_overlay(
                self._runtime,
                t_sec,
                paused=paused,
                overlay_dt=self._overlay_dt,
            )

    def run(self) -> None:
        if not isinstance(self._runtime, VisualizerSeed):
            raise TypeError("run() requires a VisualizerSeed from build_runtime_base()")

        seed = self._runtime

        pygame.init()

        try:
            pygame.display.set_mode(
                (seed.display_width, seed.display_height), pygame.OPENGL | pygame.DOUBLEBUF
            )
        except pygame.error as exc:
            print(f"error: failed to open OpenGL window: {exc}", file=sys.stderr)
            pygame.quit()
            sys.exit(1)

        pygame.display.set_caption(seed.window_title)
        clock = pygame.time.Clock()

        rt: LiveVisualizerRuntime | None = None
        try:
            compositor, post_process, overlay_surface = _init_gl_resources_cheap(seed)
            draw_loading_screen(
                compositor, "Loading...", seed.display_width, seed.display_height
            )

            quit_during_load = False

            def on_progress(message: str) -> None:
                nonlocal quit_during_load
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        quit_during_load = True
                        return
                draw_loading_screen(
                    compositor, message, seed.display_width, seed.display_height
                )

            rt = _init_gl_resources_heavy(
                seed, compositor, post_process, overlay_surface, on_progress=on_progress
            )
            self._runtime = rt
            if quit_during_load:
                return

            warmup_frames = round(seed.cfg.visualizer.warmup_sec * seed.fps)
            if warmup_frames > 0:
                draw_loading_screen(
                    rt.compositor,
                    "Warming up Milkdrop presets...",
                    seed.display_width,
                    seed.display_height,
                )
                LayerFramePipeline.warmup(
                    rt.layers,
                    rt.seed.pcm_bank,
                    0.0,
                    warmup_frames,
                    rt.seed.fps,
                    rt.seed.n_pcm,
                    session=rt.seed.session,
                )

            self.tick_frame(0.0, paused=False)
            pygame.display.flip()
            rt.mix_player.start()

            running = True
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        if rt.controls.try_quit():
                            running = False
                        else:
                            rt.overlay.notify_input()
                    elif event.type == pygame.KEYDOWN:
                        tl = rt.seed.session.timeline
                        if dispatch_keydown(event, rt) is False:
                            running = False
                        else:
                            if (
                                key_handler_for_runtime(rt, event.key) is rt.controls
                                and event.key == pygame.K_t
                                and tl.panel_open
                            ):
                                rt.timeline_controls.focused_cue_index = None
                            if rt.controls.consume_hide_overlay():
                                rt.overlay.hide_immediately()
                                tl.submenu_focused = False
                            elif dispatch_should_notify_overlay(event, rt):
                                rt.overlay.notify_input()
                    elif event.type == pygame.KEYUP:
                        dispatch_keyup(event, rt)

                if rt.controls.consume_pending_exit():
                    running = False

                self._overlay_dt = clock.tick(rt.seed.fps) / 1000.0
                rt.controls.tick(self._overlay_dt)
                if rt.controls.key_repeat_armed:
                    rt.overlay.notify_input()

                t_sec = current_sec(rt.playback, rt.seed.duration_sec)
                self.tick_frame(t_sec, paused=rt.playback.paused)

                pygame.display.flip()

        finally:
            if rt is not None:
                LayerFramePipeline.destroy(rt.layers)
                rt.compositor.destroy()
                rt.post_process.destroy()
                rt.mix_player.stop()
            pygame.quit()
