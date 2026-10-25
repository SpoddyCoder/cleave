"""Tests for the remaining pygame info panel."""

from __future__ import annotations

import pygame

from cleave.viz import modal_overlay
from cleave.viz.info_panel import InfoPanelViewState
from cleave.viz.modal_layout import PANEL_PAD_Y
from cleave.viz.overlay_primitives import overlay_font
from cleave.viz.theme import MODAL_SCRIM_ALPHA


def _font() -> pygame.font.Font:
    return overlay_font(17)


def test_draw_info_covers_viewport_with_scrim() -> None:
    pygame.init()
    surface = pygame.Surface((640, 480), pygame.SRCALPHA)
    modal_overlay.draw_info(
        surface,
        InfoPanelViewState(
            title_lines=("Listening",),
            body_lines=("120 BPM",),
            footer_line="tap",
        ),
        font=_font(),
    )
    sw, sh = surface.get_size()
    for x, y in ((0, 0), (sw - 1, 0), (0, sh - 1), (sw - 1, sh - 1)):
        pixel = surface.get_at((x, y))
        assert pixel[:3] == (0, 0, 0)
        assert pixel[3] == MODAL_SCRIM_ALPHA


def test_info_panel_sections_include_blank_line_gaps() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    state = InfoPanelViewState(
        title_lines=("Detection in progress", "Tap Enter on each bar beat"),
        body_lines=(
            "Streak: 2/4",
            "Spread: 10 ms",
            "Estimate: 205 ms",
        ),
        footer_line="Esc to cancel",
    )
    _panel_w, panel_h = modal_overlay._measure_info_panel(
        font, state, line_gap=line_gap, screen_w=1280
    )
    title_h = 2 * line_h + line_gap
    body_h = 3 * line_h + 2 * line_gap
    footer_h = line_h
    section_gap = line_h + line_gap
    expected_h = (
        PANEL_PAD_Y * 2 + title_h + section_gap + body_h + section_gap + footer_h
    )
    assert panel_h == expected_h
