"""Centered modal overlay with full-viewport scrim."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from cleave.viz.modal import ModalViewState, modal_options_vertical
from cleave.viz.text_fit import wrap_text_to_width
from cleave.viz.theme import (
    ACTION,
    BACKGROUND,
    BACKGROUND_ALPHA,
    BORDER_COLOR,
    BORDER_WIDTH,
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


def draw_rect(
    rect: tuple[int, int, int, int],
    surface: pygame.Surface,
) -> tuple[int, int, int, int] | None:
    """Intersection of rect with surface bounds (same as overlay.clip_rect_to_surface)."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return None
    sw, sh = surface.get_width(), surface.get_height()
    left = max(x, 0)
    top = max(y, 0)
    right = min(x + w, sw)
    bottom = min(y + h, sh)
    clip_w = right - left
    clip_h = bottom - top
    if clip_w <= 0 or clip_h <= 0:
        return None
    return (left, top, clip_w, clip_h)


_tuning_ui = tuning_ui_metrics()
_OPTION_GAP = _tuning_ui.modal_option_gap
_PANEL_PAD_X = _tuning_ui.modal_panel_pad_x
_PANEL_PAD_Y = _tuning_ui.modal_panel_pad_y


def _message_max_width(screen_w: int) -> int:
    return max(1, int(screen_w * _MESSAGE_MAX_SCREEN_FRACTION))


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
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((*BACKGROUND, BACKGROUND_ALPHA))

    cur_y = _PANEL_PAD_Y
    line_h = font.get_linesize()
    if state.message is not None:
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

    if state.options:
        if state.message is not None:
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

    if BORDER_WIDTH > 0:
        border_alpha = int(255 * text_alpha / 255)
        if border_alpha >= 2:
            pygame.draw.rect(
                panel,
                (*BORDER_COLOR, border_alpha),
                (0, 0, panel_w, panel_h),
                BORDER_WIDTH,
            )

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
        content_w + _PANEL_PAD_X * 2,
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
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((*BACKGROUND, BACKGROUND_ALPHA))

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

    if BORDER_WIDTH > 0:
        border_alpha = int(255 * text_alpha / 255)
        if border_alpha >= 2:
            pygame.draw.rect(
                panel,
                (*BORDER_COLOR, border_alpha),
                (0, 0, panel_w, panel_h),
                BORDER_WIDTH,
            )

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

    if state.message is not None:
        lines = _message_lines(font, state.message, screen_w=screen_w)
        msg_w = max((font.size(line)[0] for line in lines), default=0)
        content_w = max(content_w, msg_w)
        content_h += len(lines) * line_h + max(0, len(lines) - 1) * line_gap

    if state.options:
        if state.message is not None:
            content_h += line_h + line_gap
        options_w, options_h = _measure_options(font, state.options, line_gap=line_gap)
        content_w = max(content_w, options_w)
        content_h += options_h

    return (
        content_w + _PANEL_PAD_X * 2,
        content_h + _PANEL_PAD_Y * 2,
    )


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
    if modal_options_vertical(len(labels)):
        total_w = max(widths) if widths else 0
        count = len(labels)
        total_h = count * line_h + max(0, count - 1) * line_gap
        return total_w, total_h
    total_w = sum(widths) + _OPTION_GAP * max(0, len(labels) - 1)
    return total_w, line_h


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
    vertical = modal_options_vertical(len(labels))
    cur_y = y
    for index, label in enumerate(labels):
        focused = index == focus_index
        color = HIGHLIGHT if focused else VALUE
        text = _option_text(label)
        text_w = font.size(text)[0]
        row_x = option_x
        if vertical:
            row_x = option_x + max(0, (options_w - text_w) // 2)
        if focused and text_alpha >= 2:
            tint_alpha = int(FOCUS_ROW_BG_ALPHA * text_alpha / 255)
            blit_tint(
                surface,
                (row_x, cur_y, text_w, line_h),
                HIGHLIGHT,
                alpha=tint_alpha,
            )
        option_surf = font.render(text, True, color)
        if text_alpha >= 2:
            option_surf.set_alpha(text_alpha)
            surface.blit(option_surf, (row_x, cur_y))
        if vertical:
            cur_y += line_h + line_gap
        else:
            option_x += option_surf.get_width() + _OPTION_GAP
