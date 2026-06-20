"""Tests for live tuning overlay drawing."""

from __future__ import annotations

import pygame

from cleave.config_schema import DEFAULT_STEM_FOR_SLOT, LAYER_SLOTS
from cleave.extract import STEM_NAMES
from cleave.viz.material_icons import row_icon_prefix_width
from cleave.viz.row_semantics import RowKind
from cleave.viz.overlay import (
    PanelScrollMetrics,
    RenderOverlayBlock,
    RenderTimelineBlock,
    TrackBlock,
    TuningOverlay,
    TuningViewState,
    _row_bg_color,
    _row_text,
    _row_value_color,
    build_row_layout,
    find_row,
    find_row_by_kind,
    fit_row_text,
    navigable_row_indices,
    panel_content_max_width,
    panel_help_hint_layout,
    panel_toast_layout,
    render_visibility_icon,
    row_kind,
    TREE_INDENT,
    row_slot,
    scroll_metrics,
    visible_row_indices,
)
from cleave.viz.theme import (
    BORDER_WIDTH,
    DISABLED,
    HIGHLIGHT,
    HIGHLIGHT_MUTED,
    HOLD_IDLE_SEC,
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
            stem=DEFAULT_STEM_FOR_SLOT[slot],
            preset_dir_label=f"{slot}/dir",
            preset_label=f"{slot}/preset.milk",
            blend_mode="add",
            opacity_pct=50,
            beat_sensitivity=1.0,
            effects={},
            effects_expanded=True,
            expanded=True,
        )
        for slot in LAYER_SLOTS
    }
    return TuningViewState(
        layer_z_order=LAYER_SLOTS,
        tracks=tracks,
        paused=False,
        position_sec=0.0,
        focus_index=0,
        move_mode_slot=None,
        toast_message=None,
        toast_remaining_sec=0.0,
        allow_overwrite=False,
    )


def test_draw_effects_expanded_panel_rect_within_surface() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _effects_expanded_view_state()
    assert len(visible_row_indices(state)) > 30

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
    visible_indices = visible_row_indices(state)
    first_scrollable_visible = next(
        (
            index
            for index in visible_indices
            if row_kind(state, index) not in {
                RowKind.CONFIG_HEADER,
                RowKind.TRANSPORT,
            }
        ),
        None,
    )
    header_gap = line_h + overlay._line_gap
    _, margin_y = overlay._margin
    max_panel_h = surface_height - margin_y * 2
    if timeline_panel_open:
        max_panel_h -= timeline_viewport_reserve_px(surface_height)

    toast_active = bool(state.toast_message and state.toast_remaining_sec > 0)

    return scroll_metrics(
        visible_indices=visible_indices,
        first_scrollable_visible=first_scrollable_visible,
        line_h=line_h,
        line_gap=overlay._line_gap,
        padding=overlay._padding,
        header_gap=header_gap,
        toast_active=toast_active,
        max_panel_h=max_panel_h,
    )


def test_scrolled_panel_keeps_focus_row_in_viewport() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _effects_expanded_view_state()
    state.focus_index = find_row_by_kind(state, RowKind.RENDER_TIMELINE_HEADER) - 1

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
    scroll_focus = find_row_by_kind(state_top, RowKind.RENDER_TIMELINE_HEADER) - 1
    state_top.focus_index = scroll_focus
    state_bottom = _effects_expanded_view_state()
    state_bottom.focus_index = scroll_focus

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

    drums_dir_idx = find_row_by_kind(state, RowKind.TRACK_PRESET_DIR)
    drums_preset_idx = find_row_by_kind(state, RowKind.TRACK_PRESET)
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
        icon_w = row_icon_prefix_width(font.get_linesize())
        budget = max_w - TREE_INDENT - icon_w
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
        "focus_index": 0,
        "move_mode_slot": None,
        "toast_message": None,
        "toast_remaining_sec": 0.0,
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
    header_row = find_row_by_kind(state, RowKind.TRACK_HEADER)
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
    header_row = find_row_by_kind(state, RowKind.TRACK_HEADER)
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
    stem_row = find_row(state, "layer_1", RowKind.TRACK_STEM)
    assert _row_text(state, stem_row) == "└─ stem: full-mix"


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
    stem_row = find_row(state, "layer_1", RowKind.TRACK_STEM)
    assert stem_row not in navigable_row_indices(state)
    assert _row_value_color(state, stem_row) == LOCKED


def test_timeline_layer_hint_when_timeline_enabled() -> None:
    disabled = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=False),
    )
    enabled = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=True),
    )
    disabled_kinds = [row.kind for row in build_row_layout(disabled)]
    enabled_kinds = [row.kind for row in build_row_layout(enabled)]
    assert RowKind.TIMELINE_LAYER_HINT not in disabled_kinds
    assert RowKind.TIMELINE_LAYER_HINT in enabled_kinds
    hint_idx = find_row_by_kind(enabled, RowKind.TIMELINE_LAYER_HINT)
    gap_idx = find_row_by_kind(enabled, RowKind.RENDER_SECTION_GAP)
    overlay_idx = find_row_by_kind(enabled, RowKind.RENDER_OVERLAY_HEADER)
    assert hint_idx < gap_idx < overlay_idx
    assert hint_idx not in navigable_row_indices(enabled)
    assert _row_value_color(enabled, hint_idx) == DISABLED


