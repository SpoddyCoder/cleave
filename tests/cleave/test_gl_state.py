"""Tests for shared GL state restore and moderngl's bound-framebuffer record."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import cleave.gl_state as gl_state
from cleave.gl_state import SavedGlState, forget_moderngl_framebuffer, restore_gl_state


def _fake_ctx(*, with_screen: bool = True) -> SimpleNamespace:
    screen = SimpleNamespace(mglo=object()) if with_screen else None
    released = SimpleNamespace(mglo=object())
    return SimpleNamespace(
        screen=screen,
        fbo=released,
        mglo=SimpleNamespace(fbo=released.mglo),
        viewport=None,
    )


def _saved_state() -> SavedGlState:
    return SavedGlState(
        framebuffer=0,
        viewport=(0, 0, 640, 360),
        active_texture=0x84C0,
        texture_binding=0,
        texture_2d_enabled=False,
        blend_enabled=False,
        blend_src=1,
        blend_dst=0,
        blend_equation=0x8006,
        depth_test=False,
        scissor_enabled=False,
        scissor_box=(0, 0, 640, 360),
        color_writemask=(True, True, True, True),
        vertex_array_binding=0,
        read_framebuffer=0,
        read_buffer=0x0405,
    )


def test_forget_points_both_records_at_the_screen() -> None:
    ctx = _fake_ctx()

    forget_moderngl_framebuffer(ctx)

    assert ctx.fbo is ctx.screen
    assert ctx.mglo.fbo is ctx.screen.mglo


def test_forget_without_a_screen_leaves_the_record() -> None:
    ctx = _fake_ctx(with_screen=False)
    before = ctx.fbo

    forget_moderngl_framebuffer(ctx)

    assert ctx.fbo is before


def test_restore_with_ctx_forgets_the_released_framebuffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "glBindFramebuffer",
        "glReadBuffer",
        "glViewport",
        "glActiveTexture",
        "glBindTexture",
        "glEnable",
        "glDisable",
        "glBlendFunc",
        "glBlendEquation",
        "glScissor",
        "glColorMask",
        "glBindVertexArray",
    ):
        monkeypatch.setattr(gl_state, name, lambda *_args: None)
    ctx = _fake_ctx()

    restore_gl_state(_saved_state(), ctx)

    assert ctx.fbo is ctx.screen
    assert ctx.mglo.fbo is ctx.screen.mglo
    assert ctx.viewport == (0, 0, 640, 360)
