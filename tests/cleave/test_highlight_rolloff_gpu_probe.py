"""GPU hypothesis probe tests for highlight rolloff offload.

Whitepage tests that diagnose why prior moderngl fullscreen draws produced
all-black pixels in pytest+pygame GL, and identify a working GPU path.

PROBE A - moderngl draws non-black to its own FBO (baseline)
PROBE B - GL state interference: scissor / blend / color-mask
PROBE C - moderngl draws to external-texture-backed FBO (write-back pattern)
PROBE D - raw PyOpenGL shader (gl_VertexID, no VBO) -- bypass moderngl
PROBE E - GPU highlight rolloff shader darkens white pixels (both approaches)
TIMING  - CPU path vs GPU path (printed with pytest -s)

Run:
    /home/fernpa/anaconda3/envs/cleave/bin/python -m pytest \\
        tests/cleave/test_highlight_rolloff_gpu_probe.py -s -v
"""

from __future__ import annotations

import time

import numpy as np
import pytest

pygame = pytest.importorskip("pygame")

from OpenGL.GL import (  # noqa: E402
    GL_BLEND,
    GL_COLOR_ATTACHMENT0,
    GL_CLAMP_TO_EDGE,
    GL_COLOR_BUFFER_BIT,
    GL_COMPILE_STATUS,
    GL_DEPTH_TEST,
    GL_FRAGMENT_SHADER,
    GL_FRAMEBUFFER,
    GL_LINK_STATUS,
    GL_NEAREST,
    GL_RGBA,
    GL_RGBA8,
    GL_SCISSOR_TEST,
    GL_TEXTURE0,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_TRIANGLES,
    GL_UNSIGNED_BYTE,
    GL_VERTEX_SHADER,
    glActiveTexture,
    glAttachShader,
    glBindFramebuffer,
    glBindTexture,
    glBindVertexArray,
    glClear,
    glClearColor,
    glColorMask,
    glCompileShader,
    glCreateProgram,
    glCreateShader,
    glDeleteFramebuffers,
    glDeleteProgram,
    glDeleteShader,
    glDeleteTextures,
    glDeleteVertexArrays,
    glDisable,
    glDrawArrays,
    glEnable,
    glFinish,
    glFramebufferTexture2D,
    glGenFramebuffers,
    glGenTextures,
    glGenVertexArrays,
    glGetProgramInfoLog,
    glGetProgramiv,
    glGetShaderInfoLog,
    glGetShaderiv,
    glGetUniformLocation,
    glLinkProgram,
    glReadPixels,
    glScissor,
    glShaderSource,
    glTexImage2D,
    glTexParameteri,
    glUniform1f,
    glUniform1i,
    glUseProgram,
    glViewport,
)

import moderngl  # noqa: E402

from cleave.gl_post_process import _ensure_moderngl_draw_state  # noqa: E402

# ---------------------------------------------------------------------------
# Dimensions: small to keep tests fast; large enough to detect off-by-one
# ---------------------------------------------------------------------------
W, H = 64, 64

# ---------------------------------------------------------------------------
# Shaders: moderngl variants (in_vert/in_uv attrs; out `uv` varyings)
# ---------------------------------------------------------------------------

_MGL_QUAD_VERT = """
#version 330
in vec2 in_vert;
in vec2 in_uv;
out vec2 uv;
void main() {
    gl_Position = vec4(in_vert, 0.0, 1.0);
    uv = in_uv;
}
"""

_MGL_SOLID_RED_FRAG = """
#version 330
out vec4 fragColor;
void main() {
    fragColor = vec4(1.0, 0.0, 0.0, 1.0);
}
"""

_MGL_COPY_FRAG = """
#version 330
uniform sampler2D image;
in vec2 uv;
out vec4 fragColor;
void main() {
    fragColor = texture(image, uv);
}
"""

_MGL_HIGHLIGHT_ROLLOFF_FRAG = """
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

# ---------------------------------------------------------------------------
# Shaders: raw GL variants (gl_VertexID; `u_` uniform prefix)
# ---------------------------------------------------------------------------

_RAW_VERT_SRC = """
#version 330
out vec2 uv;
void main() {
    vec2 positions[3] = vec2[](
        vec2(-1.0, -1.0),
        vec2( 3.0, -1.0),
        vec2(-1.0,  3.0)
    );
    vec2 uvs[3] = vec2[](
        vec2(0.0, 0.0),
        vec2(2.0, 0.0),
        vec2(0.0, 2.0)
    );
    gl_Position = vec4(positions[gl_VertexID], 0.0, 1.0);
    uv = uvs[gl_VertexID];
}
"""

_RAW_SOLID_RED_FRAG_SRC = """
#version 330
out vec4 out_color;
void main() {
    out_color = vec4(1.0, 0.0, 0.0, 1.0);
}
"""

_RAW_COPY_FRAG_SRC = """
#version 330
uniform sampler2D u_image;
in vec2 uv;
out vec4 out_color;
void main() {
    out_color = texture(u_image, uv);
}
"""

_RAW_HIGHLIGHT_ROLLOFF_FRAG_SRC = """
#version 330
uniform sampler2D u_image;
uniform float u_threshold;
uniform float u_ceiling;
uniform float u_strength;
uniform float u_softness;
uniform float u_desaturation;
in vec2 uv;
out vec4 out_color;

