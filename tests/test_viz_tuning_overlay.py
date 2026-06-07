"""Tests for live tuning overlay drawing."""

from __future__ import annotations

import pygame

from cleave.extract import STEM_NAMES
from cleave.viz_tuning_overlay import (
    TrackBlock,
    TuningOverlay,
    TuningViewState,
    visible_row_indices,
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
    overlay.draw(surface, state)

    panel = overlay.panel_rect
    assert panel is not None
    px, py, pw, ph = panel
    sw, sh = surface.get_size()
    assert px >= 0 and py >= 0
    assert px + pw <= sw and py + ph <= sh
    surface.subsurface(panel)


def test_draw_effects_expanded_matches_milkdrop_subsurface() -> None:
    """Regression: milkdrop_visualizer subsurfaces panel_rect after draw."""
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
