"""Visualizer main loop and runtime."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from cleave.config import (
    CleaveConfig,
    missing_preset_anchor_notification,
    render_fps,
    project_resolution,
)
from cleave.user_config import persist_editor_settings
from cleave.effects.runtime import EffectRuntime
from cleave.gl_color_format import GlColorFormat, resolve_live_compositor_format
from cleave.gl_compositor import GlCompositor
from cleave.layer_composite import LayerCompositeRequest
from cleave.gl_masked_compositor import GlMaskedCompositor
from cleave.gl_post_process import GlPostProcess
from cleave.preset_library import PresetLibrary
from cleave.preset_playlist import PresetPlaylist
from cleave.signals import Signals
from cleave.pcm_io import load_mix_pcm
from cleave.stem_pcm import StemPcmBank, load_stem_pcm, LIVE_PROJECTM_FPS
from cleave.open_target import OpenTarget
from cleave.paths import themes_dir
from cleave.project import load_manifest
from cleave.viz.bootstrap import load_stem_signals
from cleave.viz.controls import TuningControls
from cleave.viz.session import TuningSession, session_from_cfg
from cleave.viz.mix_player import MixPlayer
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import LayerFramePipeline
from cleave.viz.layer_visibility import apply_layer_visibility, build_timeline_view_state
from cleave.viz.preset_switching import advance_timeline_preset_switching
from cleave.viz.modal import ModalHost
from cleave.viz.overlay_draw import OverlayDrawer
from cleave.viz.loading import LoadingWindow, open_loading_window
from cleave.viz.theme import palette_for_theme, set_palette, set_ui_scale_percent
from cleave.viz.user_themes import install_user_themes
from cleave.viz.tooltips import set_tooltips_enabled
from cleave.viz.timeline_controls import TimelineControls
from cleave.viz.shell_layout import ShellLayout, clamp_timeline_band_height
from cleave.viz.timeline_overlay import TimelineOverlay
from cleave.viz.timeline_strip_layout import timeline_band_height_px
from cleave.viz.playback import PlaybackState, init_playback
from cleave.viz.projectm_frame_clock import ProjectMFrameClock
from cleave.viz.frame_finish import OverlaysPanelCache, finish_content_frame
from cleave.viz.overlay_profiler import OverlayProfiler
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.menu_bar import MenuBarState
from cleave.milk_textures import project_texture_search_paths
from cleave.viz.user_presets import cleanup_unreferenced_user_presets
from cleave.viz.visual_limiter import VisualLimiterState, apply_visual_limiter_gains
from cleave.viz.wiring import LayerManager, make_timeline_controls, make_tuning_controls

if TYPE_CHECKING:
    from cleave.viz.shell_host import ShellHost


@dataclass
class VisualizerSeed:
    """Pre-GL runtime state produced by build_runtime_base."""

    project_dir: Path
    audio_path: Path
    width: int
    height: int
    window_title: str
    session: TuningSession
    cfg: CleaveConfig
    pcm_bank: StemPcmBank
    duration_sec: float
    signals: Signals | None
    effect_runtime: EffectRuntime
    preset_root: Path
    library: PresetLibrary
    playlists: dict[str, PresetPlaylist] = field(default_factory=dict)


def window_caption(title: str, *, dirty: bool) -> str:
    """Window caption; a trailing ``*`` marks unsaved project changes."""
    return f"{title}*" if dirty else title


@dataclass
class VisualizerCore:
    """GL-initialized state shared by live and offline render paths."""

    seed: VisualizerSeed
    layers: list[StemLayer]
    layers_by_slot: dict[str, StemLayer]
    compositor: GlCompositor
    post_process: GlPostProcess
    masked_compositor: GlMaskedCompositor
    visual_limiter: VisualLimiterState = field(
        default_factory=VisualLimiterState, kw_only=True
    )


@dataclass
class LiveVisualizerRuntime(VisualizerCore):
    """Fully initialized live visualizer runtime."""

    controls: TuningControls
    timeline_controls: TimelineControls
    modal_host: ModalHost
    mix_player: MixPlayer
    playback: PlaybackState
    timeline_overlay: TimelineOverlay
    overlay_surface: pygame.Surface
    overlays_panel_cache: OverlaysPanelCache = field(
        default_factory=OverlaysPanelCache
    )
    overlay_profiler: OverlayProfiler = field(default_factory=OverlayProfiler.from_env)
    menu_bar: MenuBarState = field(default_factory=MenuBarState)
    shell_host: ShellHost | None = None


@dataclass
class RenderVisualizerRuntime(VisualizerCore):
    """Fully initialized offline render runtime."""


def build_runtime_base(
    cfg: CleaveConfig,
    project_dir: Path,
    audio_path: Path,
    playlists: dict[str, PresetPlaylist],
    library: PresetLibrary,
) -> VisualizerSeed:
    pcm_bank = load_stem_pcm(project_dir)
    session = session_from_cfg(cfg, playlists)
    session.song_markers.markers = list(load_manifest(project_dir).song_markers)
    content_w, content_h = project_resolution(cfg)
    return VisualizerSeed(
        project_dir=project_dir,
        audio_path=audio_path,
        width=content_w,
        height=content_h,
        window_title=f"Cleave — {project_dir.name}",
        session=session,
        cfg=cfg,
        pcm_bank=pcm_bank,
        duration_sec=pcm_bank.duration_sec,
        signals=load_stem_signals(project_dir),
        effect_runtime=EffectRuntime(),
        preset_root=cfg.paths.preset_root,
        library=library,
        playlists=playlists,
    )


def _compositor_color_format(seed: VisualizerSeed) -> GlColorFormat:
    from cleave.viz.editor_mode_controls import is_preset_curation_mode

    return resolve_live_compositor_format(
        seed.session.project.compositor_hdr,
        preset_curation=is_preset_curation_mode(seed.session.settings.editor_mode),
    )


def _make_compositor(
    seed: VisualizerSeed, display_size: tuple[int, int]
) -> GlCompositor:
    color_format = _compositor_color_format(seed)
    c = GlCompositor(
        seed.width,
        seed.height,
        display_width=display_size[0],
        display_height=display_size[1],
        color_format=color_format,
    )
    c.init()
    return c


def _make_masked_compositor(seed: VisualizerSeed) -> GlMaskedCompositor:
    color_format = _compositor_color_format(seed)
    c = GlMaskedCompositor(
        seed.width,
        seed.height,
        color_format=color_format,
    )
    c.init()
    return c


def _adopt_loading_compositor(
    seed: VisualizerSeed, compositor: GlCompositor
) -> GlCompositor:
    """Reconfigure the loading-screen compositor for the project; same GL context.

    The display size stays the window's.
    """
    compositor.set_content_size(seed.width, seed.height)
    compositor.set_color_format(_compositor_color_format(seed))
    return compositor


def _init_compositor_and_post(
    seed: VisualizerSeed,
    display_size: tuple[int, int],
    compositor: GlCompositor | None = None,
) -> tuple[GlCompositor, GlPostProcess, GlMaskedCompositor]:
    color_format = _compositor_color_format(seed)
    if compositor is None:
        compositor = _make_compositor(seed, display_size)
    else:
        compositor = _adopt_loading_compositor(seed, compositor)
    post_process = GlPostProcess(color_format=color_format)
    post_process.init()
    masked_compositor = _make_masked_compositor(seed)
    return compositor, post_process, masked_compositor


def init_gl_resources_cheap(
    seed: VisualizerSeed,
    display_size: tuple[int, int],
    compositor: GlCompositor | None = None,
) -> tuple[GlCompositor, GlPostProcess, GlMaskedCompositor, pygame.Surface]:
    """Compositor, post-process, and overlay surface. *display_size* is the window's."""
    compositor, post_process, masked_compositor = _init_compositor_and_post(
        seed, display_size, compositor=compositor
    )
    overlay_surface = pygame.Surface(display_size, pygame.SRCALPHA)
    return compositor, post_process, masked_compositor, overlay_surface