float ss(float t) {
    t = clamp(t, 0.0, 1.0);
    return t * t * (3.0 - 2.0 * t);
}

void main() {
    vec4 rgba = texture(u_image, uv);
    vec3 rgb = rgba.rgb;
    float lum = dot(rgb, vec3(0.2126, 0.7152, 0.0722));

    if (lum <= u_threshold || u_strength <= 0.0) {
        out_color = rgba;
        return;
    }

    float eff_ceiling = min(u_ceiling, u_threshold);
    float excess = lum - u_threshold;
    float headroom = max(1.0 - u_threshold, 1e-6);
    float norm = min(excess / headroom, 1.0);

    float knee_width = max(u_softness * headroom, 1e-6);
    float knee_t = ss(min(excess / knee_width, 1.0));
    float linear_lum = u_threshold + excess * (1.0 - knee_t);

    float reinhard = norm / (1.0 + norm);
    float filmic_lum = u_threshold + (eff_ceiling - u_threshold) * (reinhard / 0.5);

    float past_knee = max(excess - knee_width, 0.0);
    float shoulder_span = max(headroom - knee_width, 1e-6);
    float shoulder_t = ss(min(past_knee / shoulder_span, 1.0));
    float compressed = linear_lum * (1.0 - shoulder_t) + filmic_lum * shoulder_t;

    float eff_strength = clamp(u_strength, 0.0, 2.0);
    float new_lum;
    if (eff_strength <= 1.0) {
        new_lum = lum + (compressed - lum) * eff_strength;
    } else {
        float extra = eff_strength - 1.0;
        float aggressive = u_threshold + (eff_ceiling - u_threshold) * norm;
        float full_lum = lum + (compressed - lum);
        new_lum = full_lum + (aggressive - full_lum) * extra;
    }

    float scale = (lum > 1e-4) ? (new_lum / lum) : 1.0;
    vec3 out_rgb = rgb * scale;

    if (u_desaturation > 0.0 && new_lum > u_threshold) {
        float span = max(1.0 - u_threshold, 1e-6);
        float t = ss((new_lum - u_threshold) / span);
        float desat_t = u_desaturation * t;
        out_rgb = mix(out_rgb, vec3(new_lum), desat_t);
    }

    out_color = vec4(clamp(out_rgb, 0.0, 1.0), rgba.a);
}
"""

# ---------------------------------------------------------------------------
# PyOpenGL helpers
# ---------------------------------------------------------------------------

def _gl_int(v: object) -> int:
    try:
        return int(v[0])  # type: ignore[index]
    except (TypeError, IndexError):
        return int(v)  # type: ignore[arg-type]


def _read_pixel_from_fbo(fbo_id: int, x: int = 0, y: int = 0) -> tuple[int, int, int, int]:
    """Read one RGBA pixel from an OpenGL FBO."""
    glBindFramebuffer(GL_FRAMEBUFFER, fbo_id)
    raw = glReadPixels(x, y, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    b = bytes(raw)
    return (b[0], b[1], b[2], b[3])


def _read_pixels_array(fbo_id: int, width: int, height: int) -> np.ndarray:
    """Read all pixels from an FBO as (H, W, 4) uint8 array."""
    glBindFramebuffer(GL_FRAMEBUFFER, fbo_id)
    raw = glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    return np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)


def _make_pygl_tex_fbo(
    width: int, height: int, fill: tuple[int, int, int, int] = (255, 255, 255, 255)
) -> tuple[int, int]:
    """Create a PyOpenGL RGBA8 texture + FBO filled with `fill` colour."""
    data = np.full((height, width, 4), fill, dtype=np.uint8)
    tex_id = _gl_int(glGenTextures(1))
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    glBindTexture(GL_TEXTURE_2D, 0)

    fbo_id = _gl_int(glGenFramebuffers(1))
    glBindFramebuffer(GL_FRAMEBUFFER, fbo_id)
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, tex_id, 0)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    return tex_id, fbo_id


def _compile_raw_program(vert_src: str, frag_src: str) -> int:
    """Compile and link a GL program; raise RuntimeError with info-log on failure."""
    def _compile_stage(kind: int, src: str) -> int:
        sh = glCreateShader(kind)
        glShaderSource(sh, src)
        glCompileShader(sh)
        if not glGetShaderiv(sh, GL_COMPILE_STATUS):
            log = glGetShaderInfoLog(sh)
            if isinstance(log, bytes):
                log = log.decode("utf-8", errors="replace")
            raise RuntimeError(f"Shader compile failed:\n{log}")
        return sh

    vert = _compile_stage(GL_VERTEX_SHADER, vert_src)
    frag = _compile_stage(GL_FRAGMENT_SHADER, frag_src)
    prog = glCreateProgram()
    glAttachShader(prog, vert)
    glAttachShader(prog, frag)
    glLinkProgram(prog)
    glDeleteShader(vert)
    glDeleteShader(frag)
    if not glGetProgramiv(prog, GL_LINK_STATUS):
        log = glGetProgramInfoLog(prog)
        if isinstance(log, bytes):
            log = log.decode("utf-8", errors="replace")
        raise RuntimeError(f"Program link failed:\n{log}")
    return prog


def _make_mgl_quad_vao(
    ctx: moderngl.Context, prog: moderngl.Program
) -> tuple[moderngl.VertexArray, moderngl.Buffer]:
    """Create a VAO + VBO for a fullscreen TRIANGLE_STRIP quad (correct binary floats)."""
    buf = ctx.buffer(
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
    vao = ctx.vertex_array(prog, [(buf, "2f 2f", "in_vert", "in_uv")])
    return vao, buf


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pygame_gl():
    """Module-scoped pygame window with an OpenGL context."""
    pygame.init()
    pygame.display.set_mode((W * 2, H * 2), pygame.OPENGL | pygame.DOUBLEBUF)
    yield
    pygame.quit()


@pytest.fixture
def mgl_ctx(pygame_gl: None):
    """Function-scoped moderngl context (attaches to pygame GL, released after each test)."""
    ctx = moderngl.create_context()
    yield ctx
    ctx.release()


# ---------------------------------------------------------------------------
# ROOT CAUSE DIAGNOSTIC  —  ASCII buffer produces garbage vertex positions
# ---------------------------------------------------------------------------

def test_root_cause_ascii_buffer_produces_garbage_positions() -> None:
    """Document the ASCII-vs-binary buffer bug that makes all moderngl draws black.

    The production GlPostProcess uses b"-1.0 -1.0  0.0 0.0 ..." (75 bytes of
    ASCII characters).  When moderngl reads it as four float32 values the first
    vertex becomes ≈(6e-10, 4e-11, …) instead of (-1, -1, 0, 0).  All triangles
    are degenerate near NDC origin and produce zero fragments.
    """
    import struct

    ascii_buf = (
        b"-1.0 -1.0  0.0 0.0 "
        b" 1.0 -1.0  1.0 0.0 "
        b"-1.0  1.0  0.0 1.0 "
        b" 1.0  1.0  1.0 1.0"
    )
    correct_buf = np.array(
        [-1.0, -1.0, 0.0, 0.0,  1.0, -1.0, 1.0, 0.0,
         -1.0,  1.0, 0.0, 1.0,  1.0,  1.0, 1.0, 1.0],
        dtype=np.float32,
    ).tobytes()

    ascii_first = struct.unpack_from("4f", ascii_buf)
    correct_first = struct.unpack_from("4f", correct_buf)
    print(f"\n[ROOT CAUSE] ASCII buffer length: {len(ascii_buf)} bytes (expect 64)")
    print(f"  first vertex (ASCII-as-binary): {ascii_first}")
    print(f"  first vertex (correct binary):  {correct_first}")

    assert len(ascii_buf) != 64, "ASCII buffer must not be 64 bytes"
    assert len(correct_buf) == 64, "Binary buffer must be 64 bytes"
    assert abs(ascii_first[0]) < 1e-6, "ASCII buffer gives near-zero x (degenerate)"
    assert correct_first[0] == -1.0, "Binary buffer gives correct NDC x=-1"


# ---------------------------------------------------------------------------
# PROBE A  —  moderngl draws to its own FBO
# ---------------------------------------------------------------------------

def test_probe_a1_moderngl_solid_red_to_own_fbo(mgl_ctx: moderngl.Context) -> None:
    """PROBE A1: moderngl solid-red draw writes non-black to its own FBO (fbo.read)."""
    ctx = mgl_ctx
    tex = ctx.texture((W, H), 4)
    fbo = ctx.framebuffer(color_attachments=[tex])
    prog = ctx.program(vertex_shader=_MGL_QUAD_VERT, fragment_shader=_MGL_SOLID_RED_FRAG)
    vao, buf = _make_mgl_quad_vao(ctx, prog)

    _ensure_moderngl_draw_state()
    fbo.use()
    vao.render(moderngl.TRIANGLE_STRIP)
    glFinish()

    raw = fbo.read(components=4)
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(H, W, 4)
    r, g = int(pixels[0, 0, 0]), int(pixels[0, 0, 1])
    print(f"\n[A1] moderngl own-FBO draw (fbo.read): r={r} g={g}")
    assert r == 255, f"PROBE A1 FAIL: expected r=255 got r={r} -- moderngl drew black"
    assert g == 0

    vao.release(); buf.release(); prog.release(); fbo.release(); tex.release()


def test_probe_a2_moderngl_solid_red_via_gl_read(mgl_ctx: moderngl.Context) -> None:
    """PROBE A2: same draw but read-back via raw glReadPixels (different code path)."""
    ctx = mgl_ctx
    tex = ctx.texture((W, H), 4)
    fbo = ctx.framebuffer(color_attachments=[tex])
    prog = ctx.program(vertex_shader=_MGL_QUAD_VERT, fragment_shader=_MGL_SOLID_RED_FRAG)
    vao, buf = _make_mgl_quad_vao(ctx, prog)

    _ensure_moderngl_draw_state()
    fbo.use()
    vao.render(moderngl.TRIANGLE_STRIP)
    glFinish()

    pixel = _read_pixel_from_fbo(fbo.glo)
    r, g, b, a = pixel
    print(f"\n[A2] moderngl own-FBO draw (glReadPixels): r={r} g={g} b={b} a={a}")
    assert r == 255, f"PROBE A2 FAIL: expected r=255 got r={r}"
    assert g == 0

    vao.release(); buf.release(); prog.release(); fbo.release(); tex.release()


# ---------------------------------------------------------------------------
# PROBE B  —  GL state interference
# ---------------------------------------------------------------------------

def test_probe_b1_moderngl_fbo_use_ignores_external_scissor(mgl_ctx: moderngl.Context) -> None:
    """PROBE B1: moderngl fbo.use() resets scissor state on Mesa/Linux.

    On this Mesa implementation fbo.use() disables or resets the scissor test
    regardless of what was set externally via PyOpenGL, so the entire FBO is
    drawn even without calling _ensure_moderngl_draw_state().  This means
    external scissor state does NOT affect moderngl draws here.
    """
    ctx = mgl_ctx
    tex = ctx.texture((W, H), 4)
    fbo = ctx.framebuffer(color_attachments=[tex])
    prog = ctx.program(vertex_shader=_MGL_QUAD_VERT, fragment_shader=_MGL_SOLID_RED_FRAG)
    vao, buf = _make_mgl_quad_vao(ctx, prog)

    glEnable(GL_SCISSOR_TEST)
    glScissor(32, 32, 1, 1)
    # Do NOT call _ensure_moderngl_draw_state — document what happens
    fbo.use()
    vao.render(moderngl.TRIANGLE_STRIP)
    glFinish()

    pixels = _read_pixels_array(fbo.glo, W, H)
    corner_r = int(pixels[0, 0, 0])
    center_r = int(pixels[32, 32, 0])
    print(f"\n[B1] Mesa: fbo.use() resets scissor — corner_r={corner_r} center_r={center_r}")
    # On Mesa, fbo.use() ignores the pre-existing scissor: entire FBO is drawn.
    assert corner_r == 255, (
        f"PROBE B1: on Mesa fbo.use() draws everywhere (corner_r should be 255), got {corner_r}"
    )
    assert center_r == 255

    vao.release(); buf.release(); prog.release(); fbo.release(); tex.release()


def test_probe_b2_scissor_with_reset_fills_entire_fbo(mgl_ctx: moderngl.Context) -> None:
    """PROBE B2: _ensure_moderngl_draw_state disables scissor, full FBO is drawn."""
    ctx = mgl_ctx
    tex = ctx.texture((W, H), 4)
    fbo = ctx.framebuffer(color_attachments=[tex])
    prog = ctx.program(vertex_shader=_MGL_QUAD_VERT, fragment_shader=_MGL_SOLID_RED_FRAG)
    vao, buf = _make_mgl_quad_vao(ctx, prog)

    glEnable(GL_SCISSOR_TEST)
    glScissor(32, 32, 1, 1)
    _ensure_moderngl_draw_state()  # must disable scissor
    fbo.use()
    vao.render(moderngl.TRIANGLE_STRIP)
    glFinish()

    pixel = _read_pixel_from_fbo(fbo.glo, x=0, y=0)
    r = pixel[0]
    print(f"\n[B2] scissor with reset: corner r={r}")
    assert r == 255, (
        f"PROBE B2 FAIL: _ensure_moderngl_draw_state must disable scissor, got r={r}"
    )

    vao.release(); buf.release(); prog.release(); fbo.release(); tex.release()


def test_probe_b3_color_mask_reset_by_ensure_state(mgl_ctx: moderngl.Context) -> None:
    """PROBE B3: color mask blocking R channel is fixed by _ensure_moderngl_draw_state."""
    ctx = mgl_ctx
    tex = ctx.texture((W, H), 4)
    fbo = ctx.framebuffer(color_attachments=[tex])
    prog = ctx.program(vertex_shader=_MGL_QUAD_VERT, fragment_shader=_MGL_SOLID_RED_FRAG)
    vao, buf = _make_mgl_quad_vao(ctx, prog)

    glColorMask(False, True, True, True)  # block R
    _ensure_moderngl_draw_state()         # must restore all-true
    fbo.use()
    vao.render(moderngl.TRIANGLE_STRIP)
    glFinish()

    pixel = _read_pixel_from_fbo(fbo.glo)
    r = pixel[0]
    print(f"\n[B3] color_mask reset: r={r}")
    assert r == 255, (
        f"PROBE B3 FAIL: _ensure_moderngl_draw_state must restore color mask, got r={r}"
    )

    vao.release(); buf.release(); prog.release(); fbo.release(); tex.release()


# ---------------------------------------------------------------------------
# PROBE C  —  moderngl draws to an external-texture-backed FBO
# ---------------------------------------------------------------------------

def test_probe_c1_moderngl_writes_to_external_tex_fbo(mgl_ctx: moderngl.Context) -> None:
    """PROBE C1: moderngl renders solid red to a PyOpenGL-texture-backed FBO."""
    ctx = mgl_ctx

    src_tex_id, src_fbo_id = _make_pygl_tex_fbo(W, H, fill=(0, 0, 0, 255))
    before = _read_pixel_from_fbo(src_fbo_id)

    ext_tex = ctx.external_texture(src_tex_id, (W, H), 4, 0, "u1")
    dest_fbo = ctx.framebuffer(color_attachments=[ext_tex])

    prog = ctx.program(vertex_shader=_MGL_QUAD_VERT, fragment_shader=_MGL_SOLID_RED_FRAG)
    vao, buf = _make_mgl_quad_vao(ctx, prog)

    _ensure_moderngl_draw_state()
    dest_fbo.use()
    vao.render(moderngl.TRIANGLE_STRIP)
    glFinish()

    after = _read_pixel_from_fbo(src_fbo_id)
    print(f"\n[C1] external-tex FBO: before={before} after={after}")
    assert after[0] == 255, (
        f"PROBE C1 FAIL: moderngl draw to external-tex FBO must write red, got {after}"
    )
    assert after[1] == 0

    vao.release(); buf.release(); prog.release(); dest_fbo.release()
    glDeleteTextures(1, [src_tex_id])
    glDeleteFramebuffers(1, [src_fbo_id])


def test_probe_c2_copy_then_highlight_via_moderngl(mgl_ctx: moderngl.Context) -> None:
    """PROBE C2: copy-then-draw pattern (same as bloom/grit) with highlight shader."""
    ctx = mgl_ctx

    # Source: white texture (simulates content FBO after projectM)
    src_tex_id, src_fbo_id = _make_pygl_tex_fbo(W, H, fill=(255, 255, 255, 255))
    ext_src = ctx.external_texture(src_tex_id, (W, H), 4, 0, "u1")
    dest_fbo = ctx.framebuffer(color_attachments=[ext_src])

    # Internal copy buffer (identical to GlPostProcess._ensure_buffers copy_fbo)
    copy_tex = ctx.texture((W, H), 4)
    copy_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
    copy_fbo = ctx.framebuffer(color_attachments=[copy_tex])

    copy_prog = ctx.program(vertex_shader=_MGL_QUAD_VERT, fragment_shader=_MGL_COPY_FRAG)
    hl_prog = ctx.program(
        vertex_shader=_MGL_QUAD_VERT,
        fragment_shader=_MGL_HIGHLIGHT_ROLLOFF_FRAG,
    )
    copy_vao, copy_buf = _make_mgl_quad_vao(ctx, copy_prog)
    hl_vao, hl_buf = _make_mgl_quad_vao(ctx, hl_prog)

    before = _read_pixel_from_fbo(src_fbo_id)

    # Step 1: copy source → internal buffer
    _ensure_moderngl_draw_state()
    copy_fbo.use()
    ext_src.use(0)
    copy_prog["image"].value = 0
    copy_vao.render(moderngl.TRIANGLE_STRIP)
    glFinish()

    raw_copy = copy_fbo.read(components=4)
    copy_r = int(np.frombuffer(raw_copy, dtype=np.uint8).reshape(H, W, 4)[0, 0, 0])
    print(f"\n[C2] internal copy r={copy_r} (need 255 to proceed)")

    # Step 2: highlight shader from internal buffer → dest (external) FBO
    _ensure_moderngl_draw_state()
    dest_fbo.use()
    copy_tex.use(0)
    hl_prog["image"].value = 0
    hl_prog["threshold"].value = 0.78
    hl_prog["ceiling"].value = 0.65
    hl_prog["strength"].value = 0.7
    hl_prog["softness"].value = 0.4
    hl_prog["desaturation"].value = 0.3
    hl_vao.render(moderngl.TRIANGLE_STRIP)
    glFinish()

    after = _read_pixel_from_fbo(src_fbo_id)
    print(f"[C2] highlight rolloff via moderngl: before={before} after={after}")
    assert copy_r == 255, f"Internal copy must preserve white (got r={copy_r})"
    assert after[0] < before[0], (
        f"PROBE C2 FAIL: moderngl highlight rolloff must darken white, "
        f"got before={before} after={after}"
    )

    copy_vao.release(); copy_buf.release(); copy_prog.release()
    hl_vao.release(); hl_buf.release(); hl_prog.release()
    copy_fbo.release(); copy_tex.release(); dest_fbo.release()
    glDeleteTextures(1, [src_tex_id])
    glDeleteFramebuffers(1, [src_fbo_id])


# ---------------------------------------------------------------------------
# PROBE D  —  raw PyOpenGL shader (bypass moderngl entirely)
# ---------------------------------------------------------------------------

def _raw_draw_to_fbo(
    prog_id: int, fbo_id: int, width: int, height: int, vao_id: int
) -> None:
    """Bind fbo, set viewport, issue the fullscreen triangle draw."""
    _ensure_moderngl_draw_state()
    glBindFramebuffer(GL_FRAMEBUFFER, fbo_id)
    glViewport(0, 0, width, height)
    glUseProgram(prog_id)
    glBindVertexArray(vao_id)
    glDrawArrays(GL_TRIANGLES, 0, 3)
    glFinish()
    glBindVertexArray(0)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    glUseProgram(0)


def test_probe_d1_raw_gl_solid_red(pygame_gl: None) -> None:
    """PROBE D1: raw PyOpenGL shader (gl_VertexID) writes solid red to FBO."""
    tex_id, fbo_id = _make_pygl_tex_fbo(W, H, fill=(0, 0, 0, 255))
    prog = _compile_raw_program(_RAW_VERT_SRC, _RAW_SOLID_RED_FRAG_SRC)
    vao_id = _gl_int(glGenVertexArrays(1))

    _raw_draw_to_fbo(prog, fbo_id, W, H, vao_id)

    pixel = _read_pixel_from_fbo(fbo_id)
    r, g, b, a = pixel
    print(f"\n[D1] raw GL solid red: r={r} g={g} b={b} a={a}")
    assert r == 255, f"PROBE D1 FAIL: raw GL must write red, got r={r}"
    assert g == 0

    glDeleteVertexArrays(1, [vao_id])
    glDeleteProgram(prog)
    glDeleteTextures(1, [tex_id])
    glDeleteFramebuffers(1, [fbo_id])


def test_probe_d2_raw_gl_copies_white_texture(pygame_gl: None) -> None:
    """PROBE D2: raw GL copy shader reads white source texture, writes to dest FBO."""
    src_tex_id, _ = _make_pygl_tex_fbo(W, H, fill=(255, 255, 255, 255))
    dst_tex_id, dst_fbo_id = _make_pygl_tex_fbo(W, H, fill=(0, 0, 0, 255))

    prog = _compile_raw_program(_RAW_VERT_SRC, _RAW_COPY_FRAG_SRC)
    vao_id = _gl_int(glGenVertexArrays(1))

    _ensure_moderngl_draw_state()
    glActiveTexture(GL_TEXTURE0)
    glBindTexture(GL_TEXTURE_2D, src_tex_id)
    glBindFramebuffer(GL_FRAMEBUFFER, dst_fbo_id)
    glViewport(0, 0, W, H)
    glUseProgram(prog)
    glBindVertexArray(vao_id)
    glUniform1i(glGetUniformLocation(prog, "u_image"), 0)
    glDrawArrays(GL_TRIANGLES, 0, 3)
    glFinish()
    glBindVertexArray(0)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    glUseProgram(0)

    pixel = _read_pixel_from_fbo(dst_fbo_id)
    r = pixel[0]
    print(f"\n[D2] raw GL copy: dst r={r} (expect 255)")
    assert r >= 250, f"PROBE D2 FAIL: raw GL copy must write white, got r={r}"

    glDeleteVertexArrays(1, [vao_id])
    glDeleteProgram(prog)
    glDeleteTextures(1, [src_tex_id])
    glDeleteTextures(1, [dst_tex_id])
    glDeleteFramebuffers(1, [dst_fbo_id])


def test_probe_d3_raw_gl_highlight_rolloff_darkens_white(pygame_gl: None) -> None:
    """PROBE D3: raw GL highlight rolloff shader darkens blown-out white."""
    src_tex_id, src_fbo_id = _make_pygl_tex_fbo(W, H, fill=(255, 255, 255, 255))
    before = _read_pixel_from_fbo(src_fbo_id)
    assert before[0] == 255

    # Temporary copy buffer
    tmp_tex_id, tmp_fbo_id = _make_pygl_tex_fbo(W, H, fill=(0, 0, 0, 255))

    copy_prog = _compile_raw_program(_RAW_VERT_SRC, _RAW_COPY_FRAG_SRC)
    hl_prog = _compile_raw_program(_RAW_VERT_SRC, _RAW_HIGHLIGHT_ROLLOFF_FRAG_SRC)
    vao_id = _gl_int(glGenVertexArrays(1))

    # Step 1: copy source → tmp
    _ensure_moderngl_draw_state()
    glActiveTexture(GL_TEXTURE0)
    glBindTexture(GL_TEXTURE_2D, src_tex_id)
    glBindFramebuffer(GL_FRAMEBUFFER, tmp_fbo_id)
    glViewport(0, 0, W, H)
    glUseProgram(copy_prog)
    glBindVertexArray(vao_id)
    glUniform1i(glGetUniformLocation(copy_prog, "u_image"), 0)
    glDrawArrays(GL_TRIANGLES, 0, 3)
    glFinish()

    # Step 2: highlight rolloff from tmp → source FBO
    _ensure_moderngl_draw_state()
    glActiveTexture(GL_TEXTURE0)
    glBindTexture(GL_TEXTURE_2D, tmp_tex_id)
    glBindFramebuffer(GL_FRAMEBUFFER, src_fbo_id)
    glViewport(0, 0, W, H)
    glUseProgram(hl_prog)
    glBindVertexArray(vao_id)
    glUniform1i(glGetUniformLocation(hl_prog, "u_image"), 0)
    glUniform1f(glGetUniformLocation(hl_prog, "u_threshold"), 0.78)
    glUniform1f(glGetUniformLocation(hl_prog, "u_ceiling"), 0.65)
    glUniform1f(glGetUniformLocation(hl_prog, "u_strength"), 0.7)
    glUniform1f(glGetUniformLocation(hl_prog, "u_softness"), 0.4)
    glUniform1f(glGetUniformLocation(hl_prog, "u_desaturation"), 0.3)
    glDrawArrays(GL_TRIANGLES, 0, 3)
    glFinish()

    glBindVertexArray(0)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    glUseProgram(0)

    after = _read_pixel_from_fbo(src_fbo_id)
    print(f"\n[D3] raw GL highlight rolloff: before={before} after={after}")
    assert after[0] < before[0], (
        f"PROBE D3 FAIL: raw GL highlight rolloff must darken white, "
        f"got before={before} after={after}"
    )

    glDeleteVertexArrays(1, [vao_id])
    glDeleteProgram(copy_prog)
    glDeleteProgram(hl_prog)
    glDeleteTextures(1, [src_tex_id])
    glDeleteTextures(1, [tmp_tex_id])
    glDeleteFramebuffers(1, [src_fbo_id])
    glDeleteFramebuffers(1, [tmp_fbo_id])


# ---------------------------------------------------------------------------
# PROBE E  —  integration with GlCompositor (matches production wiring)
# ---------------------------------------------------------------------------

def test_probe_e_moderngl_highlight_via_glcompositor(pygame_gl: None) -> None:
    """PROBE E: highlight rolloff via moderngl using GlCompositor content FBO."""
    from cleave.gl_compositor import GlCompositor

    comp = GlCompositor(
        content_width=W,
        content_height=H,
        display_width=W * 2,
        display_height=H * 2,
    )
    comp.init()

    # Fill content FBO white
    glBindFramebuffer(GL_FRAMEBUFFER, comp.content_fbo_id)
    glClearColor(1.0, 1.0, 1.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)

    before_r = _read_pixel_from_fbo(comp.content_fbo_id)[0]
    assert before_r == 255

    # Build moderngl resources without touching GlPostProcess
    ctx = moderngl.create_context()
    ext_src = ctx.external_texture(comp.content_texture_id, (W, H), 4, 0, "u1")
    dest_fbo = ctx.framebuffer(color_attachments=[ext_src])
    copy_tex = ctx.texture((W, H), 4)
    copy_fbo = ctx.framebuffer(color_attachments=[copy_tex])
    copy_prog = ctx.program(vertex_shader=_MGL_QUAD_VERT, fragment_shader=_MGL_COPY_FRAG)
    hl_prog = ctx.program(
        vertex_shader=_MGL_QUAD_VERT,
        fragment_shader=_MGL_HIGHLIGHT_ROLLOFF_FRAG,
    )
    copy_vao, copy_buf = _make_mgl_quad_vao(ctx, copy_prog)
    hl_vao, hl_buf = _make_mgl_quad_vao(ctx, hl_prog)

    # Apply highlight rolloff
    _ensure_moderngl_draw_state()
    copy_fbo.use()
    ext_src.use(0)
    copy_prog["image"].value = 0
    copy_vao.render(moderngl.TRIANGLE_STRIP)

    _ensure_moderngl_draw_state()
    dest_fbo.use()
    copy_tex.use(0)
    hl_prog["image"].value = 0
    hl_prog["threshold"].value = 0.78
    hl_prog["ceiling"].value = 0.65
    hl_prog["strength"].value = 0.7
    hl_prog["softness"].value = 0.4
    hl_prog["desaturation"].value = 0.3
    hl_vao.render(moderngl.TRIANGLE_STRIP)
    glFinish()

    after = _read_pixel_from_fbo(comp.content_fbo_id)
    after_r = after[0]
    print(f"\n[E] moderngl+GlCompositor: before_r={before_r} after_r={after_r}")
    assert after_r < before_r, (
        f"PROBE E FAIL: moderngl highlight rolloff via GlCompositor must darken white, "
        f"got before_r={before_r} after_r={after_r}"
    )

    copy_vao.release(); copy_buf.release(); copy_prog.release()
    hl_vao.release(); hl_buf.release(); hl_prog.release()
    copy_fbo.release(); copy_tex.release(); dest_fbo.release()
    ctx.release()
    comp.destroy()


# ---------------------------------------------------------------------------
# TIMING  —  CPU vs GPU (printed with pytest -s)
# ---------------------------------------------------------------------------

def _run_timing(width: int, height: int, n: int = 30) -> tuple[float, float]:
    """Return (cpu_ms, gpu_ms) averaged over n iterations at given resolution."""
    from OpenGL.GL import glTexSubImage2D
    from cleave.viz.post_fx import apply_highlight_rolloff_rgba

    tex_id, fbo_id = _make_pygl_tex_fbo(width, height, fill=(255, 255, 255, 255))

    # CPU path
    times_cpu = []
    for _ in range(n):
        t0 = time.perf_counter()
        glBindFramebuffer(GL_FRAMEBUFFER, fbo_id)
        raw = glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE)
        rgba = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)
        payload = apply_highlight_rolloff_rgba(rgba, 0.78, 0.65, 0.7, 0.4, 0.3)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, payload)
        glBindTexture(GL_TEXTURE_2D, 0)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glFinish()
        times_cpu.append(time.perf_counter() - t0)
    cpu_ms = sum(times_cpu) / len(times_cpu) * 1000

    # GPU path (raw GL shader; no CPU-GPU readback)
    copy_prog = _compile_raw_program(_RAW_VERT_SRC, _RAW_COPY_FRAG_SRC)
    hl_prog = _compile_raw_program(_RAW_VERT_SRC, _RAW_HIGHLIGHT_ROLLOFF_FRAG_SRC)
    vao_id = _gl_int(glGenVertexArrays(1))
    tmp_tex_id, tmp_fbo_id = _make_pygl_tex_fbo(width, height, fill=(0, 0, 0, 255))

    times_gpu = []
    for _ in range(n):
        t0 = time.perf_counter()
        _ensure_moderngl_draw_state()
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glBindFramebuffer(GL_FRAMEBUFFER, tmp_fbo_id)
        glViewport(0, 0, width, height)
        glUseProgram(copy_prog)
        glBindVertexArray(vao_id)
        glUniform1i(glGetUniformLocation(copy_prog, "u_image"), 0)
        glDrawArrays(GL_TRIANGLES, 0, 3)
        _ensure_moderngl_draw_state()
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, tmp_tex_id)
        glBindFramebuffer(GL_FRAMEBUFFER, fbo_id)
        glViewport(0, 0, width, height)
        glUseProgram(hl_prog)
        glBindVertexArray(vao_id)
        glUniform1i(glGetUniformLocation(hl_prog, "u_image"), 0)
        glUniform1f(glGetUniformLocation(hl_prog, "u_threshold"), 0.78)
        glUniform1f(glGetUniformLocation(hl_prog, "u_ceiling"), 0.65)
        glUniform1f(glGetUniformLocation(hl_prog, "u_strength"), 0.7)
        glUniform1f(glGetUniformLocation(hl_prog, "u_softness"), 0.4)
        glUniform1f(glGetUniformLocation(hl_prog, "u_desaturation"), 0.3)
        glDrawArrays(GL_TRIANGLES, 0, 3)
        glFinish()
        glBindVertexArray(0)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glUseProgram(0)
        times_gpu.append(time.perf_counter() - t0)
    gpu_ms = sum(times_gpu) / len(times_gpu) * 1000

    glDeleteVertexArrays(1, [vao_id])
    glDeleteProgram(copy_prog)
    glDeleteProgram(hl_prog)
    glDeleteTextures(1, [tex_id])
    glDeleteTextures(1, [tmp_tex_id])
    glDeleteFramebuffers(1, [fbo_id])
    glDeleteFramebuffers(1, [tmp_fbo_id])
    return cpu_ms, gpu_ms


def test_timing_cpu_vs_gpu(pygame_gl: None) -> None:
    """TIMING: compare CPU vs GPU shader path at 64x64 and 1280x720."""
    cpu_64, gpu_64 = _run_timing(64, 64)
    cpu_hd, gpu_hd = _run_timing(1280, 720)

    print(f"\n[TIMING]  64x 64: CPU={cpu_64:.3f}ms  GPU={gpu_64:.3f}ms  "
          f"speedup={cpu_64/gpu_64:.1f}x" if gpu_64 > 0 else "")
    print(f"[TIMING] 1280x720: CPU={cpu_hd:.3f}ms  GPU={gpu_hd:.3f}ms  "
          f"speedup={cpu_hd/gpu_hd:.1f}x" if gpu_hd > 0 else "")

    # At 1280x720 the GPU path must win (avoiding 3.7 MB CPU-GPU roundtrip)
    assert gpu_hd < cpu_hd, (
        f"GPU path must be faster than CPU at 1280x720: "
        f"gpu={gpu_hd:.3f}ms cpu={cpu_hd:.3f}ms"
    )
