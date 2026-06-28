"""Tests for help panel cache and GPU upload signatures."""

from __future__ import annotations

from unittest.mock import patch

import pygame

from cleave.viz.help_overlay import HelpOverlay
from cleave.viz.help_panel_cache import (
    HelpPanelCache,
    help_content_signature,
    help_upload_signature,
)
from cleave.viz.overlay_upload import OverlayGpuState, upload_plan_for_signature
from cleave.viz.row_semantics import RowDescriptor, RowKind


def test_help_content_signature_stable_for_same_inputs() -> None:
    focus = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    sig_a = help_content_signature(
        focus,
        timeline_enabled=False,
        timeline_submenu_focused=False,
        paused=False,
        timeline_recording=False,
        timeline_override_active=False,
        preset_switching=None,
    )
    sig_b = help_content_signature(
        focus,
        timeline_enabled=False,
        timeline_submenu_focused=False,
        paused=False,
        timeline_recording=False,
        timeline_override_active=False,
        preset_switching=None,
    )
    assert sig_a == sig_b


def test_help_content_signature_changes_on_focus_change() -> None:
    transport = help_content_signature(
        RowDescriptor(RowKind.TRANSPORT),
        timeline_enabled=False,
        timeline_submenu_focused=False,
        paused=False,
        timeline_recording=False,
        timeline_override_active=False,
        preset_switching=None,
    )
    track = help_content_signature(
        RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"),
        timeline_enabled=False,
        timeline_submenu_focused=False,
        paused=False,
        timeline_recording=False,
        timeline_override_active=False,
        preset_switching=None,
    )
    assert transport != track


def test_compose_panel_cpu_cache_hit_reuses_panel_surface() -> None:
    pygame.init()
    overlay = HelpOverlay()
    focus = RowDescriptor(RowKind.TRANSPORT)
    kwargs = dict(
        viewport_width=1280,
        viewport_height=720,
        timeline_enabled=False,
        timeline_submenu_focused=False,
        paused=False,
        timeline_recording=False,
        timeline_override_active=False,
        preset_switching=None,
    )

    with patch.object(overlay, "_build_panel_surface", wraps=overlay._build_panel_surface) as build:
        first = overlay.compose_panel(focus, **kwargs)
        second = overlay.compose_panel(focus, **kwargs)

    assert first is not None
    assert second is not None
    assert build.call_count == 1
    assert first.upload_surface is second.upload_surface


def test_upload_plan_full_on_first_frame() -> None:
    pygame.init()
    overlay = HelpOverlay()
    composed = overlay.compose_panel(
        RowDescriptor(RowKind.TRANSPORT),
        viewport_width=1280,
        viewport_height=720,
    )
    assert composed is not None
    assert composed.upload_plan.mode == "full"


def test_upload_plan_skip_when_signature_unchanged() -> None:
    pygame.init()
    overlay = HelpOverlay()
    focus = RowDescriptor(RowKind.TRANSPORT)
    kwargs = dict(viewport_width=1280, viewport_height=720)

    first = overlay.compose_panel(focus, **kwargs)
    assert first is not None

    cache = overlay._cache
    cache.gpu.last_signature = first.upload_signature
    cache.gpu.last_texture_id = 1
    cache.gpu.capacity = first.capacity

    second = overlay.compose_panel(focus, **kwargs)
    assert second is not None
    assert second.upload_plan.mode == "skip"


def test_upload_plan_full_on_focus_change() -> None:
    pygame.init()
    overlay = HelpOverlay()
    kwargs = dict(viewport_width=1280, viewport_height=720)

    first = overlay.compose_panel(RowDescriptor(RowKind.TRANSPORT), **kwargs)
    assert first is not None

    cache = overlay._cache
    cache.gpu.last_signature = first.upload_signature
    cache.gpu.last_texture_id = 1
    cache.gpu.capacity = first.capacity

    second = overlay.compose_panel(
        RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1"),
        **kwargs,
    )
    assert second is not None
    assert second.upload_plan.mode == "full"


def test_help_upload_signature_uses_screen_rect_active_size() -> None:
    content_sig = help_content_signature(
        RowDescriptor(RowKind.TRANSPORT),
        timeline_enabled=False,
        timeline_submenu_focused=False,
        paused=False,
        timeline_recording=False,
        timeline_override_active=False,
        preset_switching=None,
    )
    screen_rect = (1000, 10, 260, 180)
    upload_sig = help_upload_signature(content_sig, screen_rect, (260, 180))
    assert upload_sig.active_size == (260, 180)
    assert upload_sig.screen_rect == screen_rect
    assert upload_sig.content_hash == (content_sig,)


def test_help_panel_cache_gpu_state_defaults() -> None:
    cache = HelpPanelCache()
    assert isinstance(cache.gpu, OverlayGpuState)
    assert cache.gpu.last_signature is None


def test_upload_plan_for_signature_skip_matches_help_path() -> None:
    pygame.init()
    overlay = HelpOverlay()
    composed = overlay.compose_panel(
        RowDescriptor(RowKind.TRANSPORT),
        viewport_width=1280,
        viewport_height=720,
    )
    assert composed is not None
    plan = upload_plan_for_signature(
        composed.upload_signature,
        composed.upload_signature,
    )
    assert plan.mode == "skip"
