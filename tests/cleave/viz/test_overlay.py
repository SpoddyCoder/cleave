"""Tests for live tuning overlay drawing."""

from __future__ import annotations

import pygame

from cleave.extract import STEM_NAMES
from cleave.viz.material_icons import row_icon_prefix_width
from cleave.viz.overlay import (
    PanelScrollMetrics,
    RenderOverlayBlock,
    RenderTimelineBlock,
    RowKind,
    TrackBlock,
    TuningOverlay,
    TuningViewState,
    build_row_layout,
    find_row_by_kind,
    fit_row_text,
    panel_content_max_width,
    render_visibility_icon,
    row_kind,
    row_stem,
    scroll_metrics,
    track_row_count,
    visible_row_indices,
)
from cleave.viz.theme import (
    BORDER_WIDTH,
    DISABLED,
    HOLD_IDLE_SEC,
    PANEL_CONTENT_MAX_WIDTH,
    SCROLLBAR_TRACK,
    SCROLLBAR_WIDTH,
    SOLO_BG,
    TIMELINE_PANEL_HOLD_IDLE_SEC,
    VALUE,
)


def _effects_expanded_view_state() -> TuningViewState:
    tracks = {
        stem: TrackBlock(
            stem=stem,
            preset_dir_label=f"{stem}/dir",
            preset_label=f"{stem}/preset.milk",
            blend_mode="add",
            opacity_pct=50,
            beat_sensitivity=1.0,
            effects={},
            effects_expanded=True,
            expanded=True,
        )
        for stem in STEM_NAMES
    }
    return TuningViewState(
        layer_z_order=STEM_NAMES,
        tracks=tracks,
        paused=False,
        position_sec=0.0,
        focus_index=0,
        move_mode_stem=None,
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
    overlay: TuningOverlay, state: TuningViewState, *, surface_height: int = 720
) -> PanelScrollMetrics:
    font = overlay._font_get()
    line_h = font.get_linesize()
    visible_indices = visible_row_indices(state)
    track_rows_boundary = track_row_count(state)
    first_footer_visible = next(
        (index for index in visible_indices if index >= track_rows_boundary),
        None,
    )
    footer_gap = (line_h + overlay._line_gap) * 2
    _, margin_y = overlay._margin
    return scroll_metrics(
        visible_indices=visible_indices,
        first_footer_visible=first_footer_visible,
        line_h=line_h,
        line_gap=overlay._line_gap,
        padding=overlay._padding,
        footer_gap=footer_gap,
        confirm_h=0,
        confirm_active=False,
        save_choice_h=0,
        save_choice_active=False,
        toast_active=False,
        max_panel_h=surface_height - margin_y * 2,
    )


def _copy_panel_surface(overlay: TuningOverlay, state: TuningViewState) -> pygame.Surface:
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    panel = overlay.panel_rect
    assert panel is not None
    return surface.subsurface(panel).copy()


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


def test_footer_rows_pinned_when_scrolled() -> None:
    pygame.init()
    state_top = _effects_expanded_view_state()
    state_top.focus_index = 0
    state_bottom = _effects_expanded_view_state()
    state_bottom.focus_index = find_row_by_kind(state_bottom, RowKind.RENDER_TIMELINE_HEADER) - 1

    panel_top = _copy_panel_surface(TuningOverlay(), state_top)
    panel_bottom = _copy_panel_surface(TuningOverlay(), state_bottom)

    overlay = TuningOverlay()
    metrics = _panel_scroll_metrics(overlay, state_bottom)
    assert metrics.needs_scroll
    font = overlay._font_get()
    transport_y = overlay._padding + metrics.scroll_viewport_h + (font.get_linesize() + overlay._line_gap) * 2
    footer_h = panel_top.get_height() - transport_y
    top_strip = panel_top.subsurface((0, transport_y, panel_top.get_width(), footer_h))
    bottom_strip = panel_bottom.subsurface(
        (0, transport_y, panel_bottom.get_width(), footer_h)
    )
    assert pygame.image.tostring(top_strip, "RGBA") == pygame.image.tostring(
        bottom_strip, "RGBA"
    )


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
    state.tracks["drums"].preset_dir_label = long_dir
    state.tracks["drums"].preset_label = long_preset

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
        budget = max_w - 16 - icon_w  # TREE_INDENT
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
        "layer_z_order": ("drums",),
        "tracks": {
            "drums": TrackBlock(
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
        "move_mode_stem": None,
        "toast_message": None,
        "toast_remaining_sec": 0.0,
    }
    defaults.update(kwargs)
    return TuningViewState(**defaults)  # type: ignore[arg-type]


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
    assert header_idx < config_idx


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
        layer_z_order=("drums",),
        tracks={
            "drums": TrackBlock(
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
        move_mode_stem=None,
        toast_message=None,
        toast_remaining_sec=0.0,
        solo_stem="drums",
        solo_active=True,
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.notify_input()
    overlay.draw(surface, state)
    assert overlay.panel_rect is not None

    header_row = next(
        i
        for i in visible_row_indices(state)
        if row_kind(state, i) == RowKind.TRACK_HEADER and row_stem(state, i) == "drums"
    )
    assert state.solo_stem == "drums"
    assert header_row == 0


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
    overlay.draw(surface, state)
    assert overlay.panel_rect is None


def test_overlay_normal_hold_idle_without_timeline_panel() -> None:
    overlay = TuningOverlay()
    overlay.notify_input()
    overlay.update(HOLD_IDLE_SEC - 0.1)
    assert overlay._visibility == 1.0
    overlay.update(0.2)
    assert overlay._visibility < 1.0


def test_overlay_short_hold_idle_with_timeline_panel_open() -> None:
    overlay = TuningOverlay()
    overlay.notify_input()
    overlay.update(TIMELINE_PANEL_HOLD_IDLE_SEC - 0.1, timeline_panel_open=True)
    assert overlay._visibility == 1.0
    overlay.update(0.2, timeline_panel_open=True)
    assert overlay._visibility < 1.0
