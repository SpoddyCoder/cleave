"""GPU overlay upload planning and execution for stable-size textures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pygame

from cleave.gl_compositor import GlCompositor, OverlayTextureSlot

UploadMode = Literal["skip", "partial", "full"]


@dataclass(frozen=True)
class UploadSignature:
    """Hashable signature of everything that affects GPU texels for one overlay frame."""

    active_size: tuple[int, int]
    screen_rect: tuple[int, int, int, int]
    content_hash: tuple


@dataclass(frozen=True)
class UploadPlan:
    mode: UploadMode
    dirty_rects: tuple[tuple[int, int, int, int], ...]
    active_size: tuple[int, int]
    screen_rect: tuple[int, int, int, int]


@dataclass
class OverlayGpuState:
    """Per-overlay GPU upload cache state (lives on overlay cache objects in todo 3+)."""

    capacity: tuple[int, int] | None = None
    last_signature: UploadSignature | None = None
    last_texture_id: int = 0


def upload_plan_for_signature(
    signature: UploadSignature,
    last: UploadSignature | None,
    *,
    dirty_rects: tuple[tuple[int, int, int, int], ...] = (),
) -> UploadPlan:
    if signature == last:
        return UploadPlan(
            mode="skip",
            dirty_rects=(),
            active_size=signature.active_size,
            screen_rect=signature.screen_rect,
        )
    if dirty_rects:
        return UploadPlan(
            mode="partial",
            dirty_rects=dirty_rects,
            active_size=signature.active_size,
            screen_rect=signature.screen_rect,
        )
    pw, ph = signature.active_size
    return UploadPlan(
        mode="full",
        dirty_rects=((0, 0, pw, ph),),
        active_size=signature.active_size,
        screen_rect=signature.screen_rect,
    )


def tex_uv_for_active(
    capacity: tuple[int, int],
    active_size: tuple[int, int],
) -> tuple[float, float, float, float]:
    cap_w, cap_h = capacity
    active_w, active_h = active_size
    if cap_w <= 0 or cap_h <= 0:
        return (0.0, 0.0, 1.0, 1.0)
    return (0.0, 0.0, active_w / cap_w, active_h / cap_h)


def clip_dirty_rects(
    rects: tuple[tuple[int, int, int, int], ...],
    active_w: int,
    active_h: int,
) -> tuple[tuple[int, int, int, int], ...]:
    clipped: list[tuple[int, int, int, int]] = []
    for rect in rects:
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            continue
        left = max(x, 0)
        top = max(y, 0)
        right = min(x + w, active_w)
        bottom = min(y + h, active_h)
        clip_w = right - left
        clip_h = bottom - top
        if clip_w <= 0 or clip_h <= 0:
            continue
        clipped.append((left, top, clip_w, clip_h))
    return tuple(clipped)


def _tex_uv_for_draw(
    capacity: tuple[int, int],
    active_size: tuple[int, int],
) -> tuple[float, float, float, float] | None:
    if capacity == active_size:
        return None
    return tex_uv_for_active(capacity, active_size)


class OverlayUploadCoordinator:
    """Stateless coordinator for stable-size overlay texture uploads."""

    @staticmethod
    def _texture_capacity(
        compositor: GlCompositor,
        slot: OverlayTextureSlot,
        gpu_state: OverlayGpuState,
        requested_capacity: tuple[int, int],
    ) -> tuple[int, int]:
        """GL texel dimensions for UV mapping (textures never shrink on the GPU)."""
        tex_w, tex_h = compositor.overlay_texture_capacity(slot)
        if tex_w > 0 and tex_h > 0:
            return (tex_w, tex_h)
        stored = gpu_state.capacity
        if stored is not None and stored[0] > 0 and stored[1] > 0:
            return stored
        return requested_capacity

    def upload(
        self,
        compositor: GlCompositor,
        slot: OverlayTextureSlot,
        surface: pygame.Surface,
        plan: UploadPlan,
        capacity: tuple[int, int],
        gpu_state: OverlayGpuState,
        signature: UploadSignature,
    ) -> tuple[int, tuple[float, float, float, float] | None]:
        if plan.mode == "skip":
            if gpu_state.last_texture_id <= 0:
                raise ValueError(
                    "overlay upload skip requires a previously uploaded texture"
                )
            tex_capacity = self._texture_capacity(
                compositor, slot, gpu_state, capacity
            )
            return (
                gpu_state.last_texture_id,
                _tex_uv_for_draw(tex_capacity, plan.active_size),
            )

        capacity_w, capacity_h = capacity
        texture_id = compositor.ensure_overlay_texture(slot, capacity_w, capacity_h)
        tex_capacity = self._texture_capacity(
            compositor, slot, gpu_state, capacity
        )
        active_w, active_h = plan.active_size

        if plan.mode == "full":
            compositor.upload_overlay_region(
                slot,
                surface,
                dest_x=0,
                dest_y=0,
                active_w=active_w,
                active_h=active_h,
            )
        else:
            for rx, ry, rw, rh in plan.dirty_rects:
                region = surface.subsurface((rx, ry, rw, rh))
                compositor.upload_overlay_region(
                    slot,
                    region,
                    dest_x=rx,
                    dest_y=ry,
                )

        gpu_state.capacity = tex_capacity
        gpu_state.last_signature = signature
        gpu_state.last_texture_id = texture_id
        return texture_id, _tex_uv_for_draw(tex_capacity, plan.active_size)


def present_overlay(
    compositor: GlCompositor,
    texture_id: int,
    screen_rect: tuple[int, int, int, int],
    tex_uv: tuple[float, float, float, float] | None = None,
    alpha: float = 1.0,
) -> None:
    x, y, w, h = screen_rect
    compositor.draw_overlay(texture_id, x, y, w, h, alpha, tex_uv)
