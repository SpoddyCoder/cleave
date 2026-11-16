"""OpenGL integration: batched passes match unbatched ones; the luma grid lands a frame late."""

from __future__ import annotations

import numpy as np
import pytest

pygame = pytest.importorskip("pygame")
from OpenGL.GL import (  # noqa: E402
    GL_BLEND,
    GL_COLOR_BUFFER_BIT,
    GL_FRAMEBUFFER,
    GL_RGBA,
    GL_TEXTURE0,
    GL_TEXTURE_2D,
    GL_UNSIGNED_BYTE,
    glActiveTexture,
    glBindFramebuffer,
    glBindTexture,
    glClear,
    glClearColor,
    glDeleteTextures,
    glDisable,
    glEnable,
    glGenTextures,
    glReadPixels,
    glViewport,
)

from cleave.gl_compositor import GlCompositor  # noqa: E402
from cleave.gl_post_process import GlPostProcess  # noqa: E402
from cleave.gl_state import save_gl_state  # noqa: E402


@pytest.fixture
def gl_context():
    pygame.init()
    pygame.display.set_mode((128, 128), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
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


def _fill_content(comp: GlCompositor, rgb: tuple[float, float, float]) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, comp.content_fbo_id)
    glViewport(0, 0, comp.content_width, comp.content_height)
    glClearColor(rgb[0], rgb[1], rgb[2], 1.0)
    glClear(GL_COLOR_BUFFER_BIT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)


def _read_content(comp: GlCompositor) -> bytes:
    glBindFramebuffer(GL_FRAMEBUFFER, comp.content_fbo_id)
    raw = glReadPixels(
        0, 0, comp.content_width, comp.content_height, GL_RGBA, GL_UNSIGNED_BYTE
    )
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    return bytes(raw)


def _run_passes(comp: GlCompositor, pp: GlPostProcess) -> None:
    tex = comp.content_texture_id
    w, h = comp.content_width, comp.content_height
    pp.apply_highlight_rolloff(tex, w, h, 0.5, 0.6, 0.8, 0.4, 0.3, 0)
    pp.apply_chroma_boost(tex, w, h, amount_pct=50, variant=0)
    pp.apply_grit(tex, w, h, 0.0, 2.0)


def test_batched_passes_match_unbatched(gl_context) -> None:
    comp, pp = gl_context
    _fill_content(comp, (0.9, 0.5, 0.2))
    _run_passes(comp, pp)
    unbatched = _read_content(comp)

    _fill_content(comp, (0.9, 0.5, 0.2))
    with pp.batch():
        _run_passes(comp, pp)
    batched = _read_content(comp)

    assert batched == unbatched


def test_batch_restores_state_from_before_it(gl_context) -> None:
    comp, pp = gl_context
    textures = [int(t) for t in glGenTextures(3)]
    try:
        kept = textures[-1]
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, kept)
        glEnable(GL_BLEND)
        glViewport(3, 4, 50, 60)
        before = save_gl_state()

        _fill_content(comp, (0.5, 0.5, 0.5))
        glBindTexture(GL_TEXTURE_2D, kept)
        glEnable(GL_BLEND)
        glViewport(3, 4, 50, 60)
        with pp.batch():
            _run_passes(comp, pp)
        after = save_gl_state()

        assert after.texture_binding == before.texture_binding == kept
        assert after.blend_enabled is True
        assert after.viewport == (3, 4, 50, 60)
    finally:
        glDisable(GL_BLEND)
        glBindTexture(GL_TEXTURE_2D, 0)
        glDeleteTextures(textures)


def test_queued_luma_grid_arrives_on_the_next_call(gl_context) -> None:
    comp, pp = gl_context
    tex = comp.content_texture_id
    w, h = comp.content_width, comp.content_height

    _fill_content(comp, (0.0, 0.0, 0.0))
    assert pp.queue_luma_grid(tex, w, h, grid_width=4, grid_height=3) is None

    _fill_content(comp, (1.0, 1.0, 1.0))
    dark = pp.queue_luma_grid(tex, w, h, grid_width=4, grid_height=3)
    assert dark is not None
    assert dark.shape == (3, 4)

    _fill_content(comp, (0.0, 0.0, 0.0))
    bright = pp.queue_luma_grid(tex, w, h, grid_width=4, grid_height=3)
    assert bright is not None

    assert float(np.mean(dark)) < 0.05
    assert float(np.mean(bright)) > float(np.mean(dark)) + 0.5
