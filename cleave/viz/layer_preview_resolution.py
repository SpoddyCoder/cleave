"""Live preview layer resolution from visualizer preview quality and z-order."""

from __future__ import annotations

import math
from collections.abc import Sequence

from cleave.config import (
    CleaveConfig,
    EditorPreviewQuality,
    project_resolution,
)
from cleave.gl_fit import aspect_fit_size
from cleave.viz.session import TuningSession

PREVIEW_MIN_VIZ_SCALE = 0.25

# Fitted live widths round up to this step so a window or splitter drag does
# not reallocate the framebuffers for every pixel.
LIVE_CONTENT_WIDTH_STEP = 64
# Narrowest fitted live width (unless the project itself is narrower).
LIVE_CONTENT_MIN_WIDTH = 256

_BALANCED_SCALES: tuple[float, ...] = (1.00, 0.85, 0.70, 0.55, 0.40)
_PERFORMANCE_SCALES: tuple[float, ...] = (0.75, 0.55, 0.40, 0.30)
_ULTRA_PERFORMANCE_SCALES: tuple[float, ...] = (0.50, 0.35, 0.25)

_FLOOR_ONLY = 0.0


def _full_size(preview_quality: EditorPreviewQuality) -> bool:
    return preview_quality in ("output", "full-quality")


def _requested_scale(preview_quality: EditorPreviewQuality, z_index: int) -> float:
    if _full_size(preview_quality):
        return 1.0
    if preview_quality == "balanced":
        if z_index < len(_BALANCED_SCALES):
            return _BALANCED_SCALES[z_index]
        return _FLOOR_ONLY
    if preview_quality == "performance":
        if z_index < len(_PERFORMANCE_SCALES):
            return _PERFORMANCE_SCALES[z_index]
        return _FLOOR_ONLY
    if z_index < len(_ULTRA_PERFORMANCE_SCALES):
        return _ULTRA_PERFORMANCE_SCALES[z_index]
    return _FLOOR_ONLY


def session_project_size(session: TuningSession) -> tuple[int, int]:
    resolution = session.project.resolution
    return resolution.width, resolution.height


def live_content_size(
    project_size: tuple[int, int],
    draw_size: tuple[int, int] | None,
    preview_quality: EditorPreviewQuality,
) -> tuple[int, int]:
    """Live content size: the project aspect fitted to the on-screen size.

    The result never exceeds *project_size*. ``output`` quality, or no known
    *draw_size*, uses *project_size* itself.
    """
    project_w, project_h = project_size
    if preview_quality == "output" or draw_size is None:
        return project_w, project_h
    fit = aspect_fit_size((project_w, project_h), draw_size)
    if fit is None:
        return project_w, project_h
    step = LIVE_CONTENT_WIDTH_STEP
    width = math.ceil(fit[0] / step) * step
    width = max(width, LIVE_CONTENT_MIN_WIDTH)
    if width >= project_w:
        return project_w, project_h
    height = max(1, round(width * project_h / project_w))
    return width, height


def preview_layer_size(
    preview_quality: EditorPreviewQuality,
    z_index: int,
    base: tuple[int, int],
) -> tuple[int, int]:
    """Layer size for *z_index*: *base* scaled by the preview quality tier."""
    layer_w, layer_h = base
    if _full_size(preview_quality):
        return layer_w, layer_h

    requested_scale = _requested_scale(preview_quality, z_index)
    min_w = round(layer_w * PREVIEW_MIN_VIZ_SCALE)
    min_h = round(layer_h * PREVIEW_MIN_VIZ_SCALE)
    effective_scale = max(requested_scale, min_w / layer_w, min_h / layer_h)
    w = max(1, round(layer_w * effective_scale))
    h = max(1, round(layer_h * effective_scale))
    return w, h


def offline_layer_sizes(
    cfg: CleaveConfig,
    layer_z_order: Sequence[str],
) -> dict[str, tuple[int, int]]:
    preview_quality = cfg.editor.preview_quality
    base = project_resolution(cfg)
    return {
        slot: preview_layer_size(preview_quality, z_index, base)
        for z_index, slot in enumerate(layer_z_order)
    }


def render_layer_size(
    cfg: CleaveConfig,
    z_index: int,
    *,
    viz_quality: bool,
) -> tuple[int, int]:
    if not viz_quality:
        return project_resolution(cfg)
    return preview_layer_size(
        cfg.editor.preview_quality,
        z_index,
        project_resolution(cfg),
    )


def preview_sizes_for_session(
    cfg: CleaveConfig,
    session: TuningSession,
    base: tuple[int, int],
) -> dict[str, tuple[int, int]]:
    """Layer sizes for the live content size *base*, keyed by slot."""
    preview_quality = cfg.editor.preview_quality
    return {
        slot: preview_layer_size(preview_quality, z_index, base)
        for z_index, slot in enumerate(session.layer_z_order)
    }
