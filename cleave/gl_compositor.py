"""OpenGL FBO layer stack and black-key compositing."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from cleave.blend_modes import BlendMode
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
    GL_SRC_COLOR,
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
    glReadPixels,
    glRenderbufferStorage,
    glTexCoord2f,
    glTexImage2D,
    glTexParameteri,
    glTexSubImage2D,
    glVertex2f,
    glViewport,
    glUseProgram,
    glCheckFramebufferStatus,
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
    flash_alpha: float = 0.0
    bloom_strength: float = 0.0
    hue_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)
    hue_mix: float = 0.0
    grit_strength: float = 0.0
    aberration_px: float = 0.0
    blend_mode: BlendMode = "black-key"

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
    """Stack tiered layer FBO textures into a content FBO, then present to display.

    Layer blend mode ``black-key`` treats each pixel's RGB as its compositing
    weight (black is fully transparent). Stem composite and post-FX always render
    into the content FBO; ``present_content()`` blits to the default framebuffer
    at display size (1:1 when upscale is 1.0). The tuning overlay uses SRCALPHA
    blending on the display framebuffer after present.
    """

    def __init__(
        self,
        content_width: int = 1280,
        content_height: int = 720,
        *,
        display_width: int | None = None,
        display_height: int | None = None,
        bg: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
    ) -> None:
        self.content_width = content_width
        self.content_height = content_height
        self.display_width = (
            display_width if display_width is not None else content_width
        )
        self.display_height = (
            display_height if display_height is not None else content_height
        )
        self.bg = bg
        self._initialized = False
        self._layers: list[LayerFbo] = []
        self._overlay_texture_id: int = 0
        self._overlay_texture_size: tuple[int, int] | None = None
        self._content_fbo_id: int = 0
        self._content_texture_id: int = 0
        self._content_depth_rbo_id: int = 0

    def init(self) -> None:
        """Initialize GL state after a pygame OPENGL context exists."""
        self.setup_gl_state()
        self._allocate_content_fbo()
        self._initialized = True

    def setup_gl_state(self) -> None:
        glEnable(GL_BLEND)
        glEnable(GL_TEXTURE_2D)
        glDisable(GL_DEPTH_TEST)
        self._set_display_projection()
        glViewport(0, 0, self.display_width, self.display_height)

    def _set_content_projection(self) -> None:
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.content_width, self.content_height, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def _set_display_projection(self) -> None:
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.display_width, self.display_height, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def _allocate_content_fbo(self) -> None:
        width = self.content_width
        height = self.content_height
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
                f"content FBO incomplete ({width}x{height}): status 0x{status:x}"
            )

        self._content_fbo_id = fbo_id
        self._content_texture_id = texture_id
        self._content_depth_rbo_id = depth_rbo_id

    def _destroy_content_fbo(self) -> None:
        if self._content_texture_id:
            glDeleteTextures(1, [self._content_texture_id])
            self._content_texture_id = 0
        if self._content_depth_rbo_id:
            glDeleteRenderbuffers(1, [self._content_depth_rbo_id])
            self._content_depth_rbo_id = 0
        if self._content_fbo_id:
            glDeleteFramebuffers(1, [self._content_fbo_id])
            self._content_fbo_id = 0

    def _ensure_init(self) -> None:
        if not self._initialized:
            self.init()

    @staticmethod
    def _apply_layer_blend_mode(mode: BlendMode) -> None:
        """Configure GL blend for stacking layer FBOs onto the output framebuffer."""
        if mode == "black-key":
            glBlendEquation(GL_FUNC_ADD)
            glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_COLOR)
        elif mode == "add":
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
            glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_COLOR)

    @staticmethod
    def _apply_src_alpha_blend() -> None:
        """SRCALPHA blend for pygame overlay textures and libprojectM FBO reset."""
        glBlendEquation(GL_FUNC_ADD)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    @staticmethod
    def reset_blend_for_external_render() -> None:
        """Reset blend state before libprojectM renders into a layer FBO."""
        glEnable(GL_BLEND)
        GlCompositor._apply_src_alpha_blend()

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

    def _allocate_layer_framebuffer(
        self,
        name: str,
        width: int,
        height: int,
    ) -> tuple[int, int, int]:
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

        return fbo_id, texture_id, depth_rbo_id

    def create_layer_fbo(
        self,
        name: str,
        width: int,
        height: int,
        opacity: float = 1.0,
        blend_mode: BlendMode = "black-key",
    ) -> LayerFbo:
        self._ensure_init()

        fbo_id, texture_id, depth_rbo_id = self._allocate_layer_framebuffer(
            name, width, height
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

    def resize_layer_fbo(self, name: str, width: int, height: int) -> None:
        """Resize an existing layer FBO, preserving compositor state fields."""
        for layer in self._layers:
            if layer.name != name:
                continue
            if layer.width == width and layer.height == height:
                return

            enabled = layer.enabled
            opacity = layer.opacity
            blend_mode = layer.blend_mode
            flash_alpha = layer.flash_alpha
            bloom_strength = layer.bloom_strength
            hue_rgb = layer.hue_rgb
            hue_mix = layer.hue_mix
            grit_strength = layer.grit_strength
            aberration_px = layer.aberration_px

            layer.destroy()
            fbo_id, texture_id, depth_rbo_id = self._allocate_layer_framebuffer(
                name, width, height
            )

            layer.width = width
            layer.height = height
            layer.fbo_id = fbo_id
            layer.texture_id = texture_id
            layer.depth_rbo_id = depth_rbo_id
            layer.enabled = enabled
            layer.opacity = opacity
            layer.blend_mode = blend_mode
            layer.flash_alpha = flash_alpha
            layer.bloom_strength = bloom_strength
            layer.hue_rgb = hue_rgb
            layer.hue_mix = hue_mix
            layer.grit_strength = grit_strength
            layer.aberration_px = aberration_px
            return

        raise ValueError(f"no layer FBO named {name!r}")

    def remove_layer_fbo(self, name: str) -> None:
        """Destroy the named FBO and remove it from the compositor stack."""
        for i, fbo in enumerate(self._layers):
            if fbo.name == name:
                fbo.destroy()
                del self._layers[i]
                return
        raise ValueError(f"no layer FBO named {name!r}")

    def _bind_content_fbo(self) -> None:
        glBindFramebuffer(GL_FRAMEBUFFER, self._content_fbo_id)
        glUseProgram(0)
        glEnable(GL_TEXTURE_2D)
        glViewport(0, 0, self.content_width, self.content_height)
        self._set_content_projection()

    def _bind_default_framebuffer(self) -> None:
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glUseProgram(0)
        glEnable(GL_TEXTURE_2D)
        glViewport(0, 0, self.display_width, self.display_height)
        self._set_display_projection()

    @staticmethod
    def _lerp_tint_rgb(
        hue_rgb: tuple[float, float, float],
        hue_mix: float,
    ) -> tuple[float, float, float]:
        if hue_mix <= 0.0:
            return (1.0, 1.0, 1.0)
        return tuple(1.0 + (c - 1.0) * hue_mix for c in hue_rgb)

    @staticmethod
    def _layer_gl_color(
        tint_rgb: tuple[float, float, float],
        opacity: float,
        blend_mode: BlendMode,
    ) -> tuple[float, float, float, float]:
        """Map layer opacity to glColor4f for the active layer blend mode.

        GL_MODULATE only multiplies texture RGB by glColor RGB; glColor alpha
        affects fragment alpha. Modes that blend on SRC_COLOR need opacity baked
        into RGB. ``add`` uses GL_SRC_ALPHA and keeps opacity in the alpha channel.
        """
        if blend_mode == "add":
            return (tint_rgb[0], tint_rgb[1], tint_rgb[2], opacity)
        scaled = tuple(c * opacity for c in tint_rgb)
        return (scaled[0], scaled[1], scaled[2], 1.0)

    @staticmethod
    def _draw_textured_quad(
        texture_id: int,
        x: float,
        y: float,
        width: int,
        height: int,
        rgba: tuple[float, float, float, float],
    ) -> None:
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glColor4f(*rgba)
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
    def _draw_solid_quad(
        x: float,
        y: float,
        width: int,
        height: int,
        rgba: tuple[float, float, float, float],
    ) -> None:
        glDisable(GL_TEXTURE_2D)
        glColor4f(*rgba)
        glBegin(GL_QUADS)
        glVertex2f(x, y)
        glVertex2f(x + float(width), y)
        glVertex2f(x + float(width), y + float(height))
        glVertex2f(x, y + float(height))
        glEnd()
        glEnable(GL_TEXTURE_2D)

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
        if not layer.enabled:
            return
        if layer.opacity <= 0.0 and layer.flash_alpha < 0.01:
            return
        self._ensure_init()
        self._bind_content_fbo()
        if layer.opacity > 0.0:
            glEnable(GL_BLEND)
            self._apply_layer_blend_mode(layer.blend_mode)
            tint_rgb = self._lerp_tint_rgb(layer.hue_rgb, layer.hue_mix)
            rgba = self._layer_gl_color(tint_rgb, layer.opacity, layer.blend_mode)
            self._draw_textured_quad(
                layer.texture_id,
                0.0,
                0.0,
                self.content_width,
                self.content_height,
                rgba,
            )
        if layer.flash_alpha >= 0.01:
            blend_enabled, blend_src, blend_dst, blend_equation = (
                self._push_blend_state()
            )
            try:
                glEnable(GL_BLEND)
                self._apply_layer_blend_mode("add")
                self._draw_solid_quad(
                    0.0,
                    0.0,
                    self.content_width,
                    self.content_height,
                    (240 / 255.0, 235 / 255.0, 230 / 255.0, layer.flash_alpha),
                )
            finally:
                self._pop_blend_state(
                    blend_enabled, blend_src, blend_dst, blend_equation
                )
                glColor4f(1.0, 1.0, 1.0, 1.0)

    def composite(self, layers: list[LayerFbo]) -> None:
        """Clear to background and stack *layers* bottom-to-top."""
        self._ensure_init()
        self._bind_content_fbo()
        glClearColor(*self.bg)
        glClear(GL_COLOR_BUFFER_BIT)
        for layer in layers:
            self.draw_layer(layer)

    def apply_frame_fade(self, alpha: float) -> None:
        """Multiply content-target RGB by *alpha* (render fade in/out)."""
        if alpha >= 1.0:
            return
        self._ensure_init()
        self._bind_content_fbo()
        if alpha <= 0.0:
            glClearColor(0.0, 0.0, 0.0, 1.0)
            glClear(GL_COLOR_BUFFER_BIT)
            return
        blend_enabled, blend_src, blend_dst, blend_equation = self._push_blend_state()
        try:
            glEnable(GL_BLEND)
            glBlendEquation(GL_FUNC_ADD)
            glBlendFunc(GL_ZERO, GL_SRC_COLOR)
            self._draw_solid_quad(
                0.0,
                0.0,
                self.content_width,
                self.content_height,
                (alpha, alpha, alpha, 1.0),
            )
        finally:
            self._pop_blend_state(blend_enabled, blend_src, blend_dst, blend_equation)
            glColor4f(1.0, 1.0, 1.0, 1.0)

    def present_content(self) -> None:
        """Blit content FBO to the default framebuffer at display size."""
        self._ensure_init()
        self._bind_default_framebuffer()
        glDisable(GL_BLEND)
        self._draw_textured_quad(
            self._content_texture_id,
            0.0,
            0.0,
            self.display_width,
            self.display_height,
            (1.0, 1.0, 1.0, 1.0),
        )
        glEnable(GL_BLEND)

    def read_rgba_frame(self) -> bytes:
        """Read RGBA pixels from the default framebuffer for ffmpeg rawvideo."""
        self._ensure_init()
        width = self.display_width
        height = self.display_height
        raw = glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE)
        row_stride = width * 4
        rows = [
            raw[row * row_stride : (row + 1) * row_stride] for row in range(height)
        ]
        return b"".join(reversed(rows))

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

    def _draw_overlay_quad(
        self,
        texture_id: int,
        x: int,
        y: int,
        width: int,
        height: int,
        alpha: float,
    ) -> None:
        blend_enabled, blend_src, blend_dst, blend_equation = self._push_blend_state()
        try:
            glEnable(GL_BLEND)
            self._apply_src_alpha_blend()
            self._draw_textured_quad(
                texture_id, float(x), float(y), width, height, (1.0, 1.0, 1.0, alpha)
            )
        finally:
            self._pop_blend_state(blend_enabled, blend_src, blend_dst, blend_equation)
            glColor4f(1.0, 1.0, 1.0, 1.0)

    def draw_content_overlay(
        self,
        texture_id: int,
        x: int,
        y: int,
        width: int,
        height: int,
        alpha: float = 1.0,
    ) -> None:
        """Draw *texture_id* onto the content FBO with SRCALPHA blending."""
        self._ensure_init()
        self._bind_content_fbo()
        self._draw_overlay_quad(texture_id, x, y, width, height, alpha)

    def draw_overlay(
        self,
        texture_id: int,
        x: int,
        y: int,
        width: int,
        height: int,
        alpha: float = 1.0,
    ) -> None:
        """Draw *texture_id* onto the display framebuffer with SRCALPHA blending."""
        self._ensure_init()
        self._bind_default_framebuffer()
        self._draw_overlay_quad(texture_id, x, y, width, height, alpha)

    def destroy(self) -> None:
        for layer in self._layers:
            layer.destroy()
        self._layers.clear()
        self._destroy_content_fbo()
        if self._overlay_texture_id:
            glDeleteTextures(1, [self._overlay_texture_id])
            self._overlay_texture_id = 0
        self._overlay_texture_size = None
        self._initialized = False

    def __enter__(self) -> GlCompositor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.destroy()
