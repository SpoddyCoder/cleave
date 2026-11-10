"""Tests for UI scale helpers in cleave.viz.theme."""

from __future__ import annotations

import re
from pathlib import Path

from cleave.config_schema.editor import DEFAULT_UI_SCALE, UI_SCALE_MAX
from cleave.viz.theme import (
    BASE_UI_SCALE,
    scale_px,
    set_ui_scale_percent,
    timeline_panel_height_px,
    timeline_ui_metrics,
    tuning_ui_metrics,
    ui_px,
    ui_scale,
    ui_scale_generation,
    ui_scale_percent,
)


def test_tuning_ui_metrics_default_scale() -> None:
    metrics = tuning_ui_metrics(scale=1.5)
    assert metrics.font_size == 21
    assert metrics.padding == 12
    assert metrics.line_gap == 4
    assert metrics.tree_indent == 12


def test_timeline_ui_metrics_default_scale() -> None:
    metrics = timeline_ui_metrics(scale=1.0)
    assert metrics.font_size == 11
    assert metrics.padding == 6
    assert metrics.row_height == 20
    assert metrics.row_gap == 2


def test_timeline_panel_height_px_scales_with_ui_scale() -> None:
    assert timeline_panel_height_px(4, scale=1.0) == 106
    assert timeline_panel_height_px(4, scale=1.2) == 129


def test_timeline_ui_metrics_row_height_scales() -> None:
    assert timeline_ui_metrics(scale=1.0).row_height == 20
    assert timeline_ui_metrics(scale=1.2).row_height == 24


def test_timeline_is_smaller_than_ui_scale_at_every_scale() -> None:
    from cleave.viz.theme import TIMELINE_SCALE, scale_px

    for scale in (0.96, 1.2, 1.8, 2.4):
        metrics = timeline_ui_metrics(scale=scale)
        assert metrics.row_height == scale_px(25, scale=scale * TIMELINE_SCALE)
        assert metrics.font_size == scale_px(14, scale=scale * TIMELINE_SCALE)


def test_scale_px_rounds_and_clamps() -> None:
    assert scale_px(3, scale=1.5) == 4
    assert scale_px(8, scale=1.5) == 12
    assert scale_px(1, scale=0.1) == 1
    assert scale_px(0.4, scale=1.0) == 1


def test_baseline_tuning_ui_metrics() -> None:
    metrics = tuning_ui_metrics(scale=1.0)
    assert metrics.font_size == 14
    assert metrics.padding == 8
    assert metrics.tree_indent == 8


def test_live_scale_defaults_to_base_at_100_percent() -> None:
    assert ui_scale_percent() == DEFAULT_UI_SCALE
    assert ui_scale() == BASE_UI_SCALE
    assert tuning_ui_metrics() == tuning_ui_metrics(scale=BASE_UI_SCALE)
    assert timeline_ui_metrics() == timeline_ui_metrics(scale=BASE_UI_SCALE)


def test_set_ui_scale_percent_drives_metrics_and_generation() -> None:
    generation = ui_scale_generation()
    try:
        set_ui_scale_percent(200)
        assert ui_scale_generation() == generation + 1
        assert ui_scale() == BASE_UI_SCALE * 2
        assert tuning_ui_metrics().font_size == 40
        assert timeline_ui_metrics().row_height == 58
        assert ui_px(10) == 29
        set_ui_scale_percent(200)
        assert ui_scale_generation() == generation + 1
        set_ui_scale_percent(1000)
        assert ui_scale_percent() == UI_SCALE_MAX
    finally:
        set_ui_scale_percent(DEFAULT_UI_SCALE)
    assert tuning_ui_metrics().font_size == 20


def test_no_import_time_metric_captures_in_viz() -> None:
    """Module-level metric reads freeze the scale; read them at draw time."""
    pattern = re.compile(
        r"^[A-Za-z_][A-Za-z_0-9]*(?:\s*:\s*[^=]+)?\s*=\s*.*"
        r"(tuning_ui_metrics\(|timeline_ui_metrics\(|ui_px\(|scale=BASE_UI_SCALE)",
        re.MULTILINE,
    )
    viz = Path(__file__).resolve().parents[3] / "cleave" / "viz"
    offenders = [
        f"{path.relative_to(viz)}: {match.group(0).strip()}"
        for path in sorted(viz.rglob("*.py"))
        for match in pattern.finditer(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
