"""GPU post-processing (bloom, grit, highlight rolloff) via moderngl sharing the active pygame GL context.

See docs/gl-post-process.md for moderngl buffer and verification conventions.
"""

from __future__ import annotations

from dataclasses import dataclass

import moderngl
import numpy as np
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
    GL_SCISSOR_BOX,
    GL_SCISSOR_TEST,
    GL_TEXTURE0,
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
    glScissor,
    glUseProgram,
    glViewport,
)

try:
    from OpenGL.GL import GL_VERTEX_ARRAY_BINDING, glBindVertexArray
except ImportError:  # pragma: no cover - PyOpenGL without VAO entry points
    GL_VERTEX_ARRAY_BINDING = None  # type: ignore[misc, assignment]
    glBindVertexArray = None  # type: ignore[misc, assignment]

from cleave.effects.flare import FLARE_BLUR_RADIUS, FLARE_INTENSITY_SCALE

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

_BLUR_FRAG = """
#version 330
uniform sampler2D image;
uniform vec2 direction;
uniform vec2 texel_size;
uniform float radius;
in vec2 uv;
out vec4 fragColor;

void main() {
    vec4 color = vec4(0.0);
    float total = 0.0;
    float sigma = max(radius, 1.0);
    int radius_i = int(ceil(sigma * 2.0));
    for (int i = -radius_i; i <= radius_i; i++) {
        float x = float(i);
        float weight = exp(-0.5 * (x * x) / (sigma * sigma));
        color += texture(image, uv + direction * texel_size * x) * weight;
        total += weight;
    }
    fragColor = color / total;
}
"""

_COPY_FRAG = """
#version 330
uniform sampler2D image;
in vec2 uv;
out vec4 fragColor;
void main() {
    fragColor = texture(image, uv);
}
"""

_COMPOSITE_FRAG = """
#version 330
uniform sampler2D original;
uniform sampler2D blurred;
uniform float strength;
in vec2 uv;
out vec4 fragColor;

void main() {
    vec4 base = texture(original, uv);
    vec4 bloom = texture(blurred, uv);
    fragColor = min(base + bloom * strength, vec4(1.0));
}
"""

_GRIT_FRAG = """
#version 330
uniform sampler2D image;
uniform float grit_strength;
uniform float aberration_px;
uniform vec2 resolution;
in vec2 uv;
out vec4 fragColor;

float film_grain(vec2 coord) {
    return fract(sin(dot(coord, vec2(12.9898, 78.233))) * 43758.5453);
}

void main() {
    vec2 offset = vec2(aberration_px / resolution.x, 0.0);
    float r = texture(image, uv + offset).r;
    float g = texture(image, uv).g;
    float b = texture(image, uv - offset).b;
    float a = texture(image, uv).a;
    vec4 base = vec4(r, g, b, a);

    float grain = (film_grain(uv * resolution) - 0.5) * grit_strength;
    fragColor = clamp(base + vec4(grain, grain, grain, 0.0), 0.0, 1.0);
}
"""