def init_gl_resources_heavy(
    seed: VisualizerSeed,
    compositor: GlCompositor,
    post_process: GlPostProcess,
    masked_compositor: GlMaskedCompositor,
    overlay_surface: pygame.Surface,
    on_progress: Callable[[str], None] | None = None,
) -> LiveVisualizerRuntime:
    def report(message: str) -> None:
        if on_progress is not None:
            on_progress(message)

    report("Building layers…")
    layers, layers_by_slot = LayerFramePipeline.build(
        seed.cfg,
        compositor,
        seed.playlists,
        seed.session,
        projectm_fps=LIVE_PROJECTM_FPS,
        preview_resolutions=True,
        project_dir=seed.project_dir,
    )

    mix_pcm, sample_rate = load_mix_pcm(seed.audio_path)
    mix_player = MixPlayer(mix_pcm, sample_rate)
    playback = init_playback(mix_player)

    modal_host = ModalHost(
        on_start_text_input=pygame.key.start_text_input,
        on_stop_text_input=pygame.key.stop_text_input,
    )
    layer_manager = LayerManager(
        cfg=seed.cfg,
        session=seed.session,
        compositor=compositor,
        layers=layers,
        layers_by_slot=layers_by_slot,
        playlists=seed.playlists,
        preset_root=seed.preset_root,
        project_dir=seed.project_dir,
        projectm_fps=LIVE_PROJECTM_FPS,
        texture_paths=project_texture_search_paths(
            seed.project_dir, seed.cfg.paths.texture_paths
        ),
        post_process=post_process,
        catalog=seed.library,
    )
    controls = make_tuning_controls(
        session=seed.session,
        cfg=seed.cfg,
        preset_root=seed.preset_root,
        project_dir=seed.project_dir,
        layers_by_slot=layers_by_slot,
        layers=layers,
        playback=playback,
        duration_sec=seed.duration_sec,
        signals=seed.signals,
        effect_runtime=seed.effect_runtime,
        pcm_bank=seed.pcm_bank,
        mix_player=mix_player,
        modal_host=modal_host,
        layer_manager=layer_manager,
        compositor=compositor,
        post_process=post_process,
        masked_compositor=masked_compositor,
        library=seed.library,
    )
    timeline_controls = make_timeline_controls(
        session=seed.session,
        playback=playback,
        duration_sec=seed.duration_sec,
        layers_by_slot=layers_by_slot,
        layers=layers,
        signals=seed.signals,
        effect_runtime=seed.effect_runtime,
        preset_root=seed.preset_root,
        mix_player=mix_player,
        on_notification=controls.show_notification,
        tuning_controls=controls,
    )

    missing_anchor = missing_preset_anchor_notification(
        {slot: layer.playlist.current for slot, layer in seed.session.layers.items()},
        seed.session.layer_z_order,
    )
    if missing_anchor is not None:
        controls.show_notification(missing_anchor)

    runtime = LiveVisualizerRuntime(
        seed=seed,
        layers=layers,
        layers_by_slot=layers_by_slot,
        compositor=compositor,
        post_process=post_process,
        masked_compositor=masked_compositor,
        controls=controls,
        timeline_controls=timeline_controls,
        modal_host=modal_host,
        mix_player=mix_player,
        playback=playback,
        timeline_overlay=TimelineOverlay(),
        overlay_surface=overlay_surface,
    )
    return runtime


