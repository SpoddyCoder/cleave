"""Tests for live tuning panel row and panel cache."""

from __future__ import annotations

import pygame

from cleave.viz.overlay_profiler import OverlayDrawCounters
from cleave.viz.row_semantics import RowDescriptor, RowKind, row_is_pinned
from cleave.viz.theme import BORDER_COLOR
from cleave.viz.focus_nav import MainFocus
from cleave.viz.tuning_panel_cache import (
    TuningPanelCache,
    ensure_row_surface,
    row_render_key,
    static_row_keys,
)
from cleave.viz.tuning_panel_draw import TuningOverlay
from cleave.viz.tuning_view_state import TrackBlock, TuningViewState
from tests.cleave.viz.test_overlay import (
    _effects_expanded_view_state,
    _minimal_view_state,
    _panel_scroll_metrics,
)


def _static_keys(
    state: TuningViewState,
    font: pygame.font.Font,
    cache: TuningPanelCache,
) -> tuple[tuple, ...]:
    visible = tuple(state.layout.visible_indices(state))
    panel_max_width = 400

    def max_w(index: int) -> int:
        return panel_max_width

    return static_row_keys(
        state,
        font=font,
        cache=cache,
        visible_indices=visible,
        max_content_width_for_index=max_w,
        line_h=font.get_linesize(),
    )


def test_row_render_key_stable_across_fps_and_position() -> None:
    pygame.init()
    overlay = TuningOverlay()
    font = overlay._font_get()
    cache = TuningPanelCache()
    state_a = _minimal_view_state(fps=30.0, position_sec=12.5)
    state_b = _minimal_view_state(fps=60.0, position_sec=99.0)

    track_index = state_a.layout.find_by_kind(RowKind.TRACK_HEADER)
    key_a = row_render_key(
        state_a,
        track_index,
        font,
        cache=cache,
        max_content_width=300,
        line_h=font.get_linesize(),
    )
    key_b = row_render_key(
        state_b,
        track_index,
        font,
        cache=cache,
        max_content_width=300,
        line_h=font.get_linesize(),
    )
    assert key_a == key_b


def test_focus_change_changes_static_row_keys_for_affected_rows() -> None:
    pygame.init()
    overlay = TuningOverlay()
    font = overlay._font_get()
    cache = TuningPanelCache()

    focused_track = _minimal_view_state(
        focus_cursor=MainFocus(
            RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
        ),
    )
    focused_transport = _minimal_view_state(
        focus_cursor=MainFocus(RowDescriptor(RowKind.TRANSPORT)),
    )

    track_key_when_track_focused = next(
        k
        for k in _static_keys(focused_track, font, cache)
        if k[0] == RowKind.TRACK_HEADER
    )
    track_key_when_transport_focused = next(
        k
        for k in _static_keys(focused_transport, font, cache)
        if k[0] == RowKind.TRACK_HEADER
    )

    assert track_key_when_track_focused != track_key_when_transport_focused


def test_repeated_compose_panel_near_zero_font_renders_when_idle() -> None:
    pygame.init()
    overlay = TuningOverlay()
    overlay.notify_input()
    state = _minimal_view_state(fps=30.0, position_sec=1.0)

    overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )

    counters = OverlayDrawCounters()
    overlay.compose_panel(
        _minimal_view_state(fps=31.0, position_sec=2.0),
        viewport_width=1280,
        viewport_height=720,
        counters=counters,
    )
    overlay.compose_panel(
        _minimal_view_state(fps=32.0, position_sec=3.0),
        viewport_width=1280,
        viewport_height=720,
        counters=counters,
    )

    assert counters.font_renders <= 8
    assert counters.surface_builds == 0


def test_row_cache_hits_on_full_recompose_with_warm_cache() -> None:
    pygame.init()
    overlay = TuningOverlay()
    overlay.notify_input()
    state = _minimal_view_state(fps=30.0, position_sec=1.0)

    overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    overlay._panel_cache.panel_signature = None

    counters = OverlayDrawCounters()
    overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
        counters=counters,
    )

    assert counters.row_cache_hits > 0
    assert counters.row_cache_misses > 0


def test_expand_collapse_invalidates_row_cache() -> None:
    pygame.init()
    overlay = TuningOverlay()
    overlay.notify_input()
    font = overlay._font_get()
    cache = overlay._panel_cache

    collapsed = _minimal_view_state(
        tracks={
            "layer_1": TrackBlock(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                expanded=False,
            )
        },
    )
    expanded = _minimal_view_state(
        tracks={
            "layer_1": TrackBlock(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                expanded=True,
            )
        },
    )

    overlay.compose_panel(
        collapsed,
        viewport_width=1280,
        viewport_height=720,
    )
    assert len(cache.row_surfaces) > 0

    overlay.compose_panel(
        expanded,
        viewport_width=1280,
        viewport_height=720,
    )
    assert cache.row_cache_structure == tuple(expanded.layout.visible_indices(expanded))
    assert len(cache.row_surfaces) > 0


