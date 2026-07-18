"""Tests for centered modal overlay drawing."""

from __future__ import annotations

import pygame

from cleave.viz import modal_overlay
from cleave.viz.modal import (
    ModalHost,
    ModalKind,
    ModalOption,
    ModalViewState,
    capital_case_modal_option,
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

    sw, sh = surface.get_size()
    panel_w, panel_h = modal_overlay._measure_panel(
        font, view, line_gap=3, screen_w=sw
    )
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

    panel_w, panel_h = modal_overlay._measure_panel(
        font, view, line_gap=3, screen_w=sw
    )
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
    screen_w = 1280
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
        font, with_message, line_gap=line_gap, screen_w=screen_w
    )
    _, height_options_only = modal_overlay._measure_panel(
        font, options_only, line_gap=line_gap, screen_w=screen_w
    )

    assert height_with_message - height_options_only == line_h + line_h + line_gap


def test_modal_focused_option_has_highlight_background() -> None:
    pygame.init()
    font = _font()
    labels = ("Yes", "No")
    line_gap = 3
    line_h = font.get_linesize()
    panel = pygame.Surface((200, 80), pygame.SRCALPHA)
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
        focus_index=0,
        text_alpha=255,
        line_gap=line_gap,
    )

    highlight_x, _, highlight_w, _ = modal_overlay._focus_highlight_rect(
        font, panel_width=panel.get_width(), y=pad_y, line_h=line_h
    )
    tint_probe = pygame.Surface((4, 4), pygame.SRCALPHA)
    tint_probe.fill((0, 0, 0, 255))
    blit_tint(tint_probe, (0, 0, 4, 4), HIGHLIGHT)
    expected = tint_probe.get_at((2, 2))[:3]
    focused_pixels = [
        panel.get_at((highlight_x + x, pad_y + y))
        for x in range(highlight_w)
        for y in range(line_h)
    ]
    assert any(pixel[:3] == expected for pixel in focused_pixels)

    no_y = pad_y + line_h + line_gap
    unfocused_pixels = [
        panel.get_at((highlight_x + x, no_y + y))
        for x in range(highlight_w)
        for y in range(line_h)
    ]
    assert not any(pixel[:3] == expected for pixel in unfocused_pixels)