def init_gl_resources_render(
    seed: VisualizerSeed,
    *,
    output_width: int,
    output_height: int,
    viz_quality: bool = False,
) -> RenderVisualizerRuntime:
    color_format = _compositor_color_format(seed)
    compositor = GlCompositor(
        output_width,
        output_height,
        display_width=output_width,
        display_height=output_height,
        color_format=color_format,
    )
    compositor.init()
    post_process = GlPostProcess(color_format=color_format)
    post_process.init()
    masked_compositor = GlMaskedCompositor(
        output_width,
        output_height,
        color_format=color_format,
    )
    masked_compositor.init()
    layers, layers_by_slot = LayerFramePipeline.build(
        seed.cfg,
        compositor,
        seed.playlists,
        seed.session,
        projectm_fps=render_fps(seed.cfg),
        preview_resolutions=False,
        viz_quality=viz_quality,
        project_dir=seed.project_dir,
    )

    return RenderVisualizerRuntime(
        seed=seed,
        layers=layers,
        layers_by_slot=layers_by_slot,
        compositor=compositor,
        post_process=post_process,
        masked_compositor=masked_compositor,
    )


def tick_frame_core(
    runtime: VisualizerCore,
    t_sec: float,
    *,
    paused: bool,
    was_paused: bool | None,
    n_pcm: int,
    pm_time_sec: float,
    blank_visualizers: bool = False,
) -> bool | None:
    """Shared frame tick for live and render. Returns updated was_paused."""
    if was_paused is not None and paused != was_paused:
        LayerFramePipeline.flush_pcm(runtime.layers)
    was_paused = paused

    apply_layer_visibility(runtime.seed.session, runtime.layers_by_slot, t_sec)
    apply_visual_limiter_gains(runtime, blank_visualizers=blank_visualizers)

    if not paused and not blank_visualizers:
        advance_timeline_preset_switching(
            runtime.seed.session, runtime.layers_by_slot, t_sec
        )

    on_panel_notification = None
    profiler = _NO_PROFILER
    if isinstance(runtime, LiveVisualizerRuntime):
        on_panel_notification = runtime.controls.show_notification
        profiler = runtime.overlay_profiler

    if blank_visualizers:
        with profiler.time_section("composite"):
            runtime.compositor.composite(
                LayerCompositeRequest(
                    target_fbo_id=runtime.compositor.content_fbo_id,
                    layers=(),
                    color_format=runtime.compositor.color_format,
                )
            )
    else:
        with profiler.time_section("layers"):
            LayerFramePipeline.render_frame(
                runtime.seed.session,
                runtime.layers,
                runtime.layers_by_slot,
                runtime.seed.pcm_bank,
                n_pcm,
                runtime.post_process,
                runtime.seed.effect_runtime,
                runtime.seed.signals,
                t_sec,
                paused=paused,
                pm_time_sec=pm_time_sec,
                compositor=runtime.compositor,
                masked_compositor=runtime.masked_compositor,
                on_panel_notification=on_panel_notification,
            )

        with profiler.time_section("composite"):
            LayerFramePipeline.composite(
                runtime.compositor,
                runtime.layers_by_slot,
                runtime.seed.session,
                masked_compositor=runtime.masked_compositor,
                song_time_sec=t_sec,
            )
    return was_paused


