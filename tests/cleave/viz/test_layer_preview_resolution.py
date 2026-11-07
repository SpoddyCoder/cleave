"""Tests for live preview layer resolution from preview quality and z-order."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from cleave.config import CleaveConfig, LayerConfig, PathsConfig, EditorConfig
from cleave.config_schema.layers import DEFAULT_LAYER_SLOTS
from cleave.viz.layer_preview_resolution import (
    PREVIEW_MIN_VIZ_SCALE,
    live_content_size,
    offline_layer_sizes,
    preview_layer_size,
    preview_sizes_for_session,
    render_layer_size,
)
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.config import TEST_LAYER_STEMS
from tests.support.viz import make_playlist


def _layer_cfg(*, slot: str = "layer_1") -> LayerConfig:
    return LayerConfig(
        preset=Path(f"/tmp/presets/{slot}/preset.milk"),
        stem=TEST_LAYER_STEMS[slot],
    )


BASE = (1280, 720)


def _editor(preview_quality: str = "balanced") -> EditorConfig:
    return EditorConfig(preview_quality=preview_quality)  # type: ignore[arg-type]


def _session(
    slots: tuple[str, ...] = ("layer_1", "layer_2", "layer_3", "layer_4"),
    *,
    size: tuple[int, int] = BASE,
) -> TuningSession:
    preset_root = Path("/tmp/presets")
    session = TuningSession(
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
    session.project.resolution.width, session.project.resolution.height = size
    return session


def _cfg(
    *,
    preview_quality: str = "balanced",
    slots: tuple[str, ...] = ("layer_1", "layer_2", "layer_3", "layer_4"),
) -> CleaveConfig:
    preset_root = Path("/tmp/presets")
    layers = {
        slot: _layer_cfg(slot=slot)
        for slot in DEFAULT_LAYER_SLOTS
    }
    return CleaveConfig(
        paths=PathsConfig(preset_root=preset_root, texture_paths=()),
        layers=layers,
        layer_z_order=list(slots),
        editor=_editor(preview_quality),
        resolution_width=BASE[0],
        resolution_height=BASE[1],
        config_path=Path("/tmp/test/cleave.config.yaml"),
        user_config_path=Path("/tmp/user-config.yaml"),
    )


@pytest.mark.parametrize(
    ("preview_quality", "z_index", "expected"),
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
    preview_quality: str,
    z_index: int,
    expected: tuple[int, int],
) -> None:
    size = preview_layer_size(
        preview_quality,  # type: ignore[arg-type]
        z_index,
        BASE,
    )
    assert size == expected


def test_balanced_floor_boundary_index_5_uses_base_floor() -> None:
    base = (1920, 1080)
    size = preview_layer_size("balanced", 5, base)
    min_w = round(base[0] * PREVIEW_MIN_VIZ_SCALE)
    min_h = round(base[1] * PREVIEW_MIN_VIZ_SCALE)
    assert size == (min_w, min_h)


def test_performance_floor_boundary_index_4_uses_base_floor() -> None:
    base = (1920, 1080)
    size = preview_layer_size("performance", 4, base)
    min_w = round(base[0] * PREVIEW_MIN_VIZ_SCALE)
    min_h = round(base[1] * PREVIEW_MIN_VIZ_SCALE)
    assert size == (min_w, min_h)


def test_ultra_performance_floor_boundary_index_3_uses_base_floor() -> None:
    base = (1920, 1080)
    size = preview_layer_size("ultra-performance", 3, base)
    min_w = round(base[0] * PREVIEW_MIN_VIZ_SCALE)
    min_h = round(base[1] * PREVIEW_MIN_VIZ_SCALE)
    assert size == (min_w, min_h)


def test_floor_clamp_preserves_base_aspect() -> None:
    base = (1920, 1080)
    size = preview_layer_size("balanced", 5, base)
    min_w = round(base[0] * PREVIEW_MIN_VIZ_SCALE)
    assert size[0] == min_w
    assert size[0] / size[1] == pytest.approx(
        base[0] / base[1], rel=0.02
    )


def test_full_quality_returns_base_size() -> None:
    assert preview_layer_size("full-quality", 0, (1600, 900)) == (1600, 900)


def test_preview_sizes_for_session_keys_slots_with_z_order_indices() -> None:
    cfg = _cfg(preview_quality="balanced")
    session = _session(("layer_2", "layer_1"))
    sizes = preview_sizes_for_session(cfg, session)

    assert set(sizes) == {"layer_2", "layer_1"}
    assert sizes["layer_2"] == preview_layer_size("balanced", 0, BASE)
    assert sizes["layer_1"] == preview_layer_size("balanced", 1, BASE)


def test_preview_sizes_for_session_follow_session_render_size() -> None:
    cfg = _cfg(preview_quality="full-quality")
    session = _session(("layer_1",), size=(1080, 1920))
    assert live_content_size(session) == (1080, 1920)
    assert preview_sizes_for_session(cfg, session)["layer_1"] == (1080, 1920)


def test_preview_sizes_for_session_follows_cfg_preview_quality() -> None:
    cfg = replace(_cfg(), editor=_editor("performance"))
    session = _session(("layer_1",))
    sizes = preview_sizes_for_session(cfg, session)
    assert sizes["layer_1"] == (960, 540)


def test_offline_layer_sizes_uses_passed_layer_z_order() -> None:
    cfg = _cfg(preview_quality="balanced", slots=("layer_1", "layer_2"))
    sizes = offline_layer_sizes(cfg, ("layer_2", "layer_1"))

    assert set(sizes) == {"layer_2", "layer_1"}
    assert sizes["layer_2"] == preview_layer_size("balanced", 0, BASE)
    assert sizes["layer_1"] == preview_layer_size("balanced", 1, BASE)


def test_offline_layer_sizes_follow_render_output_size() -> None:
    cfg = replace(
        _cfg(preview_quality="performance", slots=("layer_1",)),
        resolution_width=1080,
        resolution_height=1920,
    )
    assert offline_layer_sizes(cfg, ("layer_1",))["layer_1"] == (810, 1440)


def test_render_layer_size_full_quality_uses_render_output() -> None:
    cfg = replace(
        _cfg(),
        resolution_width=1920,
        resolution_height=1080,
    )
    assert render_layer_size(cfg, 0, viz_quality=False) == (1920, 1080)
    assert render_layer_size(cfg, 3, viz_quality=False) == (1920, 1080)


def test_render_layer_size_full_quality_uses_output_at_mismatched_aspect() -> None:
    cfg = replace(
        _cfg(),
        resolution_width=1080,
        resolution_height=1920,
    )
    assert render_layer_size(cfg, 0, viz_quality=False) == (1080, 1920)
    assert render_layer_size(cfg, 3, viz_quality=False) == (1080, 1920)


def test_render_layer_size_viz_quality_uses_preview_scales() -> None:
    cfg = _cfg(preview_quality="performance")
    assert render_layer_size(cfg, 0, viz_quality=True) == (960, 540)
    assert render_layer_size(cfg, 2, viz_quality=True) == (512, 288)
