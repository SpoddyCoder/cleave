"""Tests for live tuning overlay drawing."""

from __future__ import annotations

import pygame

from cleave.extract import STEM_NAMES
from cleave.viz.overlay import (
    RenderOverlayBlock,
    RowKind,
    TrackBlock,
    TuningOverlay,
    TuningViewState,
    build_row_layout,
    find_row_by_kind,
    render_visibility_icon,
    row_kind,
    row_stem,
    visible_row_indices,
)
from cleave.viz.theme import DISABLED, SOLO_BG, VALUE


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
    surface.subsurface(panel)


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
