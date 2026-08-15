"""Pattern mask generators and GL upload helpers (hard and feathered weights)."""

from __future__ import annotations

import math
from dataclasses import dataclass

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

# Value-noise plasma (shared by CPU generators and GPU shader port).
PLASMA_HASH_X_MULT = 374_761_393
PLASMA_HASH_Y_MULT = 668_265_263
PLASMA_HASH_SEED_MULT = 1_274_126_177
PLASMA_HASH_MIX_MULT = 1_274_126_177
PLASMA_LAYER_SEED_STEP = 97_331
PLASMA_LAYER_BLEND_SEED_OFFSET = 224_682
PLASMA_LAYER_FREQ_SCALE = 0.17
PLASMA_LAYER_BLEND_PRIMARY = 0.65
PLASMA_LAYER_BLEND_SECONDARY = 0.35
PLASMA_FREQ_BASE = 2.0
PLASMA_FREQ_MIN = 0.25
PLASMA_HASH_DIVISOR = 4_294_967_295.0
PATTERN_MASK_DENSITY_MIN = 1.0
PATTERN_MASK_DENSITY_MAX = 10.0
DEFAULT_PATTERN_MASK_DENSITY = 1.0


@dataclass(frozen=True)
class PatternMaskParams:
    """Pattern mask settings passed into the masked compositor."""

    mask_type: str
    feather_pct: int
    density: float
    invert: bool
    seed: int


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


def pattern_mask_feather_half_width(feather_pct: int) -> float:
    """Tent half-width: 0.5 at 0% (no overlap) to 1.0 at 100% (current soft)."""
    pct = max(0, min(100, int(feather_pct)))
    return 0.5 + 0.5 * (pct / 100.0)


def pattern_mask_plasma_power(feather_pct: int) -> float:
    """Plasma field exponent: 1.0 at 100%; higher as feather approaches 0."""
    pct = max(0, min(100, int(feather_pct)))
    if pct <= 0:
        return 1.0
    return 100.0 / float(pct)


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


def _resolve_active_flags(
    layer_count: int,
    active_flags: tuple[bool, ...] | None,
) -> tuple[bool, ...]:
    if active_flags is None:
        return tuple(True for _ in range(layer_count))
    if len(active_flags) != layer_count:
        raise ValueError(
            f"active_flags length {len(active_flags)} != layer_count {layer_count}"
        )
    return tuple(bool(flag) for flag in active_flags)


def _active_layer_indices(active_flags: tuple[bool, ...]) -> list[int]:
    return [index for index, flag in enumerate(active_flags) if flag]


def _clamp_density(density: float) -> float:
    return max(PATTERN_MASK_DENSITY_MIN, min(PATTERN_MASK_DENSITY_MAX, float(density)))


def _subdivision_count(layer_count: int, density: float) -> int:
    """Segment count = round(layer_count * density); minimum equals *layer_count*.

    Density is a multiplier: 1.0x = one segment per layer, 10.0x = ten per layer.
    """
    density = _clamp_density(density)
    return max(layer_count, int(round(layer_count * density)))


def _checker_grid_dims(
    width: int, height: int, layer_count: int, density: float
) -> tuple[int, int]:
    """Column and row tile counts for checker patterns at *width* x *height*."""
    tile_count = _subdivision_count(layer_count, density)
    aspect = float(width) / float(height)
    cols = max(1, int(round(math.sqrt(tile_count * aspect))))
    rows = max(1, int(math.ceil(tile_count / cols)))
    return cols, rows


def _checker_tile_layer(row: int, col: int, layer_count: int) -> int:
    """Layer index for a checker tile; alternates in 2D (not row-major striping)."""
    return (int(row) + int(col)) % int(layer_count)


def _apply_invert(region: np.ndarray, layer_count: int, invert: bool) -> np.ndarray:
    if not invert:
        return region.astype(np.uint8, copy=False)
    return (layer_count - 1 - region.astype(np.int64)).astype(np.uint8)


def _cover_zero_mass(fields: np.ndarray, winner: np.ndarray) -> np.ndarray:
    """Assign weight 1 to *winner* where every channel is 0 (exact boundaries)."""
    total = np.sum(fields, axis=0)
    uncovered = total <= 0.0
    if not np.any(uncovered):
        return fields
    out = fields.copy()
    ys, xs = np.nonzero(uncovered)
    out[:, ys, xs] = 0.0
    out[winner[ys, xs].astype(np.int64), ys, xs] = 1.0
    return out


