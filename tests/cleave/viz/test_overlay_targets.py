"""Tests that live UI overlays target the display framebuffer."""

from __future__ import annotations

from unittest.mock import ANY, MagicMock, patch

import pygame

from cleave.gl_compositor import OverlayTextureSlot
from cleave.viz.help_overlay import HelpOverlay
from cleave.viz.overlay_draw import OverlayDrawer
from cleave.viz.overlay_profiler import OverlayProfiler
from cleave.viz.overlay_upload import OverlayGpuState, UploadPlan, UploadSignature
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.tuning_panel_draw import ComposedTuningPanel
from cleave.viz.timeline_overlay import ComposedTimelinePanel, TimelineViewState
from tests.support.compositor_mock import recording_compositor


def _overlay_surface_mock() -> MagicMock:
    surface = MagicMock()
    surface.get_size.return_value = (1280, 720)
    return surface


def _mock_tuning_compose(
    overlay: MagicMock,
    *,
    screen_rect: tuple[int, int, int, int] = (10, 20, 100, 50),
) -> None:
    px, py, pw, ph = screen_rect
    panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
    upload_signature = UploadSignature(
        active_size=(pw, ph),
        screen_rect=screen_rect,
        content_hash=(1,),
    )
    upload_plan = UploadPlan(
        mode="full",
        dirty_rects=((0, 0, pw, ph),),
        active_size=(pw, ph),
        screen_rect=screen_rect,
    )
    overlay.compose_panel.return_value = ComposedTuningPanel(
        upload_surface=panel_surf,
        panel_size=(pw, ph),
        screen_rect=screen_rect,
        upload_plan=upload_plan,
        upload_signature=upload_signature,
        capacity=(pw, ph),
    )
    overlay.gpu_state = OverlayGpuState()
    overlay.panel_rect = screen_rect


def test_draw_tuning_overlay_uses_display_target() -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.ensure_overlay_texture.return_value = 11
    compositor.upload_overlay_region.return_value = 11

    overlay = MagicMock()
    _mock_tuning_compose(overlay)
    overlay_surface = _overlay_surface_mock()

    OverlayDrawer.draw_tuning(compositor, overlay, overlay_surface, MagicMock())

    overlay.compose_panel.assert_called_once()
    overlay_surface.fill.assert_not_called()
    compositor.ensure_overlay_texture.assert_called_once()
    compositor.upload_overlay_region.assert_called_once()
    compositor.upload_overlay_texture.assert_not_called()
    compositor.draw_overlay.assert_called_once_with(11, 10, 20, 100, 50, 1.0, None)
    compositor.draw_content_overlay.assert_not_called()


def test_draw_tuning_overlay_uploads_help_panel() -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.ensure_overlay_texture.side_effect = [11, 22]
    compositor.upload_overlay_region.return_value = 22

    overlay = MagicMock()
    _mock_tuning_compose(overlay)
    help_overlay = HelpOverlay()
    view_state = MagicMock()
    view_state.help_visible = True
    view_state.focus_descriptor = RowDescriptor(RowKind.TRANSPORT)
    view_state.render_timeline.enabled = False
    view_state.timeline_submenu_focused = False
    view_state.paused = False
    view_state.timeline_recording = False
    view_state.timeline_override_active = False
    view_state.tracks = {}
    overlay_surface = _overlay_surface_mock()
    help_warm = help_overlay.compose_panel(
        view_state.focus_descriptor,
        viewport_width=1280,
        viewport_height=720,
    )
    assert help_warm is not None
    help_capacity = help_warm.capacity

    OverlayDrawer.draw_tuning(
        compositor,
        overlay,
        overlay_surface,
        view_state,
        help_overlay=help_overlay,
    )

    overlay_surface.fill.assert_not_called()
    assert compositor.draw_overlay.call_count == 2
    compositor.draw_overlay.assert_any_call(11, 10, 20, 100, 50, 1.0, None)
    help_panel = help_overlay.panel_rect
    assert help_panel is not None
    compositor.draw_overlay.assert_any_call(22, *help_panel, 1.0, ANY)
    assert compositor.ensure_overlay_texture.call_count == 2
    compositor.ensure_overlay_texture.assert_any_call(
        OverlayTextureSlot.TUNING, 100, 50
    )
    compositor.ensure_overlay_texture.assert_any_call(
        OverlayTextureSlot.HELP,
        help_capacity[0],
        help_capacity[1],
    )
    compositor.upload_overlay_texture.assert_not_called()
    assert compositor.upload_overlay_region.call_count == 2


