"""Shared OpenGL state save and restore for draws that share the pygame context."""

from __future__ import annotations

from dataclasses import dataclass

import moderngl
from OpenGL.GL import (
    GL_ACTIVE_TEXTURE,
    GL_BLEND,
    GL_BLEND_DST_ALPHA,
    GL_BLEND_EQUATION,
    GL_BLEND_SRC_ALPHA,
    GL_COLOR_WRITEMASK,
    GL_DEPTH_TEST,
    GL_FRAMEBUFFER,
    GL_FRAMEBUFFER_BINDING,
    GL_READ_BUFFER,
    GL_READ_FRAMEBUFFER,
    GL_READ_FRAMEBUFFER_BINDING,
    GL_SCISSOR_BOX,
    GL_SCISSOR_TEST,
    GL_TEXTURE_2D,
    GL_VIEWPORT,
    glActiveTexture,
    glBindFramebuffer,
    glBindTexture,
    glBlendEquation,
    glBlendFunc,
    glColorMask,
    glDisable,
    glEnable,
    glGetIntegerv,
    glIsEnabled,
    glReadBuffer,
    glScissor,
    glViewport,
)

try:
    from OpenGL.GL import GL_VERTEX_ARRAY_BINDING, glBindVertexArray
except ImportError:  # pragma: no cover - PyOpenGL without VAO entry points
    GL_VERTEX_ARRAY_BINDING = None  # type: ignore[misc, assignment]
    glBindVertexArray = None  # type: ignore[misc, assignment]


def _gl_int(param: int) -> int:
    value = glGetIntegerv(param)
    try:
        return int(value[0])
    except (TypeError, IndexError):
        return int(value)


def _color_writemask() -> tuple[bool, bool, bool, bool]:
    values = glGetIntegerv(GL_COLOR_WRITEMASK)
    return (
        bool(int(values[0])),
        bool(int(values[1])),
        bool(int(values[2])),
        bool(int(values[3])),
    )


@dataclass
class SavedGlState:
    framebuffer: int
    viewport: tuple[int, int, int, int]
    active_texture: int
    texture_binding: int
    texture_2d_enabled: bool
    blend_enabled: bool
    blend_src: int
    blend_dst: int
    blend_equation: int
    depth_test: bool
    scissor_enabled: bool
    scissor_box: tuple[int, int, int, int]
    color_writemask: tuple[bool, bool, bool, bool]
    vertex_array_binding: int | None
    read_framebuffer: int
    read_buffer: int


def save_gl_state() -> SavedGlState:
    viewport = glGetIntegerv(GL_VIEWPORT)
    scissor = glGetIntegerv(GL_SCISSOR_BOX)
    vao_binding: int | None = None
    if GL_VERTEX_ARRAY_BINDING is not None:
        vao_binding = _gl_int(GL_VERTEX_ARRAY_BINDING)
    return SavedGlState(
        framebuffer=_gl_int(GL_FRAMEBUFFER_BINDING),
        viewport=(
            int(viewport[0]),
            int(viewport[1]),
            int(viewport[2]),
            int(viewport[3]),
        ),
        active_texture=_gl_int(GL_ACTIVE_TEXTURE),
        texture_binding=_gl_int(GL_TEXTURE_2D),
        texture_2d_enabled=bool(glIsEnabled(GL_TEXTURE_2D)),
        blend_enabled=bool(glIsEnabled(GL_BLEND)),
        blend_src=_gl_int(GL_BLEND_SRC_ALPHA),
        blend_dst=_gl_int(GL_BLEND_DST_ALPHA),
        blend_equation=_gl_int(GL_BLEND_EQUATION),
        depth_test=bool(glIsEnabled(GL_DEPTH_TEST)),
        scissor_enabled=bool(glIsEnabled(GL_SCISSOR_TEST)),
        scissor_box=(
            int(scissor[0]),
            int(scissor[1]),
            int(scissor[2]),
            int(scissor[3]),
        ),
        color_writemask=_color_writemask(),
        vertex_array_binding=vao_binding,
        read_framebuffer=_gl_int(GL_READ_FRAMEBUFFER_BINDING),
        read_buffer=_gl_int(GL_READ_BUFFER),
    )


def restore_gl_state(
    state: SavedGlState,
    ctx: moderngl.Context | None = None,
) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, state.framebuffer)
    glBindFramebuffer(GL_READ_FRAMEBUFFER, state.read_framebuffer)
    glReadBuffer(state.read_buffer)
    glViewport(*state.viewport)
    if ctx is not None:
        ctx.viewport = state.viewport
    glActiveTexture(state.active_texture)
    glBindTexture(GL_TEXTURE_2D, state.texture_binding)
    if state.texture_2d_enabled:
        glEnable(GL_TEXTURE_2D)
    else:
        glDisable(GL_TEXTURE_2D)
    if state.blend_enabled:
        glEnable(GL_BLEND)
    else:
        glDisable(GL_BLEND)
    glBlendFunc(state.blend_src, state.blend_dst)
    glBlendEquation(state.blend_equation)
    if state.depth_test:
        glEnable(GL_DEPTH_TEST)
    else:
        glDisable(GL_DEPTH_TEST)
    if state.scissor_enabled:
        glEnable(GL_SCISSOR_TEST)
    else:
        glDisable(GL_SCISSOR_TEST)
    glScissor(*state.scissor_box)
    r, g, b, a = state.color_writemask
    glColorMask(r, g, b, a)
    if glBindVertexArray is not None and state.vertex_array_binding is not None:
        glBindVertexArray(state.vertex_array_binding)
