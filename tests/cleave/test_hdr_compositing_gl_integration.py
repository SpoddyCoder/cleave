"""OpenGL integration: HDR compositing retains chroma where 8-bit clamps to white."""

from __future__ import annotations

import struct

import pytest

pygame = pytest.importorskip("pygame")
from OpenGL.GL import (  # noqa: E402
    GL_COLOR_BUFFER_BIT,
    GL_FLOAT,
    GL_FRAMEBUFFER,
    GL_RGBA,
    GL_UNSIGNED_BYTE,
    glBindFramebuffer,
    glClear,
    glClearColor,
    glReadPixels,
)

from cleave.gl_color_format import RGBA16F, RGBA8  # noqa: E402
from cleave.gl_compositor import GlCompositor, LayerFbo  # noqa: E402
from cleave.gl_post_process import GlPostProcess  # noqa: E402

W, H = 64, 64
CENTER = (W // 2, H // 2)

# HDR layer energy (>1) on float FBOs; 8-bit clears clamp to [0,1] and stack to white.
HDR_LAYER_COLORS = (
    (1.5, 0.4, 0.2),
    (0.3, 1.3, 0.2),
    (0.2, 0.3, 1.5),
)


def _channel_spread(rgb: tuple[float, ...]) -> float:
    return max(rgb[:3]) - min(rgb[:3])


def _fill_layer_fbo(layer: LayerFbo, rgba: tuple[float, float, float, float]) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, layer.fbo_id)
    glClearColor(*rgba)
    glClear(GL_COLOR_BUFFER_BIT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)


