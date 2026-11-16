"""OpenGL integration: save and restore must round-trip the bound 2D texture."""

from __future__ import annotations

import pytest

pygame = pytest.importorskip("pygame")
from OpenGL.GL import (  # noqa: E402
    GL_TEXTURE0,
    GL_TEXTURE_2D,
    GL_TEXTURE_BINDING_2D,
    glActiveTexture,
    glBindTexture,
    glDeleteTextures,
    glGenTextures,
    glGetIntegerv,
)

from cleave.gl_state import restore_gl_state, save_gl_state  # noqa: E402


@pytest.fixture
def gl_context():
    pygame.init()
    pygame.display.set_mode((32, 32), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
    try:
        yield
    finally:
        pygame.quit()


def _bound_texture() -> int:
    value = glGetIntegerv(GL_TEXTURE_BINDING_2D)
    try:
        return int(value[0])
    except (TypeError, IndexError):
        return int(value)


def test_restore_rebinds_the_saved_texture(gl_context) -> None:
    textures = [int(t) for t in glGenTextures(3)]
    try:
        # Skip names 0 and 1 so the old enabled-flag query could not pass by luck.
        kept, other = textures[-1], textures[-2]
        assert kept > 1
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, kept)

        state = save_gl_state()
        glBindTexture(GL_TEXTURE_2D, other)
        restore_gl_state(state)

        assert state.texture_binding == kept
        assert _bound_texture() == kept
    finally:
        glBindTexture(GL_TEXTURE_2D, 0)
        glDeleteTextures(textures)
