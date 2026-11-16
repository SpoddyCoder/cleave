"""GL upload path for the timeline overlay."""

from __future__ import annotations

import pygame

from cleave.gl_compositor import GlCompositor, OverlayTextureSlot
from cleave.viz.overlay_profiler import OverlayProfiler
from cleave.viz.overlay_upload import (
    OverlayUploadCoordinator,
    present_overlay,
)
from cleave.viz.timeline_overlay import TimelineOverlay, TimelineViewState

_TIMELINE_UPLOAD_COORDINATOR = OverlayUploadCoordinator()
_NO_PROFILER = OverlayProfiler(enabled=False)


class OverlayDrawer:
    """Upload pygame overlay surfaces to the display framebuffer."""

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
        if profiler is None:
            profiler = _NO_PROFILER
        with profiler.time_section("strip_compose"):
            composed = overlay.compose_panel(
                view_state,
                viewport_width=overlay_surface.get_width(),
                viewport_height=overlay_surface.get_height(),
                visibility=visibility,
                timeline_rect=timeline_rect,
            )
        if composed is None or visibility <= 0.01:
            return
        with profiler.time_section("strip_upload"):
            tex_id, tex_uv = _TIMELINE_UPLOAD_COORDINATOR.upload(
                compositor,
                OverlayTextureSlot.TIMELINE,
                composed.upload_surface,
                composed.upload_plan,
                composed.capacity,
                overlay.gpu_state,
                composed.upload_signature,
            )
            present_overlay(
                compositor,
                tex_id,
                composed.screen_rect,
                tex_uv,
                alpha=visibility,
            )
        profiler.note_upload_plan(composed.upload_plan)
        profiler.note_texture_reallocs(compositor.consume_texture_reallocs())
