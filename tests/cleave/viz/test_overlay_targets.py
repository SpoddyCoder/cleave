"""Tests that live UI overlays target the display framebuffer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pygame

from cleave.gl_compositor import OverlayTextureSlot
from cleave.viz.overlay_draw import OverlayDrawer
from cleave.viz.overlay_primitives import ComposedPanel
from cleave.viz.overlay_upload import OverlayGpuState, UploadPlan, UploadSignature
from cleave.viz.timeline_overlay import TimelineViewState
from tests.support.compositor_mock import recording_compositor


def _overlay_surface_mock() -> MagicMock:
    surface = MagicMock()
    surface.get_size.return_value = (1280, 720)
    return surface


def _mock_timeline_compose(
    overlay: MagicMock,
    *,
    screen_rect: tuple[int, int, int, int] = (0, 580, 1280, 140),
) -> None:
    px, py, pw, ph = screen_rect
    panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
    upload_signature = UploadSignature(
        active_size=(pw, ph),
        screen_rect=screen_rect,
        content_hash=(2,),
    )
    upload_plan = UploadPlan(
        mode="full",
        dirty_rects=((0, 0, pw, ph),),
        active_size=(pw, ph),
        screen_rect=screen_rect,
    )
    overlay.compose_panel.return_value = ComposedPanel(
        upload_surface=panel_surf,
        panel_size=(pw, ph - 20),
        screen_rect=screen_rect,
        upload_plan=upload_plan,
        upload_signature=upload_signature,
        capacity=(pw, ph),
    )
    overlay.gpu_state = OverlayGpuState()


def test_draw_timeline_overlay_uses_display_target() -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.ensure_overlay_texture.return_value = 22
    compositor.upload_overlay_region.return_value = 22

    overlay = MagicMock()
    _mock_timeline_compose(overlay)
    overlay_surface = _overlay_surface_mock()
    view_state = TimelineViewState(
        layer_z_order=["layer_1"],
        lanes={},
        defaults={},
        position_sec=0.0,
        duration_sec=120.0,
        focus_row=0,
        monitor_visible={"layer_1": True},
        timeline_level={"layer_1": 1.0},
        override_slots=set(),
        armed_slots=set(),
        recording=False,
        record_start_sec=0.0,
        record_baseline={},
        record_buffer={},
        enabled=True,
    )

    OverlayDrawer.draw_timeline(
        compositor, overlay, overlay_surface, view_state
    )

    overlay.compose_panel.assert_called_once()
    overlay_surface.fill.assert_not_called()
    compositor.ensure_overlay_texture.assert_called_once_with(
        OverlayTextureSlot.TIMELINE, 1280, 140
    )
    compositor.upload_overlay_region.assert_called_once()
    compositor.upload_overlay_texture.assert_not_called()
    compositor.draw_overlay.assert_called_once_with(22, 0, 580, 1280, 140, 1.0, None)
    compositor.draw_content_overlay.assert_not_called()


def test_draw_timeline_overlay_applies_visibility_alpha() -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.ensure_overlay_texture.return_value = 33
    compositor.upload_overlay_region.return_value = 33

    overlay = MagicMock()
    _mock_timeline_compose(overlay)
    overlay_surface = _overlay_surface_mock()
    view_state = TimelineViewState(
        layer_z_order=["layer_1"],
        lanes={},
        defaults={},
        position_sec=0.0,
        duration_sec=120.0,
        focus_row=0,
        monitor_visible={"layer_1": True},
        timeline_level={"layer_1": 1.0},
        override_slots=set(),
        armed_slots=set(),
        recording=False,
        record_start_sec=0.0,
        record_baseline={},
        record_buffer={},
        enabled=True,
    )

    OverlayDrawer.draw_timeline(
        compositor,
        overlay,
        overlay_surface,
        view_state,
        visibility=0.4,
    )

    compositor.draw_overlay.assert_called_once_with(33, 0, 580, 1280, 140, 0.4, None)
