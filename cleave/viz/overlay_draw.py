"""GL upload path for live tuning and timeline overlays."""

from __future__ import annotations

import pygame

from cleave.gl_compositor import GlCompositor, OverlayTextureSlot
from cleave.viz import modal_overlay
from cleave.viz.help_overlay import HelpOverlay
from cleave.viz.modal import ModalHost
from cleave.viz.tap_sync import CONSISTENCY_WINDOW
from cleave.viz.tap_sync_controls import TapSyncProgressView
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


def _help_compose_kwargs(view_state: TuningViewState) -> dict[str, object]:
    focus = view_state.focus_descriptor
    preset_switching_scope = None
    if focus.slot is not None:
        track = view_state.tracks.get(focus.slot)
        if track is not None:
            preset_switching_scope = track.preset_switching_scope
    return {
        "focus": focus,
        "timeline_enabled": view_state.render_timeline.enabled,
        "timeline_submenu_focused": view_state.timeline_submenu_focused,
        "paused": view_state.paused,
        "timeline_recording": view_state.timeline_recording,
        "timeline_override_active": view_state.timeline_override_active,
        "preset_switching_scope": preset_switching_scope,
        "preset_curation": view_state.settings.editor_mode == "preset_curation",
    }


def _tap_sync_progress_view_state(
    progress: TapSyncProgressView,
) -> modal_overlay.InfoPanelViewState:
    spread_text = (
        "--"
        if progress.spread_ms is None
        else f"{progress.spread_ms} ms"
    )
    estimate_text = (
        "--"
        if progress.estimate_ms is None
        else f"{progress.estimate_ms} ms"
    )
    return modal_overlay.InfoPanelViewState(
        title_lines=(
            "Detection in progress",
            "Tap Space on each bar beat",
        ),
        body_lines=(
            f"Streak: {progress.streak}/{CONSISTENCY_WINDOW}",
            f"Spread: {spread_text}",
            f"Estimate: {estimate_text}",
        ),
        footer_line="Esc to cancel",
    )


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
        overlay_visible: bool = True,
        help_overlay: HelpOverlay | None = None,
        modal_host: ModalHost | None = None,
        profiler: OverlayProfiler | None = None,
    ) -> None:
        viewport_w, viewport_h = overlay_surface.get_size()
        counters = profiler.counters() if profiler is not None else None
        modal_active = modal_host is not None and modal_host.active
        show_help = view_state.help_visible and overlay_visible

        def _upload(surface: pygame.Surface) -> int:
            if profiler is not None:
                with profiler.time_section("upload"):
                    return compositor.upload_overlay_texture(surface)
            return compositor.upload_overlay_texture(surface)

        def _present(
            tex_id: int,
            x: int,
            y: int,
            w: int,
            h: int,
        ) -> None:
            if profiler is not None:
                with profiler.time_section("overlay_present"):
                    compositor.draw_overlay(tex_id, x, y, w, h)
            else:
                compositor.draw_overlay(tex_id, x, y, w, h)

        if modal_active:
            overlay_surface.fill((0, 0, 0, 0))
            overlay.draw(
                overlay_surface,
                view_state,
                timeline_panel_open=timeline_panel_open,
                counters=counters,
            )
            if help_overlay is not None and show_help:
                help_overlay.draw(
                    overlay_surface,
                    **_help_compose_kwargs(view_state),
                )
            modal_view = modal_host.view_state()
            assert modal_view is not None
            modal_overlay.draw(
                overlay_surface,
                modal_view,
                font=overlay._font_get(),
                line_gap=overlay._line_gap,
            )
            tex_id = _upload(overlay_surface)
            _present(tex_id, 0, 0, viewport_w, viewport_h)
            return

        composed = overlay.compose_panel(
            view_state,
            viewport_width=viewport_w,
            viewport_height=viewport_h,
            timeline_panel_open=timeline_panel_open,
            counters=counters,
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
                **_help_compose_kwargs(view_state),
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
    def draw_tap_sync_progress(
        compositor: GlCompositor,
        overlay: TuningOverlay,
        overlay_surface: pygame.Surface,
        progress: TapSyncProgressView,
        *,
        profiler: OverlayProfiler | None = None,
    ) -> None:
        viewport_w, viewport_h = overlay_surface.get_size()
        overlay_surface.fill((0, 0, 0, 0))
        modal_overlay.draw_info(
            overlay_surface,
            _tap_sync_progress_view_state(progress),
            font=overlay._font_get(),
            line_gap=overlay._line_gap,
        )

        def _upload(surface: pygame.Surface) -> int:
            if profiler is not None:
                with profiler.time_section("upload"):
                    return compositor.upload_overlay_texture(surface)
            return compositor.upload_overlay_texture(surface)

        def _present(tex_id: int) -> None:
            if profiler is not None:
                with profiler.time_section("overlay_present"):
                    compositor.draw_overlay(tex_id, 0, 0, viewport_w, viewport_h)
            else:
                compositor.draw_overlay(tex_id, 0, 0, viewport_w, viewport_h)

        tex_id = _upload(overlay_surface)
        _present(tex_id)

    @staticmethod
    def draw_timeline(
        compositor: GlCompositor,
        overlay: TimelineOverlay,
        overlay_surface: pygame.Surface,
        view_state: TimelineViewState,
        *,
        visibility: float = 1.0,
        profiler: OverlayProfiler | None = None,
    ) -> None:
        composed = overlay.compose_panel(
            view_state,
            viewport_width=overlay_surface.get_width(),
            viewport_height=overlay_surface.get_height(),
            visibility=visibility,
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
