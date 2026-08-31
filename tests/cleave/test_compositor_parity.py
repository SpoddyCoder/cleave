"""Mask-on vs mask-off composite parity (soft full-coverage single slot)."""

from __future__ import annotations

import struct

import pytest

from cleave.blend_modes import BLEND_MODES
from cleave.gl_color_format import RGBA16F, RGBA8, GlColorFormat, probe_rgba16f_framebuffer
from cleave.gl_compositor import GlCompositor
from cleave.gl_masked_compositor import GlMaskedCompositor
from cleave.layer_composite import LayerCompositeRequest
from cleave.pattern_mask import PatternMaskParams

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

W, H = 32, 32
_U8_TOL = 3
_F32_TOL = 0.02


@pytest.fixture
def gl_ready():
    pygame.init()
    try:
        pygame.display.set_mode((W * 2, H * 2), pygame.OPENGL | pygame.DOUBLEBUF)
    except pygame.error as exc:
        pygame.quit()
        pytest.skip(f"OpenGL context unavailable: {exc}")
    yield
    pygame.quit()


def _fill_layer(layer, rgb: tuple[float, float, float]) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, layer.fbo_id)
    glClearColor(rgb[0], rgb[1], rgb[2], 1.0)
    glClear(GL_COLOR_BUFFER_BIT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)


def _read_u8(comp: GlCompositor) -> bytes:
    glBindFramebuffer(GL_FRAMEBUFFER, comp.content_fbo_id)
    raw = glReadPixels(0, 0, W, H, GL_RGBA, GL_UNSIGNED_BYTE)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    return bytes(raw)


def _read_f32(comp: GlCompositor) -> list[float]:
    glBindFramebuffer(GL_FRAMEBUFFER, comp.content_fbo_id)
    raw = glReadPixels(0, 0, W, H, GL_RGBA, GL_FLOAT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    return list(struct.unpack(f"{W * H * 4}f", bytes(raw)))


def _unmasked_request(comp: GlCompositor, layers) -> LayerCompositeRequest:
    return LayerCompositeRequest(
        target_fbo_id=comp.content_fbo_id,
        layers=layers,
        color_format=comp.color_format,
    )


def _masked_request(comp: GlCompositor, layers) -> LayerCompositeRequest:
    return LayerCompositeRequest(
        target_fbo_id=comp.content_fbo_id,
        layers=layers,
        color_format=comp.color_format,
        mask=PatternMaskParams(
            mask_type="strips",
            feather_pct=50,
            density=1.0,
            invert=False,
            seed=0,
        ),
        active_slots=(True,),
        song_time_sec=0.0,
    )


def _assert_u8_close(left: bytes, right: bytes) -> None:
    assert len(left) == len(right)
    worst = 0
    for a, b in zip(left, right, strict=True):
        worst = max(worst, abs(a - b))
    assert worst <= _U8_TOL, f"max channel delta {worst} > {_U8_TOL}"


def _assert_f32_close(left: list[float], right: list[float]) -> None:
    assert len(left) == len(right)
    worst = 0.0
    for a, b in zip(left, right, strict=True):
        worst = max(worst, abs(a - b))
    assert worst <= _F32_TOL, f"max channel delta {worst} > {_F32_TOL}"


def _parity_once(color_format: GlColorFormat, blend_mode: str) -> None:
    if color_format is RGBA16F and not probe_rgba16f_framebuffer(W, H):
        pytest.skip("RGBA16F framebuffer unsupported")
    unmasked = GlCompositor(
        content_width=W,
        content_height=H,
        display_width=W,
        display_height=H,
        color_format=color_format,
    )
    unmasked.init()
    masked = GlMaskedCompositor(W, H, color_format=color_format)
    masked.init()
    try:
        layer = unmasked.create_layer_fbo(
            "solo", W, H, opacity=0.7, blend_mode=blend_mode
        )
        # Tint stays in 0..1 so fixed-function glColor and the soft shaders match.
        layer.hue_rgb = (0.4, 0.7, 1.0)
        layer.hue_mix = 0.5
        layer.flash_alpha = 0.2
        _fill_layer(layer, (0.8, 0.3, 0.15))
        unmasked.composite(_unmasked_request(unmasked, [layer]))
        if color_format is RGBA16F:
            expected = _read_f32(unmasked)
        else:
            expected = _read_u8(unmasked)
        masked.composite(_masked_request(unmasked, [layer]))
        if color_format is RGBA16F:
            _assert_f32_close(expected, _read_f32(unmasked))
        else:
            _assert_u8_close(expected, _read_u8(unmasked))
    finally:
        masked.release()
        unmasked.destroy()


@pytest.mark.parametrize("blend_mode", BLEND_MODES)
@pytest.mark.parametrize("color_format", [RGBA8, RGBA16F], ids=["rgba8", "rgba16f"])
def test_masked_full_coverage_matches_unmasked(
    gl_ready, blend_mode: str, color_format: GlColorFormat
) -> None:
    _parity_once(color_format, blend_mode)
