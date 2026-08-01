"""Tests for GPU post-process GL state save/restore and draw dispatch."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from OpenGL.GL import (
    GL_COLOR_WRITEMASK,
    GL_FRAMEBUFFER,
    GL_FRAMEBUFFER_BINDING,
    GL_SCISSOR_BOX,
    GL_VERTEX_ARRAY_BINDING,
    glGetIntegerv,
)

from cleave.gl_post_process import (
    GlPostProcess,
    _prepare_fixed_function_gl,
    _restore_gl_state,
    _save_gl_state,
)
from cleave.gl_color_format import RGBA16F


def test_gl_framebuffer_binding_is_valid_getintegerv_pname() -> None:
    """Regression: GL_FRAMEBUFFER is a bind target, not a glGetIntegerv pname."""
    with pytest.raises(KeyError, match="GL_FRAMEBUFFER"):
        glGetIntegerv(GL_FRAMEBUFFER)
    assert glGetIntegerv(GL_FRAMEBUFFER_BINDING) is not None


def test_save_gl_state_queries_framebuffer_binding() -> None:
    queried: list[object] = []

    def _record_getintegerv(pname: object) -> list[int]:
        queried.append(pname)
        if pname is GL_FRAMEBUFFER_BINDING:
            return [42]
        if pname is GL_COLOR_WRITEMASK:
            return [1, 1, 1, 1]
        if pname is GL_SCISSOR_BOX:
            return [0, 0, 800, 600]
        if pname is GL_VERTEX_ARRAY_BINDING:
            return [9]
        return [0, 0, 800, 600]

    with patch("cleave.gl_post_process.glGetIntegerv", side_effect=_record_getintegerv):
        with patch("cleave.gl_post_process.glIsEnabled", return_value=False):
            state = _save_gl_state()

    assert GL_FRAMEBUFFER_BINDING in queried
    assert GL_FRAMEBUFFER not in queried
    assert state.framebuffer == 42
    assert state.blend_src == 0
    assert state.vertex_array_binding == 9


def test_prepare_fixed_function_gl_binds_program_zero() -> None:
    with patch("cleave.gl_post_process.glUseProgram") as use_program:
        with patch("cleave.gl_post_process.glEnable"):
            with patch("cleave.gl_post_process.glActiveTexture"):
                with patch("cleave.gl_post_process.glBindFramebuffer"):
                    with patch("cleave.gl_post_process.glBindVertexArray"):
                        _prepare_fixed_function_gl()
    use_program.assert_called_once_with(0)


def test_apply_bloom_prepares_fixed_function_gl() -> None:
    ctx, _vaos = _mock_gl_post_process_ctx()
    post = GlPostProcess()

    with patch("cleave.gl_post_process.moderngl.create_context", return_value=ctx):
        with patch("cleave.gl_post_process._save_gl_state", return_value=MagicMock()):
            with patch("cleave.gl_post_process._restore_gl_state") as restore:
                with patch(
                    "cleave.gl_post_process._prepare_fixed_function_gl"
                ) as prepare:
                    post.apply_bloom(texture_id=7, width=64, height=64, strength=0.5)

    restore.assert_called_once()
    prepare.assert_called_once()


def test_apply_highlight_rolloff_prepares_fixed_function_gl() -> None:
    ctx, _vaos = _mock_gl_post_process_ctx()
    post = GlPostProcess()

    with patch("cleave.gl_post_process.moderngl.create_context", return_value=ctx):
        with patch("cleave.gl_post_process._save_gl_state", return_value=MagicMock()):
            with patch("cleave.gl_post_process._restore_gl_state") as restore:
                with patch(
                    "cleave.gl_post_process._prepare_fixed_function_gl"
                ) as prepare:
                    post.apply_highlight_rolloff(
                        texture_id=7,
                        width=64,
                        height=64,
                        threshold=0.78,
                        ceiling=0.65,
                        strength=0.7,
                        softness=0.4,
                        desaturation=0.3,
                        mode=0,
                    )

    restore.assert_called_once()
    prepare.assert_called_once()


def test_apply_highlight_rolloff_draws_via_gpu_shader() -> None:
    """Highlight rolloff must use the GPU shader path (copy + highlight draw)."""
    ctx, _vaos = _mock_gl_post_process_ctx()
    post = GlPostProcess()

    with patch("cleave.gl_post_process.moderngl.create_context", return_value=ctx):
        with patch("cleave.gl_post_process._save_gl_state", return_value=MagicMock()):
            with patch("cleave.gl_post_process._restore_gl_state"):
                with patch("cleave.gl_post_process._prepare_fixed_function_gl"):
                    with patch.object(post, "_draw_quad") as mock_draw:
                        result = post.apply_highlight_rolloff(
                            texture_id=7,
                            width=64,
                            height=64,
                            threshold=0.78,
                            ceiling=0.65,
                            strength=0.7,
                            softness=0.4,
                            desaturation=0.3,
                            mode=0,
                        )

    assert result == 7
    assert mock_draw.call_count == 2, (
        f"Expected 2 _draw_quad calls (copy + highlight), got {mock_draw.call_count}"
    )


def test_apply_highlight_rolloff_skips_when_strength_zero() -> None:
    post = GlPostProcess()
    assert post.apply_highlight_rolloff(7, 64, 64, 0.78, 0.65, 0.0, 0.4, 0.0, 0) == 7


def test_apply_highlight_rolloff_sets_mode_uniform() -> None:
    ctx, _vaos = _mock_gl_post_process_ctx()
    post = GlPostProcess()

    with patch("cleave.gl_post_process.moderngl.create_context", return_value=ctx):
        with patch("cleave.gl_post_process._save_gl_state", return_value=MagicMock()):
            with patch("cleave.gl_post_process._restore_gl_state"):
                with patch("cleave.gl_post_process._prepare_fixed_function_gl"):
                    with patch.object(post, "_draw_quad") as mock_draw:
                        post.apply_highlight_rolloff(
                            texture_id=7,
                            width=64,
                            height=64,
                            threshold=0.78,
                            ceiling=0.65,
                            strength=0.7,
                            softness=0.4,
                            desaturation=0.3,
                            mode=2,
                        )

    highlight_call = mock_draw.call_args_list[1]
    assert highlight_call.kwargs["extra_uniforms"]["mode"] == 2


def test_apply_chroma_boost_skips_when_amount_zero() -> None:
    post = GlPostProcess()
    assert post.apply_chroma_boost(7, 64, 64, 0, 0) == 7


def test_apply_chroma_boost_draws_via_gpu_shader() -> None:
    ctx, _vaos = _mock_gl_post_process_ctx()
    post = GlPostProcess()

    with patch("cleave.gl_post_process.moderngl.create_context", return_value=ctx):
        with patch("cleave.gl_post_process._save_gl_state", return_value=MagicMock()):
            with patch("cleave.gl_post_process._restore_gl_state"):
                with patch("cleave.gl_post_process._prepare_fixed_function_gl"):
                    with patch.object(post, "_draw_quad") as mock_draw:
                        result = post.apply_chroma_boost(
                            texture_id=7,
                            width=64,
                            height=64,
                            amount_pct=25,
                            variant=1,
                        )

    assert result == 7
    assert mock_draw.call_count == 2


def test_apply_bloom_caches_dest_fbo_per_texture() -> None:
    ctx, _vaos = _mock_gl_post_process_ctx()
    post = GlPostProcess()
    ping_buffers = MagicMock(
        copy_tex=MagicMock(use=MagicMock()),
        copy_fbo=MagicMock(use=MagicMock()),
        ping_tex=MagicMock(use=MagicMock()),
        ping_fbo=MagicMock(use=MagicMock()),
        pong_tex=MagicMock(use=MagicMock()),
        pong_fbo=MagicMock(use=MagicMock()),
    )

    with patch("cleave.gl_post_process.moderngl.create_context", return_value=ctx):
        with patch("cleave.gl_post_process._save_gl_state", return_value=MagicMock()):
            with patch("cleave.gl_post_process._restore_gl_state"):
                with patch("cleave.gl_post_process._prepare_fixed_function_gl"):
                    with patch.object(
                        post, "_ensure_buffers", return_value=ping_buffers
                    ):
                        post.apply_bloom(texture_id=7, width=64, height=64, strength=0.5)
                        first_count = ctx.framebuffer.call_count
                        post.apply_bloom(texture_id=7, width=64, height=64, strength=0.5)

    assert first_count == 1
    assert ctx.framebuffer.call_count == 1


class _ReadOnlyProgramVao:
    """Moderngl VAO stand-in: program is fixed at creation."""

    def __init__(self, program: object) -> None:
        self._program = program

    @property
    def program(self) -> object:
        return self._program

    @program.setter
    def program(self, _value: object) -> None:
        raise AttributeError("can't set attribute 'program'")

    def render(self, _mode: object) -> None:
        return None

    def release(self) -> None:
        return None


def _mock_gl_post_process_ctx() -> tuple[MagicMock, list[_ReadOnlyProgramVao]]:
    ctx = MagicMock(name="ctx")
    vaos: list[_ReadOnlyProgramVao] = []

    class _Program:
        def __init__(self) -> None:
            self._uniforms: dict[str, SimpleNamespace] = {}

        def __getitem__(self, name: str) -> SimpleNamespace:
            if name not in self._uniforms:
                self._uniforms[name] = SimpleNamespace(value=None)
            return self._uniforms[name]

    def _program(**_kwargs: object) -> _Program:
        return _Program()

    def _vertex_array(program: object, _content: object) -> _ReadOnlyProgramVao:
        vao = _ReadOnlyProgramVao(program)
        vaos.append(vao)
        return vao

    def _texture(
        size: tuple[int, int], _components: int, **kwargs: object
    ) -> MagicMock:
        tex = MagicMock(name="texture")
        tex.filter = None
        tex.repeat_x = None
        tex.repeat_y = None
        tex.use = MagicMock()
        return tex

    def _framebuffer(*, color_attachments: list[object]) -> MagicMock:
        fbo = MagicMock(name="fbo")
        fbo.use = MagicMock()
        fbo.color_attachments = color_attachments
        fbo.release = MagicMock()
        return fbo

    ctx.program.side_effect = _program
    ctx.buffer.return_value = MagicMock(name="buffer", release=MagicMock())
    ctx.vertex_array.side_effect = _vertex_array
    ctx.texture.side_effect = _texture
    ctx.framebuffer.side_effect = _framebuffer
    ctx.external_texture.return_value = _texture((64, 64), 4)
    ctx.release = MagicMock()
    return ctx, vaos


def test_read_luma_grid_returns_zeros_without_gpu() -> None:
    post = GlPostProcess()
    grid = post.read_luma_grid(0, 0, 0, grid_width=4, grid_height=3)
    assert grid.shape == (3, 4)
    assert np.all(grid == 0.0)


def test_read_luma_grid_draws_once_and_reads_fbo() -> None:
    ctx, _vaos = _mock_gl_post_process_ctx()
    post = GlPostProcess()
    grid_w, grid_h = 8, 6
    expected = np.linspace(0.0, 1.0, grid_w * grid_h, dtype=np.float32)
    grid_fbo = MagicMock(name="grid_fbo")
    grid_fbo.use = MagicMock()
    grid_fbo.read.return_value = expected.tobytes()
    grid_tex = MagicMock(name="grid_tex")
    grid_buffers = SimpleNamespace(tex=grid_tex, fbo=grid_fbo)

    with patch("cleave.gl_post_process.moderngl.create_context", return_value=ctx):
        with patch("cleave.gl_post_process._save_gl_state", return_value=MagicMock()):
            with patch("cleave.gl_post_process._restore_gl_state") as restore:
                with patch(
                    "cleave.gl_post_process._prepare_fixed_function_gl"
                ) as prepare:
                    with patch.object(
                        post,
                        "_ensure_luma_grid_buffers",
                        return_value=grid_buffers,
                    ):
                        with patch.object(post, "_draw_quad") as mock_draw:
                            grid = post.read_luma_grid(
                                texture_id=7,
                                width=64,
                                height=36,
                                grid_width=grid_w,
                                grid_height=grid_h,
                            )

    assert mock_draw.call_count == 1
    assert mock_draw.call_args.kwargs["extra_uniforms"]["hdr"] is False
    grid_fbo.read.assert_called_once_with(components=1, alignment=1, dtype="f4")
    assert grid.shape == (grid_h, grid_w)
    assert grid.ravel() == pytest.approx(expected)
    restore.assert_called_once()
    prepare.assert_called_once()


def test_read_luma_grid_sets_hdr_uniform_for_rgba16f() -> None:
    ctx, _vaos = _mock_gl_post_process_ctx()
    post = GlPostProcess(color_format=RGBA16F)
    grid_fbo = MagicMock(name="grid_fbo")
    grid_fbo.use = MagicMock()
    grid_fbo.read.return_value = np.zeros(4, dtype=np.float32).tobytes()
    grid_buffers = SimpleNamespace(tex=MagicMock(), fbo=grid_fbo)

    with patch("cleave.gl_post_process.moderngl.create_context", return_value=ctx):
        with patch("cleave.gl_post_process._save_gl_state", return_value=MagicMock()):
            with patch("cleave.gl_post_process._restore_gl_state"):
                with patch("cleave.gl_post_process._prepare_fixed_function_gl"):
                    with patch.object(
                        post,
                        "_ensure_luma_grid_buffers",
                        return_value=grid_buffers,
                    ):
                        with patch.object(post, "_draw_quad") as mock_draw:
                            post.read_luma_grid(7, 64, 36, grid_width=2, grid_height=2)

    assert mock_draw.call_args.kwargs["extra_uniforms"]["hdr"] is True


def test_apply_bloom_caches_vao_per_program() -> None:
    """Bloom must not reassign VAO.program; one VAO per shader instead."""
    ctx, vaos = _mock_gl_post_process_ctx()
    post = GlPostProcess()

    with patch("cleave.gl_post_process.moderngl.create_context", return_value=ctx):
        with patch("cleave.gl_post_process._save_gl_state", return_value=MagicMock()):
            with patch("cleave.gl_post_process._restore_gl_state"):
                with patch("cleave.gl_post_process._prepare_fixed_function_gl"):
                    result = post.apply_bloom(texture_id=7, width=64, height=64, strength=0.5)

    assert result == 7
    assert len(vaos) == 3
    assert len({id(vao.program) for vao in vaos}) == 3
    assert ctx.vertex_array.call_count == 3


def test_restore_gl_state_does_not_restore_shader_program() -> None:
    from OpenGL.GL import (
        GL_BLEND_DST_ALPHA,
        GL_BLEND_SRC_ALPHA,
        GL_TEXTURE0,
    )

    saved = MagicMock(
        framebuffer=3,
        viewport=(0, 0, 1280, 720),
        active_texture=GL_TEXTURE0,
        texture_binding=12,
        texture_2d_enabled=True,
        blend_enabled=True,
        blend_src=GL_BLEND_SRC_ALPHA,
        blend_dst=GL_BLEND_DST_ALPHA,
        blend_equation=0,
        depth_test=False,
        scissor_enabled=False,
        scissor_box=(0, 0, 1280, 720),
        color_writemask=(True, True, True, True),
        vertex_array_binding=0,
    )

    with patch("cleave.gl_post_process.glUseProgram") as use_program:
        with patch("cleave.gl_post_process.glBindFramebuffer"):
            with patch("cleave.gl_post_process.glViewport"):
                with patch("cleave.gl_post_process.glActiveTexture"):
                    with patch("cleave.gl_post_process.glBindTexture"):
                        with patch("cleave.gl_post_process.glEnable"):
                            with patch("cleave.gl_post_process.glDisable"):
                                with patch("cleave.gl_post_process.glBlendFunc"):
                                    with patch("cleave.gl_post_process.glBlendEquation"):
                                        with patch("cleave.gl_post_process.glScissor"):
                                            with patch("cleave.gl_post_process.glColorMask"):
                                                with patch(
                                                    "cleave.gl_post_process.glBindVertexArray"
                                                ):
                                                    _restore_gl_state(saved)

    use_program.assert_not_called()
