"""Centered modal overlay with full-viewport scrim."""

from __future__ import annotations

import pygame

from cleave.viz.modal import ModalViewState
from cleave.viz.theme import (
    BACKGROUND,
    BACKGROUND_ALPHA,
    BORDER_COLOR,
    BORDER_WIDTH,
    DISABLED,
    HIGHLIGHT,
    MODAL_SCRIM_ALPHA,
    VALUE,
    tuning_ui_metrics,
)


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

    panel_w, panel_h = _measure_panel(font, state, line_gap=line_gap)
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
        )

    if state.options:
        if state.message is not None:
            cur_y += line_h + line_gap
        _draw_options(
            panel,
            font,
            x=_PANEL_PAD_X,
            y=cur_y,
            labels=state.options,
            focus_index=state.focus_index,
            text_alpha=text_alpha,
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


def _measure_panel(
    font: pygame.font.Font,
    state: ModalViewState,
    *,
    line_gap: int,
) -> tuple[int, int]:
    line_h = font.get_linesize()
    content_w = 0
    content_h = 0

    if state.message is not None:
        msg_w = font.size(state.message)[0]
        content_w = max(content_w, msg_w)
        content_h += line_h

    if state.options:
        if state.message is not None:
            content_h += line_h + line_gap
        options_w, options_h = _measure_options(font, state.options)
        content_w = max(content_w, options_w)
        content_h += options_h

    return (
        content_w + _PANEL_PAD_X * 2,
        content_h + _PANEL_PAD_Y * 2,
    )


def _measure_options(
    font: pygame.font.Font,
    labels: tuple[str, ...],
) -> tuple[int, int]:
    line_h = font.get_linesize()
    widths = [font.size(f"> {label}")[0] for label in labels]
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
) -> int:
    line_h = font.get_linesize()
    msg_surf = font.render(message, True, VALUE)
    msg_surf.set_alpha(text_alpha)
    surface.blit(msg_surf, (x, y))
    return y + line_h


def _draw_options(
    surface: pygame.Surface,
    font: pygame.font.Font,
    *,
    x: int,
    y: int,
    labels: tuple[str, ...],
    focus_index: int,
    text_alpha: int,
) -> None:
    option_x = x
    for index, label in enumerate(labels):
        focused = index == focus_index
        color = HIGHLIGHT if focused else DISABLED
        prefix = ">" if focused else " "
        option_surf = font.render(f"{prefix} {label}", True, color)
        if text_alpha >= 2:
            option_surf.set_alpha(text_alpha)
            surface.blit(option_surf, (option_x, y))
        option_x += option_surf.get_width() + _OPTION_GAP