def _zero_inactive_fields(
    fields: np.ndarray, active_flags: tuple[bool, ...]
) -> np.ndarray:
    """Zero weight fields for inactive slots (caller renormalizes)."""
    out = fields
    for index, flag in enumerate(active_flags):
        if not flag:
            if out is fields:
                out = fields.copy()
            out[index] = 0.0
    return out


def generate_strips_mask(
    width: int,
    height: int,
    layer_count: int,
    density: float = DEFAULT_PATTERN_MASK_DENSITY,
    invert: bool = False,
    active_flags: tuple[bool, ...] | None = None,
) -> np.ndarray:
    """Return a (H, W) uint8 region-index mask of vertical strips.

    Each element is a layer index in ``0 .. layer_count-1``. Density is a
    multiplier of segments per active layer (1.0x = one strip per active
    layer); inactive slots are omitted and neighbors widen. Invert reverses
    assignment order. Every row is identical.
    """
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    flags = _resolve_active_flags(layer_count, active_flags)
    active = _active_layer_indices(flags)
    if not active:
        return np.zeros((height, width), dtype=np.uint8)
    n_active = len(active)
    strip_count = _subdivision_count(n_active, density)
    xs = np.arange(width, dtype=np.int64)
    strip_index = np.minimum(
        (xs * strip_count) // width,
        strip_count - 1,
    )
    active_arr = np.asarray(active, dtype=np.uint8)
    row = active_arr[strip_index % n_active]
    row = _apply_invert(row, layer_count, invert)
    return np.broadcast_to(row, (height, width)).copy()


def _radial_default_rotation_radians(wedge_count: int) -> float:
    """Sensible default rotation so wedges avoid flat axis-aligned splits.

    Without an offset, 2 wedges are a horizontal split and 4 form a plus.
    ``pi / max(n, 4)`` yields 45 deg for n <= 4 and half a wedge thereafter,
    keeping boundaries off the cardinal axes for typical densities.
    """
    return math.pi / max(int(wedge_count), 4)


def _radial_normalized_angle(
    width: int,
    height: int,
    wedge_count: int,
) -> np.ndarray:
    """Return (H, W) angle in [0, 1) from screen-space atan2 plus default rotation.

    Coordinates use equal pixel units on X and Y so wedge angles are true on
    any aspect ratio (not skewed by normalizing each axis independently).
    Row 0 is the GL bottom edge.
    """
    xs = (np.arange(width, dtype=np.float64) + 0.5) - width * 0.5
    ys = (np.arange(height, dtype=np.float64) + 0.5) - height * 0.5
    xx, yy = np.meshgrid(xs, ys)
    rotation = _radial_default_rotation_radians(wedge_count)
    # atan2 range (-pi, pi]; shift, rotate, wrap into [0, 1).
    return np.mod(
        (np.arctan2(yy, xx) + math.pi + rotation) / (2.0 * math.pi),
        1.0,
    )


def generate_radial_mask(
    width: int,
    height: int,
    layer_count: int,
    density: float = DEFAULT_PATTERN_MASK_DENSITY,
    invert: bool = False,
    active_flags: tuple[bool, ...] | None = None,
) -> np.ndarray:
    """Return a (H, W) uint8 mask of angular wedges from the frame center.

    Density is a multiplier of wedges per active layer (1.0x = one wedge per
    active layer). Inactive slots are omitted and neighbors widen. Wedge
    angles are computed in screen pixel space (aspect-correct) with a default
    rotation so low segment counts are diagonal rather than flat splits.
    Row 0 is the GL bottom edge (uv.y = 0).
    """
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    flags = _resolve_active_flags(layer_count, active_flags)
    active = _active_layer_indices(flags)
    if not active:
        return np.zeros((height, width), dtype=np.uint8)
    n_active = len(active)
    wedge_count = _subdivision_count(n_active, density)
    angle = _radial_normalized_angle(width, height, wedge_count)
    wedge_index = np.minimum(
        (angle * wedge_count).astype(np.int64),
        wedge_count - 1,
    )
    active_arr = np.asarray(active, dtype=np.uint8)
    region = active_arr[wedge_index % n_active]
    return _apply_invert(region, layer_count, invert)


