"""Tests for live tuning panel row and panel cache."""

from __future__ import annotations

from dataclasses import replace

import pygame

from cleave.viz.overlay_profiler import OverlayDrawCounters
from cleave.viz.row_semantics import RowDescriptor, RowKind, row_is_pinned
from cleave.viz.theme import (
    BORDER_COLOR,
    BORDER_WIDTH,
    SCROLLBAR_CONTENT_GAP,
    SCROLLBAR_WIDTH,
    SOLO_BG,
)
from cleave.viz.focus_nav import MainFocus
from cleave.viz.tuning_panel_cache import (
    TuningPanelCache,
    ensure_row_surface,
    live_upload_signature,
    panel_signature,
    row_render_key,
    static_row_keys,
    static_upload_content_hash,
    tuning_upload_signature,
)
from cleave.viz.tuning_panel_draw import TuningOverlay, tuning_panel_max_dimensions
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


def test_solo_change_invalidates_track_header_row_key() -> None:
    pygame.init()
    overlay = TuningOverlay()
    font = overlay._font_get()
    cache = TuningPanelCache()
    state = _two_layer_view_state(focus_slot="layer_1")
    index = next(
        i
        for i in state.layout.visible_indices(state)
        if state.layout.kind(i) == RowKind.TRACK_HEADER
        and state.layout.slot(i) == "layer_1"
    )
    line_h = font.get_linesize()
    max_w = 400

    key_before = row_render_key(
        state,
        index,
        font,
        cache=cache,
        max_content_width=max_w,
        line_h=line_h,
    )
    state_solo = replace(
        state,
        solo_slot="layer_1",
        solo_active=True,
        tracks={
            "layer_1": replace(state.tracks["layer_1"], visible=True),
            "layer_2": replace(state.tracks["layer_2"], visible=False),
        },
    )
    key_after = row_render_key(
        state_solo,
        index,
        font,
        cache=cache,
        max_content_width=max_w,
        line_h=line_h,
    )
    assert key_before != key_after
    assert key_before.visibility_icon == (True, False)
    assert key_after.visibility_icon == (True, True)