def _read_content_pixel_u8(comp: GlCompositor, x: int, y: int) -> tuple[float, float, float]:
    glBindFramebuffer(GL_FRAMEBUFFER, comp.content_fbo_id)
    raw = glReadPixels(x, y, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    b = bytes(raw)
    return (b[0] / 255.0, b[1] / 255.0, b[2] / 255.0)


def _read_content_pixel_float(
    comp: GlCompositor, x: int, y: int
) -> tuple[float, float, float]:
    glBindFramebuffer(GL_FRAMEBUFFER, comp.content_fbo_id)
    raw = glReadPixels(x, y, 1, 1, GL_RGBA, GL_FLOAT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    r, g, b, _a = struct.unpack("4f", bytes(raw))
    return (r, g, b)


def _make_bright_layers(comp: GlCompositor) -> list[LayerFbo]:
    layers: list[LayerFbo] = []
    for idx, color in enumerate(HDR_LAYER_COLORS):
        layer = comp.create_layer_fbo(
            f"layer_{idx}",
            W,
            H,
            opacity=1.0,
            blend_mode="black-key",
        )
        _fill_layer_fbo(layer, (*color, 1.0))
        layers.append(layer)
    return layers


@pytest.fixture
def gl_context_8bit():
    pygame.init()
    pygame.display.set_mode((W * 2, H * 2), pygame.OPENGL | pygame.DOUBLEBUF)
    comp = GlCompositor(
        content_width=W,
        content_height=H,
        display_width=W * 2,
        display_height=H * 2,
        color_format=RGBA8,
    )
    comp.init()
    pp = GlPostProcess(color_format=RGBA8)
    pp.init()
    try:
        yield comp, pp
    finally:
        pp.destroy()
        comp.destroy()
        pygame.quit()


@pytest.fixture
def gl_context_float():
    pygame.init()
    pygame.display.set_mode((W * 2, H * 2), pygame.OPENGL | pygame.DOUBLEBUF)
    comp = GlCompositor(
        content_width=W,
        content_height=H,
        display_width=W * 2,
        display_height=H * 2,
        color_format=RGBA16F,
    )
    comp.init()
    pp = GlPostProcess(color_format=RGBA16F)
    pp.init()
    try:
        yield comp, pp
    finally:
        pp.destroy()
        comp.destroy()
        pygame.quit()


def test_float_compositor_layer_fbo_end_to_end(gl_context_float) -> None:
    """Float layer FBOs accept glClear fills and composite without error."""
    comp, _pp = gl_context_float
    layers = _make_bright_layers(comp)
    comp.composite(layers)
    rgb = _read_content_pixel_float(comp, *CENTER)
    assert _channel_spread(rgb) > 0.1
    assert max(rgb) > 1.0


def test_stack_bright_layers_8bit_clamps_to_white(gl_context_8bit) -> None:
    comp, _pp = gl_context_8bit
    comp.composite(_make_bright_layers(comp))
    rgb = _read_content_pixel_u8(comp, *CENTER)
    assert _channel_spread(rgb) == pytest.approx(0.0, abs=1e-6)
    assert rgb == pytest.approx((1.0, 1.0, 1.0), abs=1.0 / 255.0)


def test_stack_bright_layers_float_retains_chroma(gl_context_float) -> None:
    comp, _pp = gl_context_float
    comp.composite(_make_bright_layers(comp))
    rgb = _read_content_pixel_float(comp, *CENTER)
    assert _channel_spread(rgb) > 0.1


def test_composite_rolloff_maps_hdr_with_hue(gl_context_float) -> None:
    comp, pp = gl_context_float
    comp.composite(_make_bright_layers(comp))
    before = _read_content_pixel_float(comp, *CENTER)
    assert _channel_spread(before) > 0.1
    assert max(before) > 1.0

    pp.apply_highlight_rolloff(
        comp.content_texture_id,
        comp.content_width,
        comp.content_height,
        threshold=0.78,
        ceiling=0.65,
        strength=0.7,
        softness=0.4,
        desaturation=0.0,
        mode=0,
    )
    after = _read_content_pixel_float(comp, *CENTER)
    assert _channel_spread(after) > 0.02
    assert max(after) < 1.0


def test_float_external_texture_dtype_matches(gl_context_float) -> None:
    comp, pp = gl_context_float
    src = comp.create_layer_fbo("src", W, H)
    dest = comp.create_layer_fbo("dest", W, H)
    chroma = (1.5, 0.8, 0.4, 1.0)
    _fill_layer_fbo(src, chroma)
    pp.copy_texture(src.texture_id, dest.texture_id, W, H)

    glBindFramebuffer(GL_FRAMEBUFFER, dest.fbo_id)
    raw = glReadPixels(*CENTER, 1, 1, GL_RGBA, GL_FLOAT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    r, g, b, _a = struct.unpack("4f", bytes(raw))
    copied = (r, g, b)
    assert _channel_spread(copied) > 0.05
    assert copied == pytest.approx(chroma[:3], rel=0.02, abs=0.02)


def test_u8_external_texture_copy_preserves_chroma(gl_context_8bit) -> None:
    """Regression: 8-bit copy must use f1 internal ping-pong (not u1) or output is black."""
    comp, pp = gl_context_8bit
    src = comp.create_layer_fbo("src", W, H)
    dest = comp.create_layer_fbo("dest", W, H)
    chroma = (0.8, 0.2, 0.1, 1.0)
    _fill_layer_fbo(src, chroma)
    pp.copy_texture(src.texture_id, dest.texture_id, W, H)

    rgb = _read_content_pixel_u8_from_layer(dest)
    assert _channel_spread(rgb) > 0.05
    assert rgb == pytest.approx(chroma[:3], abs=2.0 / 255.0)


def _read_content_pixel_u8_from_layer(layer: LayerFbo) -> tuple[float, float, float]:
    glBindFramebuffer(GL_FRAMEBUFFER, layer.fbo_id)
    raw = glReadPixels(*CENTER, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    b = bytes(raw)
    return (b[0] / 255.0, b[1] / 255.0, b[2] / 255.0)


def test_present_then_read_rgba_frame_uses_default_framebuffer(gl_context_8bit) -> None:
    """Offline render reads 8-bit default FB after present (tone-mapped blit)."""
    comp, _pp = gl_context_8bit
    comp.composite(_make_bright_layers(comp))
    comp.present_content()
    frame = comp.read_rgba_frame()
    assert len(frame) == comp.display_width * comp.display_height * 4
    cx = (comp.display_width // 2) * 4
    row = comp.display_height // 2
    row_stride = comp.display_width * 4
    # read_rgba_frame flips rows; center pixel is white after 8-bit stack.
    offset = (comp.display_height - 1 - row) * row_stride + cx
    assert frame[offset] == 255
    assert frame[offset + 1] == 255
    assert frame[offset + 2] == 255
