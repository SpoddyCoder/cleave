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
        mode="hard",
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
        mode="soft",
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
        mode="soft",
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
        mode="hard",
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
        mode="hard",
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
        mode="hard",
        density=2.0,
        seed=1,
    )
    first_key = masked._mask_cache_key

    masked.composite(
        comp.content_fbo_id,
        [layer],
        mask_type="strips",
        mode="hard",
        density=2.0,
        seed=1,
    )
    assert masked._mask_cache_key is first_key
