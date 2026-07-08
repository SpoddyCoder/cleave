"""Tests for centered modal overlay drawing."""

from __future__ import annotations

import pygame

from cleave.viz import modal_overlay
from cleave.viz.modal import (
    ModalHost,
    ModalKind,
    ModalOption,
    ModalViewState,
    modal_options_vertical,
)
from cleave.viz.theme import HIGHLIGHT, MODAL_SCRIM_ALPHA
from cleave.viz.ui_tint import blit_tint


def _font() -> pygame.font.Font:
    return pygame.font.SysFont("monospace", 17)


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0)


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


def test_modal_focused_option_has_highlight_background() -> None:
    pygame.init()
    font = _font()
    panel = pygame.Surface((200, 40), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 255))
    line_h = font.get_linesize()
    pad_x = modal_overlay._PANEL_PAD_X
    pad_y = modal_overlay._PANEL_PAD_Y
    content_w = panel.get_width() - pad_x * 2
    modal_overlay._draw_options(
        panel,
        font,
        x=pad_x,
        content_width=content_w,
        y=pad_y,
        labels=("Yes", "No"),
        focus_index=0,
        text_alpha=255,
        line_gap=3,
    )

    yes_w = font.size(modal_overlay._option_text("Yes"))[0]
    options_w, _ = modal_overlay._measure_options(font, ("Yes", "No"), line_gap=3)
    option_x = pad_x + (content_w - options_w) // 2
    tint_probe = pygame.Surface((4, 4), pygame.SRCALPHA)
    tint_probe.fill((0, 0, 0, 255))
    blit_tint(tint_probe, (0, 0, 4, 4), HIGHLIGHT)
    expected = tint_probe.get_at((2, 2))[:3]
    focused_pixels = [
        panel.get_at((option_x + x, pad_y + y))
        for x in range(yes_w)
        for y in range(line_h)
    ]
    assert any(pixel[:3] == expected for pixel in focused_pixels)

    no_x = option_x + yes_w + modal_overlay._OPTION_GAP
    no_w = font.size(modal_overlay._option_text("No"))[0]
    unfocused_pixels = [
        panel.get_at((no_x + x, pad_y + y))
        for x in range(no_w)
        for y in range(line_h)
    ]
    assert not any(pixel[:3] == expected for pixel in unfocused_pixels)


def test_modal_options_centered_when_message_is_wider() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    view = ModalViewState(
        kind=ModalKind.YES_NO,
        message="Overwrite cleave-viz.yaml?",
        options=("Yes", "No"),
        focus_index=0,
    )
    panel_w, _ = modal_overlay._measure_panel(font, view, line_gap=line_gap)
    content_w = panel_w - modal_overlay._PANEL_PAD_X * 2
    options_w, _ = modal_overlay._measure_options(font, view.options, line_gap=line_gap)
    msg_w = font.size(view.message)[0]

    assert msg_w > options_w
    assert content_w == msg_w
    assert modal_overlay._PANEL_PAD_X + (content_w - options_w) // 2 > modal_overlay._PANEL_PAD_X


def test_prompt_choice_renders_n_options() -> None:
    pygame.init()
    font = _font()
    modal = ModalHost()
    modal.prompt_choice(
        "Favourite preset: demo.milk?",
        [
            ModalOption("(root)", lambda: None),
            ModalOption("keepers", lambda: None),
            ModalOption("wip", lambda: None),
            ModalOption("Cancel", lambda: None),
        ],
    )
    view = modal.view_state()
    assert view is not None
    assert view.kind == ModalKind.CHOICE
    assert view.options == ("(root)", "keepers", "wip", "Cancel")

    options_w, options_h = modal_overlay._measure_options(font, view.options, line_gap=3)
    assert options_h == font.get_linesize()
    assert options_w > font.size(modal_overlay._option_text("(root)"))[0]

    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    modal_overlay.draw(surface, view, font=font)


