"""Tests for live tuning overlay drawing."""

from __future__ import annotations

import pygame
import pytest

from cleave.config_schema import DEFAULT_LAYER_SLOTS, MAX_LAYER_COUNT
from tests.support.config import TEST_LAYER_STEMS
from cleave.extract import STEM_NAMES
from cleave.viz.frame_rate import format_fps_display
from cleave.viz.focus_nav import MainFocus
from cleave.viz.row_semantics import RowDescriptor, RowKind, row_is_pinned
from cleave.viz.tuning_panel_draw import (
    PanelScrollMetrics,
    TuningOverlay,
    _row_bg_color,
    _row_text,
    _row_value_color,
    fit_row_text,
    panel_content_max_width,
    panel_fps_layout,
    panel_help_hint_layout,
    preset_row_prefix_width,
    render_visibility_icon,
    TREE_INDENT,
    scroll_metrics,
)
from cleave.viz.controls import (
    NOTIFICATION_TIMELINE_ENABLED_TEXT,
)
from cleave.viz.tuning_view_state import (
    RenderOverlayBlock,
    RenderTimelineBlock,
    TrackBlock,
    TuningViewState,
)
from cleave.config_schema import DEFAULT_UI_FADE_SEC
from cleave.viz.theme import (
    ACTION,
    BORDER_WIDTH,
    DISABLED,
    HIGHLIGHT,
    HIGHLIGHT_MUTED,
    LABEL,
    LOCKED,
    PANEL_CONTENT_MAX_WIDTH,
    SCROLLBAR_CONTENT_GAP,
    SCROLLBAR_TRACK,
    SCROLLBAR_WIDTH,
    SOLO_BG,
    VALUE,
)
from cleave.viz.timeline_overlay import timeline_viewport_reserve_px


def _effects_expanded_view_state() -> TuningViewState:
    tracks = {
        slot: TrackBlock(
            stem=TEST_LAYER_STEMS[slot],
            preset_dir_label=f"{slot}/dir",
            preset_label=f"{slot}/preset.milk",
            blend_mode="add",
            opacity_pct=50,
            beat_sensitivity=1.0,
            effects={},
            effects_expanded=True,
            expanded=True,
        )
        for slot in DEFAULT_LAYER_SLOTS
    }
    return TuningViewState(
        layer_z_order=DEFAULT_LAYER_SLOTS,
        tracks=tracks,
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.TRANSPORT)),
        move_mode_slot=None,
        notification_message=None,
        notification_remaining_sec=0.0,
        allow_overwrite=False,
    )


def test_draw_effects_expanded_panel_rect_within_surface() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _effects_expanded_view_state()
    assert len(state.layout.visible_indices(state)) > 30

    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)

    panel = overlay.panel_rect
    assert panel is not None
    px, py, pw, ph = panel
    sw, sh = surface.get_size()
    assert px >= 0 and py >= 0
    assert px + pw <= sw and py + ph <= sh
    _, margin_y = overlay._margin
    assert ph <= sh - margin_y * 2
    surface.subsurface(panel)


def _panel_scroll_metrics(
    overlay: TuningOverlay,
    state: TuningViewState,
    *,
    surface_height: int = 720,
    timeline_panel_open: bool = False,
) -> PanelScrollMetrics:
    font = overlay._font_get()
    line_h = font.get_linesize()
    visible_indices = state.layout.visible_indices(state)
    first_scrollable_visible = next(
        (
            index
            for index in visible_indices
            if not row_is_pinned(state.layout.kind(index))
        ),
        None,
    )
    header_gap = line_h + overlay._line_gap
    _, margin_y = overlay._margin
    max_panel_h = surface_height - margin_y * 2
    if timeline_panel_open:
        max_panel_h -= timeline_viewport_reserve_px(len(state.layer_z_order))

    return scroll_metrics(
        visible_indices=visible_indices,
        first_scrollable_visible=first_scrollable_visible,
        line_h=line_h,
        line_gap=overlay._line_gap,
        padding=overlay._padding,
        header_gap=header_gap,
        max_panel_h=max_panel_h,
    )


