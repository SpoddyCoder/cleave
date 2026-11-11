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

BLEND_MODE_HELP_ENTRIES: tuple[tuple[BlendMode, str], ...] = (
    ("black-key", "black is transparent; brighter areas show more."),
    ("add", "adds brightness; good for drums."),
    ("multiply", "darkens; multiplies the colours below."),
    ("screen", "lightens; the opposite of multiply."),
    ("subtract", "subtracts this layer from the layers below."),
    ("difference", "shows the difference between the layers."),
    ("exclusion", "a softer, lower-contrast difference."),
    ("max", "keeps the brighter value of each colour channel."),
    ("pure-add", "adds this layer at full strength; ignores transparency."),
)
