"""Tests for centered modal overlay drawing."""

from __future__ import annotations

from dataclasses import replace

import pygame

from cleave.viz import modal_overlay
from cleave.viz.modal import (
    ModalHost,
    ModalKind,
    ModalLabeledLine,
    ModalOption,
    ModalViewState,
    TextFocusRegion,
    capital_case_modal_option,
)
from cleave.viz.overlay_primitives import overlay_font
from cleave.viz.theme import FOCUS_ROW_BG_ALPHA, HIGHLIGHT, LABEL, MODAL_SCRIM_ALPHA, VALUE
from cleave.viz.ui_tint import blit_tint


def _font() -> pygame.font.Font:
    return overlay_font(17)


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
    min_content_w = (
        modal_overlay._panel_min_width(screen_w) - modal_overlay._PANEL_PAD_X * 2
    )

    assert msg_w > options_w
    assert content_w == max(msg_w, min_content_w)
    assert modal_overlay._PANEL_PAD_X + (content_w - options_w) // 2 > modal_overlay._PANEL_PAD_X


def test_modal_panel_min_width_is_20_percent_of_screen() -> None:
    pygame.init()
    font = _font()
    screen_w = 1280
    view = ModalViewState(
        kind=ModalKind.YES_NO,
        message="Save?",
        options=("Yes", "No"),
        focus_index=0,
    )
    panel_w, _ = modal_overlay._measure_panel(
        font, view, line_gap=3, screen_w=screen_w
    )
    assert panel_w >= modal_overlay._panel_min_width(screen_w)
    assert modal_overlay._panel_min_width(screen_w) == int(screen_w * 0.2)


def test_long_message_wraps_to_half_screen_width() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    screen_w = 640
    message = (
        "Song and visuals pause for calibration. A 140 BPM click track plays: "
        "a loud click on beat 1 of each bar and quieter clicks on beats 2 to 4. "
        "Tap Enter in time with each click until the delay is detected automatically. "
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
        title_lines=("Detection in progress", "Tap Enter on each bar beat"),
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


def test_labeled_lines_blank_gaps_and_height() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    screen_w = 1280
    labeled = (
        ModalLabeledLine("character", "breathing"),
        ModalLabeledLine("density", "normal"),
    )
    view = ModalViewState(
        kind=ModalKind.YES_NO,
        message="Apply timeline preset?",
        options=("Yes", "Cancel"),
        focus_index=0,
        labeled_lines=labeled,
    )
    _, panel_h = modal_overlay._measure_panel(
        font, view, line_gap=line_gap, screen_w=screen_w
    )
    title_h = line_h
    labeled_h = 2 * line_h + line_gap
    options_h = 2 * line_h + line_gap
    section_gap = line_h + line_gap
    expected_h = (
        modal_overlay._PANEL_PAD_Y * 2
        + title_h
        + section_gap
        + labeled_h
        + section_gap
        + options_h
    )
    assert panel_h == expected_h

    without_labeled = ModalViewState(
        kind=ModalKind.YES_NO,
        message="Apply timeline preset?",
        options=("Yes", "Cancel"),
        focus_index=0,
    )
    _, height_without = modal_overlay._measure_panel(
        font, without_labeled, line_gap=line_gap, screen_w=screen_w
    )
    assert panel_h - height_without == section_gap + labeled_h


def test_labeled_lines_draw_label_and_value_colors() -> None:
    pygame.init()
    font = _font()
    line = ModalLabeledLine("character", "breathing")
    panel = pygame.Surface((400, 40), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 255))
    modal_overlay._draw_labeled_lines(
        panel,
        font,
        x=0,
        y=0,
        lines=(line,),
        text_alpha=255,
        line_gap=3,
    )
    prefix_w = font.size(line.prefix())[0]
    value_w = font.size(line.value)[0]
    line_h = font.get_linesize()
    mid_y = line_h // 2

    def _has_color(
        x0: int, x1: int, color: tuple[int, int, int]
    ) -> bool:
        return any(
            panel.get_at((x, mid_y))[:3] == color for x in range(x0, x1)
        )

    assert _has_color(0, prefix_w, LABEL)
    assert _has_color(prefix_w, prefix_w + value_w, VALUE)
    assert not _has_color(0, prefix_w, VALUE)
    assert not _has_color(prefix_w, prefix_w + value_w, LABEL)


