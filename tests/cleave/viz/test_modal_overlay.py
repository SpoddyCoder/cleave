"""Tests for centered modal overlay drawing."""

from __future__ import annotations

import pygame

from cleave.viz import modal_overlay
from cleave.viz.modal import ModalHost, ModalKind, ModalViewState
from cleave.viz.theme import MODAL_SCRIM_ALPHA


def _font() -> pygame.font.Font:
    return pygame.font.SysFont("monospace", 17)


def test_modal_panel_is_centered() -> None:
    pygame.init()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    font = _font()
    modal = ModalHost()
    modal.prompt_yes_no("Overwrite cleave-viz.yaml?", on_confirm=lambda: None)
    view = modal.view_state()
    assert view is not None

    modal_overlay.draw(surface, view, font=font)

    panel_w, panel_h = modal_overlay._measure_panel(font, view, line_gap=3)
    sw, sh = surface.get_size()
    expected_x = (sw - panel_w) // 2
    expected_y = (sh - panel_h) // 2
    left_margin = expected_x
    right_margin = sw - (expected_x + panel_w)
    top_margin = expected_y
    bottom_margin = sh - (expected_y + panel_h)
    assert abs(left_margin - right_margin) <= 1
    assert abs(top_margin - bottom_margin) <= 1


def test_modal_scrim_covers_viewport() -> None:
    pygame.init()
    surface = pygame.Surface((640, 480), pygame.SRCALPHA)
    font = _font()
    modal = ModalHost()
    modal.prompt_unsaved_quit(on_save=lambda: None, on_discard=lambda: None)
    view = modal.view_state()
    assert view is not None
    assert view.kind == ModalKind.UNSAVED_QUIT

    modal_overlay.draw(surface, view, font=font)

    sw, sh = surface.get_size()
    for x, y in ((0, 0), (sw - 1, 0), (0, sh - 1), (sw - 1, sh - 1)):
        pixel = surface.get_at((x, y))
        assert pixel[:3] == (0, 0, 0)
        assert pixel[3] == MODAL_SCRIM_ALPHA

    panel_w, panel_h = modal_overlay._measure_panel(font, view, line_gap=3)
    panel_x = (sw - panel_w) // 2
    panel_y = (sh - panel_h) // 2
    outside = surface.get_at((panel_x // 2, sh // 2))
    inside = surface.get_at((panel_x + panel_w // 2, panel_y + panel_h - 4))
    assert outside[3] == MODAL_SCRIM_ALPHA
    assert inside[3] > MODAL_SCRIM_ALPHA


def test_message_options_vertical_spacing() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    with_message = ModalViewState(
        kind=ModalKind.YES_NO,
        message="Save configuration?",
        options=("Yes", "No"),
        focus_index=0,
    )
    options_only = ModalViewState(
        kind=ModalKind.YES_NO,
        message=None,
        options=("Yes", "No"),
        focus_index=0,
    )

    _, height_with_message = modal_overlay._measure_panel(
        font, with_message, line_gap=line_gap
    )
    _, height_options_only = modal_overlay._measure_panel(
        font, options_only, line_gap=line_gap
    )

    assert height_with_message - height_options_only == line_h + line_h + line_gap