def test_scrolled_panel_keeps_focus_row_in_viewport() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _effects_expanded_view_state()
    state.focus_descriptor = state.layout.descriptor(
        state.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER) - 1
    )

    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)

    metrics = _panel_scroll_metrics(overlay, state)
    assert metrics.needs_scroll
    row_pos = metrics.scrollable_indices.index(state.focus_index)
    row_y = row_pos * metrics.row_stride
    line_h = overlay._font_get().get_linesize()
    assert overlay._scroll_y <= row_y
    assert row_y + line_h <= overlay._scroll_y + metrics.scroll_viewport_h


def _copy_panel_surface(overlay: TuningOverlay, state: TuningViewState) -> pygame.Surface:
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    panel = overlay.panel_rect
    assert panel is not None
    return surface.subsurface(panel).copy()


def test_header_rows_pinned_when_scrolled() -> None:
    pygame.init()
    state_top = _effects_expanded_view_state()
    scroll_focus = state_top.layout.find_by_kind(RowKind.RENDER_TIMELINE_HEADER) - 1
    state_top.focus_descriptor = state_top.layout.descriptor(scroll_focus)
    state_bottom = _effects_expanded_view_state()
    state_bottom.focus_descriptor = state_bottom.layout.descriptor(scroll_focus)

    panel_top = _copy_panel_surface(TuningOverlay(), state_top)
    panel_bottom = _copy_panel_surface(TuningOverlay(), state_bottom)

    overlay = TuningOverlay()
    metrics = _panel_scroll_metrics(overlay, state_bottom)
    assert metrics.needs_scroll
    transport_y = overlay._padding
    header_h = metrics.header_block_h
    top_strip = panel_top.subsurface((0, transport_y, panel_top.get_width(), header_h))
    bottom_strip = panel_bottom.subsurface(
        (0, transport_y, panel_bottom.get_width(), header_h)
    )
    assert pygame.image.tostring(top_strip, "RGBA") == pygame.image.tostring(
        bottom_strip, "RGBA"
    )


def test_help_hint_layout_avoids_scrollbar_column() -> None:
    pygame.init()
    overlay = TuningOverlay()
    font = overlay._font_get()
    hint_w = font.render("h - help", True, LABEL).get_width()
    panel_w = 320
    panel_h = 200
    without_bar = panel_help_hint_layout(
        panel_w=panel_w,
        panel_h=panel_h,
        padding=overlay._padding,
        line_h=font.get_linesize(),
        hint_width=hint_w,
        show_scrollbar=False,
    )
    with_bar = panel_help_hint_layout(
        panel_w=panel_w,
        panel_h=panel_h,
        padding=overlay._padding,
        line_h=font.get_linesize(),
        hint_width=hint_w,
        show_scrollbar=True,
    )
    assert with_bar.y == without_bar.y
    assert with_bar.x == without_bar.x - SCROLLBAR_WIDTH - SCROLLBAR_CONTENT_GAP


def test_fps_layout_top_right_on_transport_row() -> None:
    pygame.init()
    overlay = TuningOverlay()
    font = overlay._font_get()
    fps_w = font.render(format_fps_display(30.0), True, (255, 255, 255)).get_width()
    panel_w = 320
    without_bar = panel_fps_layout(
        panel_w=panel_w,
        padding=overlay._padding,
        text_width=fps_w,
        show_scrollbar=False,
    )
    with_bar = panel_fps_layout(
        panel_w=panel_w,
        padding=overlay._padding,
        text_width=fps_w,
        show_scrollbar=True,
    )
    assert without_bar.y == overlay._padding
    assert with_bar.y == overlay._padding
    assert with_bar.x == without_bar.x - SCROLLBAR_WIDTH - SCROLLBAR_CONTENT_GAP