def test_prompt_yes_no_passes_labeled_lines() -> None:
    modal = ModalHost()
    labeled = (
        ModalLabeledLine("character", "arc"),
        ModalLabeledLine("conductor", "on"),
    )
    modal.prompt_yes_no(
        "Apply timeline preset?",
        on_confirm=lambda: None,
        cancel_label="Cancel",
        labeled_lines=labeled,
    )
    view = modal.view_state()
    assert view is not None
    assert view.message == "Apply timeline preset?"
    assert view.labeled_lines == labeled
    assert view.options == ("Yes", "Cancel")


def test_prompt_progress_has_bar_and_ignores_keys() -> None:
    pygame.init()
    modal = ModalHost()
    labeled = (
        ModalLabeledLine("output", "renders/song.mp4"),
        ModalLabeledLine("quality", "high"),
    )
    modal.prompt_progress(
        "Rendering project...",
        labeled_lines=labeled,
        fraction=0.25,
    )
    view = modal.view_state()
    assert view is not None
    assert view.kind == ModalKind.PROGRESS
    assert view.message == "Rendering project..."
    assert view.options == ()
    assert view.progress_fraction == 0.25
    assert view.labeled_lines == labeled
    assert modal.handle_keydown(_keydown(pygame.K_ESCAPE)) is True
    assert modal.active is True
    assert modal.handle_keydown(_keydown(pygame.K_RETURN)) is True
    assert modal.active is True
    modal.update_progress(0.8)
    assert modal.view_state().progress_fraction == 0.8

    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    screen_w = 1280
    _, panel_h = modal_overlay._measure_panel(
        font, modal.view_state(), line_gap=line_gap, screen_w=screen_w
    )
    without_bar = ModalViewState(
        kind=ModalKind.PROGRESS,
        message="Rendering project...",
        options=(),
        focus_index=0,
        labeled_lines=labeled,
    )
    _, height_without = modal_overlay._measure_panel(
        font, without_bar, line_gap=line_gap, screen_w=screen_w
    )
    section_gap = line_h + line_gap
    assert panel_h - height_without == section_gap + modal_overlay._BAR_HEIGHT


def test_prompt_choice_passes_labeled_lines() -> None:
    modal = ModalHost()
    labeled = (ModalLabeledLine("output", "renders/song.mp4"),)
    modal.prompt_choice(
        "Render complete",
        [ModalOption("OK", lambda: None)],
        labeled_lines=labeled,
    )
    view = modal.view_state()
    assert view is not None
    assert view.message == "Render complete"
    assert view.labeled_lines == labeled
    assert view.options == ("Ok",)


def _prompt_text(
    modal: ModalHost,
    *,
    cta: str = "Change text...",
    initial: str = "hello",
    single_line: bool = True,
) -> None:
    modal.prompt_text(
        cta,
        initial,
        on_confirm=lambda _draft: None,
        on_cancel=lambda: None,
        single_line=single_line,
    )


def _highlight_tint_rgb() -> tuple[int, int, int]:
    tint_probe = pygame.Surface((4, 4), pygame.SRCALPHA)
    tint_probe.fill((0, 0, 0, 255))
    blit_tint(tint_probe, (0, 0, 4, 4), HIGHLIGHT, alpha=FOCUS_ROW_BG_ALPHA)
    return tint_probe.get_at((2, 2))[:3]


def _draw_text_panel_for_tests(
    font: pygame.font.Font,
    view: ModalViewState,
    *,
    line_gap: int = 3,
    screen_w: int = 1280,
    screen_h: int = 720,
) -> pygame.Surface:
    panel_w, panel_h = modal_overlay._measure_text_panel(
        font, view, line_gap=line_gap, screen_w=screen_w, screen_h=screen_h
    )
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 255))
    modal_overlay._draw_text_panel(
        panel,
        font,
        view,
        line_gap=line_gap,
        screen_w=screen_w,
        screen_h=screen_h,
        text_alpha=255,
        panel_w=panel_w,
    )
    return panel


def _text_field_origin(
    font: pygame.font.Font,
    view: ModalViewState,
    *,
    line_gap: int,
    screen_w: int,
    screen_h: int,
) -> tuple[int, int, int]:
    line_h = font.get_linesize()
    section_gap = line_h + line_gap
    cta_h = modal_overlay._lines_block_height(
        len(modal_overlay._text_cta_lines(view)), line_h, line_gap
    )
    panel_w, _ = modal_overlay._measure_text_panel(
        font, view, line_gap=line_gap, screen_w=screen_w, screen_h=screen_h
    )
    content_w = panel_w - modal_overlay._PANEL_PAD_X * 2
    field_x = modal_overlay._PANEL_PAD_X
    field_y = modal_overlay._PANEL_PAD_Y + cta_h + section_gap
    return field_x, field_y, content_w


