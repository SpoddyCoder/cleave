"""Pattern mask generators and GL upload helpers (hard and soft modes)."""

from __future__ import annotations

import math

import numpy as np
from OpenGL.GL import (
    GL_CLAMP_TO_EDGE,
    GL_NEAREST,
    GL_R8,
    GL_RED,
    GL_TEXTURE_2D,
    GL_TEXTURE_2D_ARRAY,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_R,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_UNSIGNED_BYTE,
    glBindTexture,
    glDeleteTextures,
    glGenTextures,
    glPixelStorei,
    glTexImage2D,
    glTexImage3D,
    glTexParameteri,
    glTexSubImage2D,
    glTexSubImage3D,
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


def pattern_mask_mode_display(mode: str) -> str:
    return str(mode)


def cycle_pattern_mask_mode(value: str, *, forward: bool) -> str:
    options = ("hard", "soft")
    try:
        index = options.index(value)
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


def _validate_mask_dims(width: int, height: int, layer_count: int) -> None:
    if int(width) <= 0:
        raise ValueError("width must be positive")
    if int(height) <= 0:
        raise ValueError("height must be positive")
    if int(layer_count) <= 0:
        raise ValueError("layer_count must be positive")


def _clamp_density(density: float) -> float:
    return max(0.0, min(1.0, float(density)))


def _subdivision_count(layer_count: int, density: float) -> int:
    """Geometric subdivision count; minimum equals *layer_count*."""
    density = _clamp_density(density)
    return max(
        layer_count,
        int(round(layer_count + density * layer_count * 3)),
    )


def _apply_invert(region: np.ndarray, layer_count: int, invert: bool) -> np.ndarray:
    if not invert:
        return region.astype(np.uint8, copy=False)
    return (layer_count - 1 - region.astype(np.int64)).astype(np.uint8)


def generate_strips_mask(
    width: int,
    height: int,
    layer_count: int,
    density: float = 0.5,
    invert: bool = False,
) -> np.ndarray:
    """Return a (H, W) uint8 region-index mask of vertical strips.

    Each element is a layer index in ``0 .. layer_count-1``. Density controls how
    many vertical strips subdivide the frame (minimum = layer_count); indices
    cycle through layers. Invert reverses assignment order. Every row is identical.
    """
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    strip_count = _subdivision_count(layer_count, density)
    xs = np.arange(width, dtype=np.int64)
    strip_index = np.minimum(
        (xs * strip_count) // width,
        strip_count - 1,
    )
    row = (strip_index % layer_count).astype(np.uint8)
    row = _apply_invert(row, layer_count, invert)
    return np.broadcast_to(row, (height, width)).copy()


def generate_radial_mask(
    width: int,
    height: int,
    layer_count: int,
    density: float = 0.5,
    invert: bool = False,
) -> np.ndarray:
    """Return a (H, W) uint8 mask of angular wedges from the frame center.

    Density controls wedge count (minimum = layer_count). Row 0 is the GL
    bottom edge (uv.y = 0).
    """
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    wedge_count = _subdivision_count(layer_count, density)
    xs = (np.arange(width, dtype=np.float64) + 0.5) / width - 0.5
    ys = (np.arange(height, dtype=np.float64) + 0.5) / height - 0.5
    xx, yy = np.meshgrid(xs, ys)
    # atan2 range (-pi, pi]; map to [0, 1).
    angle = (np.arctan2(yy, xx) + math.pi) / (2.0 * math.pi)
    wedge_index = np.minimum(
        (angle * wedge_count).astype(np.int64),
        wedge_count - 1,
    )
    region = (wedge_index % layer_count).astype(np.uint8)
    return _apply_invert(region, layer_count, invert)


def generate_checker_mask(
    width: int,
    height: int,
    layer_count: int,
    density: float = 0.5,
    invert: bool = False,
) -> np.ndarray:
    """Return a (H, W) uint8 mask of grid tiles cycling layers row-major.

    Density controls tile count (minimum = layer_count). Row 0 is the GL
    bottom edge (uv.y = 0).
    """
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    tile_count = _subdivision_count(layer_count, density)
    cols = max(1, int(math.ceil(math.sqrt(tile_count))))
    rows = max(1, int(math.ceil(tile_count / cols)))
    xs = np.arange(width, dtype=np.int64)
    ys = np.arange(height, dtype=np.int64)
    col = np.minimum((xs * cols) // width, cols - 1)
    row = np.minimum((ys * rows) // height, rows - 1)
    xx, yy = np.meshgrid(col, row)
    region = ((yy * cols + xx) % layer_count).astype(np.uint8)
    return _apply_invert(region, layer_count, invert)


def _hash_u32(x: np.ndarray, y: np.ndarray, seed: int) -> np.ndarray:
    """Deterministic 32-bit hash of integer lattice points."""
    n = (
        x.astype(np.int64) * 374761393
        + y.astype(np.int64) * 668265263
        + int(seed) * 1274126177
    ) & np.int64(0xFFFFFFFF)
    n = (n ^ (n >> 13)) * np.int64(1274126177)
    return (n & np.int64(0xFFFFFFFF)).astype(np.uint32)


def _value_noise_2d(
    width: int,
    height: int,
    *,
    frequency: float,
    seed: int,
) -> np.ndarray:
    """Bilinear value noise in [0, 1), shape (H, W). Row 0 = GL bottom."""
    frequency = max(0.25, float(frequency))
    xs = (np.arange(width, dtype=np.float64) + 0.5) / width * frequency
    ys = (np.arange(height, dtype=np.float64) + 0.5) / height * frequency
    xx, yy = np.meshgrid(xs, ys)
    x0 = np.floor(xx).astype(np.int64)
    y0 = np.floor(yy).astype(np.int64)
    fx = xx - x0
    fy = yy - y0
    # Smoothstep fade.
    ux = fx * fx * (3.0 - 2.0 * fx)
    uy = fy * fy * (3.0 - 2.0 * fy)

    def lattice(ix: np.ndarray, iy: np.ndarray) -> np.ndarray:
        return _hash_u32(ix, iy, seed).astype(np.float64) / 4294967295.0

    v00 = lattice(x0, y0)
    v10 = lattice(x0 + 1, y0)
    v01 = lattice(x0, y0 + 1)
    v11 = lattice(x0 + 1, y0 + 1)
    v0 = v00 * (1.0 - ux) + v10 * ux
    v1 = v01 * (1.0 - ux) + v11 * ux
    return v0 * (1.0 - uy) + v1 * uy


def _plasma_fields(
    width: int,
    height: int,
    layer_count: int,
    *,
    density: float,
    seed: int,
) -> np.ndarray:
    """Return (N, H, W) float plasma fields in [0, 1). Row 0 = GL bottom."""
    density = _clamp_density(density)
    # density 0 -> coarse (~2 features across), density 1 -> finer (~14).
    frequency = 2.0 + density * 12.0
    fields = np.empty((layer_count, height, width), dtype=np.float64)
    for index in range(layer_count):
        fields[index] = _value_noise_2d(
            width,
            height,
            frequency=frequency,
            seed=int(seed) + index * 97_331,
        )
        # Slight frequency offset per layer so regions stay distinct.
        if index > 0:
            fields[index] = 0.65 * fields[index] + 0.35 * _value_noise_2d(
                width,
                height,
                frequency=frequency * (1.0 + 0.17 * index),
                seed=int(seed) + index * 224_682 + 17,
            )
    return fields


def _fields_to_u8_weights(fields: np.ndarray) -> np.ndarray:
    """Normalize (N, H, W) non-negative floats to (H, W, N) uint8 summing to ~255."""
    if fields.ndim != 3:
        raise ValueError("fields must be (N, H, W)")
    n = int(fields.shape[0])
    if n <= 0:
        raise ValueError("layer_count must be positive")
    total = np.sum(fields, axis=0, keepdims=True)
    safe = np.maximum(total, 1e-12)
    norm = fields / safe
    equal = np.full_like(fields, 1.0 / n)
    norm = np.where(total > 0.0, norm, equal)
    scaled = np.rint(norm * 255.0).astype(np.int64)
    residual = 255 - scaled.sum(axis=0)
    max_i = np.argmax(fields, axis=0)
    height, width = residual.shape
    ys, xs = np.indices((height, width))
    scaled[max_i, ys, xs] = np.clip(scaled[max_i, ys, xs] + residual, 0, 255)
    return np.transpose(scaled.astype(np.uint8), (1, 2, 0))


def _invert_weight_layers(weights: np.ndarray, invert: bool) -> np.ndarray:
    """Reverse layer axis of (H, W, N) weights when *invert* is set."""
    if not invert:
        return weights
    return weights[:, :, ::-1].copy()


def generate_plasma_mask(
    width: int,
    height: int,
    layer_count: int,
    density: float = 0.5,
    seed: int = 0,
    invert: bool = False,
) -> np.ndarray:
    """Return a (H, W) uint8 hard-mode plasma mask (argmax of seeded noise).

    Density controls noise frequency (feature size). Same *seed* yields the same
    mask. Row 0 is the GL bottom edge (uv.y = 0).
    """
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    fields = _plasma_fields(
        width, height, layer_count, density=density, seed=seed
    )
    region = np.argmax(fields, axis=0).astype(np.uint8)
    return _apply_invert(region, layer_count, invert)


def generate_strips_weights(
    width: int,
    height: int,
    layer_count: int,
    density: float = 0.5,
    invert: bool = False,
) -> np.ndarray:
    """Return (H, W, N) uint8 soft strip weights (sum ~255 per pixel)."""
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    strip_count = _subdivision_count(layer_count, density)
    xs = (np.arange(width, dtype=np.float64) + 0.5) / width * strip_count
    fields = np.zeros((layer_count, height, width), dtype=np.float64)
    for strip in range(strip_count):
        layer = strip % layer_count
        center = strip + 0.5
        row = np.maximum(0.0, 1.0 - np.abs(xs - center))
        fields[layer] += row
    weights = _fields_to_u8_weights(fields)
    return _invert_weight_layers(weights, invert)


def generate_radial_weights(
    width: int,
    height: int,
    layer_count: int,
    density: float = 0.5,
    invert: bool = False,
) -> np.ndarray:
    """Return (H, W, N) uint8 soft wedge weights (sum ~255 per pixel)."""
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    wedge_count = _subdivision_count(layer_count, density)
    xs = (np.arange(width, dtype=np.float64) + 0.5) / width - 0.5
    ys = (np.arange(height, dtype=np.float64) + 0.5) / height - 0.5
    xx, yy = np.meshgrid(xs, ys)
    angle = (np.arctan2(yy, xx) + math.pi) / (2.0 * math.pi) * wedge_count
    fields = np.zeros((layer_count, height, width), dtype=np.float64)
    for wedge in range(wedge_count):
        layer = wedge % layer_count
        center = wedge + 0.5
        delta = np.abs(angle - center)
        # Circular wrap so the first and last wedges blend across 0.
        delta = np.minimum(delta, float(wedge_count) - delta)
        fields[layer] += np.maximum(0.0, 1.0 - delta)
    weights = _fields_to_u8_weights(fields)
    return _invert_weight_layers(weights, invert)


def generate_checker_weights(
    width: int,
    height: int,
    layer_count: int,
    density: float = 0.5,
    invert: bool = False,
) -> np.ndarray:
    """Return (H, W, N) uint8 soft checker weights (sum ~255 per pixel)."""
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    tile_count = _subdivision_count(layer_count, density)
    cols = max(1, int(math.ceil(math.sqrt(tile_count))))
    rows = max(1, int(math.ceil(tile_count / cols)))
    xs = (np.arange(width, dtype=np.float64) + 0.5) / width * cols
    ys = (np.arange(height, dtype=np.float64) + 0.5) / height * rows
    xx, yy = np.meshgrid(xs, ys)
    fields = np.zeros((layer_count, height, width), dtype=np.float64)
    for row in range(rows):
        for col in range(cols):
            tile = row * cols + col
            if tile >= tile_count:
                break
            layer = tile % layer_count
            dx = np.abs(xx - (col + 0.5))
            dy = np.abs(yy - (row + 0.5))
            fields[layer] += np.maximum(0.0, 1.0 - np.maximum(dx, dy))
    weights = _fields_to_u8_weights(fields)
    return _invert_weight_layers(weights, invert)


def generate_plasma_weights(
    width: int,
    height: int,
    layer_count: int,
    density: float = 0.5,
    seed: int = 0,
    invert: bool = False,
) -> np.ndarray:
    """Return (H, W, N) uint8 soft plasma weights (sum ~255 per pixel)."""
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    fields = _plasma_fields(
        width, height, layer_count, density=density, seed=seed
    )
    weights = _fields_to_u8_weights(fields)
    return _invert_weight_layers(weights, invert)


def generate_hard_mask(
    mask_type: str,
    width: int,
    height: int,
    layer_count: int,
    *,
    density: float = 0.5,
    invert: bool = False,
    seed: int = 0,
) -> np.ndarray:
    """Dispatch hard-mode mask generation by pattern *mask_type*."""
    if mask_type == "strips":
        return generate_strips_mask(
            width, height, layer_count, density=density, invert=invert
        )
    if mask_type == "radial":
        return generate_radial_mask(
            width, height, layer_count, density=density, invert=invert
        )
    if mask_type == "checker":
        return generate_checker_mask(
            width, height, layer_count, density=density, invert=invert
        )
    if mask_type == "plasma":
        return generate_plasma_mask(
            width,
            height,
            layer_count,
            density=density,
            seed=seed,
            invert=invert,
        )
    raise ValueError(f"unknown pattern mask type: {mask_type!r}")


def generate_soft_weights(
    mask_type: str,
    width: int,
    height: int,
    layer_count: int,
    *,
    density: float = 0.5,
    invert: bool = False,
    seed: int = 0,
) -> np.ndarray:
    """Dispatch soft-mode weight generation by pattern *mask_type*.

    Returns an (H, W, N) uint8 array whose per-pixel layer weights sum to
    approximately 255.
    """
    if mask_type == "strips":
        return generate_strips_weights(
            width, height, layer_count, density=density, invert=invert
        )
    if mask_type == "radial":
        return generate_radial_weights(
            width, height, layer_count, density=density, invert=invert
        )
    if mask_type == "checker":
        return generate_checker_weights(
            width, height, layer_count, density=density, invert=invert
        )
    if mask_type == "plasma":
        return generate_plasma_weights(
            width,
            height,
            layer_count,
            density=density,
            seed=seed,
            invert=invert,
        )
    raise ValueError(f"unknown pattern mask type: {mask_type!r}")


def upload_mask_r8_texture(
    mask: np.ndarray,
    *,
    texture_id: int | None = None,
) -> int:
    """Upload a 2D uint8 mask as an R8 width x height texture with NEAREST filtering.

    When *texture_id* is provided, replaces its contents (size must match).
    Returns the GL texture id. *mask* row 0 is the GL bottom edge (uv.y = 0).
    """
    if mask.ndim != 2 or mask.dtype != np.uint8:
        raise ValueError("mask must be a 2D uint8 array")
    height, width = int(mask.shape[0]), int(mask.shape[1])
    if width <= 0 or height <= 0:
        raise ValueError("mask dimensions must be positive")

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
                height,
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
                height,
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


def upload_mask_weight_textures(
    weights: np.ndarray,
    *,
    texture_ids: list[int] | None = None,
) -> list[int]:
    """Upload (H, W, N) uint8 soft weights as N R8 2D textures.

    When *texture_ids* is provided it must have length N; each id is updated
    in place (sizes must match). Returns the list of GL texture ids.
    """
    if weights.ndim != 3 or weights.dtype != np.uint8:
        raise ValueError("weights must be a 3D uint8 array (H, W, N)")
    height, width, layer_count = (
        int(weights.shape[0]),
        int(weights.shape[1]),
        int(weights.shape[2]),
    )
    if width <= 0 or height <= 0 or layer_count <= 0:
        raise ValueError("weights dimensions must be positive")
    if texture_ids is not None and len(texture_ids) != layer_count:
        raise ValueError(
            f"texture_ids length {len(texture_ids)} != layer_count {layer_count}"
        )

    out: list[int] = []
    for index in range(layer_count):
        existing = None if texture_ids is None else texture_ids[index]
        out.append(
            upload_mask_r8_texture(weights[:, :, index], texture_id=existing)
        )
    return out


def upload_mask_weight_array(
    weights: np.ndarray,
    *,
    texture_id: int | None = None,
) -> int:
    """Upload (H, W, N) uint8 soft weights as an R8 texture array (N slices).

    When *texture_id* is provided, replaces its contents (size must match).
    Returns the GL texture id. Row 0 of each slice is the GL bottom edge.
    """
    if weights.ndim != 3 or weights.dtype != np.uint8:
        raise ValueError("weights must be a 3D uint8 array (H, W, N)")
    height, width, layers = (
        int(weights.shape[0]),
        int(weights.shape[1]),
        int(weights.shape[2]),
    )
    if width <= 0 or height <= 0 or layers <= 0:
        raise ValueError("weights dimensions must be positive")

    created = False
    if texture_id is None or texture_id == 0:
        texture_id = _gl_name(glGenTextures)
        created = True

    # GL expects consecutive depth slices; rearrange to (N, H, W).
    data = np.ascontiguousarray(np.transpose(weights, (2, 0, 1)))
    glBindTexture(GL_TEXTURE_2D_ARRAY, texture_id)
    try:
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        if created:
            glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE)
            glTexImage3D(
                GL_TEXTURE_2D_ARRAY,
                0,
                GL_R8,
                width,
                height,
                layers,
                0,
                GL_RED,
                GL_UNSIGNED_BYTE,
                data,
            )
        else:
            glTexSubImage3D(
                GL_TEXTURE_2D_ARRAY,
                0,
                0,
                0,
                0,
                width,
                height,
                layers,
                GL_RED,
                GL_UNSIGNED_BYTE,
                data,
            )
    except Exception:
        if created:
            glDeleteTextures(1, [texture_id])
        raise
    finally:
        glBindTexture(GL_TEXTURE_2D_ARRAY, 0)
    return int(texture_id)