def generate_checker_mask(
    width: int,
    height: int,
    layer_count: int,
    density: float = DEFAULT_PATTERN_MASK_DENSITY,
    invert: bool = False,
    active_flags: tuple[bool, ...] | None = None,
) -> np.ndarray:
    """Return a (H, W) uint8 mask of grid tiles cycling layers row-major.

    Density is a multiplier of tiles per layer (1.0x = one tile per layer).
    Inactive slots keep a channel index of 0 weight after soft renormalize;
    hard mode maps tiles onto active slots only. Row 0 is the GL bottom edge.
    """
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    flags = _resolve_active_flags(layer_count, active_flags)
    active = _active_layer_indices(flags)
    if not active:
        return np.zeros((height, width), dtype=np.uint8)
    n_active = len(active)
    cols, rows = _checker_grid_dims(width, height, n_active, density)
    xs = np.arange(width, dtype=np.int64)
    ys = np.arange(height, dtype=np.int64)
    col = np.minimum((xs * cols) // width, cols - 1)
    row = np.minimum((ys * rows) // height, rows - 1)
    xx, yy = np.meshgrid(col, row)
    active_arr = np.asarray(active, dtype=np.uint8)
    region = active_arr[((yy + xx) % n_active)]
    return _apply_invert(region, layer_count, invert)


def _hash_u32(x: np.ndarray, y: np.ndarray, seed: int) -> np.ndarray:
    """Deterministic 32-bit hash of integer lattice points."""
    n = (
        x.astype(np.int64) * PLASMA_HASH_X_MULT
        + y.astype(np.int64) * PLASMA_HASH_Y_MULT
        + int(seed) * PLASMA_HASH_SEED_MULT
    ) & np.int64(0xFFFFFFFF)
    n = (n ^ (n >> 13)) * np.int64(PLASMA_HASH_MIX_MULT)
    return (n & np.int64(0xFFFFFFFF)).astype(np.uint32)


def _value_noise_2d(
    width: int,
    height: int,
    *,
    frequency: float,
    seed: int,
) -> np.ndarray:
    """Bilinear value noise in [0, 1), shape (H, W). Row 0 = GL bottom."""
    frequency = max(PLASMA_FREQ_MIN, float(frequency))
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
        return _hash_u32(ix, iy, seed).astype(np.float64) / PLASMA_HASH_DIVISOR

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
    # 1.0x -> coarse (~2 features across), 10.0x -> finer (~20).
    frequency = PLASMA_FREQ_BASE * density
    fields = np.empty((layer_count, height, width), dtype=np.float64)
    for index in range(layer_count):
        fields[index] = _value_noise_2d(
            width,
            height,
            frequency=frequency,
            seed=int(seed) + index * PLASMA_LAYER_SEED_STEP,
        )
        # Slight frequency offset per layer so regions stay distinct.
        if index > 0:
            fields[index] = (
                PLASMA_LAYER_BLEND_PRIMARY * fields[index]
                + PLASMA_LAYER_BLEND_SECONDARY
                * _value_noise_2d(
                    width,
                    height,
                    frequency=frequency * (1.0 + PLASMA_LAYER_FREQ_SCALE * index),
                    seed=int(seed) + index * PLASMA_LAYER_BLEND_SEED_OFFSET + 17,
                )
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
    # Pixels with no mass: equal-split among channels that have any mass elsewhere.
    # All-zero channels (inactive slots) stay zero.
    channel_active = np.any(fields > 0.0, axis=(1, 2))
    n_active = int(np.count_nonzero(channel_active))
    if n_active <= 0:
        height, width = int(fields.shape[1]), int(fields.shape[2])
        return np.zeros((height, width, n), dtype=np.uint8)
    equal = np.zeros_like(fields)
    equal[channel_active] = 1.0 / float(n_active)
    norm = np.where(total > 0.0, norm, equal)
    scaled = np.rint(norm * 255.0).astype(np.int64)
    residual = 255 - scaled.sum(axis=0)
    max_i = np.argmax(fields, axis=0)
    # Prefer an active channel when all fields are zero at a pixel.
    if n_active < n:
        fallback = int(np.flatnonzero(channel_active)[0])
        max_i = np.where(np.max(fields, axis=0) > 0.0, max_i, fallback)
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
    density: float = DEFAULT_PATTERN_MASK_DENSITY,
    seed: int = 0,
    invert: bool = False,
    active_flags: tuple[bool, ...] | None = None,
) -> np.ndarray:
    """Return a (H, W) uint8 hard-mode plasma mask (argmax of seeded noise).

    Density scales noise frequency (1.0x coarse, 10.0x finer). Same *seed*
    yields the same mask. Inactive slots are zeroed before argmax.
    Row 0 is the GL bottom edge (uv.y = 0).
    """
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    flags = _resolve_active_flags(layer_count, active_flags)
    fields = _plasma_fields(
        width, height, layer_count, density=density, seed=seed
    )
    fields = _zero_inactive_fields(fields, flags)
    if not any(flags):
        return np.zeros((height, width), dtype=np.uint8)
    region = np.argmax(fields, axis=0).astype(np.uint8)
    return _apply_invert(region, layer_count, invert)


def _strips_weight_fields(
    width: int,
    height: int,
    layer_count: int,
    density: float,
    active_flags: tuple[bool, ...],
    feather_pct: int = 100,
) -> np.ndarray:
    """Return (N, H, W) float strip weight fields; inactive slots stay 0."""
    active = _active_layer_indices(active_flags)
    fields = np.zeros((layer_count, height, width), dtype=np.float64)
    if not active:
        return fields
    n_active = len(active)
    strip_count = _subdivision_count(n_active, density)
    half_width = pattern_mask_feather_half_width(feather_pct)
    xs = (np.arange(width, dtype=np.float64) + 0.5) / width * strip_count
    for strip in range(strip_count):
        layer = active[strip % n_active]
        center = strip + 0.5
        row = np.maximum(0.0, 1.0 - np.abs(xs - center) / half_width)
        fields[layer] += row
    strip_index = np.minimum(xs.astype(np.int64), strip_count - 1)
    active_arr = np.asarray(active, dtype=np.int64)
    winner = np.broadcast_to(active_arr[strip_index % n_active], (height, width))
    return _cover_zero_mass(fields, winner)


def _radial_weight_fields(
    width: int,
    height: int,
    layer_count: int,
    density: float,
    active_flags: tuple[bool, ...],
    feather_pct: int = 100,
) -> np.ndarray:
    """Return (N, H, W) float wedge weight fields; inactive slots stay 0."""
    active = _active_layer_indices(active_flags)
    fields = np.zeros((layer_count, height, width), dtype=np.float64)
    if not active:
        return fields
    n_active = len(active)
    wedge_count = _subdivision_count(n_active, density)
    half_width = pattern_mask_feather_half_width(feather_pct)
    angle = _radial_normalized_angle(width, height, wedge_count) * wedge_count
    for wedge in range(wedge_count):
        layer = active[wedge % n_active]
        center = wedge + 0.5
        delta = np.abs(angle - center)
        delta = np.minimum(delta, float(wedge_count) - delta)
        fields[layer] += np.maximum(0.0, 1.0 - delta / half_width)
    wedge_index = np.minimum(angle.astype(np.int64), wedge_count - 1)
    active_arr = np.asarray(active, dtype=np.int64)
    winner = active_arr[wedge_index % n_active]
    return _cover_zero_mass(fields, winner)


def _checker_weight_fields(
    width: int,
    height: int,
    layer_count: int,
    density: float,
    active_flags: tuple[bool, ...],
    feather_pct: int = 100,
) -> np.ndarray:
    """Return (N, H, W) float checker fields; inactive zeroed then renormalized."""
    tile_count = _subdivision_count(layer_count, density)
    cols, rows = _checker_grid_dims(width, height, layer_count, density)
    half_width = pattern_mask_feather_half_width(feather_pct)
    xs = (np.arange(width, dtype=np.float64) + 0.5) / width * cols
    ys = (np.arange(height, dtype=np.float64) + 0.5) / height * rows
    xx, yy = np.meshgrid(xs, ys)
    fields = np.zeros((layer_count, height, width), dtype=np.float64)
    for row in range(rows):
        for col in range(cols):
            tile = row * cols + col
            if tile >= tile_count:
                break
            layer = _checker_tile_layer(row, col, layer_count)
            dx = np.abs(xx - (col + 0.5))
            dy = np.abs(yy - (row + 0.5))
            fields[layer] += np.maximum(
                0.0, 1.0 - np.maximum(dx, dy) / half_width
            )
    fields = _zero_inactive_fields(fields, active_flags)
    col_i = np.minimum(xx.astype(np.int64), cols - 1)
    row_i = np.minimum(yy.astype(np.int64), rows - 1)
    winner = (row_i + col_i) % layer_count
    if any(not flag for flag in active_flags):
        active = _active_layer_indices(active_flags)
        if active:
            active_arr = np.asarray(active, dtype=np.int64)
            winner = active_arr[winner % len(active)]
    return _cover_zero_mass(fields, winner)


def generate_strips_weights(
    width: int,
    height: int,
    layer_count: int,
    density: float = DEFAULT_PATTERN_MASK_DENSITY,
    invert: bool = False,
    active_flags: tuple[bool, ...] | None = None,
    feather_pct: int = 100,
) -> np.ndarray:
    """Return (H, W, N) uint8 soft strip weights (sum ~255 per pixel)."""
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    flags = _resolve_active_flags(layer_count, active_flags)
    fields = _strips_weight_fields(
        width, height, layer_count, density, flags, feather_pct=feather_pct
    )
    weights = _fields_to_u8_weights(fields)
    return _invert_weight_layers(weights, invert)


def generate_radial_weights(
    width: int,
    height: int,
    layer_count: int,
    density: float = DEFAULT_PATTERN_MASK_DENSITY,
    invert: bool = False,
    active_flags: tuple[bool, ...] | None = None,
    feather_pct: int = 100,
) -> np.ndarray:
    """Return (H, W, N) uint8 soft wedge weights (sum ~255 per pixel)."""
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    flags = _resolve_active_flags(layer_count, active_flags)
    fields = _radial_weight_fields(
        width, height, layer_count, density, flags, feather_pct=feather_pct
    )
    weights = _fields_to_u8_weights(fields)
    return _invert_weight_layers(weights, invert)


def generate_checker_weights(
    width: int,
    height: int,
    layer_count: int,
    density: float = DEFAULT_PATTERN_MASK_DENSITY,
    invert: bool = False,
    active_flags: tuple[bool, ...] | None = None,
    feather_pct: int = 100,
) -> np.ndarray:
    """Return (H, W, N) uint8 soft checker weights (sum ~255 per pixel)."""
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    flags = _resolve_active_flags(layer_count, active_flags)
    fields = _checker_weight_fields(
        width, height, layer_count, density, flags, feather_pct=feather_pct
    )
    weights = _fields_to_u8_weights(fields)
    return _invert_weight_layers(weights, invert)


def _apply_plasma_feather(fields: np.ndarray, feather_pct: int) -> np.ndarray:
    """Raise plasma fields to 100/feather_pct; 100% is identity."""
    power = pattern_mask_plasma_power(feather_pct)
    if power == 1.0:
        return fields
    return np.power(np.maximum(fields, 0.0), power)


def generate_plasma_weights(
    width: int,
    height: int,
    layer_count: int,
    density: float = DEFAULT_PATTERN_MASK_DENSITY,
    seed: int = 0,
    invert: bool = False,
    active_flags: tuple[bool, ...] | None = None,
    feather_pct: int = 100,
) -> np.ndarray:
    """Return (H, W, N) uint8 soft plasma weights (sum ~255 per pixel)."""
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    flags = _resolve_active_flags(layer_count, active_flags)
    fields = _plasma_fields(
        width, height, layer_count, density=density, seed=seed
    )
    fields = _zero_inactive_fields(fields, flags)
    fields = _apply_plasma_feather(fields, feather_pct)
    weights = _fields_to_u8_weights(fields)
    return _invert_weight_layers(weights, invert)


def generate_soft_weight_fields(
    mask_type: str,
    width: int,
    height: int,
    layer_count: int,
    *,
    density: float = DEFAULT_PATTERN_MASK_DENSITY,
    invert: bool = False,
    seed: int = 0,
    active_flags: tuple[bool, ...] | None = None,
    feather_pct: int = 100,
) -> np.ndarray:
    """Return (N, H, W) float64 soft weight fields for *mask_type*.

    Inactive slots are weight 0. Fields are non-negative and suitable for
    linear blending during mask transitions; callers convert to uint8 or
    derive hard masks via argmax. *feather_pct* 100 matches full overlap;
    0 uses tent half-width 0.5 (geometric) or unpowered plasma fields.
    """
    _validate_mask_dims(width, height, layer_count)
    width = int(width)
    height = int(height)
    layer_count = int(layer_count)
    flags = _resolve_active_flags(layer_count, active_flags)
    if mask_type == "strips":
        fields = _strips_weight_fields(
            width, height, layer_count, density, flags, feather_pct=feather_pct
        )
    elif mask_type == "radial":
        fields = _radial_weight_fields(
            width, height, layer_count, density, flags, feather_pct=feather_pct
        )
    elif mask_type == "checker":
        fields = _checker_weight_fields(
            width, height, layer_count, density, flags, feather_pct=feather_pct
        )
    elif mask_type == "plasma":
        fields = _plasma_fields(
            width, height, layer_count, density=density, seed=seed
        )
        fields = _zero_inactive_fields(fields, flags)
        fields = _apply_plasma_feather(fields, feather_pct)
    else:
        raise ValueError(f"unknown pattern mask type: {mask_type!r}")
    if invert:
        fields = fields[::-1].copy()
    return fields


def hard_mask_from_weight_fields(fields: np.ndarray) -> np.ndarray:
    """Derive a (H, W) uint8 hard mask via argmax over (N, H, W) *fields*."""
    if fields.ndim != 3:
        raise ValueError("fields must be (N, H, W)")
    if fields.shape[0] <= 0:
        raise ValueError("layer_count must be positive")
    return np.argmax(fields, axis=0).astype(np.uint8)


def u8_weights_from_fields(fields: np.ndarray) -> np.ndarray:
    """Normalize (N, H, W) fields to (H, W, N) uint8 soft weights."""
    return _fields_to_u8_weights(fields)


def generate_hard_mask(
    mask_type: str,
    width: int,
    height: int,
    layer_count: int,
    *,
    density: float = DEFAULT_PATTERN_MASK_DENSITY,
    invert: bool = False,
    seed: int = 0,
    active_flags: tuple[bool, ...] | None = None,
) -> np.ndarray:
    """Dispatch hard-mode mask generation by pattern *mask_type*."""
    if mask_type == "strips":
        return generate_strips_mask(
            width,
            height,
            layer_count,
            density=density,
            invert=invert,
            active_flags=active_flags,
        )
    if mask_type == "radial":
        return generate_radial_mask(
            width,
            height,
            layer_count,
            density=density,
            invert=invert,
            active_flags=active_flags,
        )
    if mask_type == "checker":
        return generate_checker_mask(
            width,
            height,
            layer_count,
            density=density,
            invert=invert,
            active_flags=active_flags,
        )
    if mask_type == "plasma":
        return generate_plasma_mask(
            width,
            height,
            layer_count,
            density=density,
            seed=seed,
            invert=invert,
            active_flags=active_flags,
        )
    raise ValueError(f"unknown pattern mask type: {mask_type!r}")


def generate_soft_weights(
    mask_type: str,
    width: int,
    height: int,
    layer_count: int,
    *,
    density: float = DEFAULT_PATTERN_MASK_DENSITY,
    invert: bool = False,
    seed: int = 0,
    active_flags: tuple[bool, ...] | None = None,
    feather_pct: int = 100,
) -> np.ndarray:
    """Dispatch feathered weight generation by pattern *mask_type*.

    Returns an (H, W, N) uint8 array whose per-pixel layer weights sum to
    approximately 255. *feather_pct* 100 is maximum overlap.
    """
    if mask_type == "strips":
        return generate_strips_weights(
            width,
            height,
            layer_count,
            density=density,
            invert=invert,
            active_flags=active_flags,
            feather_pct=feather_pct,
        )
    if mask_type == "radial":
        return generate_radial_weights(
            width,
            height,
            layer_count,
            density=density,
            invert=invert,
            active_flags=active_flags,
            feather_pct=feather_pct,
        )
    if mask_type == "checker":
        return generate_checker_weights(
            width,
            height,
            layer_count,
            density=density,
            invert=invert,
            active_flags=active_flags,
            feather_pct=feather_pct,
        )
    if mask_type == "plasma":
        return generate_plasma_weights(
            width,
            height,
            layer_count,
            density=density,
            seed=seed,
            invert=invert,
            active_flags=active_flags,
            feather_pct=feather_pct,
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