def test_draw_timeline_layer_hint_without_error() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=True),
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    assert overlay.panel_rect is not None
    hint_idx = find_row_by_kind(state, RowKind.TIMELINE_LAYER_HINT)
    assert hint_idx in visible_row_indices(state)


def test_render_overlay_row_layout_includes_header_and_sub_rows_when_expanded() -> None:
    state = _minimal_view_state(
        render_overlay=RenderOverlayBlock(expanded=True),
    )
    kinds = [row.kind for row in build_row_layout(state)]
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
    header_idx = find_row_by_kind(state, RowKind.RENDER_OVERLAY_HEADER)
    config_idx = find_row_by_kind(state, RowKind.CONFIG_HEADER)
    assert config_idx < header_idx


def test_render_overlay_title_and_body_font_rows_when_expanded() -> None:
    state = _minimal_view_state(
        render_overlay=RenderOverlayBlock(
            expanded=True,
            title_expanded=True,
            body_expanded=True,
        ),
    )
    kinds = [row.kind for row in build_row_layout(state)]
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
    collapsed_kinds = {row.kind for row in build_row_layout(collapsed)}
    expanded_kinds = {row.kind for row in build_row_layout(expanded)}
    assert RowKind.RENDER_OVERLAY_HEADER in collapsed_kinds
    assert RowKind.RENDER_OVERLAY_POSITION not in collapsed_kinds
    assert RowKind.RENDER_OVERLAY_TITLE_HEADER not in collapsed_kinds
    assert len(visible_row_indices(collapsed)) + 7 == len(visible_row_indices(expanded))


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
    header_row = find_row_by_kind(state, RowKind.RENDER_OVERLAY_HEADER)
    assert header_row in visible_row_indices(state)


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
        focus_index=0,
        move_mode_slot=None,
        toast_message=None,
        toast_remaining_sec=0.0,
        solo_slot="layer_1",
        solo_active=True,
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    assert overlay.panel_rect is not None

    header_row = next(
        i
        for i in visible_row_indices(state)
        if row_kind(state, i) == RowKind.TRACK_HEADER and row_slot(state, i) == "layer_1"
    )
    assert state.solo_slot == "layer_1"
    assert header_row == find_row_by_kind(state, RowKind.TRACK_HEADER)


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
    header_row = find_row_by_kind(state, RowKind.TRACK_HEADER)
    state.focus_index = header_row
    assert _row_value_color(state, header_row) == HIGHLIGHT_MUTED
    assert _row_bg_color(state, header_row) == HIGHLIGHT_MUTED
    assert _row_value_color(state, header_row) != HIGHLIGHT
    assert _row_value_color(state, header_row) != DISABLED


def test_main_tree_rows_not_highlighted_when_timeline_submenu_focused() -> None:
    state = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=True, expanded=True),
    )
    for row_kind_target in (RowKind.TRANSPORT, RowKind.TRACK_HEADER):
        row = find_row_by_kind(state, row_kind_target)
        state.focus_index = row
        state.timeline_submenu_focused = False
        assert _row_value_color(state, row) == HIGHLIGHT
        assert _row_bg_color(state, row) == HIGHLIGHT

        state.timeline_submenu_focused = True
        assert _row_value_color(state, row) != HIGHLIGHT
        assert _row_bg_color(state, row) is None

    timeline_row = find_row_by_kind(state, RowKind.RENDER_TIMELINE_HEADER)
    state.focus_index = timeline_row
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
    header_row = find_row_by_kind(state, RowKind.RENDER_TIMELINE_HEADER)
    assert header_row in visible_row_indices(state)


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
    overlay.update(HOLD_IDLE_SEC - 0.1)
    assert overlay._visibility == 1.0
    overlay.update(0.2)
    assert overlay._visibility < 1.0


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
    reserve = timeline_viewport_reserve_px(surface_height)
    assert py + ph + reserve <= surface_height - margin_y

    open_metrics = _panel_scroll_metrics(
        overlay, state, surface_height=surface_height, timeline_panel_open=True
    )
    closed_metrics = _panel_scroll_metrics(
        overlay, state, surface_height=surface_height, timeline_panel_open=False
    )
    assert open_metrics.max_panel_h < closed_metrics.max_panel_h
    assert open_metrics.max_panel_h == closed_metrics.max_panel_h - reserve


def test_toast_stays_at_panel_bottom() -> None:
    pygame.init()
    overlay = TuningOverlay()
    state = _minimal_view_state(
        toast_message="Saved",
        toast_remaining_sec=2.0,
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    panel = overlay.panel_rect
    assert panel is not None
    _, _, _, panel_h = panel

    font = overlay._font_get()
    line_h = font.get_linesize()
    toast_layout = panel_toast_layout(
        panel_h=panel_h,
        padding=overlay._padding,
        line_h=line_h,
        toast_active=True,
    )
    assert toast_layout.toast_y is not None
    assert toast_layout.toast_y == panel_h - overlay._padding - line_h
