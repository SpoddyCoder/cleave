"""Pattern mask generators and GL upload helpers (phase 1: strips, hard mode)."""

from __future__ import annotations

import numpy as np
from OpenGL.GL import (
    GL_CLAMP_TO_EDGE,
    GL_NEAREST,
    GL_R8,
    GL_RED,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_UNSIGNED_BYTE,
    glBindTexture,
    glDeleteTextures,
    glGenTextures,
    glPixelStorei,
    glTexImage2D,
    glTexParameteri,
    glTexSubImage2D,
    GL_UNPACK_ALIGNMENT,
)

DEFAULT_TIMELINE_PRESET_PATTERN_MASK = False


def timeline_preset_pattern_mask_display(pattern_mask: bool) -> str:
    return "on" if pattern_mask else "off"


def cycle_timeline_preset_pattern_mask(value: bool, *, forward: bool) -> bool:
    options = (False, True)
    try:
        index = options.index(bool(value))
    except ValueError:
        index = options.index(DEFAULT_TIMELINE_PRESET_PATTERN_MASK)
    delta = 1 if forward else -1
    return options[(index + delta) % len(options)]


def pattern_mask_invert_display(invert: bool) -> str:
    return "on" if invert else "off"


def cycle_pattern_mask_invert(value: bool, *, forward: bool) -> bool:
    options = (False, True)
    try:
        index = options.index(bool(value))
    except ValueError:
        index = 0
    delta = 1 if forward else -1
    return options[(index + delta) % len(options)]


def _gl_name(gen_fn, count: int = 1) -> int:
    names = gen_fn(count)
    try:
        return int(names[0])
    except (TypeError, IndexError):
        return int(names)


def generate_strips_mask(
    width: int,
    layer_count: int,
    density: float = 0.5,
    invert: bool = False,
) -> np.ndarray:
    """Return a 1D uint8 region-index mask of length *width*.

    Each element is a layer index in ``0 .. layer_count-1``. Density controls how
    many vertical strips subdivide the frame (minimum = layer_count); indices
    cycle through layers. Invert reverses assignment order.
    """
    width = int(width)
    layer_count = int(layer_count)
    if width <= 0:
        raise ValueError("width must be positive")
    if layer_count <= 0:
        raise ValueError("layer_count must be positive")
    density = max(0.0, min(1.0, float(density)))
    strip_count = max(
        layer_count,
        int(round(layer_count + density * layer_count * 3)),
    )
    # Column x maps to strip s in [0, strip_count); assign layer s % layer_count.
    xs = np.arange(width, dtype=np.int64)
    # Use floor((x+0.5)/width * strip_count) so edge columns stay balanced.
    strip_index = np.minimum(
        (xs * strip_count) // width,
        strip_count - 1,
    )
    region = (strip_index % layer_count).astype(np.uint8)
    if invert:
        region = (layer_count - 1 - region.astype(np.int64)).astype(np.uint8)
    return region


def upload_mask_r8_texture(
    mask: np.ndarray,
    *,
    texture_id: int | None = None,
) -> int:
    """Upload a 1D uint8 mask as an R8 width x 1 texture with NEAREST filtering.

    When *texture_id* is provided, replaces its contents (size must match).
    Returns the GL texture id.
    """
    if mask.ndim != 1 or mask.dtype != np.uint8:
        raise ValueError("mask must be a 1D uint8 array")
    width = int(mask.shape[0])
    if width <= 0:
        raise ValueError("mask width must be positive")

    created = False
    if texture_id is None or texture_id == 0:
        texture_id = _gl_name(glGenTextures)
        created = True

    data = np.ascontiguousarray(mask)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    try:
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        if created:
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexImage2D(
                GL_TEXTURE_2D,
                0,
                GL_R8,
                width,
                1,
                0,
                GL_RED,
                GL_UNSIGNED_BYTE,
                data,
            )
        else:
            glTexSubImage2D(
                GL_TEXTURE_2D,
                0,
                0,
                0,
                width,
                1,
                GL_RED,
                GL_UNSIGNED_BYTE,
                data,
            )
    except Exception:
        if created:
            glDeleteTextures(1, [texture_id])
        raise
    finally:
        glBindTexture(GL_TEXTURE_2D, 0)
    return int(texture_id)
