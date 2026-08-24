"""Shared layer blend and opacity mapping for both compositors."""

from __future__ import annotations

from cleave.blend_modes import BlendMode
from OpenGL.GL import (
    GL_DST_COLOR,
    GL_FUNC_ADD,
    GL_FUNC_REVERSE_SUBTRACT,
    GL_FUNC_SUBTRACT,
    GL_MAX,
    GL_ONE,
    GL_ONE_MINUS_DST_COLOR,
    GL_ONE_MINUS_SRC_COLOR,
    GL_SRC_ALPHA,
    GL_ZERO,
    glBlendEquation,
    glBlendFunc,
)

LAYER_FLASH_RGB: tuple[float, float, float] = (
    240 / 255.0,
    235 / 255.0,
    230 / 255.0,
)
LAYER_FLASH_MIN_ALPHA = 0.01


def apply_layer_blend_mode(mode: BlendMode) -> None:
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


def opacity_in_alpha(mode: BlendMode | str) -> bool:
    """True when layer opacity is carried in fragment alpha (add), not RGB."""
    return mode == "add"
