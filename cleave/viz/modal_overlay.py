"""Centered informational panel on the pygame overlay."""

from __future__ import annotations

import pygame

from cleave.viz.info_panel import InfoPanelViewState
from cleave.viz.modal_layout import PANEL_PAD_X, PANEL_PAD_Y, panel_min_width
from cleave.viz.overlay_primitives import draw_panel_border, overlay_panel_surface
from cleave.viz.theme import ACTION, LABEL, MODAL_SCRIM_ALPHA, VALUE, tuning_ui_metrics

_tuning_ui = tuning_ui_metrics()


def _measure_info_panel(
    font: pygame.font.Font,
    state: InfoPanelViewState,
    *,
    line_gap: int,
    screen_w: int,
) -> tuple[int, int]:
    line_h = font.get_linesize()
    content_w = 0
    content_h = 0

    def _add_block(lines: tuple[str, ...]) -> None:
        nonlocal content_w, content_h
        if not lines:
            return
        block_w = max((font.size(line)[0] for line in lines), default=0)
        content_w = max(content_w, block_w)
        content_h += len(lines) * line_h + max(0, len(lines) - 1) * line_gap

    _add_block(state.title_lines)
    if state.title_lines and state.body_lines:
        content_h += line_h + line_gap
    _add_block(state.body_lines)
    if state.footer_line is not None:
        if state.title_lines or state.body_lines:
            content_h += line_h + line_gap
        footer_w = font.size(state.footer_line)[0]
        content_w = max(content_w, footer_w)
        content_h += line_h

    return (
        max(content_w + PANEL_PAD_X * 2, panel_min_width(screen_w)),
        content_h + PANEL_PAD_Y * 2,
    )


def draw_info(
    surface: pygame.Surface,
    state: InfoPanelViewState,
    *,
    font: pygame.font.Font,
    line_gap: int | None = None,
    text_alpha: int = 255,
) -> None:
    """Draw a centered informational panel with full-viewport scrim."""
    if text_alpha < 2:
        return
    if line_gap is None:
        line_gap = _tuning_ui.line_gap

    sw, sh = surface.get_width(), surface.get_height()
    scrim = pygame.Surface((sw, sh), pygame.SRCALPHA)
    scrim.fill((0, 0, 0, MODAL_SCRIM_ALPHA))
    surface.blit(scrim, (0, 0))

    panel_w, panel_h = _measure_info_panel(
        font, state, line_gap=line_gap, screen_w=sw
    )
    panel_x = (sw - panel_w) // 2
    panel_y = (sh - panel_h) // 2
    panel = overlay_panel_surface((panel_w, panel_h))

    cur_y = PANEL_PAD_Y
    line_h = font.get_linesize()

    def _draw_lines(lines: tuple[str, ...], color: tuple[int, int, int]) -> None:
        nonlocal cur_y
        for index, line in enumerate(lines):
            line_surf = font.render(line, True, color)
            line_surf.set_alpha(text_alpha)
            panel.blit(line_surf, (PANEL_PAD_X, cur_y))
            cur_y += line_h
            if index + 1 < len(lines):
                cur_y += line_gap

    _draw_lines(state.title_lines, LABEL)
    if state.title_lines and state.body_lines:
        cur_y += line_h + line_gap
    _draw_lines(state.body_lines, VALUE)
    if state.footer_line is not None:
        if state.title_lines or state.body_lines:
            cur_y += line_h + line_gap
        footer_surf = font.render(state.footer_line, True, ACTION)
        footer_surf.set_alpha(text_alpha)
        panel.blit(footer_surf, (PANEL_PAD_X, cur_y))

    draw_panel_border(panel, alpha=int(255 * text_alpha / 255))

    surface.blit(panel, (panel_x, panel_y))
