"""Shared OpenGL color attachment formats for compositor and post-process."""

from __future__ import annotations

from dataclasses import dataclass

from OpenGL.GL import (
    GL_COLOR_ATTACHMENT0,
    GL_FRAMEBUFFER,
    GL_FRAMEBUFFER_COMPLETE,
    GL_HALF_FLOAT,
    GL_RGBA,
    GL_RGBA16F,
    GL_RGBA8,
    GL_TEXTURE_2D,
    GL_UNSIGNED_BYTE,
    glBindFramebuffer,
    glBindTexture,
    glCheckFramebufferStatus,
    glDeleteFramebuffers,
    glDeleteTextures,
    glFramebufferTexture2D,
    glGenFramebuffers,
    glGenTextures,
    glTexImage2D,
)


def _gl_name(gen_fn, count: int = 1) -> int:
    names = gen_fn(count)
    try:
        return int(names[0])
    except (TypeError, IndexError):
        return int(names)


@dataclass(frozen=True)
class GlColorFormat:
    internal_format: int
    pixel_type: int
    moderngl_external_dtype: str
    moderngl_internal_dtype: str


RGBA8 = GlColorFormat(
    internal_format=GL_RGBA8,
    pixel_type=GL_UNSIGNED_BYTE,
    # PyOpenGL layer FBOs use GL_RGBA8; moderngl ping-pong buffers stay f1 (normalized
    # uint8), matching ctx.texture() default before HDR. u1 internal buffers break copy.
    moderngl_external_dtype="u1",
    moderngl_internal_dtype="f1",
)

RGBA16F = GlColorFormat(
    internal_format=GL_RGBA16F,
    pixel_type=GL_HALF_FLOAT,
    moderngl_external_dtype="f2",
    moderngl_internal_dtype="f2",
)


def resolve_compositor_format(hdr_compositing: bool) -> GlColorFormat:
    return RGBA16F if hdr_compositing else RGBA8


def probe_rgba16f_framebuffer(width: int = 1, height: int = 1) -> bool:
    """Return True when a throwaway RGBA16F color attachment is framebuffer-complete."""
    texture_id = _gl_name(glGenTextures)
    fbo_id = _gl_name(glGenFramebuffers)
    try:
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA16F,
            width,
            height,
            0,
            GL_RGBA,
            GL_HALF_FLOAT,
            None,
        )
        glBindFramebuffer(GL_FRAMEBUFFER, fbo_id)
        glFramebufferTexture2D(
            GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture_id, 0
        )
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        return status == GL_FRAMEBUFFER_COMPLETE
    finally:
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glDeleteTextures(1, [texture_id])
        glDeleteFramebuffers(1, [fbo_id])
