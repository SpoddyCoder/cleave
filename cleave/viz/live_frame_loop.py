"""One live editor frame: events, controller ticks, the visualiser, the shell."""

from __future__ import annotations

from typing import Protocol

import pygame

from cleave.open_target import OpenTarget
from cleave.stem_pcm import LIVE_PROJECTM_FPS, samples_for_dt, samples_per_frame
from cleave.viz.app import (
    LiveVisualizerRuntime,
    begin_live_frame,
    draw_live_overlay,
    window_caption,
)
from cleave.viz.commands import command_context
from cleave.viz.frame_rate import FrameRateMeter, ProjectMFpsGovernor
from cleave.viz.input_dispatch import (
    dispatch_keydown,
    dispatch_keyup,
    dispatch_window_event,
)
from cleave.viz.loading import LoadingWindow
from cleave.viz.playback import current_sec
from cleave.viz.preview_context_menu import play_fullscreen_menu, preview_menu
from cleave.viz.shell_host import ShellHost, draw_shell_frame
from cleave.viz.shell_layout import ShellLayout
from cleave.viz.shell_menu_bar import menu_bar_height_px
from cleave.viz.shell_prompts import ShellPrompts
from cleave.viz.shell_transport import TransportReadout
from cleave.viz.timeline_overlay import playback_bar_text
from cleave.viz.timeline_pointer import TimelinePointer
from cleave.viz.timeline_time_menu import TimelineTimeMenu
from cleave.viz.window_controls import WindowControls


class ContentTick(Protocol):
    """`VisualizerApp.tick_frame`: projectM, composite, post-FX and the strip."""

    def __call__(
        self,
        t_sec: float,
        *,
        paused: bool,
        n_pcm: int,
        dt_sec: float = 0.0,
        draw_overlay: bool = True,
        layout: ShellLayout | None = None,
    ) -> None: ...


def apply_window_requests(
    controls: WindowControls, window: LoadingWindow, *, prompt_open: bool
) -> None:
    """Carry out Full Screen Editor and Play Full Screen on the GL window.

    A modal, the project picker, or any other prompt while playing full
    screen returns to the editor so it can be answered.
    """
    if controls.consume_fullscreen_toggle() and not controls.play_fullscreen:
        window.toggle_fullscreen()
    if prompt_open and controls.play_fullscreen:
        controls.request_play_fullscreen(False)
    change = controls.consume_play_fullscreen()
    if change is True:
        controls.play_restores_window = not window.fullscreen
        if controls.play_restores_window:
            window.toggle_fullscreen()
        controls.play_fullscreen = True
    elif change is False:
        if controls.play_restores_window and window.fullscreen:
            window.toggle_fullscreen()
        controls.play_restores_window = False
        controls.play_fullscreen = False
    controls.fullscreen = window.fullscreen


def build_shell(
    rt: LiveVisualizerRuntime, window: LoadingWindow, strip_pointer: TimelinePointer
) -> ShellHost:
    """The editor shell over the window's ImGui context."""
    assert window.imgui is not None
    return ShellHost(
        window.imgui,
        rt.menu_bar,
        rt.controls,
        menu_bar_height_px(),
        strip_pointer=strip_pointer,
        preview_menu=preview_menu(rt.controls, rt.timeline_controls),
        play_menu=play_fullscreen_menu(rt.controls, rt.timeline_controls),
        profiler=rt.overlay_profiler,
    )


