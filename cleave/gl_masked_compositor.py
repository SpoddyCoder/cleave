"""Shader-based masked layer composite via moderngl (hard and soft modes).

Hard mode against a cleared black background: only one layer wins per pixel, so
per-layer blend modes (black-key, add, etc.) collapse to writing the winning
layer colour scaled by opacity.

Soft mode draws one pass per layer: spatial weights modulate opacity before the
layer's existing GL blend mode (same channel mapping as GlCompositor).
"""

from __future__ import annotations

from dataclasses import dataclass

import moderngl
import numpy as np
from cleave.config_schema import MAX_LAYER_COUNT
from cleave.gl_color_format import RGBA8, GlColorFormat
from cleave.gl_compositor import GlCompositor, LayerFbo
from OpenGL.GL import (
    GL_ACTIVE_TEXTURE,
    GL_BLEND,
    GL_BLEND_DST_ALPHA,
    GL_BLEND_EQUATION,
    GL_BLEND_SRC_ALPHA,
    GL_COLOR_ATTACHMENT0,
    GL_COLOR_BUFFER_BIT,
    GL_COLOR_WRITEMASK,
    GL_DEPTH_TEST,
    GL_FRAMEBUFFER,
    GL_FRAMEBUFFER_BINDING,
    GL_READ_BUFFER,
    GL_READ_FRAMEBUFFER,
    GL_READ_FRAMEBUFFER_BINDING,
    GL_SCISSOR_BOX,
    GL_SCISSOR_TEST,
    GL_TEXTURE0,
    GL_TEXTURE_2D,
    GL_TEXTURE_2D_ARRAY,
    GL_VIEWPORT,
    glActiveTexture,
    glBindFramebuffer,
    glBindTexture,
    glBlendEquation,
    glBlendFunc,
    glClear,
    glClearColor,
    glColorMask,
    glCopyTexSubImage3D,
    glDeleteTextures,
    glDisable,
    glEnable,
    glGetIntegerv,
    glIsEnabled,
    glReadBuffer,
    glScissor,
    glUseProgram,
    glViewport,
)

try:
    from OpenGL.GL import GL_VERTEX_ARRAY_BINDING, glBindVertexArray
except ImportError:  # pragma: no cover - PyOpenGL without VAO entry points
    GL_VERTEX_ARRAY_BINDING = None  # type: ignore[misc, assignment]
    glBindVertexArray = None  # type: ignore[misc, assignment]

from cleave.pattern_mask import upload_mask_r8_texture, upload_mask_weight_textures

_QUAD_VERT = """
#version 330
in vec2 in_vert;
in vec2 in_uv;
out vec2 uv;
void main() {
    gl_Position = vec4(in_vert, 0.0, 1.0);
    uv = in_uv;
}
"""

_MASKED_FRAG = """
#version 330
uniform sampler2DArray layers;
uniform sampler2D mask;
uniform int layer_count;
uniform float opacities[8];
in vec2 uv;
out vec4 fragColor;

void main() {
    float r = texture(mask, uv).r;
    int idx = int(r * 255.0 + 0.5);
    idx = clamp(idx, 0, max(layer_count - 1, 0));
    vec4 color = texture(layers, vec3(uv, float(idx)));
    float opacity = opacities[idx];
    // Hard mode vs cleared black: blend modes are identity; scale by opacity.
    fragColor = vec4(color.rgb * opacity, 1.0);
}
"""

_SOFT_FRAG = """
#version 330
uniform sampler2D layer_tex;
uniform sampler2D weight_tex;
uniform float layer_opacity;
uniform int opacity_in_alpha;
in vec2 uv;
out vec4 fragColor;

void main() {
    vec4 color = texture(layer_tex, uv);
    float w = texture(weight_tex, uv).r;
    float op = layer_opacity * w;
    if (opacity_in_alpha != 0) {
        // Match GlCompositor add mode: opacity lives in fragment alpha.
        fragColor = vec4(color.rgb, op);
    } else {
        // Black-key and other SRC_COLOR-weighted modes bake opacity into RGB.
        fragColor = vec4(color.rgb * op, 1.0);
    }
}
"""


def _ensure_moderngl_draw_state() -> None:
    """Leave fixed-function GL state compatible with moderngl fullscreen draws."""
    glColorMask(True, True, True, True)
    glDisable(GL_SCISSOR_TEST)
    glDisable(GL_BLEND)
    glDisable(GL_DEPTH_TEST)


