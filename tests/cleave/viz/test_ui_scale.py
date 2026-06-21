"""Tests for UI scale helpers in cleave.viz.theme."""

from __future__ import annotations

from cleave.viz.theme import (
    scale_px,
    timeline_panel_height_px,
    timeline_ui_metrics,
    tuning_ui_metrics,
)


def test_tuning_ui_metrics_default_scale() -> None:
    metrics = tuning_ui_metrics(scale=1.5)
    assert metrics.font_size == 21
    assert metrics.padding == 12
    assert metrics.line_gap == 4
    assert metrics.tree_indent == 12
    assert metrics.panel_content_max_width == 660


def test_timeline_ui_metrics_default_scale() -> None:
    metrics = timeline_ui_metrics(scale=1.0)
    assert metrics.font_size == 14
    assert metrics.padding == 8
    assert metrics.row_height == 25
    assert metrics.row_gap == 2
    assert metrics.panel_gap == 16


def test_timeline_panel_height_px_scales_with_ui_scale() -> None:
    assert timeline_panel_height_px(4, scale=1.0) == 122
    assert timeline_panel_height_px(4, scale=1.2) == 146


def test_timeline_ui_metrics_row_height_scales() -> None:
    assert timeline_ui_metrics(scale=1.0).row_height == 25
    assert timeline_ui_metrics(scale=1.2).row_height == 30


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