def test_prompt_choice_left_right_cycles_options() -> None:
    modal = ModalHost()
    modal.prompt_choice(
        "Blacklist preset: demo.milk?",
        [
            ModalOption("(root)", lambda: None),
            ModalOption("review", lambda: None),
            ModalOption("Cancel", lambda: None),
        ],
    )
    view = modal.view_state()
    assert view is not None
    assert view.focus_index == 0

    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    assert modal.view_state() is not None
    assert modal.view_state().focus_index == 1

    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    assert modal.view_state().focus_index == 2

    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    assert modal.view_state().focus_index == 0

    modal.handle_keydown(_keydown(pygame.K_LEFT))
    assert modal.view_state().focus_index == 2


def test_modal_options_vertical_threshold() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    horizontal_labels = ("a", "b", "c", "d", "e")
    vertical_labels = horizontal_labels + ("f",)

    assert not modal_options_vertical(len(horizontal_labels))
    assert modal_options_vertical(len(vertical_labels))

    horiz_w, horiz_h = modal_overlay._measure_options(
        font, horizontal_labels, line_gap=line_gap
    )
    vert_w, vert_h = modal_overlay._measure_options(
        font, vertical_labels, line_gap=line_gap
    )

    assert horiz_h == line_h
    assert horiz_w > font.size(modal_overlay._option_text("a"))[0]
    assert vert_h == 6 * line_h + 5 * line_gap
    assert vert_w == max(
        font.size(modal_overlay._option_text(label))[0] for label in vertical_labels
    )


def test_modal_vertical_focused_option_has_highlight_background() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    labels = ("(root)", "a-tier", "b-tier", "c-tier", "d-tier", "Cancel")
    panel = pygame.Surface((200, 200), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 255))
    pad_x = modal_overlay._PANEL_PAD_X
    pad_y = modal_overlay._PANEL_PAD_Y
    content_w = panel.get_width() - pad_x * 2
    modal_overlay._draw_options(
        panel,
        font,
        x=pad_x,
        content_width=content_w,
        y=pad_y,
        labels=labels,
        focus_index=1,
        text_alpha=255,
        line_gap=line_gap,
    )

    options_w, _ = modal_overlay._measure_options(font, labels, line_gap=line_gap)
    option_x = pad_x + (content_w - options_w) // 2
    focused_label = labels[1]
    text_w = font.size(modal_overlay._option_text(focused_label))[0]
    row_x = option_x + max(0, (options_w - text_w) // 2)
    row_y = pad_y + line_h + line_gap

    tint_probe = pygame.Surface((4, 4), pygame.SRCALPHA)
    tint_probe.fill((0, 0, 0, 255))
    blit_tint(tint_probe, (0, 0, 4, 4), HIGHLIGHT)
    expected = tint_probe.get_at((2, 2))[:3]
    focused_pixels = [
        panel.get_at((row_x + x, row_y + y))
        for x in range(text_w)
        for y in range(line_h)
    ]
    assert any(pixel[:3] == expected for pixel in focused_pixels)


def test_prompt_choice_vertical_up_down_cycles_options() -> None:
    modal = ModalHost()
    modal.prompt_choice(
        "Favourite preset: demo.milk?",
        [
            ModalOption("(root)", lambda: None),
            ModalOption("a-tier", lambda: None),
            ModalOption("b-tier", lambda: None),
            ModalOption("c-tier", lambda: None),
            ModalOption("d-tier", lambda: None),
            ModalOption("Cancel", lambda: None),
        ],
    )
    view = modal.view_state()
    assert view is not None
    assert view.options_vertical
    assert view.focus_index == 0

    modal.handle_keydown(_keydown(pygame.K_DOWN))
    assert modal.view_state().focus_index == 1

    modal.handle_keydown(_keydown(pygame.K_DOWN))
    assert modal.view_state().focus_index == 2

    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    assert modal.view_state().focus_index == 3

    modal.handle_keydown(_keydown(pygame.K_UP))
    assert modal.view_state().focus_index == 2

    modal.handle_keydown(_keydown(pygame.K_LEFT))
    assert modal.view_state().focus_index == 1
