"""OpenGL integration: soft pattern-mask composite must blend weight-gated layers."""

from __future__ import annotations

import pytest

pygame = pytest.importorskip("pygame")
from OpenGL.GL import (  # noqa: E402
    GL_COLOR_BUFFER_BIT,
    GL_FRAMEBUFFER,
    GL_RGBA,
    GL_UNSIGNED_BYTE,
    glBindFramebuffer,
    glClear,
    glClearColor,
    glReadPixels,
)

from cleave.gl_compositor import GlCompositor  # noqa: E402
from cleave.gl_masked_compositor import GlMaskedCompositor, PatternMaskParams  # noqa: E402
from cleave.pattern_mask import lerp_hard_layout_1d  # noqa: E402

W, H = 64, 32


@pytest.fixture
def gl_context():
    pygame.init()
    pygame.display.set_mode((W * 2, H * 2), pygame.OPENGL | pygame.DOUBLEBUF)
    comp = GlCompositor(
        content_width=W,
        content_height=H,
        display_width=W * 2,
        display_height=H * 2,
    )
    comp.init()
    masked = GlMaskedCompositor(W, H)
    masked.init()
    try:
        yield comp, masked
    finally:
        masked.release()
        comp.destroy()
        pygame.quit()


def _fill_layer(layer, rgb: tuple[float, float, float]) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, layer.fbo_id)
    glClearColor(rgb[0], rgb[1], rgb[2], 1.0)
    glClear(GL_COLOR_BUFFER_BIT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)