def test_draw_fps_counter_when_present() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _minimal_view_state(fps=28.4)

    without_fps = _copy_panel_surface(overlay, _minimal_view_state())
    with_fps = _copy_panel_surface(overlay, state)
    assert pygame.image.tostring(without_fps, "RGBA") != pygame.image.tostring(
        with_fps, "RGBA"
    )

    font = overlay._font_get()
    fps_text = format_fps_display(28.4)
    fps_surf = font.render(fps_text, True, VALUE)
    metrics = _panel_scroll_metrics(overlay, state)
    layout = panel_fps_layout(
        panel_w=with_fps.get_width(),
        padding=overlay._padding,
        text_width=fps_surf.get_width(),
        show_scrollbar=metrics.show_scrollbar,
    )
    sampled = with_fps.get_at((layout.x + 2, layout.y + font.get_linesize() // 2))
    assert sampled[:3] == VALUE


def test_fps_color_ignores_transport_focus() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _minimal_view_state(
        fps=30.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.TRANSPORT)),
    )

    with_fps = _copy_panel_surface(overlay, state)
    font = overlay._font_get()
    fps_surf = font.render(format_fps_display(30.0), True, VALUE)
    metrics = _panel_scroll_metrics(overlay, state)
    layout = panel_fps_layout(
        panel_w=with_fps.get_width(),
        padding=overlay._padding,
        text_width=fps_surf.get_width(),
        show_scrollbar=metrics.show_scrollbar,
    )
    sampled = with_fps.get_at((layout.x + 2, layout.y + font.get_linesize() // 2))
    assert sampled[:3] == VALUE
    assert sampled[:3] != HIGHLIGHT


def test_panel_content_max_width_reserves_scrollbar() -> None:
    scrollable = frozenset({1, 2, 3})
    assert panel_content_max_width(
        index=1, scrollable_indices=scrollable, show_scrollbar=True
    ) == PANEL_CONTENT_MAX_WIDTH - SCROLLBAR_WIDTH
    assert panel_content_max_width(
        index=9, scrollable_indices=scrollable, show_scrollbar=True
    ) == PANEL_CONTENT_MAX_WIDTH
    assert panel_content_max_width(
        index=1, scrollable_indices=scrollable, show_scrollbar=False
    ) == PANEL_CONTENT_MAX_WIDTH


def test_no_scrollbar_when_content_fits() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _minimal_view_state()
    metrics = _panel_scroll_metrics(overlay, state)
    assert not metrics.needs_scroll
    assert not metrics.show_scrollbar

    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    panel = overlay.panel_rect
    assert panel is not None
    panel_surf = surface.subsurface(panel)
    track_x = panel_surf.get_width() - SCROLLBAR_WIDTH - BORDER_WIDTH - 1
    track_y = overlay._padding + 2
    assert panel_surf.get_at((track_x, track_y))[:3] != SCROLLBAR_TRACK


def test_scrollbar_track_is_vertical_channel_only() -> None:
    pygame.init()
    overlay = TuningOverlay()
    panel_w = 120
    scroll_viewport_h = 80
    panel = pygame.Surface(
        (panel_w, scroll_viewport_h + overlay._padding * 2), pygame.SRCALPHA
    )
    overlay._draw_scrollbar(
        panel,
        panel_w=panel_w,
        scroll_top=overlay._padding,
        scroll_viewport_h=scroll_viewport_h,
        scroll_content_h=scroll_viewport_h * 10,
        border_alpha=255,
    )

    track_x = panel_w - SCROLLBAR_WIDTH
    track_y = overlay._padding
    track_bottom = track_y + scroll_viewport_h - 1
    channel_mid_x = track_x + SCROLLBAR_WIDTH // 2
    edge_y = track_y + 20

    assert panel.get_at((track_x, edge_y))[:3] == SCROLLBAR_TRACK
    assert panel.get_at((track_x + SCROLLBAR_WIDTH - 1, edge_y))[:3] == SCROLLBAR_TRACK
    assert panel.get_at((channel_mid_x, track_y))[:3] != SCROLLBAR_TRACK
    assert panel.get_at((channel_mid_x, track_bottom))[:3] != SCROLLBAR_TRACK


def test_preset_rows_fit_within_scrollbar_content_width() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _effects_expanded_view_state()
    long_dir = "presets/very/long/directory/path/for/testing (12/99)"
    long_preset = "presets/very/long/filename/for/testing-preset.milk (34/99)"
    state.tracks["layer_1"].preset_dir_label = long_dir
    state.tracks["layer_1"].preset_label = long_preset

    metrics = _panel_scroll_metrics(overlay, state)
    assert metrics.show_scrollbar
    scrollable = frozenset(metrics.scrollable_indices)
    font = overlay._font_get()

    drums_dir_idx = state.layout.find_by_kind( RowKind.TRACK_PRESET_DIR)
    drums_preset_idx = state.layout.find_by_kind( RowKind.TRACK_PRESET)
    for index, expected_counter in (
        (drums_dir_idx, "(12/99)"),
        (drums_preset_idx, "(34/99)"),
    ):
        max_w = panel_content_max_width(
            index=index,
            scrollable_indices=scrollable,
            show_scrollbar=True,
        )
        label = fit_row_text(font, state, index, max_content_width=max_w)
        assert expected_counter in label
        prefix_w = preset_row_prefix_width(font, font.get_linesize())
        budget = max_w - TREE_INDENT - prefix_w
        assert font.size(label)[0] <= budget


def test_draw_effects_expanded_subsurface_panel_rect() -> None:
    """Regression: overlay subsurfaces panel_rect after draw."""
    pygame.init()
    overlay = TuningOverlay()
    state = _effects_expanded_view_state()
    width, height = 1280, 720
    overlay_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay_surface.fill((0, 0, 0, 0))
    overlay.notify_input()
    overlay.draw(overlay_surface, state)
    panel = overlay.panel_rect
    assert panel is not None
    overlay_surface.subsurface(panel)


def test_solo_visibility_icon_uses_red_background() -> None:
    pygame.init()
    line_h = 17
    soloed = render_visibility_icon(enabled=True, solo=True, line_height=line_h)
    normal = render_visibility_icon(enabled=True, solo=False, line_height=line_h)
    assert soloed.get_height() == line_h
    assert soloed.get_width() == normal.get_width()
    assert soloed.get_at((1, line_h // 2))[:3] == SOLO_BG
    assert normal.get_at((normal.get_width() // 2, line_h // 2))[:3] != SOLO_BG


def test_solo_visibility_icon_disabled_stem_uses_value_not_disabled() -> None:
    pygame.init()
    line_h = 17
    disabled = render_visibility_icon(enabled=False, solo=False, line_height=line_h)
    soloed_off = render_visibility_icon(enabled=False, solo=True, line_height=line_h)
    assert soloed_off.get_at((1, line_h // 2))[:3] == SOLO_BG
    assert pygame.mask.from_surface(soloed_off).count() != pygame.mask.from_surface(
        disabled
    ).count()


def _minimal_view_state(**kwargs: object) -> TuningViewState:
    defaults: dict[str, object] = {
        "layer_z_order": ("layer_1",),
        "tracks": {
            "layer_1": TrackBlock(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
            )
        },
        "paused": False,
        "position_sec": 0.0,
        "focus_cursor": MainFocus(RowDescriptor(RowKind.TRANSPORT)),
        "move_mode_slot": None,
        "notification_message": None,
        "notification_remaining_sec": 0.0,
    }
    defaults.update(kwargs)
    return TuningViewState(**defaults)  # type: ignore[arg-type]


def test_track_header_uses_stem_display_not_slot_key() -> None:
    state = _minimal_view_state(
        tracks={
            "layer_1": TrackBlock(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
            )
        },
    )
    header_row = state.layout.find_by_kind( RowKind.TRACK_HEADER)
    text = _row_text(state, header_row)
    assert "DRUMS" in text
    assert "LAYER_1" not in text.upper()


def test_track_header_full_mix_shows_mix() -> None:
    state = _minimal_view_state(
        tracks={
            "layer_1": TrackBlock(
                stem="full_mix",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
            )
        },
    )
    header_row = state.layout.find_by_kind( RowKind.TRACK_HEADER)
    text = _row_text(state, header_row)
    assert "MIX" in text
    assert "FULL_MIX" not in text.upper()


def test_track_stem_row_text() -> None:
    state = _minimal_view_state(
        tracks={
            "layer_1": TrackBlock(
                stem="full_mix",
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
    stem_row = state.layout.find( "layer_1", RowKind.TRACK_STEM)
    assert _row_text(state, stem_row) == "└─ driving stem: full-mix"


def test_locked_stem_row_not_navigable_and_uses_locked_color() -> None:
    state = _minimal_view_state(
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
                locked=True,
            )
        },
    )
    stem_row = state.layout.find( "layer_1", RowKind.TRACK_STEM)
    assert stem_row not in state.layout.navigable_indices(state)
    assert _row_value_color(state, stem_row) == LOCKED


def test_panel_notification_pinned_under_transport() -> None:
    inactive = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=True),
        notification_message=None,
        notification_remaining_sec=0.0,
    )
    active = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=True),
        notification_message=NOTIFICATION_TIMELINE_ENABLED_TEXT,
        notification_remaining_sec=5.0,
    )
    inactive_kinds = [row.kind for row in inactive.layout.rows]
    active_kinds = [row.kind for row in active.layout.rows]
    assert RowKind.PANEL_NOTIFICATION not in inactive_kinds
    assert RowKind.PANEL_NOTIFICATION in active_kinds
    notification_idx = active.layout.find_by_kind(RowKind.PANEL_NOTIFICATION)
    transport_idx = active.layout.find_by_kind(RowKind.TRANSPORT)
    header_idx = active.layout.find("layer_1", RowKind.TRACK_HEADER)
    assert transport_idx < notification_idx < header_idx
    assert row_is_pinned(RowKind.PANEL_NOTIFICATION)
    assert notification_idx not in active.layout.navigable_indices(active)
    assert _row_value_color(active, notification_idx) == HIGHLIGHT
    assert _row_text(active, notification_idx) == NOTIFICATION_TIMELINE_ENABLED_TEXT


def test_draw_panel_notification_without_error() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=True),
        notification_message=NOTIFICATION_TIMELINE_ENABLED_TEXT,
        notification_remaining_sec=5.0,
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    assert overlay.panel_rect is not None
    notification_idx = state.layout.find_by_kind(RowKind.PANEL_NOTIFICATION)
    assert notification_idx in state.layout.visible_indices(state)


def test_build_row_layout_includes_add_before_render_gap() -> None:
    state = _minimal_view_state()
    add_idx = state.layout.find_by_kind( RowKind.LAYER_MANAGEMENT_ADD)
    gap_idx = state.layout.find_by_kind( RowKind.RENDER_SECTION_GAP)
    overlay_idx = state.layout.find_by_kind( RowKind.RENDER_OVERLAY_HEADER)
    assert add_idx < gap_idx < overlay_idx


def test_build_row_layout_omits_add_at_max_layers() -> None:
    slots = tuple(f"layer_{i}" for i in range(1, MAX_LAYER_COUNT + 1))
    tracks = {
        slot: TrackBlock(
            stem="drums",
            preset_dir_label="dir",
            preset_label="preset.milk",
            blend_mode="black-key",
            opacity_pct=50,
            beat_sensitivity=1.0,
            effects={},
        )
        for slot in slots
    }
    state = _minimal_view_state(layer_z_order=slots, tracks=tracks)
    with pytest.raises(ValueError, match="no row for kind"):
        state.layout.find_by_kind(RowKind.LAYER_MANAGEMENT_ADD)


def test_delete_row_after_effects_when_expanded() -> None:
    state = _minimal_view_state(
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
                effects_expanded=True,
            )
        },
    )
    layout = state.layout.rows
    delete_idx = state.layout.find( "layer_1", RowKind.LAYER_MANAGEMENT_DELETE)
    effects_header = state.layout.find( "layer_1", RowKind.TRACK_EFFECTS_HEADER)
    effect_rows = [
        index
        for index, row in enumerate(layout)
        if row.kind == RowKind.TRACK_EFFECT and row.slot == "layer_1"
    ]
    assert effect_rows
    assert delete_idx > effects_header
    assert delete_idx > max(effect_rows)


def test_delete_row_omitted_when_track_collapsed() -> None:
    state = _minimal_view_state(
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
    kinds = [row.kind for row in state.layout.rows]
    assert RowKind.LAYER_MANAGEMENT_DELETE not in kinds


def test_delete_row_navigable_when_locked() -> None:
    state = _minimal_view_state(
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
                locked=True,
            )
        },
    )
    delete_row = state.layout.find( "layer_1", RowKind.LAYER_MANAGEMENT_DELETE)
    assert delete_row in state.layout.navigable_indices(state)


def test_add_row_always_navigable() -> None:
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
    for state in (collapsed, expanded):
        add_row = state.layout.find_by_kind( RowKind.LAYER_MANAGEMENT_ADD)
        assert add_row in state.layout.navigable_indices(state)


def test_delete_row_disabled_color_single_layer() -> None:
    state = _minimal_view_state(
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
    delete_row = state.layout.find( "layer_1", RowKind.LAYER_MANAGEMENT_DELETE)
    assert _row_value_color(state, delete_row) == DISABLED


def test_delete_layer_row_text_has_tree_prefix() -> None:
    state = _minimal_view_state(
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
    delete_row = state.layout.find( "layer_1", RowKind.LAYER_MANAGEMENT_DELETE)
    assert _row_text(state, delete_row) == "└─ Delete Layer"


def test_action_row_value_color() -> None:
    state = _minimal_view_state(
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
        layer_z_order=["layer_1", "layer_2"],
    )
    config_row = state.layout.find_by_kind( RowKind.CONFIG_HEADER)
    add_row = state.layout.find_by_kind( RowKind.LAYER_MANAGEMENT_ADD)
    delete_row = state.layout.find( "layer_1", RowKind.LAYER_MANAGEMENT_DELETE)
    assert _row_value_color(state, config_row) == ACTION
    assert _row_value_color(state, add_row) == ACTION
    assert _row_value_color(state, delete_row) == ACTION


def test_draw_layer_management_rows_without_error() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _minimal_view_state(
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
                effects_expanded=True,
            )
        },
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    assert overlay.panel_rect is not None
    add_row = state.layout.find_by_kind( RowKind.LAYER_MANAGEMENT_ADD)
    delete_row = state.layout.find( "layer_1", RowKind.LAYER_MANAGEMENT_DELETE)
    assert add_row in state.layout.visible_indices(state)
    assert delete_row in state.layout.visible_indices(state)


def test_render_overlay_row_layout_includes_header_and_sub_rows_when_expanded() -> None:
    state = _minimal_view_state(
        render_overlay=RenderOverlayBlock(expanded=True),
    )
    kinds = [row.kind for row in state.layout.rows]
    assert RowKind.RENDER_OVERLAY_HEADER in kinds
    assert RowKind.RENDER_OVERLAY_POSITION in kinds
    assert RowKind.RENDER_OVERLAY_TITLE_HEADER in kinds
    assert RowKind.RENDER_OVERLAY_BODY_HEADER in kinds
    assert RowKind.RENDER_OVERLAY_OPACITY in kinds
    assert RowKind.RENDER_OVERLAY_BORDER_WIDTH in kinds
    assert RowKind.RENDER_OVERLAY_START_DELAY in kinds
    assert RowKind.RENDER_OVERLAY_DISPLAY_TIME in kinds
    assert RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE not in kinds
    assert RowKind.RENDER_OVERLAY_BODY_FONT_SIZE not in kinds
    header_idx = state.layout.find_by_kind( RowKind.RENDER_OVERLAY_HEADER)
    config_idx = state.layout.find_by_kind( RowKind.CONFIG_HEADER)
    assert config_idx < header_idx


def test_render_overlay_title_and_body_font_rows_when_expanded() -> None:
    state = _minimal_view_state(
        render_overlay=RenderOverlayBlock(
            expanded=True,
            title_expanded=True,
            body_expanded=True,
        ),
    )
    kinds = [row.kind for row in state.layout.rows]
    assert RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE in kinds
    assert RowKind.RENDER_OVERLAY_TITLE_FONT in kinds
    assert RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM in kinds
    assert RowKind.RENDER_OVERLAY_BODY_FONT_SIZE in kinds
    assert RowKind.RENDER_OVERLAY_BODY_FONT in kinds


def test_render_overlay_collapsed_hides_sub_rows() -> None:
    collapsed = _minimal_view_state(
        render_overlay=RenderOverlayBlock(expanded=False),
    )
    expanded = _minimal_view_state(
        render_overlay=RenderOverlayBlock(expanded=True),
    )
    collapsed_kinds = {row.kind for row in collapsed.layout.rows}
    expanded_kinds = {row.kind for row in expanded.layout.rows}
    assert RowKind.RENDER_OVERLAY_HEADER in collapsed_kinds
    assert RowKind.RENDER_OVERLAY_POSITION not in collapsed_kinds
    assert RowKind.RENDER_OVERLAY_TITLE_HEADER not in collapsed_kinds
    assert len(collapsed.layout.visible_indices(collapsed)) + 7 == len(expanded.layout.visible_indices(expanded))


def test_draw_render_overlay_header_without_error() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _minimal_view_state(
        render_overlay=RenderOverlayBlock(
            enabled=True,
            expanded=False,
            solo=True,
        ),
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    assert overlay.panel_rect is not None
    header_row = state.layout.find_by_kind( RowKind.RENDER_OVERLAY_HEADER)
    assert header_row in state.layout.visible_indices(state)


def test_draw_track_header_with_solo_eye() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = TuningViewState(
        layer_z_order=("layer_1",),
        tracks={
            "layer_1": TrackBlock(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                enabled=True,
                expanded=False,
            )
        },
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.TRANSPORT)),
        move_mode_slot=None,
        notification_message=None,
        notification_remaining_sec=0.0,
        solo_slot="layer_1",
        solo_active=True,
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    assert overlay.panel_rect is not None

    header_row = next(
        i
        for i in state.layout.visible_indices(state)
        if state.layout.kind( i) == RowKind.TRACK_HEADER and state.layout.slot( i) == "layer_1"
    )
    assert state.solo_slot == "layer_1"
    assert header_row == state.layout.find_by_kind( RowKind.TRACK_HEADER)


def test_disabled_track_focus_uses_muted_highlight() -> None:
    state = _minimal_view_state(
        tracks={
            "layer_1": TrackBlock(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                visible=False,
            )
        },
    )
    header_row = state.layout.find_by_kind( RowKind.TRACK_HEADER)
    state.focus_descriptor = state.layout.descriptor(header_row)
    assert _row_value_color(state, header_row) == HIGHLIGHT_MUTED
    assert _row_bg_color(state, header_row) == HIGHLIGHT_MUTED
    assert _row_value_color(state, header_row) != HIGHLIGHT
    assert _row_value_color(state, header_row) != DISABLED


def test_main_tree_rows_not_highlighted_when_timeline_submenu_focused() -> None:
    state = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=True, expanded=True),
    )
    for row_kind_target in (RowKind.TRANSPORT, RowKind.TRACK_HEADER):
        row = state.layout.find_by_kind(row_kind_target)
        state.focus_descriptor = state.layout.descriptor(row)
        state.timeline_submenu_focused = False
        assert _row_value_color(state, row) == HIGHLIGHT
        assert _row_bg_color(state, row) == HIGHLIGHT

        state.timeline_submenu_focused = True
        assert _row_value_color(state, row) != HIGHLIGHT
        assert _row_bg_color(state, row) is None

    timeline_row = state.layout.find_by_kind( RowKind.RENDER_TIMELINE_HEADER)
    state.focus_descriptor = state.layout.descriptor(timeline_row)
    state.timeline_submenu_focused = False
    assert _row_value_color(state, timeline_row) == HIGHLIGHT
    assert _row_bg_color(state, timeline_row) == HIGHLIGHT

    state.timeline_submenu_focused = True
    assert _row_value_color(state, timeline_row) == VALUE
    assert _row_bg_color(state, timeline_row) is None


