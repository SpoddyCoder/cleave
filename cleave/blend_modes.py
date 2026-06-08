"""Compositor blend mode names (no OpenGL / pygame dependency)."""

from __future__ import annotations

from typing import Literal

BlendMode = Literal[
    "black-key",
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
    "black-key",
    "add",
    "multiply",
    "screen",
    "subtract",
    "difference",
    "exclusion",
    "max",
    "pure-add",
)
