"""GL upload path for live tuning and timeline overlays."""

from __future__ import annotations

import pygame

from cleave.gl_compositor import GlCompositor, OverlayTextureSlot
from cleave.viz.help_content import help_section_kwargs, help_stop_for_shell
from cleave.viz.help_overlay import HelpOverlay
from cleave.viz.shell_focus import ShellFocusState, ShellRegion
from cleave.viz.tuning_panel_draw import TuningOverlay
from cleave.viz.tuning_view_state import TuningViewState
from cleave.viz.overlay_profiler import OverlayProfiler
from cleave.viz.overlay_upload import (
    OverlayGpuState,
    OverlayUploadCoordinator,
    UploadPlan,
    UploadSignature,
    present_overlay,
)
from cleave.viz.timeline_overlay import TimelineOverlay, TimelineViewState

_TIMELINE_UPLOAD_COORDINATOR = OverlayUploadCoordinator()

_TUNING_UPLOAD_COORDINATOR = OverlayUploadCoordinator()
_HELP_UPLOAD_COORDINATOR = OverlayUploadCoordinator()


def _note_upload(
    profiler: OverlayProfiler | None,
    compositor: GlCompositor,
    plan: UploadPlan,
) -> None:
    if profiler is None:
        return
    profiler.note_upload_plan(plan)
    reallocs = compositor.consume_texture_reallocs()
    if reallocs:
        profiler.counters().texture_reallocs += reallocs


def _coordinator_upload(
    profiler: OverlayProfiler | None,
    compositor: GlCompositor,
    coordinator: OverlayUploadCoordinator,
    slot: OverlayTextureSlot,
    upload_surface: pygame.Surface,
    upload_plan: UploadPlan,
    capacity: tuple[int, int],
    gpu_state: OverlayGpuState,
    upload_signature: UploadSignature,
) -> tuple[int, tuple[float, float, float, float] | None]:
    if profiler is not None:
        with profiler.time_section("upload"):
            tex_id, tex_uv = coordinator.upload(
                compositor,
                slot,
                upload_surface,
                upload_plan,
                capacity,
                gpu_state,
                upload_signature,
            )
        _note_upload(profiler, compositor, upload_plan)
    else:
        tex_id, tex_uv = coordinator.upload(
            compositor,
            slot,
            upload_surface,
            upload_plan,
            capacity,
            gpu_state,
            upload_signature,
        )
    return tex_id, tex_uv


def _present_overlay(
    profiler: OverlayProfiler | None,
    compositor: GlCompositor,
    tex_id: int,
    screen_rect: tuple[int, int, int, int],
    tex_uv: tuple[float, float, float, float] | None,
    *,
    alpha: float = 1.0,
) -> None:
    if profiler is not None:
        with profiler.time_section("overlay_present"):
            present_overlay(compositor, tex_id, screen_rect, tex_uv, alpha=alpha)
    else:
        present_overlay(compositor, tex_id, screen_rect, tex_uv, alpha=alpha)


def _timeline_strip_keyboard_scope(
    view_state: TuningViewState,
    shell_focus: ShellFocusState | None,
) -> bool:
    """Strip keyboard scope is the Timeline region when the shell is known."""
    if shell_focus is not None:
        return shell_focus.region is ShellRegion.TIMELINE
    return view_state.timeline_submenu_focused


def _help_compose_kwargs(
    view_state: TuningViewState,
    shell_focus: ShellFocusState | None = None,
) -> dict[str, object]:
    timeline_focused = _timeline_strip_keyboard_scope(view_state, shell_focus)
    stop = help_stop_for_shell(shell_focus, timeline_focused=timeline_focused)
    kwargs = help_section_kwargs(view_state, shell_focus, stop=stop)
    kwargs["timeline_submenu_focused"] = timeline_focused
    return kwargs


class OverlayDrawer:
    """Upload pygame overlay surfaces to the display framebuffer."""

    @staticmethod
    def draw_tuning(
        compositor: GlCompositor,
        overlay: TuningOverlay,
        overlay_surface: pygame.Surface,
        view_state: TuningViewState,
        *,
        timeline_panel_open: bool = False,
        cue_readout_open: bool = False,
        overlay_visible: bool = True,
        help_overlay: HelpOverlay | None = None,
        profiler: OverlayProfiler | None = None,
        visualiser_rect: tuple[int, int, int, int] | None = None,
        shell_focus: ShellFocusState | None = None,
    ) -> None:
        viewport_w, viewport_h = overlay_surface.get_size()
        counters = profiler.counters() if profiler is not None else None
        show_help = view_state.help_visible and overlay_visible

        composed = overlay.compose_panel(
            view_state,
            viewport_width=viewport_w,
            viewport_height=viewport_h,
            timeline_panel_open=timeline_panel_open,
            cue_readout_open=cue_readout_open,
            counters=counters,
            visualiser_rect=visualiser_rect,
        )
        if composed is not None:
            tex_id, tex_uv = _coordinator_upload(
                profiler,
                compositor,
                _TUNING_UPLOAD_COORDINATOR,
                OverlayTextureSlot.TUNING,
                composed.upload_surface,
                composed.upload_plan,
                composed.capacity,
                overlay.gpu_state,
                composed.upload_signature,
            )
            _present_overlay(
                profiler,
                compositor,
                tex_id,
                composed.screen_rect,
                tex_uv,
            )

        if help_overlay is not None and show_help:
            help_composed = help_overlay.compose_panel(
                viewport_width=viewport_w,
                viewport_height=viewport_h,
                visualiser_rect=visualiser_rect,
                **_help_compose_kwargs(view_state, shell_focus),
            )
            if help_composed is not None:
                help_tex_id, help_tex_uv = _coordinator_upload(
                    profiler,
                    compositor,
                    _HELP_UPLOAD_COORDINATOR,
                    OverlayTextureSlot.HELP,
                    help_composed.upload_surface,
                    help_composed.upload_plan,
                    help_composed.capacity,
                    help_overlay.gpu_state,
                    help_composed.upload_signature,
                )
                _present_overlay(
                    profiler,
                    compositor,
                    help_tex_id,
                    help_composed.screen_rect,
                    help_tex_uv,
                )

    @staticmethod
    def draw_timeline(
        compositor: GlCompositor,
        overlay: TimelineOverlay,
        overlay_surface: pygame.Surface,
        view_state: TimelineViewState,
        *,
        visibility: float = 1.0,
        profiler: OverlayProfiler | None = None,
        timeline_rect: tuple[int, int, int, int] | None = None,
    ) -> None:
        composed = overlay.compose_panel(
            view_state,
            viewport_width=overlay_surface.get_width(),
            viewport_height=overlay_surface.get_height(),
            visibility=visibility,
            timeline_rect=timeline_rect,
        )
        if composed is not None and visibility > 0.01:
            tex_id, tex_uv = _coordinator_upload(
                profiler,
                compositor,
                _TIMELINE_UPLOAD_COORDINATOR,
                OverlayTextureSlot.TIMELINE,
                composed.upload_surface,
                composed.upload_plan,
                composed.capacity,
                overlay.gpu_state,
                composed.upload_signature,
            )
            _present_overlay(
                profiler,
                compositor,
                tex_id,
                composed.screen_rect,
                tex_uv,
                alpha=visibility,
            )
