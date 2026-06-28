"""GL upload path for live tuning and timeline overlays."""

from __future__ import annotations

import pygame

from cleave.gl_compositor import GlCompositor
from cleave.viz import modal_overlay
from cleave.viz.help_overlay import HelpOverlay
from cleave.viz.modal import ModalHost
from cleave.viz.tuning_panel_draw import TuningOverlay
from cleave.viz.tuning_view_state import TuningViewState
from cleave.viz.overlay_profiler import OverlayProfiler
from cleave.viz.timeline_overlay import TimelineOverlay, TimelineViewState


def _union_rect(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0 = min(ax, bx)
    y0 = min(ay, by)
    x1 = max(ax + aw, bx + bw)
    y1 = max(ay + ah, by + bh)
    return (x0, y0, x1 - x0, y1 - y0)


def _help_compose_kwargs(view_state: TuningViewState) -> dict[str, object]:
    focus = view_state.focus_descriptor
    preset_switching = None
    if focus.slot is not None:
        track = view_state.tracks.get(focus.slot)
        if track is not None:
            preset_switching = track.preset_switching
    return {
        "focus": focus,
        "timeline_enabled": view_state.render_timeline.enabled,
        "timeline_submenu_focused": view_state.timeline_submenu_focused,
        "paused": view_state.paused,
        "timeline_recording": view_state.timeline_recording,
        "timeline_override_active": view_state.timeline_override_active,
        "preset_switching": preset_switching,
    }


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
            profiler_status_line=(
                profiler.last_line
                if profiler is not None and profiler.enabled
                else None
            ),
        )
        if composed is not None:
            panel_surface, (px, py, pw, ph) = composed
            tex_id = _upload(panel_surface)
            _present(tex_id, px, py, pw, ph)

        if help_overlay is not None and show_help:
            help_composed = help_overlay.compose_panel(
                viewport_width=viewport_w,
                viewport_height=viewport_h,
                **_help_compose_kwargs(view_state),
            )
            if help_composed is not None:
                help_surface, (hx, hy, hw, hh) = help_composed
                help_tex_id = _upload(help_surface)
                _present(help_tex_id, hx, hy, hw, hh)

    @staticmethod
    def draw_timeline(
        compositor: GlCompositor,
        overlay: TimelineOverlay,
        overlay_surface: pygame.Surface,
        view_state: TimelineViewState,
        *,
        visibility: float = 1.0,
    ) -> None:
        overlay_surface.fill((0, 0, 0, 0))
        overlay.draw(overlay_surface, view_state)
        panel = overlay.panel_rect
        if panel is not None and visibility > 0.01:
            upload_rect = panel
            badge = overlay.header_badge_rect
            if badge is not None:
                upload_rect = _union_rect(panel, badge)
            px, py, pw, ph = upload_rect
            upload_surface = overlay_surface.subsurface((px, py, pw, ph))
            tex_id = compositor.upload_overlay_texture(upload_surface)
            compositor.draw_overlay(tex_id, px, py, pw, ph, visibility)