def _ensure_soft_draw_state() -> None:
    """Soft multi-pass draws need blend enabled; blend func is set per layer."""
    glColorMask(True, True, True, True)
    glDisable(GL_SCISSOR_TEST)
    glEnable(GL_BLEND)
    glDisable(GL_DEPTH_TEST)


def _gl_int(param: int) -> int:
    value = glGetIntegerv(param)
    try:
        return int(value[0])
    except (TypeError, IndexError):
        return int(value)


@dataclass
class _SavedGlState:
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


def _gl_bool_vector(param: int, size: int) -> tuple[bool, ...]:
    values = glGetIntegerv(param)
    return tuple(bool(int(values[i])) for i in range(size))


def _save_gl_state() -> _SavedGlState:
    viewport = glGetIntegerv(GL_VIEWPORT)
    scissor = glGetIntegerv(GL_SCISSOR_BOX)
    vao_binding: int | None = None
    if GL_VERTEX_ARRAY_BINDING is not None:
        vao_binding = _gl_int(GL_VERTEX_ARRAY_BINDING)
    return _SavedGlState(
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
        color_writemask=_gl_bool_vector(GL_COLOR_WRITEMASK, 4),  # type: ignore[assignment]
        vertex_array_binding=vao_binding,
        read_framebuffer=_gl_int(GL_READ_FRAMEBUFFER_BINDING),
        read_buffer=_gl_int(GL_READ_BUFFER),
    )


def _restore_gl_state(state: _SavedGlState) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, state.framebuffer)
    glBindFramebuffer(GL_READ_FRAMEBUFFER, state.read_framebuffer)
    glReadBuffer(state.read_buffer)
    glViewport(*state.viewport)
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


def _prepare_fixed_function_gl() -> None:
    """Leave GL ready for the pygame compositor (fixed-function glBegin/glEnd)."""
    glUseProgram(0)
    glEnable(GL_TEXTURE_2D)
    glActiveTexture(GL_TEXTURE0)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    if glBindVertexArray is not None:
        glBindVertexArray(0)