def test_ensure_row_surface_cache_hit_miss_counters() -> None:
    pygame.init()
    overlay = TuningOverlay()
    font = overlay._font_get()
    cache = TuningPanelCache()
    state = _minimal_view_state()
    counters = OverlayDrawCounters()
    index = state.layout.find_by_kind(RowKind.TRACK_HEADER)

    ensure_row_surface(
        cache,
        state,
        index,
        font,
        overlay._build_row_at_index,
        max_content_width=300,
        line_h=font.get_linesize(),
        counters=counters,
    )
    assert counters.row_cache_misses == 1
    assert counters.row_cache_hits == 0

    ensure_row_surface(
        cache,
        state,
        index,
        font,
        overlay._build_row_at_index,
        max_content_width=300,
        line_h=font.get_linesize(),
        counters=counters,
    )
    assert counters.row_cache_misses == 1
    assert counters.row_cache_hits == 1


def _two_layer_view_state(
    *,
    focus_slot: str,
) -> TuningViewState:
    return _minimal_view_state(
        layer_z_order=("layer_1", "layer_2"),
        tracks={
            "layer_1": TrackBlock(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                expanded=True,
            ),
            "layer_2": TrackBlock(
                stem="bass",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                expanded=True,
            ),
        },
        focus_cursor=MainFocus(
            RowDescriptor(RowKind.TRACK_HEADER, slot=focus_slot)
        ),
    )


def test_focus_change_exactly_two_row_cache_misses_on_full_recompose() -> None:
    pygame.init()
    overlay = TuningOverlay()
    overlay.notify_input()
    warm_state = _two_layer_view_state(focus_slot="layer_1")

    overlay.compose_panel(
        warm_state,
        viewport_width=1280,
        viewport_height=720,
    )

    baseline = OverlayDrawCounters()
    overlay.compose_panel(
        warm_state,
        viewport_width=1280,
        viewport_height=720,
        counters=baseline,
    )
    assert baseline.row_cache_misses == 1

    counters = OverlayDrawCounters()
    overlay.compose_panel(
        _two_layer_view_state(focus_slot="layer_2"),
        viewport_width=1280,
        viewport_height=720,
        counters=counters,
    )

    assert counters.row_cache_misses == baseline.row_cache_misses + 2
    assert counters.row_cache_hits > 0


def test_scroll_without_content_change_row_misses_bounded_by_viewport() -> None:
    pygame.init()
    overlay = TuningOverlay()
    overlay.notify_input()
    state = _effects_expanded_view_state()
    scroll_focus = state.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER) - 1
    state.focus_descriptor = state.layout.descriptor(scroll_focus)

    overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    metrics = _panel_scroll_metrics(overlay, state)
    assert metrics.needs_scroll
    overlay._scroll_y += metrics.row_stride

    counters = OverlayDrawCounters()
    overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
        counters=counters,
    )

    viewport_row_budget = len(metrics.header_indices) + (
        metrics.scroll_viewport_h // metrics.row_stride
    ) + 2
    assert counters.row_cache_misses <= viewport_row_budget
    assert counters.row_cache_misses < len(metrics.scrollable_indices)


def test_incremental_compose_preserves_transport_row_border_pixels() -> None:
    pygame.init()
    overlay = TuningOverlay()
    overlay.notify_input()
    state = _minimal_view_state(fps=30.0, position_sec=0.0)

    overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    panel = overlay._panel_cache.panel
    assert panel is not None
    panel_w = panel.get_width()
    font = overlay._font_get()
    line_h = font.get_linesize()
    visible_indices = list(state.layout.visible_indices(state))
    first_scrollable_visible = next(
        (
            index
            for index in visible_indices
            if not row_is_pinned(state.layout.kind(index))
        ),
        None,
    )
    metrics = _panel_scroll_metrics(overlay, state)
    transport_index = state.layout.find_by_kind(RowKind.TRANSPORT)
    transport_y = overlay._transport_row_y(
        transport_index,
        metrics=metrics,
        visible_indices=visible_indices,
        first_scrollable_visible=first_scrollable_visible,
    )
    sample_y = transport_y + line_h // 2

    def border_pixels() -> tuple[tuple[int, ...], tuple[int, ...]]:
        left = panel.get_at((0, sample_y))
        right = panel.get_at((panel_w - 1, sample_y))
        return left, right

    left_before, right_before = border_pixels()
    assert left_before[:3] == BORDER_COLOR
    assert right_before[:3] == BORDER_COLOR

    overlay.compose_panel(
        _minimal_view_state(fps=45.0, position_sec=15.0),
        viewport_width=1280,
        viewport_height=720,
    )

    left_after, right_after = border_pixels()
    assert left_after[:3] == BORDER_COLOR
    assert right_after[:3] == BORDER_COLOR


def test_incremental_compose_preserves_static_pixels() -> None:
    pygame.init()
    overlay = TuningOverlay()
    overlay.notify_input()
    state = _minimal_view_state(fps=30.0, position_sec=0.0)

    overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    panel = overlay._panel_cache.panel
    assert panel is not None
    before = pygame.image.tostring(panel, "RGBA")

    overlay.compose_panel(
        _minimal_view_state(fps=45.0, position_sec=15.0),
        viewport_width=1280,
        viewport_height=720,
    )
    after = pygame.image.tostring(panel, "RGBA")
    assert before != after