_HIGHLIGHT_ROLLOFF_FRAG = """
#version 330
uniform sampler2D image;
uniform float threshold;
uniform float ceiling;
uniform float strength;
uniform float softness;
uniform float desaturation;
in vec2 uv;
out vec4 fragColor;

float ss(float t) {
    t = clamp(t, 0.0, 1.0);
    return t * t * (3.0 - 2.0 * t);
}

void main() {
    vec4 rgba = texture(image, uv);
    vec3 rgb = rgba.rgb;
    float lum = dot(rgb, vec3(0.2126, 0.7152, 0.0722));

    if (lum <= threshold || strength <= 0.0) {
        fragColor = rgba;
        return;
    }

    float eff_ceiling = min(ceiling, threshold);
    float excess = lum - threshold;
    float headroom = max(1.0 - threshold, 1e-6);
    float norm = min(excess / headroom, 1.0);

    float knee_width = max(softness * headroom, 1e-6);
    float knee_t = ss(min(excess / knee_width, 1.0));
    float linear_lum = threshold + excess * (1.0 - knee_t);

    float reinhard = norm / (1.0 + norm);
    float filmic_lum = threshold + (eff_ceiling - threshold) * (reinhard / 0.5);

    float past_knee = max(excess - knee_width, 0.0);
    float shoulder_span = max(headroom - knee_width, 1e-6);
    float shoulder_t = ss(min(past_knee / shoulder_span, 1.0));
    float compressed = linear_lum * (1.0 - shoulder_t) + filmic_lum * shoulder_t;

    float eff_strength = clamp(strength, 0.0, 2.0);
    float new_lum;
    if (eff_strength <= 1.0) {
        new_lum = lum + (compressed - lum) * eff_strength;
    } else {
        float extra = eff_strength - 1.0;
        float aggressive = threshold + (eff_ceiling - threshold) * norm;
        float full_lum = lum + (compressed - lum);
        new_lum = full_lum + (aggressive - full_lum) * extra;
    }

    float scale = (lum > 1e-4) ? (new_lum / lum) : 1.0;
    vec3 out_rgb = rgb * scale;

    if (desaturation > 0.0 && new_lum > threshold) {
        float span = max(1.0 - threshold, 1e-6);
        float t = ss((new_lum - threshold) / span);
        float desat_t = desaturation * t;
        out_rgb = mix(out_rgb, vec3(new_lum), desat_t);
    }

    fragColor = vec4(clamp(out_rgb, 0.0, 1.0), rgba.a);
}
"""


def _ensure_moderngl_draw_state() -> None:
    """Leave fixed-function GL state compatible with moderngl fullscreen draws."""
    glColorMask(True, True, True, True)
    glDisable(GL_SCISSOR_TEST)
    glDisable(GL_BLEND)
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
    )


def _restore_gl_state(state: _SavedGlState) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, state.framebuffer)
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


@dataclass
class _PingPongBuffers:
    copy_tex: moderngl.Texture
    copy_fbo: moderngl.Framebuffer
    ping_tex: moderngl.Texture
    ping_fbo: moderngl.Framebuffer
    pong_tex: moderngl.Texture
    pong_fbo: moderngl.Framebuffer

    def release(self) -> None:
        self.copy_fbo.release()
        self.copy_tex.release()
        self.ping_fbo.release()
        self.ping_tex.release()
        self.pong_fbo.release()
        self.pong_tex.release()