def _text_button_rects(
    font: pygame.font.Font,
    view: ModalViewState,
    *,
    line_gap: int,
    screen_w: int,
    screen_h: int,
) -> tuple[pygame.Rect, pygame.Rect]:
    line_h = font.get_linesize()
    section_gap = line_h + line_gap
    field_x, field_y, content_w = _text_field_origin(
        font, view, line_gap=line_gap, screen_w=screen_w, screen_h=screen_h
    )
    del field_x, content_w
    field_lines = modal_overlay._text_field_lines(font, view, screen_w=screen_w)
    field_h = modal_overlay._lines_block_height(len(field_lines), line_h, line_gap)
    button_y = field_y + field_h + section_gap
    confirm_w, cancel_w = modal_overlay._text_button_widths(font)
    total_w = modal_overlay._text_buttons_width(font)
    panel_w, _ = modal_overlay._measure_text_panel(
        font, view, line_gap=line_gap, screen_w=screen_w, screen_h=screen_h
    )
    row_content_w = panel_w - modal_overlay._PANEL_PAD_X * 2
    row_x = modal_overlay._PANEL_PAD_X + max(0, (row_content_w - total_w) // 2)
    return (
        pygame.Rect(row_x, button_y, confirm_w, line_h),
        pygame.Rect(
            row_x + confirm_w + modal_overlay._TEXT_BUTTON_GAP,
            button_y,
            cancel_w,
            line_h,
        ),
    )


def _rect_has_color(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int],
) -> bool:
    for x in range(rect.x, rect.x + rect.w):
        for y in range(rect.y, rect.y + rect.h):
            if surface.get_at((x, y))[:3] == color:
                return True
    return False


def test_text_modal_shows_cta_and_draft() -> None:
    pygame.init()
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    font = _font()
    modal = ModalHost()
    _prompt_text(modal, cta="Change text...", initial="hello", single_line=True)
    view = modal.view_state()
    assert view is not None
    assert view.kind == ModalKind.TEXT
    assert view.cta == "Change text..."
    assert view.draft == "hello"

    modal_overlay.draw(surface, view, font=font)

    sw, sh = surface.get_size()
    panel_w, panel_h = modal_overlay._measure_text_panel(
        font, view, line_gap=3, screen_w=sw, screen_h=sh
    )
    expected_x = (sw - panel_w) // 2
    expected_y = (sh - panel_h) // 2
    left_margin = expected_x
    right_margin = sw - (expected_x + panel_w)
    top_margin = expected_y
    bottom_margin = sh - (expected_y + panel_h)
    assert abs(left_margin - right_margin) <= 1
    assert abs(top_margin - bottom_margin) <= 1


def test_text_modal_hint_only_when_editing() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    screen_w = 1280
    screen_h = 720
    modal = ModalHost()
    _prompt_text(modal, initial="hello", single_line=True)
    editing = modal.view_state()
    assert editing is not None
    assert editing.editing is True
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    navigating = modal.view_state()
    assert navigating is not None
    assert navigating.editing is False

    _, height_editing = modal_overlay._measure_text_panel(
        font, editing, line_gap=line_gap, screen_w=screen_w, screen_h=screen_h
    )
    _, height_navigating = modal_overlay._measure_text_panel(
        font, navigating, line_gap=line_gap, screen_w=screen_w, screen_h=screen_h
    )
    assert height_editing - height_navigating == line_h + line_gap


def test_text_modal_focused_button_highlighted() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    expected = _highlight_tint_rgb()
    modal = ModalHost()
    _prompt_text(modal, initial="hello", single_line=True)
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    modal.handle_keydown(_keydown(pygame.K_DOWN))
    view = modal.view_state()
    assert view is not None
    assert view.focus_region == TextFocusRegion.BUTTONS
    assert view.button_index == 0

    panel = _draw_text_panel_for_tests(font, view, line_gap=line_gap)
    confirm, cancel = _text_button_rects(
        font, view, line_gap=line_gap, screen_w=1280, screen_h=720
    )
    assert _rect_has_color(panel, confirm, expected)
    assert not _rect_has_color(panel, cancel, expected)

    modal.handle_keydown(_keydown(pygame.K_RIGHT))
    view = modal.view_state()
    assert view is not None
    assert view.button_index == 1
    panel = _draw_text_panel_for_tests(font, view, line_gap=line_gap)
    confirm, cancel = _text_button_rects(
        font, view, line_gap=line_gap, screen_w=1280, screen_h=720
    )
    assert _rect_has_color(panel, cancel, expected)
    assert not _rect_has_color(panel, confirm, expected)


