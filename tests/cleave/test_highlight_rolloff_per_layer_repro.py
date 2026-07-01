"""Repro: per-layer highlight rolloff writes to the wrong texture.

Stripped-down whitepage for the "per_layer mode has no visible effect" bug.
Exercises the two GL helpers the per-layer path relies on:

* GlPostProcess.copy_texture(source -> dest)
* GlPostProcess.apply_highlight_rolloff(dest, source_texture_id=source)

Both must write into their *dest* texture. The compositor's rolloff-source
slot mirrors the layer texture, then rolloff is applied back onto the layer.
"""

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


def _fill_fbo(fbo_id: int, rgba: tuple[float, float, float, float]) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, fbo_id)
    glClearColor(*rgba)
    glClear(GL_COLOR_BUFFER_BIT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)


def _read_fbo_pixel(fbo_id: int, x: int = 8, y: int = 8) -> tuple[int, ...]:
    glBindFramebuffer(GL_FRAMEBUFFER, fbo_id)
    raw = glReadPixels(x, y, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    return tuple(raw)


def test_copy_texture_writes_into_dest(gl_context) -> None:
    comp, pp = gl_context
    src = comp.create_layer_fbo("src", 32, 32)
    dst = comp.create_layer_fbo("dst", 32, 32)
    _fill_fbo(src.fbo_id, (1.0, 1.0, 1.0, 1.0))
    _fill_fbo(dst.fbo_id, (0.0, 0.0, 0.0, 1.0))

    pp.copy_texture(src.texture_id, dst.texture_id, 32, 32)

    after = _read_fbo_pixel(dst.fbo_id)
    assert after[0] == 255, f"copy_texture did not write dest, got {after}"


def test_per_layer_rolloff_darkens_the_layer_texture(gl_context) -> None:
    comp, pp = gl_context
    layer = comp.create_layer_fbo("layer_1", 32, 32)
    comp._ensure_rolloff_source("layer_1", 32, 32)
    _fill_fbo(layer.fbo_id, (1.0, 1.0, 1.0, 1.0))
    before = _read_fbo_pixel(layer.fbo_id)
    assert before[0] == 255

    comp.copy_layer_to_rolloff_source(
        pp, "layer_1", layer.texture_id, 32, 32
    )
    source_id = comp.rolloff_source_texture_id("layer_1")
    pp.apply_highlight_rolloff(
        layer.texture_id,
        32,
        32,
        threshold=0.78,
        ceiling=0.65,
        strength=0.7,
        softness=0.4,
        desaturation=0.3,
        mode=0,
        source_texture_id=source_id,
    )

    after = _read_fbo_pixel(layer.fbo_id)
    assert after[0] < before[0], (
        f"per-layer rolloff left the layer texture unchanged: "
        f"before={before} after={after}"
    )
