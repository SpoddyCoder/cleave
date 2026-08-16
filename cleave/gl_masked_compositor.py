"""Shader-based masked layer composite via moderngl (hard and feathered).

Feather 0% against a cleared black background: only one layer wins per pixel, so
per-layer blend modes (black-key, add, etc.) collapse to writing the winning
layer colour scaled by opacity.

Feather above 0% draws one pass per layer: spatial weights modulate opacity
before the layer's existing GL blend mode (same channel mapping as GlCompositor).
"""

from __future__ import annotations

from dataclasses import dataclass

import moderngl
import numpy as np
from cleave.config_schema import MAX_LAYER_COUNT
from cleave.gl_color_format import RGBA8, GlColorFormat
from cleave.gl_compositor import GlCompositor, LayerFbo
from cleave.pattern_mask import (
    HardLayout1D,
    PatternMaskParams,
    generate_hard_mask,
    generate_soft_weight_fields,
    hard_layout_1d,
    hard_mask_from_weight_fields,
    lerp_hard_layout_1d,
    one_hot_weight_fields,
    pattern_mask_plasma_power,
    rasterize_hard_layout_1d,
    u8_weights_from_fields,
    upload_mask_r8_texture,
)
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

# Transition weight fields are generated at 1/N of content resolution to avoid
# a stutter on the first frame.  GPU LINEAR filtering upscales transparently.
_TRANSITION_GEN_DIVISOR: int = 4

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
    // Feather 0% vs cleared black: blend modes are identity; scale by opacity.
    fragColor = vec4(color.rgb * opacity, 1.0);
}
"""

_SOFT_FRAG = """
#version 330
uniform sampler2D layer_tex;
uniform sampler2DArray weight_array;
uniform int layer_index;
uniform float layer_opacity;
uniform int opacity_in_alpha;
in vec2 uv;
out vec4 fragColor;