def test_modal_focus_highlight_spans_panel_minus_one_char_padding() -> None:
    pygame.init()
    font = _font()
    labels = ("Yes", "Don't Save", "Cancel")
    line_gap = 3
    line_h = font.get_linesize()
    panel = pygame.Surface((280, 120), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 255))
    pad_x = modal_overlay._PANEL_PAD_X
    pad_y = modal_overlay._PANEL_PAD_Y
    content_w = panel.get_width() - pad_x * 2
    highlight_x, _, highlight_w, _ = modal_overlay._focus_highlight_rect(
        font, panel_width=panel.get_width(), y=pad_y, line_h=line_h
    )
    char_w = font.size("M")[0]
    assert highlight_x == char_w
    assert highlight_w == panel.get_width() - 2 * char_w
    tint_probe = pygame.Surface((4, 4), pygame.SRCALPHA)
    tint_probe.fill((0, 0, 0, 255))
    blit_tint(tint_probe, (0, 0, 4, 4), HIGHLIGHT)
    expected = tint_probe.get_at((2, 2))[:3]

    for focus_index in range(len(labels)):
        panel.fill((0, 0, 0, 255))
        modal_overlay._draw_options(
            panel,
            font,
            x=pad_x,
            content_width=content_w,
            y=pad_y,
            labels=labels,
            focus_index=focus_index,
            text_alpha=255,
            line_gap=line_gap,
        )
        row_y = pad_y + focus_index * (line_h + line_gap)
        assert panel.get_at((highlight_x + 1, row_y + line_h // 2))[:3] == expected
        assert panel.get_at(
            (highlight_x + highlight_w - 2, row_y + line_h // 2)
        )[:3] == expected
        assert panel.get_at((0, row_y + line_h // 2))[:3] != expected
        assert panel.get_at((panel.get_width() - 1, row_y + line_h // 2))[:3] != expected


def test_modal_options_centered_when_message_is_wider() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    screen_w = 1280
    view = ModalViewState(
        kind=ModalKind.YES_NO,
        message="Overwrite cleave-viz.yaml?",
        options=("Yes", "No"),
        focus_index=0,
    )
    panel_w, _ = modal_overlay._measure_panel(
        font, view, line_gap=line_gap, screen_w=screen_w
    )
    content_w = panel_w - modal_overlay._PANEL_PAD_X * 2
    options_w, _ = modal_overlay._measure_options(font, view.options, line_gap=line_gap)
    msg_w = font.size(view.message)[0]

    assert msg_w > options_w
    assert content_w == msg_w
    assert modal_overlay._PANEL_PAD_X + (content_w - options_w) // 2 > modal_overlay._PANEL_PAD_X


def test_long_message_wraps_to_half_screen_width() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    screen_w = 640
    message = (
        "Song and visuals pause for calibration. A 140 BPM click track plays: "
        "a loud click on beat 1 of each bar and quieter clicks on beats 2 to 4. "
        "Tap Space in time with each click until the delay is detected automatically. "
        "Esc cancels."
    )
    view = ModalViewState(
        kind=ModalKind.YES_NO,
        message=message,
        options=("Yes", "Cancel"),
        focus_index=0,
    )
    assert font.size(message)[0] > screen_w // 2

    lines = modal_overlay._message_lines(font, message, screen_w=screen_w)
    assert len(lines) > 1
    max_msg_w = modal_overlay._message_max_width(screen_w)
    assert all(font.size(line)[0] <= max_msg_w for line in lines)
    assert any(line.endswith(".") for line in lines[:-1])

    panel_w, panel_h = modal_overlay._measure_panel(
        font, view, line_gap=line_gap, screen_w=screen_w
    )
    content_w = panel_w - modal_overlay._PANEL_PAD_X * 2
    assert content_w <= max_msg_w
    line_h = font.get_linesize()
    msg_h = len(lines) * line_h + (len(lines) - 1) * line_gap
    options_h = 2 * line_h + line_gap
    expected_h = (
        modal_overlay._PANEL_PAD_Y * 2 + msg_h + line_h + line_gap + options_h
    )
    assert panel_h == expected_h


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
    assert view.options == ("(Root)", "Keepers", "Wip", "Cancel")

    options_w, options_h = modal_overlay._measure_options(font, view.options, line_gap=3)
    line_h = font.get_linesize()
    assert options_h == 4 * line_h + 3 * 3
    assert options_w == max(
        font.size(modal_overlay._option_text(label))[0] for label in view.options
    )

    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    modal_overlay.draw(surface, view, font=font)


def test_prompt_choice_up_down_and_left_right_cycle_options() -> None:
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

    modal.handle_keydown(_keydown(pygame.K_DOWN))
    assert modal.view_state() is not None
    assert modal.view_state().focus_index == 1

    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    assert modal.view_state().focus_index == 2

    modal.handle_keydown(_keydown(pygame.K_DOWN))
    assert modal.view_state().focus_index == 0

    modal.handle_keydown(_keydown(pygame.K_UP))
    assert modal.view_state().focus_index == 2

    modal.handle_keydown(_keydown(pygame.K_LEFT))
    assert modal.view_state().focus_index == 1


def test_modal_options_always_vertical() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    labels = ("A", "B", "C")

    options_w, options_h = modal_overlay._measure_options(
        font, labels, line_gap=line_gap
    )

    assert options_h == 3 * line_h + 2 * line_gap
    assert options_w == max(
        font.size(modal_overlay._option_text(label))[0] for label in labels
    )


def test_capital_case_modal_option() -> None:
    assert capital_case_modal_option("YES") == "Yes"
    assert capital_case_modal_option("save as new") == "Save As New"
    assert capital_case_modal_option("DON'T SAVE") == "Don't Save"
    assert capital_case_modal_option("(root)") == "(Root)"
    assert capital_case_modal_option("keepers") == "Keepers"
    assert capital_case_modal_option("5.0s") == "5.0s"
    assert capital_case_modal_option("a-tier") == "A-tier"


def test_modal_vertical_focused_option_has_highlight_background() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    labels = ("(Root)", "A-tier", "B-tier", "C-tier", "D-tier", "Cancel")
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

    highlight_x, _, highlight_w, _ = modal_overlay._focus_highlight_rect(
        font, panel_width=panel.get_width(), y=pad_y, line_h=line_h
    )
    row_y = pad_y + line_h + line_gap

    tint_probe = pygame.Surface((4, 4), pygame.SRCALPHA)
    tint_probe.fill((0, 0, 0, 255))
    blit_tint(tint_probe, (0, 0, 4, 4), HIGHLIGHT)
    expected = tint_probe.get_at((2, 2))[:3]
    focused_pixels = [
        panel.get_at((highlight_x + x, row_y + y))
        for x in range(highlight_w)
        for y in range(line_h)
    ]
    assert any(pixel[:3] == expected for pixel in focused_pixels)


def test_info_panel_sections_include_blank_line_gaps() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    state = modal_overlay.InfoPanelViewState(
        title_lines=("Detection in progress", "Tap Space on each bar beat"),
        body_lines=(
            "Streak: 2/4",
            "Spread: 10 ms",
            "Estimate: 205 ms",
        ),
        footer_line="Esc to cancel",
    )
    panel_w, panel_h = modal_overlay._measure_info_panel(
        font, state, line_gap=line_gap, screen_w=1280
    )
    title_h = 2 * line_h + line_gap
    body_h = 3 * line_h + 2 * line_gap
    footer_h = line_h
    section_gap = line_h + line_gap
    expected_h = (
        modal_overlay._PANEL_PAD_Y * 2 + title_h + section_gap + body_h + section_gap + footer_h
    )
    assert panel_h == expected_h