class GlPostProcess:
    """GPU post-processing (bloom, grit, highlight rolloff) on an existing layer FBO texture."""

    def __init__(self) -> None:
        self._ctx: moderngl.Context | None = None
        self._quad_buffer: moderngl.Buffer | None = None
        self._quad_vaos: dict[int, moderngl.VertexArray] = {}
        self._blur_prog: moderngl.Program | None = None
        self._copy_prog: moderngl.Program | None = None
        self._composite_prog: moderngl.Program | None = None
        self._grit_prog: moderngl.Program | None = None
        self._highlight_rolloff_prog: moderngl.Program | None = None
        self._buffers: dict[tuple[int, int], _PingPongBuffers] = {}
        self._external_textures: dict[tuple[int, int, int], moderngl.Texture] = {}
        self._dest_fbos: dict[tuple[int, int, int], moderngl.Framebuffer] = {}

    def init(self) -> None:
        """Attach to the current pygame OpenGL context."""
        self._ctx = moderngl.create_context()
        self._blur_prog = self._ctx.program(
            vertex_shader=_QUAD_VERT,
            fragment_shader=_BLUR_FRAG,
        )
        self._copy_prog = self._ctx.program(
            vertex_shader=_QUAD_VERT,
            fragment_shader=_COPY_FRAG,
        )
        self._composite_prog = self._ctx.program(
            vertex_shader=_QUAD_VERT,
            fragment_shader=_COMPOSITE_FRAG,
        )
        self._grit_prog = self._ctx.program(
            vertex_shader=_QUAD_VERT,
            fragment_shader=_GRIT_FRAG,
        )
        self._highlight_rolloff_prog = self._ctx.program(
            vertex_shader=_QUAD_VERT,
            fragment_shader=_HIGHLIGHT_ROLLOFF_FRAG,
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

    def _ensure_init(self) -> None:
        if self._ctx is None:
            self.init()

    def _ensure_buffers(self, width: int, height: int) -> _PingPongBuffers:
        self._ensure_init()
        assert self._ctx is not None
        key = (width, height)
        if key in self._buffers:
            return self._buffers[key]

        def _make_pair() -> tuple[moderngl.Texture, moderngl.Framebuffer]:
            tex = self._ctx.texture(key, 4)
            tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            tex.repeat_x = False
            tex.repeat_y = False
            fbo = self._ctx.framebuffer(color_attachments=[tex])
            return tex, fbo

        copy_tex, copy_fbo = _make_pair()
        ping_tex, ping_fbo = _make_pair()
        pong_tex, pong_fbo = _make_pair()
        buffers = _PingPongBuffers(
            copy_tex=copy_tex,
            copy_fbo=copy_fbo,
            ping_tex=ping_tex,
            ping_fbo=ping_fbo,
            pong_tex=pong_tex,
            pong_fbo=pong_fbo,
        )
        self._buffers[key] = buffers
        return buffers

    def _external_layer_texture(
        self, texture_id: int, width: int, height: int
    ) -> moderngl.Texture:
        self._ensure_init()
        assert self._ctx is not None
        key = (texture_id, width, height)
        cached = self._external_textures.get(key)
        if cached is not None:
            return cached
        tex = self._ctx.external_texture(texture_id, (width, height), 4, 0, "u1")
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        tex.repeat_x = False
        tex.repeat_y = False
        self._external_textures[key] = tex
        return tex

    def _dest_fbo_for(self, src: moderngl.Texture, texture_id: int, width: int, height: int) -> moderngl.Framebuffer:
        self._ensure_init()
        key = (texture_id, width, height)
        cached = self._dest_fbos.get(key)
        if cached is not None:
            return cached
        dest_fbo = self._ctx.framebuffer(color_attachments=[src])
        self._dest_fbos[key] = dest_fbo
        return dest_fbo

    def _quad_vao_for(self, program: moderngl.Program) -> moderngl.VertexArray:
        assert self._ctx is not None
        assert self._quad_buffer is not None
        key = id(program)
        vao = self._quad_vaos.get(key)
        if vao is None:
            vao = self._ctx.vertex_array(
                program,
                [(self._quad_buffer, "2f 2f", "in_vert", "in_uv")],
            )
            self._quad_vaos[key] = vao
        return vao

    def _draw_quad(
        self,
        program: moderngl.Program,
        fbo: moderngl.Framebuffer,
        *,
        texture: moderngl.Texture,
        extra_uniforms: dict[str, object] | None = None,
    ) -> None:
        _ensure_moderngl_draw_state()
        fbo.use()
        texture.use(0)
        program["image"].value = 0
        if extra_uniforms:
            for name, value in extra_uniforms.items():
                program[name].value = value
        self._quad_vao_for(program).render(moderngl.TRIANGLE_STRIP)

    def apply_bloom(
        self,
        texture_id: int,
        width: int,
        height: int,
        strength: float,
        *,
        blur_radius: float = FLARE_BLUR_RADIUS,
        intensity_scale: float = FLARE_INTENSITY_SCALE,
    ) -> int:
        """Bloom *texture_id* in-place; returns the (unchanged) texture id."""
        if strength <= 0.0 or texture_id == 0:
            return texture_id

        self._ensure_init()
        assert self._ctx is not None
        assert self._blur_prog is not None
        assert self._copy_prog is not None
        assert self._composite_prog is not None

        saved = _save_gl_state()
        try:
            src = self._external_layer_texture(texture_id, width, height)

            buffers = self._ensure_buffers(width, height)
            texel = (1.0 / float(width), 1.0 / float(height))
            radius = blur_radius

            self._draw_quad(
                self._copy_prog,
                buffers.copy_fbo,
                texture=src,
            )
            self._draw_quad(
                self._blur_prog,
                buffers.ping_fbo,
                texture=buffers.copy_tex,
                extra_uniforms={
                    "direction": (1.0, 0.0),
                    "texel_size": texel,
                    "radius": radius,
                },
            )
            self._draw_quad(
                self._blur_prog,
                buffers.pong_fbo,
                texture=buffers.ping_tex,
                extra_uniforms={
                    "direction": (0.0, 1.0),
                    "texel_size": texel,
                    "radius": radius,
                },
            )

            dest_fbo = self._dest_fbo_for(src, texture_id, width, height)
            dest_fbo.use()
            buffers.copy_tex.use(0)
            buffers.pong_tex.use(1)
            self._composite_prog["original"].value = 0
            self._composite_prog["blurred"].value = 1
            self._composite_prog["strength"].value = strength * intensity_scale
            self._quad_vao_for(self._composite_prog).render(moderngl.TRIANGLE_STRIP)
        finally:
            _restore_gl_state(saved)
            _prepare_fixed_function_gl()

        return texture_id

    def apply_grit(
        self,
        texture_id: int,
        width: int,
        height: int,
        grit_strength: float,
        aberration_px: float,
    ) -> int:
        """Film grain + chromatic aberration in-place; returns texture id."""
        if (grit_strength <= 0.0 and aberration_px <= 0.0) or texture_id == 0:
            return texture_id

        self._ensure_init()
        assert self._ctx is not None
        assert self._grit_prog is not None

        saved = _save_gl_state()
        try:
            src = self._external_layer_texture(texture_id, width, height)
            buffers = self._ensure_buffers(width, height)
            self._draw_quad(
                self._copy_prog,
                buffers.copy_fbo,
                texture=src,
            )
            dest_fbo = self._dest_fbo_for(src, texture_id, width, height)
            self._draw_quad(
                self._grit_prog,
                dest_fbo,
                texture=buffers.copy_tex,
                extra_uniforms={
                    "grit_strength": grit_strength,
                    "aberration_px": aberration_px,
                    "resolution": (float(width), float(height)),
                },
            )
        finally:
            _restore_gl_state(saved)
            _prepare_fixed_function_gl()

        return texture_id

    def apply_highlight_rolloff(
        self,
        texture_id: int,
        width: int,
        height: int,
        threshold: float,
        ceiling: float,
        strength: float,
        softness: float,
        desaturation: float,
    ) -> int:
        """Compress highlights in-place via GPU shader; returns texture id."""
        if strength <= 0.0 or texture_id == 0:
            return texture_id

        self._ensure_init()
        assert self._ctx is not None
        assert self._copy_prog is not None
        assert self._highlight_rolloff_prog is not None

        saved = _save_gl_state()
        try:
            src = self._external_layer_texture(texture_id, width, height)
            buffers = self._ensure_buffers(width, height)

            # Copy source to internal buffer (avoids sampling+writing same texture).
            self._draw_quad(self._copy_prog, buffers.copy_fbo, texture=src)

            # Apply highlight rolloff from buffer back to the source texture.
            dest_fbo = self._dest_fbo_for(src, texture_id, width, height)
            self._draw_quad(
                self._highlight_rolloff_prog,
                dest_fbo,
                texture=buffers.copy_tex,
                extra_uniforms={
                    "threshold": threshold,
                    "ceiling": ceiling,
                    "strength": strength,
                    "softness": softness,
                    "desaturation": desaturation,
                },
            )
        finally:
            _restore_gl_state(saved)
            _prepare_fixed_function_gl()

        return texture_id

    def destroy(self) -> None:
        for fbo in self._dest_fbos.values():
            fbo.release()
        self._dest_fbos.clear()
        for buffers in self._buffers.values():
            buffers.release()
        self._buffers.clear()
        self._external_textures.clear()
        for vao in self._quad_vaos.values():
            vao.release()
        self._quad_vaos.clear()
        if self._quad_buffer is not None:
            self._quad_buffer.release()
            self._quad_buffer = None
        if self._ctx is not None:
            self._ctx.release()
            self._ctx = None
        self._blur_prog = None
        self._copy_prog = None
        self._composite_prog = None
        self._grit_prog = None
        self._highlight_rolloff_prog = None