def test_text_modal_existing_yes_no_unchanged() -> None:
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

    view = ModalViewState(
        kind=ModalKind.YES_NO,
        message="Save?",
        options=("Yes", "No"),
        focus_index=0,
    )
    panel_w, _ = modal_overlay._measure_panel(
        font, view, line_gap=line_gap, screen_w=screen_w
    )
    assert panel_w >= modal_overlay._panel_min_width(screen_w)
    assert modal_overlay._panel_min_width(screen_w) == int(screen_w * 0.2)

    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    modal = ModalHost()
    modal.prompt_yes_no("Overwrite cleave-viz.yaml?", on_confirm=lambda: None)
    yes_no = modal.view_state()
    assert yes_no is not None
    modal_overlay.draw(surface, yes_no, font=font)


def test_text_modal_field_highlight_when_navigating() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    expected = _highlight_tint_rgb()
    modal = ModalHost()
    _prompt_text(modal, initial="hello", single_line=True)
    modal.handle_keydown(_keydown(pygame.K_ESCAPE))
    view = modal.view_state()
    assert view is not None
    assert view.editing is False
    assert view.focus_region == TextFocusRegion.FIELD

    panel = _draw_text_panel_for_tests(font, view, line_gap=line_gap)
    field_x, field_y, _content_w = _text_field_origin(
        font, view, line_gap=line_gap, screen_w=1280, screen_h=720
    )
    del field_x
    highlight_x, _, highlight_w, _ = modal_overlay._focus_highlight_rect(
        font, panel_width=panel.get_width(), y=field_y, line_h=line_h
    )
    field_rect = pygame.Rect(highlight_x, field_y, highlight_w, line_h)
    assert _rect_has_color(panel, field_rect, expected)


def test_text_modal_caret_position() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    modal = ModalHost()
    _prompt_text(modal, initial="hello", single_line=True)
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    view = modal.view_state()
    assert view is not None
    assert view.draft == "hello"
    assert view.caret_index == 3
    assert view.editing is True

    panel = _draw_text_panel_for_tests(font, view, line_gap=line_gap)
    field_x, field_y, content_w = _text_field_origin(
        font, view, line_gap=line_gap, screen_w=1280, screen_h=720
    )
    prefix_w = font.size(view.draft[: view.caret_index])[0]
    assert prefix_w < content_w
    caret_x = field_x + prefix_w
    mid_y = field_y + line_h // 2
    assert panel.get_at((caret_x, mid_y))[:3] == HIGHLIGHT
    assert panel.get_at((caret_x + 1, mid_y))[:3] == HIGHLIGHT
    assert view.caret_visible is True


def test_text_modal_caret_hidden_when_not_visible() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    modal = ModalHost()
    _prompt_text(modal, initial="hello", single_line=True)
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    view = modal.view_state()
    assert view is not None
    assert view.editing is True
    assert view.caret_index == 3
    hidden = replace(view, caret_visible=False)

    panel = _draw_text_panel_for_tests(font, hidden, line_gap=line_gap)
    field_x, field_y, content_w = _text_field_origin(
        font, hidden, line_gap=line_gap, screen_w=1280, screen_h=720
    )
    prefix_w = font.size(hidden.draft[: hidden.caret_index])[0]
    assert prefix_w < content_w
    caret_x = field_x + prefix_w
    mid_y = field_y + line_h // 2
    assert panel.get_at((caret_x, mid_y))[:3] != HIGHLIGHT
    assert panel.get_at((caret_x + 1, mid_y))[:3] != HIGHLIGHT