void main() {
    vec4 color = texture(layer_tex, uv);
    float w = texture(weight_array, vec3(uv, float(layer_index))).r;
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

_PLASMA_GEN_COMMON = """
#version 330

uniform vec2 resolution;
uniform float density;
uniform int seed;
uniform int layer_count;

uint hash_u32(ivec2 p, int hash_seed) {
    uint n = uint(p.x) * 374761393u + uint(p.y) * 668265263u
        + uint(hash_seed) * 1274126177u;
    n = (n ^ (n >> 13u)) * 1274126177u;
    return n;
}

float lattice_value(ivec2 p, int hash_seed) {
    return float(hash_u32(p, hash_seed)) / 4294967295.0;
}

float value_noise(vec2 coords, int hash_seed) {
    ivec2 i0 = ivec2(floor(coords));
    ivec2 i1 = i0 + ivec2(1, 0);
    ivec2 i2 = i0 + ivec2(0, 1);
    ivec2 i3 = i0 + ivec2(1, 1);
    vec2 f = coords - vec2(i0);
    vec2 u = f * f * (vec2(3.0) - vec2(2.0) * f);
    float v00 = lattice_value(i0, hash_seed);
    float v10 = lattice_value(i1, hash_seed);
    float v01 = lattice_value(i2, hash_seed);
    float v11 = lattice_value(i3, hash_seed);
    float v0 = mix(v00, v10, u.x);
    float v1 = mix(v01, v11, u.x);
    return mix(v0, v1, u.y);
}

float plasma_frequency() {
    return max(0.25, 2.0 * density);
}

vec2 plasma_coords() {
    return (gl_FragCoord.xy + vec2(0.5)) / resolution * plasma_frequency();
}

float plasma_field(int layer_index) {
    float frequency = plasma_frequency();
    vec2 coords = (gl_FragCoord.xy + vec2(0.5)) / resolution * frequency;
    int layer_seed = seed + layer_index * 97331;
    float field = value_noise(coords, layer_seed);
    if (layer_index > 0) {
        int blend_seed = seed + layer_index * 224682 + 17;
        vec2 blend_coords = (gl_FragCoord.xy + vec2(0.5)) / resolution
            * frequency * (1.0 + 0.17 * float(layer_index));
        field = 0.65 * field + 0.35 * value_noise(blend_coords, blend_seed);
    }
    return field;
}
"""

_PLASMA_HARD_FRAG = (
    _PLASMA_GEN_COMMON
    + """
uniform int invert;
uniform int active_flags[8];
in vec2 uv;
out vec4 fragColor;

void main() {
    float best = -1.0;
    int best_i = 0;
    bool any_active = false;
    for (int i = 0; i < 8; i++) {
        if (i >= layer_count) {
            break;
        }
        if (active_flags[i] == 0) {
            continue;
        }
        float f = plasma_field(i);
        if (f > best || !any_active) {
            best = f;
            best_i = i;
            any_active = true;
        }
    }
    if (!any_active) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    if (invert != 0) {
        best_i = layer_count - 1 - best_i;
    }
    fragColor = vec4(float(best_i) / 255.0, 0.0, 0.0, 1.0);
}
"""
)

_PLASMA_SOFT_FRAG = (
    _PLASMA_GEN_COMMON
    + """
uniform int invert;
uniform int output_layer;
uniform int active_flags[8];
uniform float feather_power;
in vec2 uv;
out vec4 fragColor;

void main() {
    int src_layer = output_layer;
    if (invert != 0) {
        src_layer = layer_count - 1 - output_layer;
    }
    if (active_flags[src_layer] == 0) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    float fields[8];
    float total = 0.0;
    int active_count = 0;
    for (int i = 0; i < 8; i++) {
        if (i >= layer_count || active_flags[i] == 0) {
            fields[i] = 0.0;
            continue;
        }
        float f = plasma_field(i);
        if (feather_power != 1.0) {
            f = pow(max(f, 0.0), feather_power);
        }
        fields[i] = f;
        total += fields[i];
        active_count++;
    }
    float inv_n = 1.0 / max(float(active_count), 1.0);
    float w = total > 0.0 ? fields[src_layer] / total : inv_n;
    float scaled = w * 255.0;
    int u8 = int(floor(scaled + 0.5));
    u8 = clamp(u8, 0, 255);
    fragColor = vec4(float(u8) / 255.0, 0.0, 0.0, 1.0);
}
"""
)


_HARD_LAYOUT_MASK_TYPES = frozenset({"strips", "radial"})

_SOFT_TRANSITION_FRAG = """
#version 330
uniform sampler2D layer_tex;
uniform sampler2DArray old_weight_array;
uniform sampler2DArray new_weight_array;
uniform int layer_index;
uniform float layer_opacity;
uniform int opacity_in_alpha;
uniform float transition_t;
in vec2 uv;
out vec4 fragColor;

void main() {
    vec4 color = texture(layer_tex, uv);
    float w_old = texture(old_weight_array, vec3(uv, float(layer_index))).r;
    float w_new = texture(new_weight_array, vec3(uv, float(layer_index))).r;
    float w = mix(w_old, w_new, transition_t);
    float op = layer_opacity * w;
    if (opacity_in_alpha != 0) {
        fragColor = vec4(color.rgb, op);
    } else {
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


@dataclass(frozen=True)
class _MaskCacheKey:
    mask_type: str
    feather_pct: int
    width: int
    height: int
    layer_count: int
    active_slots: tuple[bool, ...]
    density: float
    invert: bool
    seed: int


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


def _restore_gl_state(
    state: _SavedGlState,
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


def _prepare_fixed_function_gl() -> None:
    """Leave GL ready for the pygame compositor (fixed-function glBegin/glEnd)."""
    glUseProgram(0)
    glEnable(GL_TEXTURE_2D)
    glActiveTexture(GL_TEXTURE0)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    if glBindVertexArray is not None:
        glBindVertexArray(0)


def _mask_cache_key(
    params: PatternMaskParams,
    *,
    gen_width: int,
    gen_height: int,
    layer_count: int,
    active_slots: tuple[bool, ...],
) -> _MaskCacheKey:
    return _MaskCacheKey(
        mask_type=params.mask_type,
        feather_pct=int(params.feather_pct),
        width=int(gen_width),
        height=int(gen_height),
        layer_count=int(layer_count),
        active_slots=tuple(bool(flag) for flag in active_slots),
        density=float(params.density),
        invert=bool(params.invert),
        seed=int(params.seed),
    )


def _uses_hard_layout_morph(params: PatternMaskParams) -> bool:
    """Strips/radial at feather 0 lerp 1D cuts; checker/plasma dissolve instead."""
    return int(params.feather_pct) == 0 and params.mask_type in _HARD_LAYOUT_MASK_TYPES


class GlMaskedCompositor:
    """Pattern-mask composite into an existing content FBO (hard and feathered)."""

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
        self._plasma_hard_vao: moderngl.VertexArray | None = None
        self._plasma_soft_vao: moderngl.VertexArray | None = None
        self._masked_prog: moderngl.Program | None = None
        self._soft_prog: moderngl.Program | None = None
        self._plasma_hard_prog: moderngl.Program | None = None
        self._plasma_soft_prog: moderngl.Program | None = None
        self._layer_array_id: int = 0
        self._layer_array_mgl: moderngl.TextureArray | None = None
        self._mask_texture_id: int = 0
        self._mask_width: int = 0
        self._mask_height: int = 0
        self._mask_owned: bool = False
        self._mask_mgl: moderngl.Texture | None = None
        self._weight_array_mgl: moderngl.TextureArray | None = None
        self._weight_width: int = 0
        self._weight_height: int = 0
        self._weight_layer_count: int = 0
        self._plasma_hard_fbo: moderngl.Framebuffer | None = None
        self._plasma_soft_slice_tex: moderngl.Texture | None = None
        self._plasma_soft_slice_fbo: moderngl.Framebuffer | None = None
        self._plasma_soft_slice_width: int = 0
        self._plasma_soft_slice_height: int = 0
        self._layer_tex_mgl: dict[int, moderngl.Texture] = {}
        self._dest_fbos: dict[int, moderngl.Framebuffer] = {}
        self._bg: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
        self._mask_cache_key: _MaskCacheKey | None = None
        self._transition_old_weights: np.ndarray | None = None
        self._transition_target_weights: np.ndarray | None = None
        self._transition_old_layout: HardLayout1D | None = None
        self._transition_target_layout: HardLayout1D | None = None
        self._transition_params: PatternMaskParams | None = None
        self._transition_start: float = 0.0
        self._transition_duration: float = 0.0
        self._transition_active_slots: tuple[bool, ...] | None = None
        self._current_weight_fields: np.ndarray | None = None
        self._last_active_slots: tuple[bool, ...] | None = None
        self._soft_transition_prog: moderngl.Program | None = None
        self._soft_transition_vao: moderngl.VertexArray | None = None
        self._transition_old_tex: moderngl.TextureArray | None = None
        self._transition_target_tex: moderngl.TextureArray | None = None
        self._transition_gpu_ready: bool = False

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
        self._release_mask_texture()
        self._release_weight_array()
        self._release_plasma_gen_targets()
        self._mask_cache_key = None
        self._clear_transition_state()
        self._current_weight_fields = None
        self._last_active_slots = None

    def _clear_transition_state(self) -> None:
        self._transition_old_weights = None
        self._transition_target_weights = None
        self._transition_old_layout = None
        self._transition_target_layout = None
        self._transition_params = None
        self._transition_start = 0.0
        self._transition_duration = 0.0
        self._transition_active_slots = None
        self._release_transition_textures()

    def _release_transition_textures(self) -> None:
        if self._transition_old_tex is not None:
            self._transition_old_tex.release()
            self._transition_old_tex = None
        if self._transition_target_tex is not None:
            self._transition_target_tex.release()
            self._transition_target_tex = None
        self._transition_gpu_ready = False

    def _upload_transition_textures(
        self, old_fields: np.ndarray, target_fields: np.ndarray
    ) -> None:
        """Convert weight fields to uint8 and upload as GPU texture arrays (once)."""
        self._ensure_init()
        assert self._ctx is not None
        old_u8 = u8_weights_from_fields(old_fields)
        target_u8 = u8_weights_from_fields(target_fields)
        height, width, layer_count = (
            int(old_u8.shape[0]),
            int(old_u8.shape[1]),
            int(old_u8.shape[2]),
        )
        old_data = np.ascontiguousarray(np.transpose(old_u8, (2, 0, 1)))
        target_data = np.ascontiguousarray(np.transpose(target_u8, (2, 0, 1)))
        self._release_transition_textures()
        for data, attr in (
            (old_data, "_transition_old_tex"),
            (target_data, "_transition_target_tex"),
        ):
            tex = self._ctx.texture_array(
                (width, height, layer_count), 1, dtype="f1",
            )
            tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            tex.repeat_x = False
            tex.repeat_y = False
            tex.write(data.tobytes())
            setattr(self, attr, tex)
        self._transition_gpu_ready = True

    def _has_hard_layout_transition(self) -> bool:
        return (
            self._transition_old_layout is not None
            and self._transition_target_layout is not None
        )

    def _has_weight_field_transition(self) -> bool:
        return (
            self._transition_old_weights is not None
            and self._transition_target_weights is not None
        )

    def _transition_in_progress(self, song_time_sec: float) -> bool:
        if not self._has_hard_layout_transition() and not self._has_weight_field_transition():
            return False
        if self._transition_duration <= 0.0:
            return False
        return float(song_time_sec) < self._transition_start + self._transition_duration

    def _transition_amount(self, song_time_sec: float) -> float:
        duration = max(self._transition_duration, 1e-9)
        t = (float(song_time_sec) - self._transition_start) / duration
        return max(0.0, min(1.0, t))

    def _transition_matches_params(self, params: PatternMaskParams) -> bool:
        stored = self._transition_params
        if stored is None:
            return False
        if (
            stored.mask_type != params.mask_type
            or int(stored.feather_pct) != int(params.feather_pct)
            or float(stored.density) != float(params.density)
            or bool(stored.invert) != bool(params.invert)
            or int(stored.seed) != int(params.seed)
        ):
            return False
        if _uses_hard_layout_morph(params):
            return self._has_hard_layout_transition()
        return self._has_weight_field_transition()

    def _blended_transition_weights(self, song_time_sec: float) -> np.ndarray:
        assert self._transition_old_weights is not None
        assert self._transition_target_weights is not None
        duration = max(self._transition_duration, 1e-9)
        t = (float(song_time_sec) - self._transition_start) / duration
        t = max(0.0, min(1.0, t))
        return (
            self._transition_old_weights * (1.0 - t)
            + self._transition_target_weights * t
        )

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
        self._plasma_hard_prog = self._ctx.program(
            vertex_shader=_QUAD_VERT,
            fragment_shader=_PLASMA_HARD_FRAG,
        )
        self._plasma_soft_prog = self._ctx.program(
            vertex_shader=_QUAD_VERT,
            fragment_shader=_PLASMA_SOFT_FRAG,
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
        self._plasma_hard_vao = self._ctx.vertex_array(
            self._plasma_hard_prog,
            [(self._quad_buffer, "2f 2f", "in_vert", "in_uv")],
        )
        self._plasma_soft_vao = self._ctx.vertex_array(
            self._plasma_soft_prog,
            [(self._quad_buffer, "2f 2f", "in_vert", "in_uv")],
        )
        self._soft_transition_prog = self._ctx.program(
            vertex_shader=_QUAD_VERT,
            fragment_shader=_SOFT_TRANSITION_FRAG,
        )
        self._soft_transition_vao = self._ctx.vertex_array(
            self._soft_transition_prog,
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

    def _release_weight_array(self) -> None:
        if self._weight_array_mgl is not None:
            self._weight_array_mgl.release()
            self._weight_array_mgl = None
        self._weight_width = 0
        self._weight_height = 0
        self._weight_layer_count = 0

    def _release_plasma_gen_targets(self) -> None:
        if self._plasma_hard_fbo is not None:
            self._plasma_hard_fbo.release()
            self._plasma_hard_fbo = None
        if self._plasma_soft_slice_fbo is not None:
            self._plasma_soft_slice_fbo.release()
            self._plasma_soft_slice_fbo = None
        if self._plasma_soft_slice_tex is not None:
            self._plasma_soft_slice_tex.release()
            self._plasma_soft_slice_tex = None
        self._plasma_soft_slice_width = 0
        self._plasma_soft_slice_height = 0

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
        if self._mask_mgl is not None:
            self._mask_mgl.release()
            self._mask_mgl = None

    def _ensure_weight_array(self, width: int, height: int, layer_count: int) -> None:
        if (
            self._weight_array_mgl is not None
            and self._weight_width == width
            and self._weight_height == height
            and self._weight_layer_count == layer_count
        ):
            return
        self._release_weight_array()
        self._ensure_init()
        assert self._ctx is not None
        arr = self._ctx.texture_array(
            (width, height, layer_count),
            1,
            dtype="f1",
        )
        arr.filter = (moderngl.LINEAR, moderngl.LINEAR)
        arr.repeat_x = False
        arr.repeat_y = False
        arr.write(np.zeros((layer_count, height, width), dtype=np.uint8).tobytes())
        self._weight_array_mgl = arr
        self._weight_width = width
        self._weight_height = height
        self._weight_layer_count = layer_count
        self._release_plasma_gen_targets()

    def _upload_weight_array_cpu(self, weights: np.ndarray) -> None:
        height, width, layer_count = (
            int(weights.shape[0]),
            int(weights.shape[1]),
            int(weights.shape[2]),
        )
        self._ensure_weight_array(width, height, layer_count)
        assert self._weight_array_mgl is not None
        data = np.ascontiguousarray(np.transpose(weights, (2, 0, 1)))
        self._weight_array_mgl.write(data.tobytes())

    def _bind_mask_mgl(self, *, linear_filter: bool = False) -> moderngl.Texture:
        self._ensure_init()
        assert self._ctx is not None
        if self._mask_mgl is not None and self._mask_mgl.glo == self._mask_texture_id:
            filt = (
                moderngl.LINEAR if linear_filter else moderngl.NEAREST,
                moderngl.LINEAR if linear_filter else moderngl.NEAREST,
            )
            if self._mask_mgl.filter != filt:
                self._mask_mgl.filter = filt
            return self._mask_mgl
        if self._mask_mgl is not None:
            self._mask_mgl.release()
        filt = (
            moderngl.LINEAR if linear_filter else moderngl.NEAREST,
            moderngl.LINEAR if linear_filter else moderngl.NEAREST,
        )
        tex = self._ctx.external_texture(
            self._mask_texture_id,
            (self._mask_width, self._mask_height),
            1,
            0,
            "f1",
        )
        tex.filter = filt
        tex.repeat_x = False
        tex.repeat_y = False
        self._mask_mgl = tex
        return tex

    def _bind_weight_array_mgl(self) -> moderngl.TextureArray:
        assert self._weight_array_mgl is not None
        return self._weight_array_mgl

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

    def _ensure_plasma_hard_target(self, width: int, height: int) -> moderngl.Framebuffer:
        self._ensure_init()
        assert self._ctx is not None
        self._ensure_mask_texture(width, height)
        if (
            self._plasma_hard_fbo is not None
            and self._mask_width == width
            and self._mask_height == height
        ):
            return self._plasma_hard_fbo
        self._release_plasma_gen_targets()
        mask_tex = self._bind_mask_mgl()
        self._plasma_hard_fbo = self._ctx.framebuffer(color_attachments=[mask_tex])
        return self._plasma_hard_fbo

    def _ensure_plasma_soft_slice_target(
        self, width: int, height: int
    ) -> tuple[moderngl.Framebuffer, moderngl.Texture]:
        """Reusable 2D R8 target; moderngl 5.x has no framebuffer(layer=)."""
        self._ensure_init()
        assert self._ctx is not None
        if (
            self._plasma_soft_slice_fbo is not None
            and self._plasma_soft_slice_tex is not None
            and self._plasma_soft_slice_width == width
            and self._plasma_soft_slice_height == height
        ):
            return self._plasma_soft_slice_fbo, self._plasma_soft_slice_tex
        if self._plasma_soft_slice_fbo is not None:
            self._plasma_soft_slice_fbo.release()
            self._plasma_soft_slice_fbo = None
        if self._plasma_soft_slice_tex is not None:
            self._plasma_soft_slice_tex.release()
            self._plasma_soft_slice_tex = None
        tex = self._ctx.texture((width, height), 1, dtype="f1")
        tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        tex.repeat_x = False
        tex.repeat_y = False
        fbo = self._ctx.framebuffer(color_attachments=[tex])
        self._plasma_soft_slice_tex = tex
        self._plasma_soft_slice_fbo = fbo
        self._plasma_soft_slice_width = width
        self._plasma_soft_slice_height = height
        return fbo, tex

    def _set_plasma_uniforms(
        self,
        program: moderngl.Program,
        *,
        gen_width: int,
        gen_height: int,
        layer_count: int,
        params: PatternMaskParams,
        active_flags: tuple[bool, ...] | None = None,
    ) -> None:
        program["resolution"].value = (float(gen_width), float(gen_height))
        program["density"].value = float(params.density)
        program["seed"].value = int(params.seed)
        program["layer_count"].value = int(layer_count)
        program["invert"].value = 1 if params.invert else 0
        flags = [0] * MAX_LAYER_COUNT
        for i in range(layer_count):
            if active_flags is None or (i < len(active_flags) and active_flags[i]):
                flags[i] = 1
        program["active_flags"].value = flags

    def _generate_plasma_hard_gpu(
        self,
        *,
        gen_width: int,
        gen_height: int,
        layer_count: int,
        params: PatternMaskParams,
        active_flags: tuple[bool, ...] | None = None,
    ) -> None:
        self._ensure_init()
        assert self._ctx is not None
        assert self._plasma_hard_prog is not None
        assert self._plasma_hard_vao is not None
        fbo = self._ensure_plasma_hard_target(gen_width, gen_height)
        saved = _save_gl_state()
        try:
            _ensure_moderngl_draw_state()
            fbo.use()
            self._ctx.viewport = (0, 0, gen_width, gen_height)
            self._set_plasma_uniforms(
                self._plasma_hard_prog,
                gen_width=gen_width,
                gen_height=gen_height,
                layer_count=layer_count,
                params=params,
                active_flags=active_flags,
            )
            self._plasma_hard_vao.render(moderngl.TRIANGLE_STRIP)
        finally:
            _restore_gl_state(saved, self._ctx)

    def _generate_plasma_soft_gpu(
        self,
        *,
        gen_width: int,
        gen_height: int,
        layer_count: int,
        params: PatternMaskParams,
        active_flags: tuple[bool, ...] | None = None,
    ) -> None:
        self._ensure_init()
        assert self._ctx is not None
        assert self._plasma_soft_prog is not None
        assert self._plasma_soft_vao is not None
        self._ensure_weight_array(gen_width, gen_height, layer_count)
        assert self._weight_array_mgl is not None
        slice_fbo, slice_tex = self._ensure_plasma_soft_slice_target(
            gen_width, gen_height
        )
        saved = _save_gl_state()
        try:
            _ensure_moderngl_draw_state()
            self._ctx.viewport = (0, 0, gen_width, gen_height)
            self._set_plasma_uniforms(
                self._plasma_soft_prog,
                gen_width=gen_width,
                gen_height=gen_height,
                layer_count=layer_count,
                params=params,
                active_flags=active_flags,
            )
            self._plasma_soft_prog["feather_power"].value = (
                pattern_mask_plasma_power(params.feather_pct)
            )
            for index in range(layer_count):
                slice_fbo.use()
                self._plasma_soft_prog["output_layer"].value = index
                self._plasma_soft_vao.render(moderngl.TRIANGLE_STRIP)
                self._weight_array_mgl.write(
                    slice_tex.read(alignment=1),
                    viewport=(0, 0, index, gen_width, gen_height, 1),
                )
        finally:
            _restore_gl_state(saved, self._ctx)

    def _generate_plasma_fields_gpu(
        self,
        *,
        gen_width: int,
        gen_height: int,
        layer_count: int,
        params: PatternMaskParams,
        active_flags: tuple[bool, ...] | None = None,
    ) -> np.ndarray:
        """Render plasma weights on GPU and read back as (N, H, W) float64 fields."""
        self._ensure_init()
        assert self._ctx is not None
        assert self._plasma_soft_prog is not None
        assert self._plasma_soft_vao is not None
        slice_fbo, slice_tex = self._ensure_plasma_soft_slice_target(
            gen_width, gen_height
        )
        saved = _save_gl_state()
        try:
            _ensure_moderngl_draw_state()
            self._ctx.viewport = (0, 0, gen_width, gen_height)
            self._set_plasma_uniforms(
                self._plasma_soft_prog,
                gen_width=gen_width,
                gen_height=gen_height,
                layer_count=layer_count,
                params=params,
                active_flags=active_flags,
            )
            self._plasma_soft_prog["feather_power"].value = (
                pattern_mask_plasma_power(params.feather_pct)
            )
            fields = np.empty((layer_count, gen_height, gen_width), dtype=np.float64)
            for index in range(layer_count):
                slice_fbo.use()
                self._plasma_soft_prog["output_layer"].value = index
                self._plasma_soft_vao.render(moderngl.TRIANGLE_STRIP)
                raw = slice_tex.read(alignment=1)
                layer_u8 = np.frombuffer(raw, dtype=np.uint8).reshape(
                    gen_height, gen_width
                )
                fields[index] = layer_u8.astype(np.float64) / 255.0
        finally:
            _restore_gl_state(saved, self._ctx)
        return fields

    def _generate_mask_cpu(
        self,
        *,
        gen_width: int,
        gen_height: int,
        layer_count: int,
        params: PatternMaskParams,
        active_slots: tuple[bool, ...],
    ) -> np.ndarray:
        """Generate and upload mask textures; return (N, H, W) float weight fields."""
        fields = generate_soft_weight_fields(
            params.mask_type,
            gen_width,
            gen_height,
            layer_count,
            density=params.density,
            invert=params.invert,
            seed=params.seed,
            active_flags=active_slots,
            feather_pct=params.feather_pct,
        )
        self._upload_weight_fields(fields, params.feather_pct)
        return fields

    def _upload_weight_fields(self, fields: np.ndarray, feather_pct: int) -> None:
        if feather_pct > 0:
            self._upload_weight_array_cpu(u8_weights_from_fields(fields))
            return
        mask = hard_mask_from_weight_fields(fields)
        height, width = int(mask.shape[0]), int(mask.shape[1])
        self._ensure_mask_texture(width, height)
        upload_mask_r8_texture(mask, texture_id=self._mask_texture_id)
        if self._mask_mgl is not None:
            self._mask_mgl.release()
            self._mask_mgl = None

    def _generate_mask_cpu_hard_direct(
        self,
        *,
        gen_width: int,
        gen_height: int,
        layer_count: int,
        params: PatternMaskParams,
        active_slots: tuple[bool, ...],
    ) -> np.ndarray:
        """CPU hard mask via pattern generators; also return soft fields for cache."""
        fields = generate_soft_weight_fields(
            params.mask_type,
            gen_width,
            gen_height,
            layer_count,
            density=params.density,
            invert=params.invert,
            seed=params.seed,
            active_flags=active_slots,
            feather_pct=params.feather_pct,
        )
        mask = generate_hard_mask(
            params.mask_type,
            gen_width,
            gen_height,
            layer_count,
            density=params.density,
            invert=params.invert,
            seed=params.seed,
            active_flags=active_slots,
        )
        self._ensure_mask_texture(gen_width, gen_height)
        upload_mask_r8_texture(mask, texture_id=self._mask_texture_id)
        if self._mask_mgl is not None:
            self._mask_mgl.release()
            self._mask_mgl = None
        return fields

    def _all_slots_active(self, active_slots: tuple[bool, ...]) -> bool:
        return bool(active_slots) and all(active_slots)

    def _weight_fields_for_slots(
        self,
        *,
        gen_width: int,
        gen_height: int,
        layer_count: int,
        params: PatternMaskParams,
        active_flags: tuple[bool, ...],
    ) -> np.ndarray:
        if params.mask_type == "plasma":
            fields = self._generate_plasma_fields_gpu(
                gen_width=gen_width,
                gen_height=gen_height,
                layer_count=layer_count,
                params=params,
                active_flags=active_flags,
            )
        else:
            fields = generate_soft_weight_fields(
                params.mask_type,
                gen_width,
                gen_height,
                layer_count,
                density=params.density,
                invert=params.invert,
                seed=params.seed,
                active_flags=active_flags,
                feather_pct=params.feather_pct,
            )
        if int(params.feather_pct) == 0:
            return one_hot_weight_fields(fields)
        return fields

    def _begin_hard_layout_transition(
        self,
        params: PatternMaskParams,
        *,
        active_slots: tuple[bool, ...],
        song_time_sec: float,
        duration: float,
    ) -> None:
        if self._has_hard_layout_transition() and self._transition_in_progress(
            song_time_sec
        ):
            assert self._transition_old_layout is not None
            assert self._transition_target_layout is not None
            old = lerp_hard_layout_1d(
                self._transition_old_layout,
                self._transition_target_layout,
                self._transition_amount(song_time_sec),
            )
        else:
            from_slots = (
                self._last_active_slots
                if self._last_active_slots is not None
                else active_slots
            )
            old = hard_layout_1d(
                params.mask_type, from_slots, params.density, params.invert
            )
        target = hard_layout_1d(
            params.mask_type, active_slots, params.density, params.invert
        )
        self._transition_old_weights = None
        self._transition_target_weights = None
        self._release_transition_textures()
        self._transition_old_layout = old
        self._transition_target_layout = target
        self._transition_params = params
        self._transition_start = float(song_time_sec)
        self._transition_duration = duration
        self._transition_active_slots = active_slots
        self._mask_cache_key = None

    def _begin_weight_field_transition(
        self,
        layer_count: int,
        params: PatternMaskParams,
        *,
        active_slots: tuple[bool, ...],
        song_time_sec: float,
        duration: float,
    ) -> None:
        trans_w = max(1, self.content_width // _TRANSITION_GEN_DIVISOR)
        trans_h = max(1, self.content_height // _TRANSITION_GEN_DIVISOR)
        from_slots = (
            self._last_active_slots
            if self._last_active_slots is not None
            else active_slots
        )
        if self._has_weight_field_transition() and self._transition_in_progress(
            song_time_sec
        ):
            old_fields = self._blended_transition_weights(song_time_sec)
        else:
            old_fields = self._weight_fields_for_slots(
                gen_width=trans_w,
                gen_height=trans_h,
                layer_count=layer_count,
                params=params,
                active_flags=from_slots,
            )
        target_fields = self._weight_fields_for_slots(
            gen_width=trans_w,
            gen_height=trans_h,
            layer_count=layer_count,
            params=params,
            active_flags=active_slots,
        )
        if old_fields.shape[0] != target_fields.shape[0]:
            n = target_fields.shape[0]
            padded = np.zeros_like(target_fields)
            copy_n = min(old_fields.shape[0], n)
            padded[:copy_n] = old_fields[:copy_n]
            old_fields = padded
        self._transition_old_layout = None
        self._transition_target_layout = None
        self._transition_old_weights = old_fields.astype(np.float64, copy=False)
        self._transition_target_weights = target_fields
        self._transition_params = params
        self._transition_start = float(song_time_sec)
        self._transition_duration = duration
        self._transition_active_slots = active_slots
        self._mask_cache_key = None
        self._upload_transition_textures(old_fields, target_fields)

    def _upload_lerped_hard_mask(self, song_time_sec: float) -> None:
        assert self._transition_old_layout is not None
        assert self._transition_target_layout is not None
        layout = lerp_hard_layout_1d(
            self._transition_old_layout,
            self._transition_target_layout,
            self._transition_amount(song_time_sec),
        )
        width = self.content_width
        height = self.content_height
        mask = rasterize_hard_layout_1d(layout, width, height, layout.mask_type)
        self._ensure_mask_texture(width, height)
        upload_mask_r8_texture(mask, texture_id=self._mask_texture_id)
        if self._mask_mgl is not None:
            self._mask_mgl.release()
            self._mask_mgl = None

    def _ensure_mask_textures(
        self,
        layer_count: int,
        params: PatternMaskParams,
        *,
        active_slots: tuple[bool, ...],
        song_time_sec: float,
        transition_duration: float,
    ) -> None:
        if layer_count <= 0:
            return
        gen_width, gen_height = self.content_width, self.content_height
        active_slots = tuple(bool(flag) for flag in active_slots)
        if len(active_slots) != layer_count:
            raise ValueError(
                f"active_slots length {len(active_slots)} != layer_count {layer_count}"
            )

        if self._transition_in_progress(song_time_sec) and not self._transition_matches_params(
            params
        ):
            self._clear_transition_state()

        slots_changed = (
            self._last_active_slots is not None
            and active_slots != self._last_active_slots
        )
        duration = max(0.0, float(transition_duration))

        if slots_changed and duration > 0.0:
            if _uses_hard_layout_morph(params):
                self._begin_hard_layout_transition(
                    params,
                    active_slots=active_slots,
                    song_time_sec=song_time_sec,
                    duration=duration,
                )
            else:
                self._begin_weight_field_transition(
                    layer_count,
                    params,
                    active_slots=active_slots,
                    song_time_sec=song_time_sec,
                    duration=duration,
                )
        elif slots_changed and duration <= 0.0:
            self._clear_transition_state()

        if self._transition_in_progress(song_time_sec):
            if self._has_hard_layout_transition():
                self._upload_lerped_hard_mask(song_time_sec)
            self._last_active_slots = active_slots
            self._mask_cache_key = None
            return

        if self._has_weight_field_transition() or self._has_hard_layout_transition():
            if params.mask_type == "plasma":
                fields = self._generate_plasma_fields_gpu(
                    gen_width=gen_width,
                    gen_height=gen_height,
                    layer_count=layer_count,
                    params=params,
                    active_flags=active_slots,
                )
                if params.feather_pct > 0:
                    self._generate_plasma_soft_gpu(
                        gen_width=gen_width,
                        gen_height=gen_height,
                        layer_count=layer_count,
                        params=params,
                        active_flags=active_slots,
                    )
                else:
                    self._generate_plasma_hard_gpu(
                        gen_width=gen_width,
                        gen_height=gen_height,
                        layer_count=layer_count,
                        params=params,
                        active_flags=active_slots,
                    )
            else:
                fields = generate_soft_weight_fields(
                    params.mask_type,
                    gen_width,
                    gen_height,
                    layer_count,
                    density=params.density,
                    invert=params.invert,
                    seed=params.seed,
                    active_flags=active_slots,
                    feather_pct=params.feather_pct,
                )
                self._upload_weight_fields(fields, params.feather_pct)
            self._current_weight_fields = fields
            self._last_active_slots = active_slots
            self._clear_transition_state()
            self._mask_cache_key = _mask_cache_key(
                params,
                gen_width=gen_width,
                gen_height=gen_height,
                layer_count=layer_count,
                active_slots=active_slots,
            )
            return

        cache_key = _mask_cache_key(
            params,
            gen_width=gen_width,
            gen_height=gen_height,
            layer_count=layer_count,
            active_slots=active_slots,
        )
        if self._mask_cache_key == cache_key and self._current_weight_fields is not None:
            self._last_active_slots = active_slots
            return

        use_gpu_plasma = params.mask_type == "plasma"
        if use_gpu_plasma:
            if params.feather_pct > 0:
                self._generate_plasma_soft_gpu(
                    gen_width=gen_width,
                    gen_height=gen_height,
                    layer_count=layer_count,
                    params=params,
                    active_flags=active_slots,
                )
            else:
                self._generate_plasma_hard_gpu(
                    gen_width=gen_width,
                    gen_height=gen_height,
                    layer_count=layer_count,
                    params=params,
                    active_flags=active_slots,
                )
            fields = self._generate_plasma_fields_gpu(
                gen_width=gen_width,
                gen_height=gen_height,
                layer_count=layer_count,
                params=params,
                active_flags=active_slots,
            )
        elif params.feather_pct == 0 and params.mask_type != "plasma":
            fields = self._generate_mask_cpu_hard_direct(
                gen_width=gen_width,
                gen_height=gen_height,
                layer_count=layer_count,
                params=params,
                active_slots=active_slots,
            )
        else:
            fields = self._generate_mask_cpu(
                gen_width=gen_width,
                gen_height=gen_height,
                layer_count=layer_count,
                params=params,
                active_slots=active_slots,
            )
        self._current_weight_fields = fields
        self._last_active_slots = active_slots
        self._mask_cache_key = cache_key

    def _copy_layers_into_array(
        self,
        layers: list[LayerFbo],
        *,
        keep_disabled_visible: bool = False,
    ) -> list[float]:
        """Copy each layer colour attachment into a texture-array slice.

        Returns the opacity uniform list (length MAX_LAYER_COUNT, unused slots 0).
        Disabled slots keep a black slice and opacity 0, unless
        *keep_disabled_visible* (mid-transition) copies their last frame at full
        opacity so weight morphs can shrink territory without popping to black.
        """
        self._ensure_layer_array()
        assert self._layer_array_id
        opacities = [0.0] * MAX_LAYER_COUNT
        width = self.content_width
        height = self.content_height
        for index, layer in enumerate(layers):
            if index >= MAX_LAYER_COUNT:
                break
            active = bool(layer.enabled and layer.opacity > 0.0 and layer.fbo_id != 0)
            if not active:
                if not keep_disabled_visible or layer.fbo_id == 0:
                    opacities[index] = 0.0
                    continue
                opacities[index] = (
                    float(layer.opacity) if layer.opacity > 0.0 else 1.0
                )
            else:
                opacities[index] = float(layer.opacity)
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

    def live_slots(
        self,
        active_slots: tuple[bool, ...] | list[bool],
        song_time_sec: float,
        transition_duration: float,
    ) -> tuple[bool, ...]:
        """Slots that are active or still have territory in the current morph.

        Call before the layer render loop. A departing slot stays True while
        its hard-layout interval has width or its weight field has mass, and
        turns False when the morph ends (width/mass 0). If *active_slots*
        differs from the last composite and *transition_duration* is positive,
        slots that will be in that morph are included even before composite
        stores the new layouts.
        """
        flags = tuple(bool(flag) for flag in active_slots)
        live = [bool(flag) for flag in flags]
        n = len(live)
        duration = max(0.0, float(transition_duration))
        last = self._last_active_slots
        if last is not None and flags != last and duration > 0.0:
            for index, flag in enumerate(last):
                if index < n and flag:
                    live[index] = True
        if self._transition_in_progress(song_time_sec):
            if self._has_hard_layout_transition():
                assert self._transition_old_layout is not None
                assert self._transition_target_layout is not None
                layout = lerp_hard_layout_1d(
                    self._transition_old_layout,
                    self._transition_target_layout,
                    self._transition_amount(song_time_sec),
                )
                for slot in layout.occupied_slots():
                    if 0 <= slot < n:
                        live[slot] = True
            elif self._has_weight_field_transition():
                assert self._transition_old_weights is not None
                assert self._transition_target_weights is not None
                for fields in (
                    self._transition_old_weights,
                    self._transition_target_weights,
                ):
                    count = min(n, int(fields.shape[0]))
                    for index in range(count):
                        if float(np.max(fields[index])) > 0.0:
                            live[index] = True
        return tuple(live)

    def composite(
        self,
        content_fbo_id: int,
        layers: list[LayerFbo],
        *,
        mask_type: str,
        feather_pct: int = 0,
        density: float = 1.0,
        invert: bool = False,
        seed: int = 0,
        slot_names: list[str] | None = None,
        active_slots: list[bool] | None = None,
        song_time_sec: float = 0.0,
        transition_duration: float = 0.0,
    ) -> None:
        """Clear *content_fbo_id* and composite *layers* through a pattern mask.

        *layers* are slot-keyed in z-order (stable channel indices). When
        *active_slots* is omitted, activity is derived from each layer's enabled
        flag and opacity. *slot_names* is accepted for API completeness.
        """
        del slot_names  # Reserved for callers / debugging; indices follow *layers*.
        params = PatternMaskParams(
            mask_type=mask_type,
            feather_pct=int(feather_pct),
            density=density,
            invert=invert,
            seed=seed,
        )
        if active_slots is None:
            resolved_active = tuple(
                bool(layer.enabled and layer.opacity > 0.0) for layer in layers
            )
        else:
            resolved_active = tuple(bool(flag) for flag in active_slots)
        if feather_pct > 0:
            self._composite_soft(
                content_fbo_id,
                layers,
                params,
                active_slots=resolved_active,
                song_time_sec=song_time_sec,
                transition_duration=transition_duration,
            )
        else:
            self._composite_hard(
                content_fbo_id,
                layers,
                params,
                active_slots=resolved_active,
                song_time_sec=song_time_sec,
                transition_duration=transition_duration,
            )

    def _composite_hard(
        self,
        content_fbo_id: int,
        layers: list[LayerFbo],
        params: PatternMaskParams,
        *,
        active_slots: tuple[bool, ...],
        song_time_sec: float,
        transition_duration: float,
    ) -> None:
        self._ensure_init()
        assert self._ctx is not None
        assert self._masked_prog is not None
        assert self._quad_vao is not None

        layer_count = len(layers)
        saved = _save_gl_state()
        try:
            glBindFramebuffer(GL_FRAMEBUFFER, content_fbo_id)
            glViewport(0, 0, self.content_width, self.content_height)
            glClearColor(*self._bg)
            glClear(GL_COLOR_BUFFER_BIT)

            if layer_count <= 0 or not any(active_slots):
                if not self._transition_in_progress(song_time_sec):
                    self._last_active_slots = active_slots
                    return

            self._ensure_mask_textures(
                layer_count,
                params,
                active_slots=active_slots,
                song_time_sec=song_time_sec,
                transition_duration=transition_duration,
            )
            transitioning = self._transition_in_progress(song_time_sec)
            dest = self._dest_fbo_for(content_fbo_id)
            dest.use()
            self._ctx.viewport = (0, 0, self.content_width, self.content_height)

            if transitioning and self._has_weight_field_transition():
                if not self._transition_gpu_ready:
                    assert self._transition_old_weights is not None
                    assert self._transition_target_weights is not None
                    self._upload_transition_textures(
                        self._transition_old_weights,
                        self._transition_target_weights,
                    )
                _ensure_soft_draw_state()
                self._draw_soft_layer_passes(
                    layers,
                    transitioning=True,
                    song_time_sec=song_time_sec,
                )
                return

            opacities = self._copy_layers_into_array(
                layers,
                keep_disabled_visible=transitioning,
            )
            layer_array = self._layer_array_mgl
            assert layer_array is not None

            _ensure_moderngl_draw_state()
            dest.use()
            self._ctx.viewport = (0, 0, self.content_width, self.content_height)
            layer_array.use(0)
            mask_tex = self._bind_mask_mgl(linear_filter=False)
            mask_tex.use(1)
            self._masked_prog["layers"].value = 0
            self._masked_prog["mask"].value = 1
            self._masked_prog["layer_count"].value = layer_count
            self._masked_prog["opacities"].value = tuple(opacities)
            self._quad_vao.render(moderngl.TRIANGLE_STRIP)
        finally:
            _restore_gl_state(saved, self._ctx)
            _prepare_fixed_function_gl()

    def _composite_soft(
        self,
        content_fbo_id: int,
        layers: list[LayerFbo],
        params: PatternMaskParams,
        *,
        active_slots: tuple[bool, ...],
        song_time_sec: float,
        transition_duration: float,
    ) -> None:
        self._ensure_init()
        assert self._ctx is not None
        assert self._soft_prog is not None
        assert self._soft_quad_vao is not None

        layer_count = len(layers)
        saved = _save_gl_state()
        try:
            glBindFramebuffer(GL_FRAMEBUFFER, content_fbo_id)
            glViewport(0, 0, self.content_width, self.content_height)
            glClearColor(*self._bg)
            glClear(GL_COLOR_BUFFER_BIT)

            if layer_count <= 0:
                self._last_active_slots = active_slots
                return
            if not any(active_slots) and not self._transition_in_progress(song_time_sec):
                self._last_active_slots = active_slots
                return

            self._ensure_mask_textures(
                layer_count,
                params,
                active_slots=active_slots,
                song_time_sec=song_time_sec,
                transition_duration=transition_duration,
            )
            transitioning = (
                self._transition_gpu_ready
                and self._transition_in_progress(song_time_sec)
            )
            dest = self._dest_fbo_for(content_fbo_id)
            _ensure_soft_draw_state()
            dest.use()
            self._ctx.viewport = (0, 0, self.content_width, self.content_height)
            self._draw_soft_layer_passes(
                layers,
                transitioning=transitioning,
                song_time_sec=song_time_sec,
            )
        finally:
            _restore_gl_state(saved, self._ctx)
            _prepare_fixed_function_gl()

    def _draw_soft_layer_passes(
        self,
        layers: list[LayerFbo],
        *,
        transitioning: bool,
        song_time_sec: float,
    ) -> None:
        weight_array = None
        if transitioning:
            prog = self._soft_transition_prog
            vao = self._soft_transition_vao
            assert prog is not None and vao is not None
            assert self._transition_old_tex is not None
            assert self._transition_target_tex is not None
            prog["layer_tex"].value = 0
            prog["old_weight_array"].value = 1
            prog["new_weight_array"].value = 2
            prog["transition_t"].value = self._transition_amount(song_time_sec)
        else:
            prog = self._soft_prog
            vao = self._soft_quad_vao
            assert prog is not None and vao is not None
            weight_array = self._bind_weight_array_mgl()
            prog["layer_tex"].value = 0
            prog["weight_array"].value = 1

        for index, layer in enumerate(layers):
            if index >= MAX_LAYER_COUNT:
                break
            active = bool(layer.enabled and layer.opacity > 0.0)
            if not active and not transitioning:
                continue
            GlCompositor._apply_layer_blend_mode(layer.blend_mode)
            layer_tex = self._bind_layer_tex_mgl(layer)
            layer_tex.use(0)
            if transitioning:
                self._transition_old_tex.use(1)
                self._transition_target_tex.use(2)
            else:
                assert weight_array is not None
                weight_array.use(1)
            prog["layer_index"].value = index
            if active:
                opacity = float(layer.opacity)
            elif transitioning:
                opacity = float(layer.opacity) if layer.opacity > 0.0 else 1.0
            else:
                opacity = 0.0
            prog["layer_opacity"].value = opacity
            prog["opacity_in_alpha"].value = (
                1 if layer.blend_mode == "add" else 0
            )
            vao.render(moderngl.TRIANGLE_STRIP)

    def release(self) -> None:
        # detect_framebuffer wraps are references; do not GL-delete them.
        self._dest_fbos.clear()
        self._release_mask_texture()
        self._release_weight_array()
        self._release_plasma_gen_targets()
        self._release_transition_textures()
        self._release_layer_tex_cache()
        self._release_layer_array()
        for attr in (
            "_soft_transition_vao",
            "_plasma_soft_vao",
            "_plasma_hard_vao",
            "_soft_quad_vao",
            "_quad_vao",
        ):
            obj = getattr(self, attr, None)
            if obj is not None:
                obj.release()
                setattr(self, attr, None)
        if self._quad_buffer is not None:
            self._quad_buffer.release()
            self._quad_buffer = None
        for attr in (
            "_soft_transition_prog",
            "_plasma_soft_prog",
            "_plasma_hard_prog",
            "_soft_prog",
            "_masked_prog",
        ):
            obj = getattr(self, attr, None)
            if obj is not None:
                obj.release()
                setattr(self, attr, None)
        self._ctx = None
        self._mask_cache_key = None
        self._clear_transition_state()
        self._current_weight_fields = None
        self._last_active_slots = None