def draw_live_overlay(
    runtime: LiveVisualizerRuntime,
    t_sec: float,
    *,
    layout: ShellLayout,
) -> None:
    """Finish the content frame, then compose and upload the open strip."""
    profiler = runtime.overlay_profiler

    with profiler.time_section("composite"):
        finish_content_frame(
            runtime,
            t_sec,
            post_fx_solo=runtime.seed.session.post_fx_solo,
            overlay_preview=runtime.seed.session.overlay_preview,
            panel_cache=runtime.overlays_panel_cache,
        )

    tap_sync_progress = runtime.controls.tap_sync.showing_progress
    tl = runtime.seed.session.timeline
    if (
        tap_sync_progress
        or runtime.controls.window.play_fullscreen
        or not tl.panel_open
    ):
        return

    with profiler.time_section("strip_compose"):
        signals = runtime.seed.signals
        tl.strip_view.follow_playhead(
            t_sec, runtime.seed.duration_sec, paused=runtime.playback.paused
        )
        timeline_state = build_timeline_view_state(
            runtime.seed.session,
            t_sec,
            runtime.seed.duration_sec,
            focus_cursor=runtime.controls.focus_cursor,
            strip_focused=(
                runtime.controls.shell_focus.region is ShellRegion.TIMELINE
            ),
            song_marker_page_open=(
                runtime.controls.shell_focus.selected_id
                == "timeline.song_markers"
            ),
            bar_times=signals.downbeat_times if signals is not None else (),
            beat_times=signals.beat_times if signals is not None else (),
            paused=runtime.playback.paused,
        )

    OverlayDrawer.draw_timeline(
        runtime.compositor,
        runtime.timeline_overlay,
        runtime.overlay_surface,
        timeline_state,
        visibility=1.0,
        profiler=profiler,
        timeline_rect=layout.timeline,
    )