class LiveFrameLoop:
    """The live session's per-frame state and steps.

    `VisualizerApp.run` owns setup, the `while`, and teardown. Building the
    loop builds the shell and sets it as `rt.shell_host`.
    """

    def __init__(
        self,
        rt: LiveVisualizerRuntime,
        window: LoadingWindow,
        tick_content: ContentTick,
    ) -> None:
        self.rt = rt
        self.window = window
        self.strip_pointer = TimelinePointer(
            rt.timeline_overlay,
            rt.timeline_controls,
            rt.seed.session,
            time_menu=TimelineTimeMenu(rt.controls, rt.timeline_controls),
        )
        self.shell = build_shell(rt, window, self.strip_pointer)
        rt.shell_host = self.shell
        self.prompts = ShellPrompts(rt.controls, rt.modal_host)
        self._tick_content = tick_content
        self.running = True
        self.switch_target: OpenTarget | None = None
        self.overlay_dt = 0.0
        self.display_fps: float | None = None
        self._measured_fps: float | None = None
        self._caption = window_caption(rt.seed.window_title, dirty=False)
        self._clock = pygame.time.Clock()
        self._frame_rate = FrameRateMeter()
        self._pm_fps_governor = ProjectMFpsGovernor(nominal_fps=LIVE_PROJECTM_FPS)

    def draw_first_frame(self) -> None:
        """Warm-up frame at the song start, drawn before the audio starts."""
        self._tick_content(
            0.0,
            paused=False,
            n_pcm=samples_per_frame(LIVE_PROJECTM_FPS),
            dt_sec=0.0,
            layout=begin_live_frame(self.rt),
        )
        self.draw_ui()
        pygame.display.flip()

    def run_frame(self) -> None:
        """One frame, each step timed under its profiler section."""
        profiler = self.rt.overlay_profiler
        self._frame_rate.begin_frame()
        with profiler.time_section("events"):
            self.handle_events()
        self._take_exit_requests()
        dt = self._clock.tick() / 1000.0
        with profiler.time_section("tick"):
            self.tick(dt)
        if self.window.apply_pending_resize():
            self.rt.overlay_surface = self.window.overlay_surface
        self.render(current_sec(self.rt.playback, self.rt.seed.duration_sec))
        self.display_fps = self._frame_rate.display_fps
        with profiler.time_section("ui_build"):
            self.draw_ui()
        with profiler.time_section("flip"):
            pygame.display.flip()
        profiler.end_frame()
        self._measured_fps = self._frame_rate.end_frame()

    def handle_events(self) -> None:
        """Route pygame events to the shell and key dispatch, then window requests."""
        rt = self.rt
        for event in pygame.event.get():
            self.window.note_event(event)
            dispatch_window_event(event, rt)
            if rt.controls.window.play_fullscreen:
                self.shell.process_play_event(event)
            else:
                self.shell.process_event(event)
            if event.type == pygame.QUIT:
                if rt.controls.try_quit():
                    self.running = False
            elif event.type == pygame.KEYDOWN:
                if dispatch_keydown(event, rt) is False:
                    self.running = False
            elif event.type == pygame.KEYUP:
                dispatch_keyup(event, rt)
            elif event.type == pygame.TEXTINPUT:
                if not rt.controls.inline_edit.handle_text_input(event.text):
                    rt.modal_host.handle_text_input(event.text)

        apply_window_requests(
            rt.controls.window,
            self.window,
            prompt_open=rt.modal_host.active or rt.controls.project_switch.active,
        )
        self.window.sync_minimum_size()

    def _take_exit_requests(self) -> None:
        controls = self.rt.controls
        if controls.consume_pending_exit():
            self.running = False
        elif controls.consume_pending_switch():
            self.switch_target = controls.project_switch.take_accepted()
            self.running = False

    def tick(self, dt: float) -> None:
        """Advance the controllers by `dt` seconds and refresh the window caption."""
        rt = self.rt
        self.overlay_dt = dt
        rt.controls.tick(dt)
        rt.timeline_controls.tick(dt)
        self.strip_pointer.tick()
        rt.modal_host.tick(dt)
        caption = window_caption(rt.seed.window_title, dirty=rt.controls.config_dirty)
        if caption != self._caption:
            self._caption = caption
            pygame.display.set_caption(caption)

    def render(self, t_sec: float) -> None:
        """Draw the visualiser and the strip for song time `t_sec`.

        While a project render runs, the last content frame is held.
        """
        rt = self.rt
        layout = begin_live_frame(rt)
        if rt.controls.project_render.busy:
            with rt.overlay_profiler.time_section("composite"):
                rt.compositor.present_content()
            draw_live_overlay(rt, t_sec, layout=layout)
            return
        self._pm_fps_governor.observe(self._measured_fps)
        self._pm_fps_governor.apply_if_changed(rt.layers)
        rt.overlay_profiler.note_projectm_fps(self._pm_fps_governor.target_fps)
        self._tick_content(
            t_sec,
            paused=rt.playback.paused,
            n_pcm=samples_for_dt(self.overlay_dt),
            dt_sec=self.overlay_dt,
            layout=layout,
        )
        rt.controls.still_capture.after_frame(rt.compositor)

    def draw_ui(self) -> None:
        """The ImGui frame: the shell and any open prompt.

        Playing full screen draws only an open context menu.
        """
        rt = self.rt
        shell = self.shell
        if rt.controls.window.play_fullscreen:
            shell.draw_play_frame(self.overlay_dt)
            return
        notice = rt.controls.notification_active()
        self.prompts.push(shell.top_layer)
        position = current_sec(rt.playback, rt.seed.duration_sec)
        signals = rt.seed.signals
        readout = TransportReadout(
            paused=rt.playback.paused,
            position_sec=position,
            duration_sec=rt.seed.duration_sec,
            bar_text=playback_bar_text(
                position, () if signals is None else signals.downbeat_times
            ),
            fps=self.display_fps,
        )
        draw_shell_frame(
            shell,
            rt.menu_bar,
            command_context(rt.controls),
            self.overlay_dt,
            readout,
            notice,
        )
        if shell.transport_notice_clicked and not shell.top_layer.modal_active:
            rt.controls.dismiss_notification()
        self.prompts.apply()
