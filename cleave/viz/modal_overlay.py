"""Centered modal overlay with full-viewport scrim."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from cleave.viz.modal import ModalLabeledLine, ModalViewState
from cleave.viz.overlay_primitives import draw_panel_border, overlay_panel_surface
from cleave.viz.text_fit import wrap_text_to_width
from cleave.viz.theme import (
    ACTION,
    FOCUS_ROW_BG_ALPHA,
    HIGHLIGHT,
    LABEL,
    MODAL_SCRIM_ALPHA,
    VALUE,
    tuning_ui_metrics,
)
from cleave.viz.ui_tint import blit_tint

# Modal title/message content width cap as a fraction of the viewport.
_MESSAGE_MAX_SCREEN_FRACTION = 0.5
# Modal panel minimum width as a fraction of the viewport.
_PANEL_MIN_SCREEN_FRACTION = 0.2


_tuning_ui = tuning_ui_metrics()
_PANEL_PAD_X = _tuning_ui.modal_panel_pad_x
_PANEL_PAD_Y = _tuning_ui.modal_panel_pad_y


def _message_max_width(screen_w: int) -> int:
    return max(1, int(screen_w * _MESSAGE_MAX_SCREEN_FRACTION))


def _panel_min_width(screen_w: int) -> int:
    return max(1, int(screen_w * _PANEL_MIN_SCREEN_FRACTION))


def _message_lines(
    font: pygame.font.Font, message: str, *, screen_w: int
) -> list[str]:
    return wrap_text_to_width(font, message, _message_max_width(screen_w))


def draw(
    surface: pygame.Surface,
    state: ModalViewState,
    *,
    font: pygame.font.Font,
    line_gap: int | None = None,
    text_alpha: int = 255,
) -> None:
    """Draw a centered modal with full-viewport scrim."""
    if text_alpha < 2:
        return
    if line_gap is None:
        line_gap = _tuning_ui.line_gap

    sw, sh = surface.get_width(), surface.get_height()
    scrim = pygame.Surface((sw, sh), pygame.SRCALPHA)
    scrim.fill((0, 0, 0, MODAL_SCRIM_ALPHA))
    surface.blit(scrim, (0, 0))

    panel_w, panel_h = _measure_panel(
        font, state, line_gap=line_gap, screen_w=sw
    )
    panel_x = (sw - panel_w) // 2
    panel_y = (sh - panel_h) // 2
    panel = overlay_panel_surface((panel_w, panel_h))

    cur_y = _PANEL_PAD_Y
    line_h = font.get_linesize()
    has_message = state.message is not None
    has_labeled = bool(state.labeled_lines)
    if has_message:
        cur_y = _draw_message(
            panel,
            font,
            x=_PANEL_PAD_X,
            y=cur_y,
            message=state.message,
            text_alpha=text_alpha,
            line_gap=line_gap,
            screen_w=sw,
        )
    if has_labeled:
        if has_message:
            cur_y += line_h + line_gap
        cur_y = _draw_labeled_lines(
            panel,
            font,
            x=_PANEL_PAD_X,
            y=cur_y,
            lines=state.labeled_lines,
            text_alpha=text_alpha,
            line_gap=line_gap,
        )

    if state.options:
        if has_message or has_labeled:
            cur_y += line_h + line_gap
        content_w = panel_w - _PANEL_PAD_X * 2
        _draw_options(
            panel,
            font,
            x=_PANEL_PAD_X,
            content_width=content_w,
            y=cur_y,
            labels=state.options,
            focus_index=state.focus_index,
            text_alpha=text_alpha,
            line_gap=line_gap,
        )

    draw_panel_border(panel, alpha=int(255 * text_alpha / 255))

    surface.blit(panel, (panel_x, panel_y))


@dataclass(frozen=True)
class InfoPanelViewState:
    title_lines: tuple[str, ...]
    body_lines: tuple[str, ...]
    footer_line: str | None = None


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
        max(content_w + _PANEL_PAD_X * 2, _panel_min_width(screen_w)),
        content_h + _PANEL_PAD_Y * 2,
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

    cur_y = _PANEL_PAD_Y
    line_h = font.get_linesize()

    def _draw_lines(lines: tuple[str, ...], color: tuple[int, int, int]) -> None:
        nonlocal cur_y
        for index, line in enumerate(lines):
            line_surf = font.render(line, True, color)
            line_surf.set_alpha(text_alpha)
            panel.blit(line_surf, (_PANEL_PAD_X, cur_y))
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
        panel.blit(footer_surf, (_PANEL_PAD_X, cur_y))

    draw_panel_border(panel, alpha=int(255 * text_alpha / 255))

    surface.blit(panel, (panel_x, panel_y))


def _measure_panel(
    font: pygame.font.Font,
    state: ModalViewState,
    *,
    line_gap: int,
    screen_w: int,
) -> tuple[int, int]:
    line_h = font.get_linesize()
    content_w = 0
    content_h = 0
    has_message = state.message is not None
    has_labeled = bool(state.labeled_lines)

    if has_message:
        lines = _message_lines(font, state.message, screen_w=screen_w)
        msg_w = max((font.size(line)[0] for line in lines), default=0)
        content_w = max(content_w, msg_w)
        content_h += len(lines) * line_h + max(0, len(lines) - 1) * line_gap

    if has_labeled:
        if has_message:
            content_h += line_h + line_gap
        labeled_w, labeled_h = _measure_labeled_lines(
            font, state.labeled_lines, line_gap=line_gap
        )
        content_w = max(content_w, labeled_w)
        content_h += labeled_h

    if state.options:
        if has_message or has_labeled:
            content_h += line_h + line_gap
        options_w, options_h = _measure_options(font, state.options, line_gap=line_gap)
        content_w = max(content_w, options_w)
        content_h += options_h

    return (
        max(content_w + _PANEL_PAD_X * 2, _panel_min_width(screen_w)),
        content_h + _PANEL_PAD_Y * 2,
    )


def _measure_labeled_lines(
    font: pygame.font.Font,
    lines: tuple[ModalLabeledLine, ...],
    *,
    line_gap: int,
) -> tuple[int, int]:
    line_h = font.get_linesize()
    if not lines:
        return 0, 0
    widths = [font.size(line.display_text())[0] for line in lines]
    count = len(lines)
    total_h = count * line_h + max(0, count - 1) * line_gap
    return max(widths), total_h


def _draw_labeled_lines(
    surface: pygame.Surface,
    font: pygame.font.Font,
    *,
    x: int,
    y: int,
    lines: tuple[ModalLabeledLine, ...],
    text_alpha: int,
    line_gap: int,
) -> int:
    line_h = font.get_linesize()
    cur_y = y
    for index, line in enumerate(lines):
        prefix_surf = font.render(line.prefix(), True, LABEL)
        value_surf = font.render(line.value, True, VALUE)
        if text_alpha >= 2:
            prefix_surf.set_alpha(text_alpha)
            value_surf.set_alpha(text_alpha)
            surface.blit(prefix_surf, (x, cur_y))
            surface.blit(value_surf, (x + prefix_surf.get_width(), cur_y))
        cur_y += line_h
        if index + 1 < len(lines):
            cur_y += line_gap
    return cur_y


def _option_text(label: str) -> str:
    return f"  {label}  "


def _measure_options(
    font: pygame.font.Font,
    labels: tuple[str, ...],
    *,
    line_gap: int,
) -> tuple[int, int]:
    line_h = font.get_linesize()
    widths = [font.size(_option_text(label))[0] for label in labels]
    total_w = max(widths) if widths else 0
    count = len(labels)
    total_h = count * line_h + max(0, count - 1) * line_gap
    return total_w, total_h


def _draw_message(
    surface: pygame.Surface,
    font: pygame.font.Font,
    *,
    x: int,
    y: int,
    message: str,
    text_alpha: int,
    line_gap: int,
    screen_w: int,
) -> int:
    line_h = font.get_linesize()
    cur_y = y
    lines = _message_lines(font, message, screen_w=screen_w)
    for index, line in enumerate(lines):
        msg_surf = font.render(line, True, LABEL)
        msg_surf.set_alpha(text_alpha)
        surface.blit(msg_surf, (x, cur_y))
        cur_y += line_h
        if index + 1 < len(lines):
            cur_y += line_gap
    return cur_y


def _focus_highlight_rect(
    font: pygame.font.Font,
    *,
    panel_width: int,
    y: int,
    line_h: int,
) -> tuple[int, int, int, int]:
    """Full panel width minus one character of padding on each side."""
    char_w = max(1, font.size("M")[0])
    highlight_w = max(0, panel_width - 2 * char_w)
    return (char_w, y, highlight_w, line_h)


def _draw_options(
    surface: pygame.Surface,
    font: pygame.font.Font,
    *,
    x: int,
    content_width: int,
    y: int,
    labels: tuple[str, ...],
    focus_index: int,
    text_alpha: int,
    line_gap: int,
) -> None:
    options_w, _ = _measure_options(font, labels, line_gap=line_gap)
    option_x = x + max(0, (content_width - options_w) // 2)
    line_h = font.get_linesize()
    cur_y = y
    for index, label in enumerate(labels):
        focused = index == focus_index
        color = HIGHLIGHT if focused else VALUE
        text = _option_text(label)
        text_w = font.size(text)[0]
        text_x = option_x + max(0, (options_w - text_w) // 2)
        if focused and text_alpha >= 2:
            tint_alpha = int(FOCUS_ROW_BG_ALPHA * text_alpha / 255)
            blit_tint(
                surface,
                _focus_highlight_rect(
                    font,
                    panel_width=surface.get_width(),
                    y=cur_y,
                    line_h=line_h,
                ),
                HIGHLIGHT,
                alpha=tint_alpha,
            )
        option_surf = font.render(text, True, color)
        if text_alpha >= 2:
            option_surf.set_alpha(text_alpha)
            surface.blit(option_surf, (text_x, cur_y))
        cur_y += line_h + line_gap
