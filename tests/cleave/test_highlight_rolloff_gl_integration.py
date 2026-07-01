"""OpenGL integration: highlight rolloff must change content FBO pixels."""

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
from cleave.gl_post_process import GlPostProcess  # noqa: E402


@pytest.fixture
def gl_context():
    pygame.init()
    pygame.display.set_mode((128, 128), pygame.OPENGL | pygame.DOUBLEBUF)
    comp = GlCompositor(
        content_width=64,
        content_height=64,
        display_width=128,
        display_height=128,
    )
    comp.init()
    pp = GlPostProcess()
    pp.init()
    try:
        yield comp, pp
    finally:
        pp.destroy()
        comp.destroy()
        pygame.quit()


def _read_content_pixel(comp: GlCompositor, x: int = 32, y: int = 32) -> tuple[int, ...]:
    glBindFramebuffer(GL_FRAMEBUFFER, comp.content_fbo_id)
    raw = glReadPixels(x, y, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    return tuple(raw)


def _fill_content_white(comp: GlCompositor) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, comp.content_fbo_id)
    glClearColor(1.0, 1.0, 1.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)


def test_highlight_rolloff_darkens_blown_out_white(gl_context) -> None:
    comp, pp = gl_context
    _fill_content_white(comp)
    before = _read_content_pixel(comp)
    assert before[0] == 255

    pp.apply_highlight_rolloff(
        comp.content_texture_id,
        comp.content_width,
        comp.content_height,
        threshold=0.78,
        ceiling=0.65,
        strength=0.7,
        softness=0.4,
        desaturation=0.3,
        mode=0,
    )
    after = _read_content_pixel(comp)
    assert after[0] < before[0], f"expected darker RGB, got before={before} after={after}"


def test_highlight_rolloff_smoothstep_darkens_white(gl_context) -> None:
    comp, pp = gl_context
    _fill_content_white(comp)
    before = _read_content_pixel(comp)
    assert before[0] == 255

    pp.apply_highlight_rolloff(
        comp.content_texture_id,
        comp.content_width,
        comp.content_height,
        threshold=0.78,
        ceiling=0.65,
        strength=0.7,
        softness=0.4,
        desaturation=0.3,
        mode=1,
    )
    after = _read_content_pixel(comp)
    assert after[0] < before[0], f"expected darker RGB, got before={before} after={after}"


def test_highlight_rolloff_strength_zero_is_noop(gl_context) -> None:
    comp, pp = gl_context
    _fill_content_white(comp)
    before = _read_content_pixel(comp)

    pp.apply_highlight_rolloff(
        comp.content_texture_id,
        comp.content_width,
        comp.content_height,
        threshold=0.78,
        ceiling=0.65,
        strength=0.0,
        softness=0.4,
        desaturation=0.0,
        mode=0,
    )
    after = _read_content_pixel(comp)
    assert after == before


def test_highlight_rolloff_toggle_off_vs_on(gl_context) -> None:
    comp, pp = gl_context
    _fill_content_white(comp)

    pp.apply_highlight_rolloff(
        comp.content_texture_id,
        comp.content_width,
        comp.content_height,
        threshold=0.78,
        ceiling=0.65,
        strength=1.0,
        softness=0.4,
        desaturation=0.0,
        mode=0,
    )
    compressed = _read_content_pixel(comp)

    _fill_content_white(comp)
    unchanged = _read_content_pixel(comp)
    assert compressed[0] < unchanged[0]