def test_draw_tuning_overlay_hides_help_when_overlay_hidden() -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.ensure_overlay_texture.return_value = 11
    compositor.upload_overlay_region.return_value = 11

    overlay = MagicMock()
    _mock_tuning_compose(overlay)
    help_overlay = HelpOverlay()
    view_state = MagicMock()
    view_state.help_visible = True
    view_state.focus_descriptor = RowDescriptor(RowKind.TRANSPORT)
    overlay_surface = _overlay_surface_mock()

    OverlayDrawer.draw_tuning(
        compositor,
        overlay,
        overlay_surface,
        view_state,
        overlay_visible=False,
        help_overlay=help_overlay,
    )

    overlay_surface.fill.assert_not_called()
    compositor.draw_overlay.assert_called_once_with(11, 10, 20, 100, 50, 1.0, None)
    compositor.upload_overlay_texture.assert_not_called()
    assert help_overlay.panel_rect is None


def test_draw_tuning_modal_path_clears_full_viewport() -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.upload_overlay_texture.return_value = 99

    overlay = MagicMock()
    overlay._font_get.return_value = pygame.font.SysFont("monospace", 14)
    overlay._line_gap = 2
    modal_host = MagicMock()
    modal_host.active = True
    modal_host.view_state.return_value = MagicMock()
    overlay_surface = _overlay_surface_mock()

    with patch("cleave.viz.overlay_draw.modal_overlay.draw"):
        OverlayDrawer.draw_tuning(
            compositor,
            overlay,
            overlay_surface,
            MagicMock(),
            modal_host=modal_host,
        )

    overlay_surface.fill.assert_called_once_with((0, 0, 0, 0))
    overlay.draw.assert_called_once()
    overlay.compose_panel.assert_not_called()
    compositor.draw_overlay.assert_called_once_with(99, 0, 0, 1280, 720)


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
    overlay.compose_panel.return_value = ComposedTimelinePanel(
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

    compositor.draw_overlay.assert_called_once_with(33, 0, 580, 1280, 140, 0.4, None)


def test_draw_tuning_overlay_notes_upload_plan_on_profiler() -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.ensure_overlay_texture.return_value = 11
    compositor.upload_overlay_region.return_value = 11

    overlay = MagicMock()
    screen_rect = (10, 20, 100, 50)
    px, py, pw, ph = screen_rect
    panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
    upload_plan = UploadPlan(
        mode="skip",
        dirty_rects=(),
        active_size=(pw, ph),
        screen_rect=screen_rect,
    )
    overlay.compose_panel.return_value = ComposedTuningPanel(
        upload_surface=panel_surf,
        panel_size=(pw, ph),
        screen_rect=screen_rect,
        upload_plan=upload_plan,
        upload_signature=UploadSignature(
            active_size=(pw, ph),
            screen_rect=screen_rect,
            content_hash=(1,),
        ),
        capacity=(pw, ph),
    )
    overlay.gpu_state = OverlayGpuState(last_texture_id=11)

    profiler = OverlayProfiler(enabled=True, emit_interval_frames=999)
    overlay_surface = _overlay_surface_mock()

    OverlayDrawer.draw_tuning(
        compositor,
        overlay,
        overlay_surface,
        MagicMock(),
        profiler=profiler,
    )

    sample = profiler.finish_frame()
    assert sample is not None
    assert sample.upload_skipped == 1
    compositor.consume_texture_reallocs.assert_called_once()