def test_solo_change_misses_warm_row_cache_for_track_header() -> None:
    pygame.init()
    overlay = TuningOverlay()
    font = overlay._font_get()
    cache = TuningPanelCache()
    state = _two_layer_view_state(focus_slot="layer_1")
    index = next(
        i
        for i in state.layout.visible_indices(state)
        if state.layout.kind(i) == RowKind.TRACK_HEADER
        and state.layout.slot(i) == "layer_1"
    )
    line_h = font.get_linesize()
    max_w = 400

    ensure_row_surface(
        cache,
        state,
        index,
        font,
        overlay._build_row_at_index,
        max_content_width=max_w,
        line_h=line_h,
    )
    state_solo = replace(
        state,
        solo_slot="layer_1",
        solo_active=True,
        tracks={
            "layer_1": replace(state.tracks["layer_1"], visible=True),
            "layer_2": replace(state.tracks["layer_2"], visible=False),
        },
    )
    counters = OverlayDrawCounters()
    entry = ensure_row_surface(
        cache,
        state_solo,
        index,
        font,
        overlay._build_row_at_index,
        max_content_width=max_w,
        line_h=line_h,
        counters=counters,
    )
    assert counters.row_cache_misses == 1
    assert counters.row_cache_hits == 0
    assert entry.primary.get_at((1, line_h // 2))[:3] == SOLO_BG


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


def test_live_upload_signature_transport_and_fps() -> None:
    state_with_fps = _minimal_view_state(fps=30.0, position_sec=65.0)
    state_no_fps = _minimal_view_state(fps=None, position_sec=12.0)

    assert live_upload_signature(state_with_fps) == ("01:05", "FPS: 30.0")
    assert live_upload_signature(state_no_fps) == ("00:12", None)


def test_tuning_upload_signature_combines_static_and_live() -> None:
    state = _minimal_view_state(fps=30.0, position_sec=1.0)
    pygame.init()
    overlay = TuningOverlay()
    font = overlay._font_get()
    cache = TuningPanelCache()
    static_keys = _static_keys(state, font, cache)
    sig = panel_signature(
        state,
        visibility=1.0,
        panel_w=400,
        panel_h=300,
        scroll_y=0,
        static_row_keys=static_keys,
    )
    live_sig = live_upload_signature(state)
    screen_rect = (10, 10, 400, 300)

    upload_sig = tuning_upload_signature(sig, screen_rect, live_sig)

    assert upload_sig.active_size == (400, 300)
    assert upload_sig.screen_rect == screen_rect
    assert upload_sig.content_hash == (static_upload_content_hash(sig), live_sig)


def test_incremental_compose_sets_transport_rect_and_partial_plan() -> None:
    pygame.init()
    overlay = TuningOverlay()
    overlay.notify_input()
    base = _minimal_view_state(fps=30.0, position_sec=0.0)

    overlay.compose_panel(
        base,
        viewport_width=1280,
        viewport_height=720,
    )
    cache = overlay._panel_cache
    assert cache.last_transport_rect is not None
    tx, ty, tw, th = cache.last_transport_rect
    assert tx == BORDER_WIDTH
    assert th == overlay._font_get().get_linesize()

    moved = _minimal_view_state(fps=45.0, position_sec=15.0)
    composed = overlay.compose_panel(
        moved,
        viewport_width=1280,
        viewport_height=720,
    )
    assert composed is not None
    assert composed.upload_plan.mode == "partial"
    assert cache.last_transport_rect in composed.upload_plan.dirty_rects


def test_incremental_compose_skip_plan_when_live_unchanged() -> None:
    pygame.init()
    overlay = TuningOverlay()
    overlay.notify_input()
    state = _minimal_view_state(fps=30.0, position_sec=5.0)

    first = overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    assert first is not None
    assert first.upload_plan.mode == "full"

    cache = overlay._panel_cache
    cache.gpu.last_signature = first.upload_signature
    cache.gpu.last_texture_id = 1
    cache.gpu.capacity = first.capacity

    second = overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    assert second is not None
    assert second.upload_plan.mode == "skip"


def test_tuning_panel_max_dimensions_reserves_timeline_strip() -> None:
    pygame.init()
    overlay = TuningOverlay()
    _, margin_y = overlay._margin
    open_h = tuning_panel_max_dimensions(
        1280,
        720,
        80,
        timeline_panel_open=True,
        margin_y=margin_y,
        padding=overlay._padding,
        timeline_row_count=4,
    )[1]
    closed_h = tuning_panel_max_dimensions(
        1280,
        720,
        80,
        timeline_panel_open=False,
        margin_y=margin_y,
        padding=overlay._padding,
    )[1]
    assert open_h < closed_h


def _focus_row_bg_sample_pos(
    overlay: TuningOverlay,
    state: TuningViewState,
    panel_w: int,
) -> tuple[int, int]:
    font = overlay._font_get()
    line_h = font.get_linesize()
    focus_index = state.focus_index
    visible_indices = list(state.layout.visible_indices(state))
    metrics = _panel_scroll_metrics(overlay, state)
    if metrics.needs_scroll:
        if focus_index in metrics.header_indices:
            row_index = metrics.header_indices.index(focus_index)
            y = overlay._padding + row_index * metrics.row_stride
        else:
            row_index = metrics.scrollable_indices.index(focus_index)
            scroll_top = overlay._padding + metrics.header_block_h
            y = scroll_top + row_index * metrics.row_stride - overlay._scroll_y
    else:
        y = overlay._padding
        for index in visible_indices:
            if index == focus_index:
                break
            y += metrics.row_stride
    sample_x = overlay._padding + 12
    if metrics.show_scrollbar:
        content_right = (
            panel_w - overlay._padding - SCROLLBAR_WIDTH - SCROLLBAR_CONTENT_GAP
        )
        if sample_x >= content_right:
            sample_x = max(overlay._padding, content_right - 12)
    sample_y = y + line_h // 2
    return sample_x, sample_y


def _focused_row_bg_pixel(
    overlay: TuningOverlay,
    state: TuningViewState,
) -> tuple[int, int, int, int]:
    """Sample a background-only pixel on the focused row (avoids glyph text)."""
    overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    panel = overlay._panel_cache.panel
    assert panel is not None
    sample_x, sample_y = _focus_row_bg_sample_pos(
        overlay, state, panel.get_width()
    )
    return panel.get_at((sample_x, sample_y))


def _focused_row_pixel(
    overlay: TuningOverlay,
    state: TuningViewState,
) -> tuple[int, int, int, int]:
    return _focused_row_bg_pixel(overlay, state)


def test_focused_row_has_opaque_panel_background() -> None:
    pygame.init()
    overlay = TuningOverlay()
    overlay.notify_input()
    state = _two_layer_view_state(focus_slot="layer_1")
    _r, _g, _b, a = _focused_row_bg_pixel(overlay, state)
    assert a >= 250


def test_focused_row_opaque_after_incremental_compose() -> None:
    pygame.init()
    overlay = TuningOverlay()
    overlay.notify_input()
    state = _two_layer_view_state(focus_slot="layer_1")
    overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
    )
    panel = overlay._panel_cache.panel
    assert panel is not None

    moved = _minimal_view_state(
        layer_z_order=state.layer_z_order,
        tracks=state.tracks,
        focus_cursor=state.focus_cursor,
        fps=45.0,
        position_sec=12.0,
    )
    overlay.compose_panel(
        moved,
        viewport_width=1280,
        viewport_height=720,
    )

    sample_x, sample_y = _focus_row_bg_sample_pos(
        overlay, state, panel.get_width()
    )
    _r, _g, _b, a = panel.get_at((sample_x, sample_y))
    assert a >= 250


def test_timeline_open_full_upload_not_skip() -> None:
    pygame.init()
    overlay = TuningOverlay()
    overlay.notify_input()
    from cleave.viz.tuning_view_state import RenderTimelineBlock

    state = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=True, expanded=True),
    )
    kwargs = dict(viewport_width=1280, viewport_height=720)

    closed = overlay.compose_panel(state, timeline_panel_open=False, **kwargs)
    assert closed is not None
    assert closed.upload_plan.mode == "full"

    cache = overlay._panel_cache
    cache.gpu.last_signature = closed.upload_signature
    cache.gpu.last_texture_id = 1
    cache.gpu.capacity = closed.capacity

    opened = overlay.compose_panel(state, timeline_panel_open=True, **kwargs)
    assert opened is not None
    assert opened.upload_plan.mode == "full"
    assert opened.upload_signature.active_size[1] <= closed.upload_signature.active_size[1]