def test_text_modal_caret_shown_when_visible() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    view = ModalViewState(
        kind=ModalKind.TEXT,
        message=None,
        options=(),
        focus_index=0,
        cta="Change text...",
        draft="hello",
        single_line=True,
        editing=True,
        caret_index=3,
        focus_region=TextFocusRegion.FIELD,
        caret_visible=True,
    )
    panel = _draw_text_panel_for_tests(font, view, line_gap=line_gap)
    field_x, field_y, content_w = _text_field_origin(
        font, view, line_gap=line_gap, screen_w=1280, screen_h=720
    )
    prefix_w = font.size(view.draft[: view.caret_index])[0]
    assert prefix_w < content_w
    caret_x = field_x + prefix_w
    mid_y = field_y + line_h // 2
    assert panel.get_at((caret_x, mid_y))[:3] == HIGHLIGHT
    assert panel.get_at((caret_x + 1, mid_y))[:3] == HIGHLIGHT


def test_text_modal_single_line_scroll_keeps_caret_in_clip() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    draft = "M" * 80
    modal = ModalHost()
    _prompt_text(modal, initial=draft, single_line=True)
    view = modal.view_state()
    assert view is not None
    assert view.caret_index == len(draft)
    assert view.single_line is True

    field_x, field_y, content_w = _text_field_origin(
        font, view, line_gap=line_gap, screen_w=1280, screen_h=720
    )
    text_w = font.size(draft)[0]
    assert text_w > content_w
    scroll_x = modal_overlay._single_line_scroll_x(
        font, draft, view.caret_index, content_w
    )
    assert scroll_x > 0
    unclipped_caret_x = field_x + text_w
    caret_x = unclipped_caret_x - scroll_x
    assert field_x <= caret_x <= field_x + content_w - modal_overlay._CARET_WIDTH
    assert caret_x != field_x
    assert unclipped_caret_x > field_x + content_w

    panel = _draw_text_panel_for_tests(font, view, line_gap=line_gap)
    mid_y = field_y + line_h // 2
    assert panel.get_at((caret_x, mid_y))[:3] == HIGHLIGHT
    assert panel.get_at((field_x, mid_y))[:3] != HIGHLIGHT
    assert modal_overlay._single_line_scroll_x(font, "", 0, content_w) == 0


def test_text_modal_caret_visible_at_end_when_panel_expands() -> None:
    pygame.init()
    font = _font()
    line_gap = 3
    line_h = font.get_linesize()
    screen_w = 1280
    screen_h = 720
    min_panel_w = modal_overlay._panel_min_width(screen_w)
    wrap_w = modal_overlay._message_max_width(screen_w)
    cta = "Change text..."
    min_content_w = max(
        min_panel_w - modal_overlay._PANEL_PAD_X * 2,
        font.size(cta)[0],
        font.size(modal_overlay._EDITING_HINT)[0],
        modal_overlay._text_buttons_width(font),
    )
    draft = "W"
    while font.size(draft)[0] <= min_content_w:
        draft += "W"
    assert font.size(draft)[0] + modal_overlay._CARET_WIDTH < wrap_w

    modal = ModalHost()
    _prompt_text(modal, cta=cta, initial=draft, single_line=True)
    view = modal.view_state()
    assert view is not None
    assert view.caret_index == len(draft)
    assert view.editing is True
    assert view.caret_visible is True

    panel_w, _ = modal_overlay._measure_text_panel(
        font, view, line_gap=line_gap, screen_w=screen_w, screen_h=screen_h
    )
    assert panel_w > min_panel_w

    def _assert_caret_in_field(state: ModalViewState) -> None:
        panel = _draw_text_panel_for_tests(
            font, state, line_gap=line_gap, screen_w=screen_w, screen_h=screen_h
        )
        field_x, field_y, content_w = _text_field_origin(
            font, state, line_gap=line_gap, screen_w=screen_w, screen_h=screen_h
        )
        prefix_w = font.size(state.draft[: state.caret_index])[0]
        scroll_x = modal_overlay._single_line_scroll_x(
            font, state.draft, state.caret_index, content_w
        )
        caret_x = field_x + prefix_w - scroll_x
        mid_y = field_y + line_h // 2
        assert field_x <= caret_x <= field_x + content_w - modal_overlay._CARET_WIDTH
        assert panel.get_at((caret_x, mid_y))[:3] == HIGHLIGHT
        assert panel.get_at((caret_x + 1, mid_y))[:3] == HIGHLIGHT

    _assert_caret_in_field(view)
    modal.handle_keydown(_keydown(pygame.K_LEFT))
    moved = modal.view_state()
    assert moved is not None
    assert moved.caret_index == len(draft) - 1
    _assert_caret_in_field(moved)