class GlMaskedCompositor:
    """Pattern-mask composite into an existing content FBO (hard and soft)."""

    def __init__(
        self,
        content_width: int,
        content_height: int,
        color_format: GlColorFormat = RGBA8,
    ) -> None:
        self.content_width = int(content_width)
        self.content_height = int(content_height)
        self._color_format = color_format
        self._ctx: moderngl.Context | None = None
        self._quad_buffer: moderngl.Buffer | None = None
        self._quad_vao: moderngl.VertexArray | None = None
        self._soft_quad_vao: moderngl.VertexArray | None = None
        self._masked_prog: moderngl.Program | None = None
        self._soft_prog: moderngl.Program | None = None
        self._layer_array_id: int = 0
        self._layer_array_mgl: moderngl.TextureArray | None = None
        self._mask_texture_id: int = 0
        self._mask_width: int = 0
        self._mask_height: int = 0
        self._mask_owned: bool = False
        self._mask_mgl: moderngl.Texture | None = None
        self._weight_texture_ids: list[int] = []
        self._weight_width: int = 0
        self._weight_height: int = 0
        self._weight_layer_count: int = 0
        self._weight_mgl: list[moderngl.Texture] = []
        self._layer_tex_mgl: dict[int, moderngl.Texture] = {}
        self._dest_fbos: dict[int, moderngl.Framebuffer] = {}
        self._bg: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)

    @property
    def color_format(self) -> GlColorFormat:
        return self._color_format

    def set_color_format(self, color_format: GlColorFormat) -> None:
        if color_format is self._color_format:
            return
        self._color_format = color_format
        self._release_layer_array()
        self._release_layer_tex_cache()

    def set_content_size(self, width: int, height: int) -> None:
        width = int(width)
        height = int(height)
        if width == self.content_width and height == self.content_height:
            return
        self.content_width = width
        self.content_height = height
        self._release_layer_array()
        self._release_layer_tex_cache()
        self._release_weight_textures()

    def init(self) -> None:
        """Attach to the current pygame OpenGL context."""
        self._ctx = moderngl.create_context(require=330)
        self._masked_prog = self._ctx.program(
            vertex_shader=_QUAD_VERT,
            fragment_shader=_MASKED_FRAG,
        )
        self._soft_prog = self._ctx.program(
            vertex_shader=_QUAD_VERT,
            fragment_shader=_SOFT_FRAG,
        )
        # Binary float32 quad: (x, y, u, v) per vertex covering NDC [-1,1] x [-1,1].
        self._quad_buffer = self._ctx.buffer(
            np.array(
                [
                    -1.0, -1.0, 0.0, 0.0,
                     1.0, -1.0, 1.0, 0.0,
                    -1.0,  1.0, 0.0, 1.0,
                     1.0,  1.0, 1.0, 1.0,
                ],
                dtype=np.float32,
            ).tobytes()
        )
        self._quad_vao = self._ctx.vertex_array(
            self._masked_prog,
            [(self._quad_buffer, "2f 2f", "in_vert", "in_uv")],
        )
        self._soft_quad_vao = self._ctx.vertex_array(
            self._soft_prog,
            [(self._quad_buffer, "2f 2f", "in_vert", "in_uv")],
        )
        self._ensure_layer_array()

    def _ensure_init(self) -> None:
        if self._ctx is None:
            self.init()

    def _release_layer_array(self) -> None:
        if self._layer_array_mgl is not None:
            self._layer_array_mgl.release()
            self._layer_array_mgl = None
        if self._layer_array_id:
            # Owned by moderngl when wrapped; only delete if we created via PyOpenGL.
            self._layer_array_id = 0

    def _release_layer_tex_cache(self) -> None:
        for tex in self._layer_tex_mgl.values():
            tex.release()
        self._layer_tex_mgl.clear()

    def _ensure_layer_array(self) -> None:
        self._ensure_init()
        assert self._ctx is not None
        if self._layer_array_mgl is not None:
            return
        dtype = self._color_format.moderngl_internal_dtype
        arr = self._ctx.texture_array(
            (self.content_width, self.content_height, MAX_LAYER_COUNT),
            4,
            dtype=dtype,
        )
        arr.filter = (moderngl.LINEAR, moderngl.LINEAR)
        arr.repeat_x = False
        arr.repeat_y = False
        self._layer_array_mgl = arr
        self._layer_array_id = int(arr.glo)

    def _dest_fbo_for(self, content_fbo_id: int) -> moderngl.Framebuffer:
        self._ensure_init()
        assert self._ctx is not None
        cached = self._dest_fbos.get(content_fbo_id)
        if cached is not None:
            return cached
        fbo = self._ctx.detect_framebuffer(content_fbo_id)
        self._dest_fbos[content_fbo_id] = fbo
        return fbo

    def _release_mask_texture(self) -> None:
        if self._mask_mgl is not None:
            self._mask_mgl.release()
            self._mask_mgl = None
        if self._mask_owned and self._mask_texture_id:
            glDeleteTextures(1, [self._mask_texture_id])
        self._mask_texture_id = 0
        self._mask_width = 0
        self._mask_height = 0
        self._mask_owned = False

    def _release_weight_textures(self) -> None:
        for tex in self._weight_mgl:
            tex.release()
        self._weight_mgl.clear()
        if self._weight_texture_ids:
            glDeleteTextures(len(self._weight_texture_ids), self._weight_texture_ids)
        self._weight_texture_ids = []
        self._weight_width = 0
        self._weight_height = 0
        self._weight_layer_count = 0

    def _ensure_mask_texture(self, width: int, height: int) -> None:
        if (
            self._mask_owned
            and self._mask_texture_id
            and self._mask_width == width
            and self._mask_height == height
        ):
            return
        self._release_mask_texture()
        self._mask_texture_id = upload_mask_r8_texture(
            np.zeros((height, width), dtype=np.uint8)
        )
        self._mask_width = width
        self._mask_height = height
        self._mask_owned = True

    def _ensure_weight_textures(self, width: int, height: int, layer_count: int) -> None:
        if (
            self._weight_texture_ids
            and self._weight_width == width
            and self._weight_height == height
            and self._weight_layer_count == layer_count
        ):
            return
        self._release_weight_textures()
        zeros = np.zeros((height, width, layer_count), dtype=np.uint8)
        self._weight_texture_ids = upload_mask_weight_textures(zeros)
        self._weight_width = width
        self._weight_height = height
        self._weight_layer_count = layer_count

    def _bind_mask_mgl(self) -> moderngl.Texture:
        self._ensure_init()
        assert self._ctx is not None
        if self._mask_mgl is not None and self._mask_mgl.glo == self._mask_texture_id:
            return self._mask_mgl
        if self._mask_mgl is not None:
            self._mask_mgl.release()
        tex = self._ctx.external_texture(
            self._mask_texture_id,
            (self._mask_width, self._mask_height),
            1,
            0,
            "f1",
        )
        tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        tex.repeat_x = False
        tex.repeat_y = False
        self._mask_mgl = tex
        return tex

    def _bind_weight_mgl(self, index: int) -> moderngl.Texture:
        self._ensure_init()
        assert self._ctx is not None
        texture_id = self._weight_texture_ids[index]
        if index < len(self._weight_mgl):
            cached = self._weight_mgl[index]
            if cached.glo == texture_id:
                return cached
            cached.release()
            self._weight_mgl[index] = self._make_weight_mgl(texture_id)
            return self._weight_mgl[index]
        while len(self._weight_mgl) < index:
            # Should not happen if ensure matched layer_count; keep list aligned.
            self._weight_mgl.append(self._make_weight_mgl(self._weight_texture_ids[len(self._weight_mgl)]))
        self._weight_mgl.append(self._make_weight_mgl(texture_id))
        return self._weight_mgl[index]

    def _make_weight_mgl(self, texture_id: int) -> moderngl.Texture:
        assert self._ctx is not None
        tex = self._ctx.external_texture(
            texture_id,
            (self._weight_width, self._weight_height),
            1,
            0,
            "f1",
        )
        tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        tex.repeat_x = False
        tex.repeat_y = False
        return tex

    def _bind_layer_tex_mgl(self, layer: LayerFbo) -> moderngl.Texture:
        self._ensure_init()
        assert self._ctx is not None
        cached = self._layer_tex_mgl.get(layer.texture_id)
        if cached is not None:
            return cached
        dtype = self._color_format.moderngl_external_dtype
        tex = self._ctx.external_texture(
            layer.texture_id,
            (layer.width, layer.height),
            4,
            0,
            dtype,
        )
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        tex.repeat_x = False
        tex.repeat_y = False
        self._layer_tex_mgl[layer.texture_id] = tex
        return tex

    def _copy_layers_into_array(self, layers: list[LayerFbo]) -> list[float]:
        """Copy each layer colour attachment into a texture-array slice.

        Returns the opacity uniform list (length MAX_LAYER_COUNT, unused slots 0).
        """
        self._ensure_layer_array()
        assert self._layer_array_id
        opacities = [0.0] * MAX_LAYER_COUNT
        width = self.content_width
        height = self.content_height
        for index, layer in enumerate(layers):
            if index >= MAX_LAYER_COUNT:
                break
            opacities[index] = float(layer.opacity)
            if layer.fbo_id == 0:
                continue
            glBindFramebuffer(GL_READ_FRAMEBUFFER, layer.fbo_id)
            glReadBuffer(GL_COLOR_ATTACHMENT0)
            glBindTexture(GL_TEXTURE_2D_ARRAY, self._layer_array_id)
            glCopyTexSubImage3D(
                GL_TEXTURE_2D_ARRAY,
                0,
                0,
                0,
                index,
                0,
                0,
                width,
                height,
            )
        glBindTexture(GL_TEXTURE_2D_ARRAY, 0)
        glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)
        return opacities

    def composite_masked(
        self,
        content_fbo_id: int,
        layers: list[LayerFbo],
        mask: np.ndarray | int,
    ) -> None:
        """Clear *content_fbo_id* and composite *layers* through a hard mask.

        *mask* is either a 2D uint8 region-index array (H x W, matching content
        size) or an existing GL texture id (R8, width x height, NEAREST).
        """
        self._ensure_init()
        assert self._ctx is not None
        assert self._masked_prog is not None
        assert self._quad_vao is not None

        active = [layer for layer in layers if layer.enabled and layer.opacity > 0.0]
        layer_count = len(active)
        saved = _save_gl_state()
        try:
            glBindFramebuffer(GL_FRAMEBUFFER, content_fbo_id)
            glViewport(0, 0, self.content_width, self.content_height)
            glClearColor(*self._bg)
            glClear(GL_COLOR_BUFFER_BIT)

            if layer_count <= 0:
                return

            if isinstance(mask, np.ndarray):
                if mask.ndim != 2 or mask.dtype != np.uint8:
                    raise ValueError("mask array must be 2D uint8")
                if (
                    int(mask.shape[0]) != self.content_height
                    or int(mask.shape[1]) != self.content_width
                ):
                    raise ValueError(
                        f"mask shape {mask.shape} != "
                        f"({self.content_height}, {self.content_width})"
                    )
                self._ensure_mask_texture(self.content_width, self.content_height)
                upload_mask_r8_texture(mask, texture_id=self._mask_texture_id)
                mask_tex_id = self._mask_texture_id
            else:
                mask_tex_id = int(mask)
                if mask_tex_id == 0:
                    raise ValueError("mask texture id must be non-zero")
                if self._mask_texture_id != mask_tex_id:
                    self._release_mask_texture()
                    self._mask_texture_id = mask_tex_id
                    self._mask_width = self.content_width
                    self._mask_height = self.content_height
                    self._mask_owned = False

            opacities = self._copy_layers_into_array(active)
            dest = self._dest_fbo_for(content_fbo_id)
            mask_tex = self._bind_mask_mgl()
            layer_array = self._layer_array_mgl
            assert layer_array is not None

            _ensure_moderngl_draw_state()
            dest.use()
            layer_array.use(0)
            mask_tex.use(1)
            self._masked_prog["layers"].value = 0
            self._masked_prog["mask"].value = 1
            self._masked_prog["layer_count"].value = layer_count
            self._masked_prog["opacities"].value = tuple(opacities)
            self._quad_vao.render(moderngl.TRIANGLE_STRIP)
        finally:
            _restore_gl_state(saved)
            _prepare_fixed_function_gl()

    def composite_soft(
        self,
        content_fbo_id: int,
        layers: list[LayerFbo],
        weights: np.ndarray,
    ) -> None:
        """Clear *content_fbo_id* and composite *layers* with soft weight textures.

        *weights* is (H, W, N) uint8 with N equal to the number of enabled layers
        that have opacity > 0. Per-pixel weights should sum to approximately 255.
        Each layer is drawn in its own pass with weight-modulated opacity and the
        layer's existing GL blend mode.
        """
        self._ensure_init()
        assert self._ctx is not None
        assert self._soft_prog is not None
        assert self._soft_quad_vao is not None

        active = [layer for layer in layers if layer.enabled and layer.opacity > 0.0]
        layer_count = len(active)
        saved = _save_gl_state()
        try:
            glBindFramebuffer(GL_FRAMEBUFFER, content_fbo_id)
            glViewport(0, 0, self.content_width, self.content_height)
            glClearColor(*self._bg)
            glClear(GL_COLOR_BUFFER_BIT)

            if layer_count <= 0:
                return

            if weights.ndim != 3 or weights.dtype != np.uint8:
                raise ValueError("weights must be a 3D uint8 array (H, W, N)")
            if (
                int(weights.shape[0]) != self.content_height
                or int(weights.shape[1]) != self.content_width
                or int(weights.shape[2]) != layer_count
            ):
                raise ValueError(
                    f"weights shape {weights.shape} != "
                    f"({self.content_height}, {self.content_width}, {layer_count})"
                )

            self._ensure_weight_textures(
                self.content_width, self.content_height, layer_count
            )
            upload_mask_weight_textures(
                weights, texture_ids=self._weight_texture_ids
            )
            for tex in self._weight_mgl:
                tex.release()
            self._weight_mgl = []

            dest = self._dest_fbo_for(content_fbo_id)
            _ensure_soft_draw_state()
            dest.use()
            self._soft_prog["layer_tex"].value = 0
            self._soft_prog["weight_tex"].value = 1

            for index, layer in enumerate(active):
                GlCompositor._apply_layer_blend_mode(layer.blend_mode)
                layer_tex = self._bind_layer_tex_mgl(layer)
                weight_tex = self._bind_weight_mgl(index)
                layer_tex.use(0)
                weight_tex.use(1)
                self._soft_prog["layer_opacity"].value = float(layer.opacity)
                self._soft_prog["opacity_in_alpha"].value = (
                    1 if layer.blend_mode == "add" else 0
                )
                self._soft_quad_vao.render(moderngl.TRIANGLE_STRIP)
        finally:
            _restore_gl_state(saved)
            _prepare_fixed_function_gl()

    def release(self) -> None:
        # detect_framebuffer wraps are references; do not GL-delete them.
        self._dest_fbos.clear()
        self._release_mask_texture()
        self._release_weight_textures()
        self._release_layer_tex_cache()
        self._release_layer_array()
        if self._soft_quad_vao is not None:
            self._soft_quad_vao.release()
            self._soft_quad_vao = None
        if self._quad_vao is not None:
            self._quad_vao.release()
            self._quad_vao = None
        if self._quad_buffer is not None:
            self._quad_buffer.release()
            self._quad_buffer = None
        if self._soft_prog is not None:
            self._soft_prog.release()
            self._soft_prog = None
        if self._masked_prog is not None:
            self._masked_prog.release()
            self._masked_prog = None
        self._ctx = None
