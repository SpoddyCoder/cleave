"""GL upload path for live tuning and timeline overlays."""

from __future__ import annotations

import pygame

from cleave.gl_compositor import GlCompositor
from cleave.viz import modal_overlay
from cleave.viz.help_overlay import HelpOverlay
from cleave.viz.modal import ModalHost
from cleave.viz.tuning_panel_draw import TuningOverlay
from cleave.viz.tuning_view_state import TuningViewState
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
        help_overlay: HelpOverlay | None = None,
        modal_host: ModalHost | None = None,
    ) -> None:
        overlay_surface.fill((0, 0, 0, 0))
        overlay.draw(
            overlay_surface, view_state, timeline_panel_open=timeline_panel_open
        )
        if help_overlay is not None and view_state.help_visible:
            help_overlay.draw(
                overlay_surface,
                view_state.focus_descriptor,
                timeline_enabled=view_state.render_timeline.enabled,
                timeline_submenu_focused=view_state.timeline_submenu_focused,
                paused=view_state.paused,
                timeline_recording=view_state.timeline_recording,
                timeline_override_active=view_state.timeline_override_active,
            )

        modal_active = modal_host is not None and modal_host.active
        if modal_active:
            modal_view = modal_host.view_state()
            assert modal_view is not None
            modal_overlay.draw(
                overlay_surface,
                modal_view,
                font=overlay._font_get(),
                line_gap=overlay._line_gap,
            )

        if modal_active:
            sw, sh = overlay_surface.get_size()
            tex_id = compositor.upload_overlay_texture(overlay_surface)
            compositor.draw_overlay(tex_id, 0, 0, sw, sh)
            return

        panel = overlay.panel_rect
        if panel is not None:
            px, py, pw, ph = panel
            panel_surface = overlay_surface.subsurface((px, py, pw, ph))
            tex_id = compositor.upload_overlay_texture(panel_surface)
            compositor.draw_overlay(tex_id, px, py, pw, ph)

        if help_overlay is not None and view_state.help_visible:
            help_panel = help_overlay.panel_rect
            if help_panel is not None:
                hx, hy, hw, hh = help_panel
                help_surface = overlay_surface.subsurface((hx, hy, hw, hh))
                help_tex_id = compositor.upload_overlay_texture(help_surface)
                compositor.draw_overlay(help_tex_id, hx, hy, hw, hh)

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
