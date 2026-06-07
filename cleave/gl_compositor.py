"""OpenGL FBO management and layer compositing for Phase 5 Milkdrop integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pygame
from OpenGL.GL import (
    GL_BLEND,
    GL_BLEND_EQUATION_RGB,
    GL_CLAMP_TO_EDGE,
    GL_COLOR_BUFFER_BIT,
    GL_COLOR_ATTACHMENT0,
    GL_DEPTH_ATTACHMENT,
    GL_DEPTH_COMPONENT24,
    GL_DEPTH_TEST,
    GL_DST_COLOR,
    GL_FRAMEBUFFER,
    GL_FRAMEBUFFER_COMPLETE,
    GL_FUNC_ADD,
    GL_FUNC_REVERSE_SUBTRACT,
    GL_FUNC_SUBTRACT,
    GL_LINEAR,
    GL_MAX,
    GL_MODELVIEW,
    GL_ONE,
    GL_ONE_MINUS_DST_COLOR,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_ONE_MINUS_SRC_COLOR,
    GL_PROJECTION,
    GL_QUADS,
    GL_RGBA,
    GL_RGBA8,
    GL_RENDERBUFFER,
    GL_SRC_ALPHA,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_UNSIGNED_BYTE,
    GL_ZERO,
    GL_BLEND_DST_ALPHA,
    GL_BLEND_SRC_ALPHA,
    glBegin,
    glBindFramebuffer,
    glBindRenderbuffer,
    glBindTexture,
    glBlendEquation,
    glBlendFunc,
    glClear,
    glClearColor,
    glColor4f,
    glDeleteFramebuffers,
    glDeleteRenderbuffers,
    glDeleteTextures,
    glDisable,
    glEnable,
    glEnd,
    glFramebufferRenderbuffer,
    glFramebufferTexture2D,
    glGenFramebuffers,
    glGenRenderbuffers,
    glGenTextures,
    glGetIntegerv,
    glIsEnabled,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glRenderbufferStorage,
    glTexCoord2f,
    glTexImage2D,
    glTexParameteri,
    glTexSubImage2D,
    glVertex2f,
    glViewport,
    glCheckFramebufferStatus,
)

BlendMode = Literal[
    "alpha",
    "add",
    "multiply",
    "screen",
    "subtract",
    "difference",
    "exclusion",
    "max",
    "pure-add",
]

BLEND_MODES: tuple[BlendMode, ...] = (
    "alpha",
    "add",
    "multiply",
    "screen",
    "subtract",
    "difference",
    "exclusion",
    "max",
    "pure-add",
)


def _gl_name(gen_fn, count: int = 1) -> int:
    # PyOpenGL may return int, a 1-element sequence, or a 0-d numpy scalar.
    names = gen_fn(count)
    try:
        return int(names[0])
    except (TypeError, IndexError):
        return int(names)


@dataclass
class LayerFbo:
    """Off-screen RGBA framebuffer for one compositor layer."""

    name: str
    width: int
    height: int
    fbo_id: int
    texture_id: int
    depth_rbo_id: int
    enabled: bool = True
    opacity: float = 1.0
    blend_mode: BlendMode = "alpha"

    def bind(self) -> None:
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo_id)

    def unbind(self) -> None:
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def destroy(self) -> None:
        if self.texture_id:
            glDeleteTextures(1, [self.texture_id])
            self.texture_id = 0
        if self.depth_rbo_id:
            glDeleteRenderbuffers(1, [self.depth_rbo_id])
            self.depth_rbo_id = 0
        if self.fbo_id:
            glDeleteFramebuffers(1, [self.fbo_id])
            self.fbo_id = 0

    def __enter__(self) -> LayerFbo:
        self.bind()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.unbind()


class GlCompositor:
    """Composite tiered layer FBO textures into the default framebuffer."""

    def __init__(
        self,
        output_width: int = 1280,
        output_height: int = 720,
        bg: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
    ) -> None:
        self.output_width = output_width
        self.output_height = output_height
        self.bg = bg
        self._initialized = False
        self._layers: list[LayerFbo] = []
        self._overlay_texture_id: int = 0
        self._overlay_texture_size: tuple[int, int] | None = None

    def init(self) -> None:
        """Initialize GL state after a pygame OPENGL context exists."""
        self.setup_gl_state()
        self._initialized = True

    def setup_gl_state(self) -> None:
        glEnable(GL_BLEND)
        glEnable(GL_TEXTURE_2D)
        glDisable(GL_DEPTH_TEST)
        glViewport(0, 0, self.output_width, self.output_height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.output_width, self.output_height, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def _ensure_init(self) -> None:
        if not self._initialized:
            self.init()

    @staticmethod
    def _apply_blend_mode(mode: BlendMode) -> None:
        if mode == "add":
            glBlendEquation(GL_FUNC_ADD)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        elif mode == "multiply":
            glBlendEquation(GL_FUNC_ADD)
            glBlendFunc(GL_DST_COLOR, GL_ZERO)
        elif mode == "screen":
            glBlendEquation(GL_FUNC_ADD)
            glBlendFunc(GL_ONE, GL_ONE_MINUS_DST_COLOR)
        elif mode == "subtract":
            glBlendEquation(GL_FUNC_SUBTRACT)
            glBlendFunc(GL_ONE, GL_ONE)
        elif mode == "difference":
            glBlendEquation(GL_FUNC_REVERSE_SUBTRACT)
            glBlendFunc(GL_ONE, GL_ONE)
        elif mode == "exclusion":
            glBlendEquation(GL_FUNC_ADD)
            glBlendFunc(GL_ONE_MINUS_DST_COLOR, GL_ONE_MINUS_SRC_COLOR)
        elif mode == "max":
            glBlendEquation(GL_MAX)
            glBlendFunc(GL_ONE, GL_ONE)
        elif mode == "pure-add":
            glBlendEquation(GL_FUNC_ADD)
            glBlendFunc(GL_ONE, GL_ONE)
        else:
            glBlendEquation(GL_FUNC_ADD)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    @staticmethod
    def reset_blend_for_external_render() -> None:
        """Reset global blend func before libprojectM renders into a layer FBO.

        draw_layer sets glBlendFunc for compositing; that state persists and
        would leak into projectM's internal feedback passes if not cleared here.
        """
        glEnable(GL_BLEND)
        GlCompositor._apply_blend_mode("alpha")

    @staticmethod
    def _configure_texture_params() -> None:
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

    def _create_rgba_texture(self, width: int, height: int) -> int:
        texture_id = _gl_name(glGenTextures)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None
        )
        self._configure_texture_params()
        return texture_id

    def create_layer_fbo(
        self,
        name: str,
        width: int,
        height: int,
        opacity: float = 1.0,
        blend_mode: BlendMode = "alpha",
    ) -> LayerFbo:
        self._ensure_init()

        texture_id = self._create_rgba_texture(width, height)
        depth_rbo_id = _gl_name(glGenRenderbuffers)
        glBindRenderbuffer(GL_RENDERBUFFER, depth_rbo_id)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, width, height)

        fbo_id = _gl_name(glGenFramebuffers)
        glBindFramebuffer(GL_FRAMEBUFFER, fbo_id)
        glFramebufferTexture2D(
            GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture_id, 0
        )
        glFramebufferRenderbuffer(
            GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depth_rbo_id
        )
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glBindRenderbuffer(GL_RENDERBUFFER, 0)
        glBindTexture(GL_TEXTURE_2D, 0)

        if status != GL_FRAMEBUFFER_COMPLETE:
            glDeleteTextures(1, [texture_id])
            glDeleteRenderbuffers(1, [depth_rbo_id])
            glDeleteFramebuffers(1, [fbo_id])
            raise RuntimeError(
                f"FBO incomplete for layer {name!r} ({width}x{height}): status 0x{status:x}"
            )

        layer = LayerFbo(
            name=name,
            width=width,
            height=height,
            fbo_id=fbo_id,
            texture_id=texture_id,
            depth_rbo_id=depth_rbo_id,
            enabled=True,
            opacity=opacity,
            blend_mode=blend_mode,
        )
        self._layers.append(layer)
        return layer

    def _bind_default_framebuffer(self) -> None:
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(0, 0, self.output_width, self.output_height)

    @staticmethod
    def _draw_textured_quad(
        texture_id: int,
        x: float,
        y: float,
        width: int,
        height: int,
        opacity: float,
    ) -> None:
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glColor4f(1.0, 1.0, 1.0, opacity)
        glBegin(GL_QUADS)
        # Flip V: OpenGL textures are bottom-origin; ortho uses top-left origin.
        glTexCoord2f(0.0, 1.0)
        glVertex2f(x, y)
        glTexCoord2f(1.0, 1.0)
        glVertex2f(x + float(width), y)
        glTexCoord2f(1.0, 0.0)
        glVertex2f(x + float(width), y + float(height))
        glTexCoord2f(0.0, 0.0)
        glVertex2f(x, y + float(height))
        glEnd()
        glBindTexture(GL_TEXTURE_2D, 0)

    @staticmethod
    def _gl_int(param: int) -> int:
        value = glGetIntegerv(param)
        try:
            return int(value[0])
        except (TypeError, IndexError):
            return int(value)

    @classmethod
    def _push_blend_state(cls) -> tuple[bool, int, int, int]:
        enabled = bool(glIsEnabled(GL_BLEND))
        return (
            enabled,
            cls._gl_int(GL_BLEND_SRC_ALPHA),
            cls._gl_int(GL_BLEND_DST_ALPHA),
            cls._gl_int(GL_BLEND_EQUATION_RGB),
        )

    @staticmethod
    def _pop_blend_state(enabled: bool, src: int, dst: int, equation: int) -> None:
        if enabled:
            glEnable(GL_BLEND)
        else:
            glDisable(GL_BLEND)
        glBlendEquation(equation)
        glBlendFunc(src, dst)

    def draw_layer(self, layer: LayerFbo) -> None:
        if not layer.enabled or layer.opacity <= 0.0:
            return
        self._ensure_init()
        self._bind_default_framebuffer()
        glEnable(GL_BLEND)
        self._apply_blend_mode(layer.blend_mode)
        self._draw_textured_quad(
            layer.texture_id,
            0.0,
            0.0,
            self.output_width,
            self.output_height,
            layer.opacity,
        )

    def composite(self, layers: list[LayerFbo]) -> None:
        """Clear to background and draw *layers* bottom-to-top."""
        self._ensure_init()
        self._bind_default_framebuffer()
        glClearColor(*self.bg)
        glClear(GL_COLOR_BUFFER_BIT)
        for layer in layers:
            self.draw_layer(layer)

    def upload_overlay_texture(self, surface: pygame.Surface) -> int:
        """Upload a pygame SRCALPHA surface as a GL texture (Y-flipped for GL)."""
        self._ensure_init()
        if not surface.get_flags() & pygame.SRCALPHA:
            surface = surface.convert_alpha()
        width, height = surface.get_size()
        data = pygame.image.tostring(surface, "RGBA", True)

        if (
            self._overlay_texture_id
            and self._overlay_texture_size == (width, height)
        ):
            glBindTexture(GL_TEXTURE_2D, self._overlay_texture_id)
            glTexSubImage2D(
                GL_TEXTURE_2D,
                0,
                0,
                0,
                width,
                height,
                GL_RGBA,
                GL_UNSIGNED_BYTE,
                data,
            )
            glBindTexture(GL_TEXTURE_2D, 0)
            return self._overlay_texture_id

        if self._overlay_texture_id:
            glDeleteTextures(1, [self._overlay_texture_id])
            self._overlay_texture_id = 0

        texture_id = _gl_name(glGenTextures)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, data
        )
        self._configure_texture_params()
        glBindTexture(GL_TEXTURE_2D, 0)
        self._overlay_texture_id = texture_id
        self._overlay_texture_size = (width, height)
        return texture_id

    def draw_overlay(
        self,
        texture_id: int,
        x: int,
        y: int,
        width: int,
        height: int,
        alpha: float = 1.0,
    ) -> None:
        """Draw *texture_id* at pixel (*x*, *y*) with alpha blending enabled."""
        self._ensure_init()
        self._bind_default_framebuffer()
        blend_enabled, blend_src, blend_dst, blend_equation = self._push_blend_state()
        try:
            glEnable(GL_BLEND)
            self._apply_blend_mode("alpha")
            self._draw_textured_quad(texture_id, float(x), float(y), width, height, alpha)
        finally:
            self._pop_blend_state(blend_enabled, blend_src, blend_dst, blend_equation)
            glColor4f(1.0, 1.0, 1.0, 1.0)

    def destroy(self) -> None:
        for layer in self._layers:
            layer.destroy()
        self._layers.clear()
        if self._overlay_texture_id:
            glDeleteTextures(1, [self._overlay_texture_id])
            self._overlay_texture_id = 0
        self._overlay_texture_size = None
        self._initialized = False

    def __enter__(self) -> GlCompositor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.destroy()
