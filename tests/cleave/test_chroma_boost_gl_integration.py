"""OpenGL integration: chroma boost must change content FBO pixels."""

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


def _fill_content_gray(comp: GlCompositor) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, comp.content_fbo_id)
    glClearColor(0.4, 0.5, 0.6, 1.0)
    glClear(GL_COLOR_BUFFER_BIT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)


def test_chroma_boost_increases_channel_spread(gl_context) -> None:
    comp, pp = gl_context
    _fill_content_gray(comp)
    before = _read_content_pixel(comp)
    spread_before = max(before[:3]) - min(before[:3])

    pp.apply_chroma_boost(
        comp.content_texture_id,
        comp.content_width,
        comp.content_height,
        amount_pct=50,
        variant=0,
    )
    after = _read_content_pixel(comp)
    spread_after = max(after[:3]) - min(after[:3])
    assert spread_after > spread_before, f"before={before} after={after}"


def test_chroma_boost_amount_zero_is_noop(gl_context) -> None:
    comp, pp = gl_context
    _fill_content_gray(comp)
    before = _read_content_pixel(comp)

    pp.apply_chroma_boost(
        comp.content_texture_id,
        comp.content_width,
        comp.content_height,
        amount_pct=0,
        variant=1,
    )
    after = _read_content_pixel(comp)
    assert after == before
