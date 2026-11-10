"""OpenGL integration: a layer resize keeps its picture for paused frames."""

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

from cleave.gl_color_format import RGBA8  # noqa: E402
from cleave.gl_compositor import GlCompositor  # noqa: E402

W, H = 64, 36
RED = (1.0, 0.0, 0.0, 1.0)


@pytest.fixture
def compositor():
    pygame.init()
    pygame.display.set_mode((W, H), pygame.OPENGL | pygame.DOUBLEBUF)
    comp = GlCompositor(content_width=W, content_height=H, color_format=RGBA8)
    comp.init()
    try:
        yield comp
    finally:
        comp.destroy()
        pygame.quit()


def _fill(fbo_id: int, rgba: tuple[float, float, float, float]) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, fbo_id)
    glClearColor(*rgba)
    glClear(GL_COLOR_BUFFER_BIT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)


def _centre_rgb(fbo_id: int, width: int, height: int) -> tuple[int, int, int]:
    glBindFramebuffer(GL_FRAMEBUFFER, fbo_id)
    raw = bytes(glReadPixels(width // 2, height // 2, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE))
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    return raw[0], raw[1], raw[2]


def test_resize_layer_fbo_keeps_layer_and_frozen_source_pixels(compositor) -> None:
    layer = compositor.create_layer_fbo("layer_1", W, H)
    _fill(layer.fbo_id, RED)
    rolloff = compositor._ensure_rolloff_source("layer_1", W, H)
    _fill(rolloff.fbo_id, RED)

    compositor.resize_layer_fbo("layer_1", W // 2, H // 2)

    assert (layer.width, layer.height) == (W // 2, H // 2)
    assert _centre_rgb(layer.fbo_id, layer.width, layer.height) == (255, 0, 0)
    rolloff = compositor._rolloff_sources["layer_1"]
    assert (rolloff.width, rolloff.height) == (W // 2, H // 2)
    assert _centre_rgb(rolloff.fbo_id, rolloff.width, rolloff.height) == (255, 0, 0)
