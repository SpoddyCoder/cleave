"""Live preview layer resolution from visualizer preview quality and z-order."""

from __future__ import annotations

from collections.abc import Sequence

from cleave.config import (
    CleaveConfig,
    EditorPreviewQuality,
    project_resolution,
)
from cleave.viz.session import TuningSession

PREVIEW_MIN_VIZ_SCALE = 0.25

_BALANCED_SCALES: tuple[float, ...] = (1.00, 0.85, 0.70, 0.55, 0.40)
_PERFORMANCE_SCALES: tuple[float, ...] = (0.75, 0.55, 0.40, 0.30)
_ULTRA_PERFORMANCE_SCALES: tuple[float, ...] = (0.50, 0.35, 0.25)

_FLOOR_ONLY = 0.0


def _requested_scale(preview_quality: EditorPreviewQuality, z_index: int) -> float:
    if preview_quality == "full-quality":
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


def live_content_size(session: TuningSession) -> tuple[int, int]:
    """Live visualiser content size: the project resolution."""
    resolution = session.project.resolution
    return resolution.width, resolution.height


def preview_layer_size(
    preview_quality: EditorPreviewQuality,
    z_index: int,
    base: tuple[int, int],
) -> tuple[int, int]:
    """Layer size for *z_index*: *base* scaled by the preview quality tier."""
    layer_w, layer_h = base
    if preview_quality == "full-quality":
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
) -> dict[str, tuple[int, int]]:
    preview_quality = cfg.editor.preview_quality
    base = live_content_size(session)
    return {
        slot: preview_layer_size(preview_quality, z_index, base)
        for z_index, slot in enumerate(session.layer_z_order)
    }