def _read_content_pixel(
    comp: GlCompositor, x: int, y: int
) -> tuple[int, ...]:
    glBindFramebuffer(GL_FRAMEBUFFER, comp.content_fbo_id)
    raw = glReadPixels(x, y, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    return tuple(raw)


def test_hard_composite_splits_layers_by_strips(gl_context) -> None:
    comp, masked = gl_context
    left = comp.create_layer_fbo("left", W, H, opacity=1.0, blend_mode="black-key")
    right = comp.create_layer_fbo("right", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(left, (1.0, 0.0, 0.0))
    _fill_layer(right, (0.0, 0.0, 1.0))

    masked.composite(
        comp.content_fbo_id,
        [left, right],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
    )

    left_px = _read_content_pixel(comp, W // 4, H // 2)
    right_px = _read_content_pixel(comp, 3 * W // 4, H // 2)
    assert left_px[0] > 200 and left_px[2] < 40, f"left={left_px}"
    assert right_px[2] > 200 and right_px[0] < 40, f"right={right_px}"


def test_soft_composite_accepts_generated_strips_weights(gl_context) -> None:
    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 1.0, 0.0))
    _fill_layer(b, (0.0, 1.0, 1.0))

    masked.composite(
        comp.content_fbo_id,
        [a, b],
        mask_type="strips",
        feather_pct=100,
        density=1.0,
    )

    mid = _read_content_pixel(comp, W // 2, H // 2)
    # Soft strips with density 1.0x still light the frame (not all black).
    assert max(mid[:3]) > 20, f"mid={mid}"


def test_soft_plasma_composite_does_not_crash(gl_context) -> None:
    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 0.0, 0.0))
    _fill_layer(b, (0.0, 0.0, 1.0))

    masked.composite(
        comp.content_fbo_id,
        [a, b],
        mask_type="plasma",
        feather_pct=100,
        density=2.0,
        seed=7,
    )

    px = _read_content_pixel(comp, W // 2, H // 2)
    assert max(px[:3]) > 10, f"plasma soft composite produced black frame: {px}"


def test_plasma_hard_gpu_restores_full_viewport(gl_context) -> None:
    comp, masked = gl_context
    assert masked._ctx is not None
    masked._ctx.viewport = (0, 0, W, H)
    gen_w, gen_h = W, H
    params = PatternMaskParams(
        mask_type="plasma",
        feather_pct=0,
        density=2.0,
        invert=False,
        seed=3,
    )

    masked._generate_plasma_hard_gpu(
        gen_width=gen_w,
        gen_height=gen_h,
        layer_count=2,
        params=params,
    )

    assert masked._ctx.viewport == (0, 0, W, H)


def test_plasma_hard_composite_fills_content_frame(gl_context) -> None:
    comp, masked = gl_context
    left = comp.create_layer_fbo("left", W, H, opacity=1.0, blend_mode="black-key")
    right = comp.create_layer_fbo("right", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(left, (1.0, 0.0, 0.0))
    _fill_layer(right, (0.0, 0.0, 1.0))

    masked.composite(
        comp.content_fbo_id,
        [left, right],
        mask_type="plasma",
        feather_pct=0,
        density=2.0,
        seed=5,
    )

    corner = _read_content_pixel(comp, W - 2, H - 2)
    assert max(corner[:3]) > 10, f"plasma hard left content corner black: {corner}"


def test_mask_cache_skips_regeneration(gl_context) -> None:
    comp, masked = gl_context
    layer = comp.create_layer_fbo("solo", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(layer, (1.0, 0.0, 0.0))

    masked.composite(
        comp.content_fbo_id,
        [layer],
        mask_type="strips",
        feather_pct=0,
        density=2.0,
        seed=1,
    )
    first_key = masked._mask_cache_key

    masked.composite(
        comp.content_fbo_id,
        [layer],
        mask_type="strips",
        feather_pct=0,
        density=2.0,
        seed=1,
    )
    assert masked._mask_cache_key is first_key


def _is_hard_primary(px: tuple[int, ...]) -> bool:
    highs = sum(1 for channel in px[:3] if channel > 200)
    lows = sum(1 for channel in px[:3] if channel < 40)
    return highs == 1 and lows == 2


def test_transition_blends_weights_over_song_time(gl_context) -> None:
    """Hard 2-to-3 strips: disputed band moves before t=0.5; one winner per pixel."""
    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    c = comp.create_layer_fbo("c", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 0.0, 0.0))
    _fill_layer(b, (0.0, 1.0, 0.0))
    _fill_layer(c, (0.0, 0.0, 1.0))

    masked.composite(
        comp.content_fbo_id,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, False],
        song_time_sec=0.0,
        transition_duration=1.0,
    )
    assert masked._transition_old_layout is None
    right_before = _read_content_pixel(comp, W - 2, H // 2)
    assert right_before[1] > 200 and right_before[0] < 40, f"t0 right={right_before}"

    c.enabled = True
    masked.composite(
        comp.content_fbo_id,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=0.0,
        transition_duration=1.0,
    )
    assert masked._transition_old_layout is not None
    assert masked._transition_target_layout is not None
    right_t0 = _read_content_pixel(comp, W - 2, H // 2)
    assert right_t0[1] > 200 and right_t0[2] < 40, f"morph t=0 right={right_t0}"

    masked.composite(
        comp.content_fbo_id,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=0.25,
        transition_duration=1.0,
    )
    right_t25 = _read_content_pixel(comp, W - 2, H // 2)
    assert right_t25[2] > 200 and right_t25[1] < 40, f"t=0.25 right={right_t25}"
    assert right_t25 != right_t0
    for x in (W // 8, W // 2, W - 2):
        px = _read_content_pixel(comp, x, H // 2)
        assert _is_hard_primary(px), f"mixed pixel at x={x}: {px}"

    masked.composite(
        comp.content_fbo_id,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=1.0,
        transition_duration=1.0,
    )
    assert masked._transition_old_layout is None
    left_px = _read_content_pixel(comp, W // 6, H // 2)
    assert left_px[0] > 200, f"after transition left={left_px}"


def test_mid_transition_retarget_snapshots_blend(gl_context) -> None:
    import numpy as np

    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    c = comp.create_layer_fbo("c", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 0.0, 0.0))
    _fill_layer(b, (0.0, 1.0, 0.0))
    _fill_layer(c, (0.0, 0.0, 1.0))

    masked.composite(
        comp.content_fbo_id,
        [a, b, c],
        mask_type="strips",
        feather_pct=100,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=0.0,
        transition_duration=2.0,
    )
    b.enabled = False
    masked.composite(
        comp.content_fbo_id,
        [a, b, c],
        mask_type="strips",
        feather_pct=100,
        density=1.0,
        active_slots=[True, False, True],
        song_time_sec=0.0,
        transition_duration=2.0,
    )
    first_old = masked._transition_old_weights.copy()
    c.enabled = False
    masked.composite(
        comp.content_fbo_id,
        [a, b, c],
        mask_type="strips",
        feather_pct=100,
        density=1.0,
        active_slots=[True, False, False],
        song_time_sec=0.5,
        transition_duration=2.0,
    )
    assert masked._transition_start == 0.5
    assert not np.array_equal(masked._transition_old_weights, first_old)


def test_hard_path_retarget_continues_from_inflight_cuts(gl_context) -> None:
    """A slot change during a hard wipe snapshots the lerped cuts as the new old."""
    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    c = comp.create_layer_fbo("c", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 0.0, 0.0))
    _fill_layer(b, (0.0, 1.0, 0.0))
    _fill_layer(c, (0.0, 0.0, 1.0))

    masked.composite(
        comp.content_fbo_id,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=0.0,
        transition_duration=2.0,
    )
    b.enabled = False
    masked.composite(
        comp.content_fbo_id,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, False, True],
        song_time_sec=0.0,
        transition_duration=2.0,
    )
    first_old = masked._transition_old_layout
    first_target = masked._transition_target_layout
    assert first_old is not None
    assert first_target is not None

    c.enabled = False
    masked.composite(
        comp.content_fbo_id,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, False, False],
        song_time_sec=0.25,
        transition_duration=2.0,
    )
    assert masked._transition_start == 0.25
    expected_old = lerp_hard_layout_1d(first_old, first_target, 0.25 / 2.0)
    assert masked._transition_old_layout == expected_old
    # Static 1-active would be all red; in-flight cuts still own the right band.
    right_px = _read_content_pixel(comp, 3 * W // 4, H // 2)
    assert right_px[0] < 200, f"retarget jumped to target: right={right_px}"
    assert _is_hard_primary(right_px), f"retarget mixed pixel: {right_px}"


def test_live_slots_matches_active_when_idle() -> None:
    masked = GlMaskedCompositor(W, H)
    assert masked.live_slots((True, False, True), 0.0, 1.0) == (True, False, True)
    assert masked.live_slots((False, False), 0.5, 0.0) == (False, False)


def test_live_slots_departing_hard_layout_until_width_zero(gl_context) -> None:
    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    c = comp.create_layer_fbo("c", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 0.0, 0.0))
    _fill_layer(b, (0.0, 1.0, 0.0))
    _fill_layer(c, (0.0, 0.0, 1.0))

    masked.composite(
        comp.content_fbo_id,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=0.0,
        transition_duration=1.0,
    )
    assert masked.live_slots((True, True, True), 0.0, 1.0) == (True, True, True)
    assert masked.live_slots((True, True, False), 0.0, 1.0) == (True, True, True)

    c.enabled = False
    masked.composite(
        comp.content_fbo_id,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, False],
        song_time_sec=0.0,
        transition_duration=1.0,
    )
    assert masked.live_slots((True, True, False), 0.25, 1.0) == (True, True, True)
    assert masked.live_slots((True, True, False), 1.0, 1.0) == (True, True, False)

    masked.composite(
        comp.content_fbo_id,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, False],
        song_time_sec=1.0,
        transition_duration=1.0,
    )
    assert masked.live_slots((True, True, False), 1.0, 1.0) == (True, True, False)