_NO_PROFILER = OverlayProfiler(enabled=False)


def live_shell_layout(runtime: LiveVisualizerRuntime) -> ShellLayout:
    """Shell regions for this frame, from editor prefs and the shell's drags."""
    from cleave.viz.shell_menu_bar import menu_bar_height_px

    shell = runtime.shell_host
    menu_h = int(shell.menu_bar_height_px) if shell is not None else 0
    transport_h = menu_bar_height_px() if shell is not None else 0
    timeline_h = 0
    display_w, display_h = runtime.overlay_surface.get_size()
    editor = runtime.seed.cfg.editor
    if (
        not runtime.controls.tap_sync.showing_progress
        and runtime.seed.session.timeline.panel_open
    ):
        requested_tl = editor.timeline_height
        if shell is not None and shell.timeline_height is not None:
            requested_tl = shell.timeline_height
        timeline_h = clamp_timeline_band_height(
            requested_tl,
            timeline_band_height_px(len(runtime.seed.session.layer_z_order)),
            display_h=display_h,
            top_h=menu_h + transport_h,
        )
    insp_width = editor.inspector_width
    help_width: int | None = None
    if runtime.seed.session.help_visible:
        help_width = editor.help_width
    nav_content_h: int | None = None
    navigator_height = editor.navigator_height
    if shell is not None:
        if shell.navigator_height is not None:
            navigator_height = shell.navigator_height
        if shell.insp_width is not None:
            insp_width = shell.insp_width
        if help_width is not None and shell.help_width is not None:
            help_width = shell.help_width
        measured = shell.nav_content_height_px
        if measured > 0:
            nav_content_h = measured
    return ShellLayout.compute(
        display_w,
        display_h,
        menu_h,
        transport_h,
        timeline_h,
        insp_width=insp_width,
        help_width=help_width,
        nav_content_h=nav_content_h,
        navigator_height=navigator_height,
        navigator_side=editor.navigator_side,
        help_side=editor.help_side,
    )


def publish_shell_layout(runtime: LiveVisualizerRuntime, layout: ShellLayout) -> None:
    """Hand the layout to the shell, and the visualiser rect to the compositor."""
    shell = runtime.shell_host
    if shell is None:
        runtime.compositor.set_present_rect(None)
        runtime.controls.visualiser_resolution.note_draw_rect(None)
        return
    shell.set_layout(layout)
    runtime.controls.settings.note_shell_stack(
        layout.navigator[3], layout.navigator[3] + layout.inspector[3]
    )
    present = layout.visualiser
    if runtime.controls.window.play_fullscreen:
        display_w, display_h = runtime.overlay_surface.get_size()
        present = (0, 0, display_w, display_h)
    runtime.compositor.set_present_rect(present)
    runtime.controls.visualiser_resolution.note_draw_rect(present)


