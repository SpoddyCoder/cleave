"""Tests for live preview layer resolution from render mode and z-order."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from cleave.config import CleaveConfig, LayerConfig, PathsConfig, VisualizerConfig
from cleave.config_schema import DEFAULT_LAYER_SLOTS
from cleave.viz.layer_preview_resolution import (
    PREVIEW_MIN_VIZ_SCALE,
    preview_layer_size,
    preview_sizes_for_session,
)
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.config import TEST_LAYER_STEMS
from tests.support.viz import make_playlist


def _layer_cfg(
    width: int = 1280,
    height: int = 720,
    *,
    slot: str = "layer_1",
) -> LayerConfig:
    return LayerConfig(
        preset=Path(f"/tmp/presets/{slot}/preset.milk"),
        stem=TEST_LAYER_STEMS[slot],
        width=width,
        height=height,
    )


def _visualizer(
    width: int = 1280,
    height: int = 720,
    *,
    render_mode: str = "balanced",
) -> VisualizerConfig:
    return VisualizerConfig(width=width, height=height, render_mode=render_mode)  # type: ignore[arg-type]


def _session(slots: tuple[str, ...] = ("layer_1", "layer_2", "layer_3", "layer_4")) -> TuningSession:
    preset_root = Path("/tmp/presets")
    return TuningSession(
        layer_z_order=list(slots),
        layers={
            slot: LayerRuntime(
                playlist=make_playlist(slot),
                browse_floor=preset_root / slot,
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in slots
        },
    )


def _cfg(
    *,
    render_mode: str = "balanced",
    layer_sizes: dict[str, tuple[int, int]] | None = None,
    slots: tuple[str, ...] = ("layer_1", "layer_2", "layer_3", "layer_4"),
) -> CleaveConfig:
    preset_root = Path("/tmp/presets")
    layers = {
        slot: _layer_cfg(
            *(layer_sizes[slot] if layer_sizes and slot in layer_sizes else (1280, 720)),
            slot=slot,
        )
        for slot in DEFAULT_LAYER_SLOTS
    }
    return CleaveConfig(
        paths=PathsConfig(preset_root=preset_root, texture_paths=()),
        layers=layers,
        layer_z_order=list(slots),
        visualizer=_visualizer(render_mode=render_mode),
        config_path=Path("/tmp/test/cleave.config.yaml"),
    )


@pytest.mark.parametrize(
    ("render_mode", "z_index", "expected"),
    [
        ("full-quality", 0, (1280, 720)),
        ("full-quality", 3, (1280, 720)),
        ("balanced", 0, (1280, 720)),
        ("balanced", 1, (1088, 612)),
        ("balanced", 2, (896, 504)),
        ("balanced", 3, (704, 396)),
        ("balanced", 4, (512, 288)),
        ("performance", 0, (960, 540)),
        ("performance", 1, (704, 396)),
        ("performance", 2, (512, 288)),
        ("performance", 3, (384, 216)),
        ("ultra-performance", 0, (640, 360)),
        ("ultra-performance", 1, (448, 252)),
        ("ultra-performance", 2, (320, 180)),
        ("ultra-performance", 3, (320, 180)),
    ],
)
def test_preview_layer_size_table_scales(
    render_mode: str,
    z_index: int,
    expected: tuple[int, int],
) -> None:
    size = preview_layer_size(
        render_mode,  # type: ignore[arg-type]
        z_index,
        _layer_cfg(),
        _visualizer(),
    )
    assert size == expected


def test_balanced_floor_boundary_index_5_uses_visualizer_floor() -> None:
    visualizer = _visualizer()
    layer = _layer_cfg(1920, 1080)
    size = preview_layer_size("balanced", 5, layer, visualizer)
    min_w = round(visualizer.width * PREVIEW_MIN_VIZ_SCALE)
    min_h = round(visualizer.height * PREVIEW_MIN_VIZ_SCALE)
    assert size == (min_w, min_h)


def test_performance_floor_boundary_index_4_uses_visualizer_floor() -> None:
    visualizer = _visualizer()
    layer = _layer_cfg(1920, 1080)
    size = preview_layer_size("performance", 4, layer, visualizer)
    min_w = round(visualizer.width * PREVIEW_MIN_VIZ_SCALE)
    min_h = round(visualizer.height * PREVIEW_MIN_VIZ_SCALE)
    assert size == (min_w, min_h)


def test_ultra_performance_floor_boundary_index_3_uses_visualizer_floor() -> None:
    visualizer = _visualizer()
    layer = _layer_cfg(1920, 1080)
    size = preview_layer_size("ultra-performance", 3, layer, visualizer)
    min_w = round(visualizer.width * PREVIEW_MIN_VIZ_SCALE)
    min_h = round(visualizer.height * PREVIEW_MIN_VIZ_SCALE)
    assert size == (min_w, min_h)


def test_floor_clamp_raises_small_layer_to_minimum_while_preserving_aspect() -> None:
    visualizer = _visualizer()
    layer = _layer_cfg(800, 600)
    size = preview_layer_size("performance", 3, layer, visualizer)
    min_w = round(visualizer.width * PREVIEW_MIN_VIZ_SCALE)
    assert size[0] == min_w
    assert size[0] / size[1] == pytest.approx(layer.width / layer.height, rel=0.02)


def test_full_quality_ignores_non_square_layer_yaml_size() -> None:
    layer = _layer_cfg(1600, 900)
    assert preview_layer_size("full-quality", 0, layer, _visualizer()) == (1600, 900)


def test_preview_sizes_for_session_keys_slots_with_z_order_indices() -> None:
    cfg = _cfg(render_mode="balanced")
    session = _session(("layer_2", "layer_1"))
    sizes = preview_sizes_for_session(cfg, session)

    assert set(sizes) == {"layer_2", "layer_1"}
    assert sizes["layer_2"] == preview_layer_size("balanced", 0, cfg.layers["layer_2"], cfg.visualizer)
    assert sizes["layer_1"] == preview_layer_size("balanced", 1, cfg.layers["layer_1"], cfg.visualizer)


def test_preview_sizes_for_session_follows_cfg_render_mode() -> None:
    cfg = replace(_cfg(), visualizer=_visualizer(render_mode="performance"))
    session = _session(("layer_1",))
    sizes = preview_sizes_for_session(cfg, session)
    assert sizes["layer_1"] == (960, 540)
