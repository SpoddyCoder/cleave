"""Tests for live tuning overlay drawing."""

from __future__ import annotations

import pygame

from cleave.extract import STEM_NAMES
from cleave.viz.overlay import (
    RowKind,
    TrackBlock,
    TuningOverlay,
    TuningViewState,
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
    overlay.draw(surface, state)
    assert overlay.panel_rect is not None

    header_row = next(
        i
        for i in visible_row_indices(state)
        if row_kind(state, i) == RowKind.TRACK_HEADER and row_stem(state, i) == "drums"
    )
    assert state.solo_stem == "drums"
    assert header_row == 0
