"""Tests for shared GL color attachment formats."""

from __future__ import annotations

import pytest

pygame = pytest.importorskip("pygame")

from OpenGL.GL import (  # noqa: E402
    GL_HALF_FLOAT,
    GL_RGBA16F,
    GL_RGBA8,
    GL_UNSIGNED_BYTE,
)

from cleave.gl_color_format import (  # noqa: E402
    RGBA16F,
    RGBA8,
    probe_rgba16f_framebuffer,
    resolve_compositor_format,
    resolve_live_compositor_format,
)


def test_resolve_compositor_format_8bit_path() -> None:
    fmt = resolve_compositor_format(False)
    assert fmt is RGBA8


def test_resolve_compositor_format_hdr_path() -> None:
    fmt = resolve_compositor_format(True)
    assert fmt is RGBA16F


def test_resolve_live_compositor_format_forces_8bit_in_curation() -> None:
    assert resolve_live_compositor_format(True, preset_curation=True) is RGBA8
    assert resolve_live_compositor_format(False, preset_curation=True) is RGBA8


def test_resolve_live_compositor_format_follows_hdr_outside_curation() -> None:
    assert resolve_live_compositor_format(True, preset_curation=False) is RGBA16F
    assert resolve_live_compositor_format(False, preset_curation=False) is RGBA8


def test_rgba8_constants() -> None:
    assert RGBA8.internal_format == GL_RGBA8
    assert RGBA8.pixel_type == GL_UNSIGNED_BYTE
    assert RGBA8.moderngl_external_dtype == "u1"
    assert RGBA8.moderngl_internal_dtype == "f1"


def test_rgba16f_constants() -> None:
    assert RGBA16F.internal_format == GL_RGBA16F
    assert RGBA16F.pixel_type == GL_HALF_FLOAT
    assert RGBA16F.moderngl_external_dtype == "f2"
    assert RGBA16F.moderngl_internal_dtype == "f2"


@pytest.fixture(scope="module")
def pygame_gl() -> None:
    pygame.init()
    pygame.display.set_mode((64, 64), pygame.OPENGL | pygame.DOUBLEBUF)
    yield
    pygame.quit()


def test_probe_rgba16f_framebuffer_complete(pygame_gl: None) -> None:
    assert probe_rgba16f_framebuffer(64, 64) is True
