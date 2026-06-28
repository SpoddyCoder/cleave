"""Tests that live UI overlays target the display framebuffer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pygame

from cleave.viz.help_overlay import HelpOverlay
from cleave.viz.overlay_draw import OverlayDrawer
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.timeline_overlay import TimelineViewState
from tests.support.compositor_mock import recording_compositor


def test_draw_tuning_overlay_uses_display_target() -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.upload_overlay_texture.return_value = 11

    overlay = MagicMock()
    overlay.panel_rect = (10, 20, 100, 50)
    overlay_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)

    OverlayDrawer.draw_tuning(compositor, overlay, overlay_surface, MagicMock())

    compositor.draw_overlay.assert_called_once_with(11, 10, 20, 100, 50)
    compositor.draw_content_overlay.assert_not_called()


def test_draw_tuning_overlay_uploads_help_panel() -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.upload_overlay_texture.side_effect = [11, 22]

    overlay = MagicMock()
    overlay.panel_rect = (10, 20, 100, 50)
    help_overlay = HelpOverlay()
    overlay_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    view_state = MagicMock()
    view_state.help_visible = True
    view_state.focus_descriptor = RowDescriptor(RowKind.TRANSPORT)
    view_state.layout.kind.return_value = RowKind.TRANSPORT

    OverlayDrawer.draw_tuning(
        compositor,
        overlay,
        overlay_surface,
        view_state,
        help_overlay=help_overlay,
    )

    assert compositor.draw_overlay.call_count == 2
    compositor.draw_overlay.assert_any_call(11, 10, 20, 100, 50)
    help_panel = help_overlay.panel_rect
    assert help_panel is not None
    compositor.draw_overlay.assert_any_call(22, *help_panel)


def test_draw_tuning_overlay_hides_help_when_overlay_hidden() -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.upload_overlay_texture.return_value = 11

    overlay = MagicMock()
    overlay.panel_rect = (10, 20, 100, 50)
    help_overlay = HelpOverlay()
    overlay_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    view_state = MagicMock()
    view_state.help_visible = True
    view_state.focus_descriptor = RowDescriptor(RowKind.TRANSPORT)

    OverlayDrawer.draw_tuning(
        compositor,
        overlay,
        overlay_surface,
        view_state,
        overlay_visible=False,
        help_overlay=help_overlay,
    )

    compositor.draw_overlay.assert_called_once_with(11, 10, 20, 100, 50)
    assert help_overlay.panel_rect is None


def test_draw_timeline_overlay_uses_display_target() -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.upload_overlay_texture.return_value = 22

    overlay = MagicMock()
    overlay.panel_rect = (0, 600, 1280, 120)
    overlay.header_badge_rect = None
    overlay_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    view_state = TimelineViewState(
        layer_z_order=["layer_1"],
        cues=[],
        defaults={},
        position_sec=0.0,
        duration_sec=120.0,
        focus_row=0,
        monitor_visible={"layer_1": True},
        timeline_visible={"layer_1": True},
        override_slots=set(),
        armed_slots=set(),
        recording=False,
        record_start_sec=0.0,
        record_baseline={},
        record_buffer=[],
        enabled=True,
    )

    OverlayDrawer.draw_timeline(
        compositor, overlay, overlay_surface, view_state
    )

    compositor.draw_overlay.assert_called_once_with(22, 0, 600, 1280, 120, 1.0)
    compositor.draw_content_overlay.assert_not_called()


def test_draw_timeline_overlay_applies_visibility_alpha() -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.upload_overlay_texture.return_value = 33

    overlay = MagicMock()
    overlay.panel_rect = (0, 600, 1280, 120)
    overlay.header_badge_rect = None
    overlay_surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    view_state = TimelineViewState(
        layer_z_order=["layer_1"],
        cues=[],
        defaults={},
        position_sec=0.0,
        duration_sec=120.0,
        focus_row=0,
        monitor_visible={"layer_1": True},
        timeline_visible={"layer_1": True},
        override_slots=set(),
        armed_slots=set(),
        recording=False,
        record_start_sec=0.0,
        record_baseline={},
        record_buffer=[],
        enabled=True,
    )

    OverlayDrawer.draw_timeline(
        compositor,
        overlay,
        overlay_surface,
        view_state,
        visibility=0.4,
    )

    compositor.draw_overlay.assert_called_once_with(33, 0, 600, 1280, 120, 0.4)
