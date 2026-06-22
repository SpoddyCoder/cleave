"""Live preview layer resolution from visualizer render mode and z-order."""

from __future__ import annotations

from cleave.config import (
    CleaveConfig,
    LayerConfig,
    VisualizerConfig,
    VisualizerRenderMode,
)
from cleave.viz.session import TuningSession

PREVIEW_MIN_VIZ_SCALE = 0.25

_BALANCED_SCALES: tuple[float, ...] = (1.00, 0.85, 0.70, 0.55, 0.40)
_PERFORMANCE_SCALES: tuple[float, ...] = (0.75, 0.55, 0.40, 0.30)
_ULTRA_PERFORMANCE_SCALES: tuple[float, ...] = (0.50, 0.35, 0.25)

_FLOOR_ONLY = 0.0


def _requested_scale(render_mode: VisualizerRenderMode, z_index: int) -> float:
    if render_mode == "full-quality":
        return 1.0
    if render_mode == "balanced":
        if z_index < len(_BALANCED_SCALES):
            return _BALANCED_SCALES[z_index]
        return _FLOOR_ONLY
    if render_mode == "performance":
        if z_index < len(_PERFORMANCE_SCALES):
            return _PERFORMANCE_SCALES[z_index]
        return _FLOOR_ONLY
    if z_index < len(_ULTRA_PERFORMANCE_SCALES):
        return _ULTRA_PERFORMANCE_SCALES[z_index]
    return _FLOOR_ONLY


def preview_layer_size(
    render_mode: VisualizerRenderMode,
    z_index: int,
    layer_cfg: LayerConfig,
    visualizer: VisualizerConfig,
) -> tuple[int, int]:
    layer_w = layer_cfg.width
    layer_h = layer_cfg.height
    if render_mode == "full-quality":
        return layer_w, layer_h

    requested_scale = _requested_scale(render_mode, z_index)
    min_w = round(visualizer.width * PREVIEW_MIN_VIZ_SCALE)
    min_h = round(visualizer.height * PREVIEW_MIN_VIZ_SCALE)
    effective_scale = max(requested_scale, min_w / layer_w, min_h / layer_h)
    w = max(1, round(layer_w * effective_scale))
    h = max(1, round(layer_h * effective_scale))
    return w, h


def preview_sizes_for_session(
    cfg: CleaveConfig,
    session: TuningSession,
) -> dict[str, tuple[int, int]]:
    render_mode = cfg.visualizer.render_mode
    visualizer = cfg.visualizer
    return {
        slot: preview_layer_size(
            render_mode,
            z_index,
            cfg.layers[slot],
            visualizer,
        )
        for z_index, slot in enumerate(session.layer_z_order)
    }
