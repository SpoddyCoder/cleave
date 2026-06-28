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
    ("black-key", "Milkdrop black is transparent; brightness sets blend weight."),
    ("add", "additive highlights, suited to drums."),
    ("multiply", "multiply destination color by source."),
    ("screen", "lighten destination with source."),
    ("subtract", "subtract source from destination."),
    ("difference", "absolute difference between layers."),
    ("exclusion", "soft difference blend."),
    ("max", "per-channel maximum of source and destination."),
    ("pure-add", "add source without alpha weighting."),
)