def begin_live_frame(runtime: LiveVisualizerRuntime) -> ShellLayout:
    """Compute and publish this frame's shell layout."""
    layout = live_shell_layout(runtime)
    publish_shell_layout(runtime, layout)
    return layout


class VisualizerApp:
    def __init__(self, runtime: VisualizerSeed | VisualizerCore) -> None:
        self._runtime = runtime
        self._was_paused: bool | None = None
        self._pm_clock = ProjectMFrameClock()

    def tick_frame(
        self,
        t_sec: float,
        *,
        paused: bool,
        n_pcm: int,
        dt_sec: float = 0.0,
        draw_overlay: bool = True,
        layout: ShellLayout | None = None,
    ) -> None:
        pm_time_sec = self._pm_clock.advance(dt_sec, paused=paused)
        blank_visualizers = (
            isinstance(self._runtime, LiveVisualizerRuntime)
            and self._runtime.controls.tap_sync.active
        )
        self._was_paused = tick_frame_core(
            self._runtime,
            t_sec,
            paused=paused,
            was_paused=self._was_paused,
            n_pcm=n_pcm,
            pm_time_sec=pm_time_sec,
            blank_visualizers=blank_visualizers,
        )
        if draw_overlay:
            if not isinstance(self._runtime, LiveVisualizerRuntime):
                raise TypeError(
                    "draw_overlay=True requires LiveVisualizerRuntime"
                )
            if layout is None:
                layout = begin_live_frame(self._runtime)
            draw_live_overlay(self._runtime, t_sec, layout=layout)

    def run(self, window: LoadingWindow | None = None) -> OpenTarget | None:
        """Run one live session on an already-open loading window.

        Returns the accepted project switch, or None when the session quit.
        The loading compositor and the pygame display stay up for the next session.
        """
        if not isinstance(self._runtime, VisualizerSeed):
            raise TypeError("run() requires a VisualizerSeed from build_runtime_base()")

        seed = self._runtime
        if window is None:
            window = open_loading_window()
        pygame.display.set_caption(window_caption(seed.window_title, dirty=False))
        set_ui_scale_percent(seed.cfg.editor.ui_scale)
        theme_problems = install_user_themes(themes_dir())
        set_palette(palette_for_theme(seed.cfg.editor.theme))
        set_tooltips_enabled(seed.cfg.editor.show_tooltips)

        rt: LiveVisualizerRuntime | None = None
        try:
            compositor, post_process, masked_compositor, overlay_surface = (
                init_gl_resources_cheap(
                    seed,
                    (window.display_width, window.display_height),
                    compositor=window.compositor,
                )
            )
            window.compositor = compositor
            window.overlay_surface = overlay_surface
            window.update("Loading…")

            def on_progress(message: str) -> None:
                window.update(message)

            rt = init_gl_resources_heavy(
                seed,
                compositor,
                post_process,
                masked_compositor,
                overlay_surface,
                on_progress=on_progress,
            )
            self._runtime = rt
            if window.quit_requested:
                return None
            rt.controls.theme_files.show_problems(theme_problems)

            # The loop module imports ImGui, which offline render never needs.
            from cleave.viz.live_frame_loop import LiveFrameLoop

            loop = LiveFrameLoop(rt, window, self.tick_frame)
            loop.draw_first_frame()
            rt.mix_player.start()
            while loop.running:
                loop.run_frame()
            return loop.switch_target

        finally:
            if rt is not None:
                rt.compositor.set_present_rect(None)
                rt.shell_host = None
            window.release_imgui()
            if rt is not None:
                persist_editor_settings(rt.seed.cfg)
                LayerFramePipeline.destroy(rt.layers, rt.compositor)
                rt.post_process.destroy()
                rt.masked_compositor.release()
                rt.mix_player.stop()
                cleanup_unreferenced_user_presets(rt.seed.project_dir)
