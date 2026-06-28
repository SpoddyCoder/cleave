"""Tests for overlay upload planning and coordinator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pygame
import pytest

from cleave.gl_compositor import OverlayTextureSlot
from cleave.viz.overlay_upload import (
    OverlayGpuState,
    OverlayUploadCoordinator,
    UploadPlan,
    UploadSignature,
    clip_dirty_rects,
    present_overlay,
    tex_uv_for_active,
    upload_plan_for_signature,
)
from tests.support.compositor_mock import recording_compositor


def _signature(
    *,
    active_size: tuple[int, int] = (100, 50),
    screen_rect: tuple[int, int, int, int] = (10, 20, 100, 50),
    content_hash: tuple = (1, "panel"),
) -> UploadSignature:
    return UploadSignature(
        active_size=active_size,
        screen_rect=screen_rect,
        content_hash=content_hash,
    )


def test_upload_plan_skip_when_signature_equal() -> None:
    sig = _signature()
    plan = upload_plan_for_signature(sig, sig)
    assert plan.mode == "skip"
    assert plan.dirty_rects == ()
    assert plan.active_size == sig.active_size
    assert plan.screen_rect == sig.screen_rect


def test_upload_plan_full_when_signature_new() -> None:
    sig = _signature(active_size=(120, 80))
    plan = upload_plan_for_signature(sig, None)
    assert plan.mode == "full"
    assert plan.dirty_rects == ((0, 0, 120, 80),)
    assert plan.active_size == (120, 80)


def test_upload_plan_partial_when_dirty_rects_passed() -> None:
    sig = _signature(content_hash=(2, "changed"))
    dirty = ((5, 10, 30, 20), (40, 0, 20, 15))
    plan = upload_plan_for_signature(sig, None, dirty_rects=dirty)
    assert plan.mode == "partial"
    assert plan.dirty_rects == dirty


def test_upload_plan_skip_wins_over_dirty_rects() -> None:
    sig = _signature()
    plan = upload_plan_for_signature(sig, sig, dirty_rects=((0, 0, 10, 10),))
    assert plan.mode == "skip"
    assert plan.dirty_rects == ()


def test_tex_uv_for_active_subregion() -> None:
    assert tex_uv_for_active((200, 100), (100, 50)) == (0.0, 0.0, 0.5, 0.5)


def test_tex_uv_for_active_full_capacity() -> None:
    assert tex_uv_for_active((100, 50), (100, 50)) == (0.0, 0.0, 1.0, 1.0)


def test_clip_dirty_rects_clips_to_bounds() -> None:
    rects = (
        (-5, 0, 20, 10),
        (90, 40, 30, 30),
        (10, 10, 0, 5),
        (5, 5, 10, 10),
    )
    clipped = clip_dirty_rects(rects, active_w=100, active_h=50)
    assert clipped == (
        (0, 0, 15, 10),
        (90, 40, 10, 10),
        (5, 5, 10, 10),
    )


def test_coordinator_skip_does_not_call_compositor_upload() -> None:
    compositor = recording_compositor()
    compositor.ensure_overlay_texture = MagicMock(name="ensure_overlay_texture")
    compositor.upload_overlay_region = MagicMock(name="upload_overlay_region")
    compositor.overlay_texture_capacity.return_value = (200, 100)

    sig = _signature()
    gpu_state = OverlayGpuState(
        capacity=(200, 100),
        last_signature=sig,
        last_texture_id=42,
    )
    plan = UploadPlan(
        mode="skip",
        dirty_rects=(),
        active_size=sig.active_size,
        screen_rect=sig.screen_rect,
    )
    coordinator = OverlayUploadCoordinator()
    surface = pygame.Surface((100, 50), pygame.SRCALPHA)

    texture_id, tex_uv = coordinator.upload(
        compositor,
        OverlayTextureSlot.TUNING,
        surface,
        plan,
        capacity=(200, 100),
        gpu_state=gpu_state,
        signature=sig,
    )

    assert texture_id == 42
    assert tex_uv == (0.0, 0.0, 0.5, 0.5)
    compositor.ensure_overlay_texture.assert_not_called()
    compositor.upload_overlay_region.assert_not_called()
    assert gpu_state.last_texture_id == 42
    assert gpu_state.last_signature == sig


def test_coordinator_skip_requires_prior_texture() -> None:
    compositor = recording_compositor()
    sig = _signature()
    plan = UploadPlan(
        mode="skip",
        dirty_rects=(),
        active_size=sig.active_size,
        screen_rect=sig.screen_rect,
    )
    coordinator = OverlayUploadCoordinator()
    surface = pygame.Surface((100, 50), pygame.SRCALPHA)

    with pytest.raises(ValueError, match="previously uploaded texture"):
        coordinator.upload(
            compositor,
            OverlayTextureSlot.TUNING,
            surface,
            plan,
            capacity=(200, 100),
            gpu_state=OverlayGpuState(),
            signature=sig,
        )


def test_coordinator_full_uploads_at_origin() -> None:
    compositor = recording_compositor()
    compositor.ensure_overlay_texture.return_value = 7
    compositor.upload_overlay_region.return_value = 7
    compositor.overlay_texture_capacity.return_value = (200, 100)

    sig = _signature(active_size=(100, 50))
    plan = upload_plan_for_signature(sig, None)
    gpu_state = OverlayGpuState()
    coordinator = OverlayUploadCoordinator()
    surface = pygame.Surface((100, 50), pygame.SRCALPHA)

    texture_id, tex_uv = coordinator.upload(
        compositor,
        OverlayTextureSlot.HELP,
        surface,
        plan,
        capacity=(200, 100),
        gpu_state=gpu_state,
        signature=sig,
    )

    assert texture_id == 7
    assert tex_uv == (0.0, 0.0, 0.5, 0.5)
    compositor.ensure_overlay_texture.assert_called_once_with(
        OverlayTextureSlot.HELP, 200, 100
    )
    compositor.upload_overlay_region.assert_called_once_with(
        OverlayTextureSlot.HELP,
        surface,
        dest_x=0,
        dest_y=0,
        active_w=100,
        active_h=50,
    )


def test_coordinator_partial_uploads_each_dirty_rect() -> None:
    compositor = recording_compositor()
    compositor.ensure_overlay_texture.return_value = 9
    compositor.upload_overlay_region.return_value = 9
    compositor.overlay_texture_capacity.return_value = (100, 50)

    sig = _signature(active_size=(100, 50), content_hash=(3,))
    dirty = ((0, 0, 40, 20), (50, 30, 25, 15))
    plan = upload_plan_for_signature(sig, None, dirty_rects=dirty)
    gpu_state = OverlayGpuState()
    coordinator = OverlayUploadCoordinator()
    surface = pygame.Surface((100, 50), pygame.SRCALPHA)

    texture_id, tex_uv = coordinator.upload(
        compositor,
        OverlayTextureSlot.TIMELINE,
        surface,
        plan,
        capacity=(100, 50),
        gpu_state=gpu_state,
        signature=sig,
    )

    assert texture_id == 9
    assert tex_uv is None
    compositor.ensure_overlay_texture.assert_called_once_with(
        OverlayTextureSlot.TIMELINE, 100, 50
    )
    assert compositor.upload_overlay_region.call_count == 2
    first_call = compositor.upload_overlay_region.call_args_list[0]
    assert first_call.args[0] == OverlayTextureSlot.TIMELINE
    assert first_call.kwargs == {"dest_x": 0, "dest_y": 0}
    second_call = compositor.upload_overlay_region.call_args_list[1]
    assert second_call.kwargs == {"dest_x": 50, "dest_y": 30}


def test_coordinator_updates_gpu_state_after_upload() -> None:
    compositor = recording_compositor()
    compositor.ensure_overlay_texture.return_value = 11
    compositor.upload_overlay_region.return_value = 11
    compositor.overlay_texture_capacity.return_value = (150, 75)

    sig = _signature(content_hash=("fresh",))
    plan = upload_plan_for_signature(sig, None)
    gpu_state = OverlayGpuState()
    coordinator = OverlayUploadCoordinator()
    surface = pygame.Surface((100, 50), pygame.SRCALPHA)

    coordinator.upload(
        compositor,
        OverlayTextureSlot.TUNING,
        surface,
        plan,
        capacity=(150, 75),
        gpu_state=gpu_state,
        signature=sig,
    )

    assert gpu_state.last_texture_id == 11
    assert gpu_state.last_signature == sig
    assert gpu_state.capacity == (150, 75)


def test_coordinator_tex_uv_uses_gl_capacity_not_logical() -> None:
    """Logical capacity can shrink while the GL texture keeps its larger size."""
    compositor = recording_compositor()
    compositor.ensure_overlay_texture.return_value = 7
    compositor.upload_overlay_region.return_value = 7
    compositor.overlay_texture_capacity.return_value = (400, 600)

    sig = _signature(active_size=(400, 280), screen_rect=(10, 20, 400, 280))
    plan = upload_plan_for_signature(sig, None)
    gpu_state = OverlayGpuState()
    coordinator = OverlayUploadCoordinator()
    surface = pygame.Surface((400, 280), pygame.SRCALPHA)

    _, tex_uv = coordinator.upload(
        compositor,
        OverlayTextureSlot.TUNING,
        surface,
        plan,
        capacity=(400, 450),
        gpu_state=gpu_state,
        signature=sig,
    )

    assert tex_uv == tex_uv_for_active((400, 600), (400, 280))
    assert gpu_state.capacity == (400, 600)

    skip_plan = UploadPlan(
        mode="skip",
        dirty_rects=(),
        active_size=sig.active_size,
        screen_rect=sig.screen_rect,
    )
    _, skip_uv = coordinator.upload(
        compositor,
        OverlayTextureSlot.TUNING,
        surface,
        skip_plan,
        capacity=(400, 450),
        gpu_state=gpu_state,
        signature=sig,
    )
    assert skip_uv == tex_uv


def test_present_overlay_calls_draw_overlay() -> None:
    compositor = recording_compositor()
    tex_uv = (0.0, 0.0, 0.5, 0.5)

    present_overlay(compositor, 3, (10, 20, 100, 50), tex_uv=tex_uv, alpha=0.8)

    compositor.draw_overlay.assert_called_once_with(
        3, 10, 20, 100, 50, 0.8, tex_uv
    )