def test_draw_render_timeline_header_without_error() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _minimal_view_state(
        render_timeline=RenderTimelineBlock(
            enabled=True,
            expanded=False,
        ),
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    assert overlay.panel_rect is not None
    header_row = state.layout.find_by_kind( RowKind.RENDER_TIMELINE_HEADER)
    assert header_row in state.layout.visible_indices(state)


def test_overlay_starts_hidden() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _effects_expanded_view_state()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.draw(surface, state)
    assert overlay.panel_rect is None


def test_hide_immediately_hides_overlay() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _effects_expanded_view_state()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    assert overlay.panel_rect is not None
    overlay.hide_immediately()
    assert overlay.is_visible() is False
    overlay.draw(surface, state)
    assert overlay.panel_rect is None


def test_is_visible_tracks_visibility() -> None:
    overlay = TuningOverlay()
    assert overlay.is_visible() is False
    overlay.notify_input()
    assert overlay.is_visible() is True
    overlay.hide_immediately()
    assert overlay.is_visible() is False


def test_overlay_normal_hold_idle_without_timeline_panel() -> None:
    overlay = TuningOverlay()
    overlay.notify_input()
    overlay.update(DEFAULT_UI_FADE_SEC - 0.1)
    assert overlay._visibility == 1.0
    overlay.update(0.2)
    assert overlay._visibility < 1.0


def test_overlay_ui_fade_disabled_stays_visible_until_hide() -> None:
    overlay = TuningOverlay(hold_idle_sec=0.0)
    overlay.notify_input()
    for _ in range(200):
        overlay.update(1.0)
    assert overlay.is_visible() is True
    overlay.hide_immediately()
    assert overlay.is_visible() is False


def test_max_panel_h_unchanged_when_timeline_closed() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _effects_expanded_view_state()
    surface_height = 720
    closed = _panel_scroll_metrics(
        overlay, state, surface_height=surface_height, timeline_panel_open=False
    )
    _, margin_y = overlay._margin
    assert closed.max_panel_h == surface_height - margin_y * 2


def test_panel_reserves_timeline_viewport_when_open() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _effects_expanded_view_state()
    surface_height = 720
    surface = pygame.Surface((1280, surface_height), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state, timeline_panel_open=True)

    panel = overlay.panel_rect
    assert panel is not None
    _, py, _, ph = panel
    _, margin_y = overlay._margin
    reserve = timeline_viewport_reserve_px(len(state.layer_z_order))
    assert py + ph + reserve <= surface_height - margin_y

    open_metrics = _panel_scroll_metrics(
        overlay, state, surface_height=surface_height, timeline_panel_open=True
    )
    closed_metrics = _panel_scroll_metrics(
        overlay, state, surface_height=surface_height, timeline_panel_open=False
    )
    assert open_metrics.max_panel_h < closed_metrics.max_panel_h
    assert open_metrics.max_panel_h == closed_metrics.max_panel_h - reserve


def test_panel_notification_in_pinned_header_block() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _minimal_view_state(
        notification_message="Saved",
        notification_remaining_sec=2.0,
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    panel = overlay.panel_rect
    assert panel is not None

    metrics = _panel_scroll_metrics(overlay, state)
    notification_idx = state.layout.find_by_kind(RowKind.PANEL_NOTIFICATION)
    assert notification_idx in metrics.header_indices
    assert metrics.header_indices.index(notification_idx) > metrics.header_indices.index(
        state.layout.find_by_kind(RowKind.TRANSPORT)
    )