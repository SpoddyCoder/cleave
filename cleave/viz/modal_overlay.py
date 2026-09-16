"""Centered modal overlay with full-viewport scrim."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from cleave.viz.modal import (
    ModalHost,
    ModalKind,
    ModalLabeledLine,
    ModalViewState,
    TextFocusRegion,
    caret_line_column,
)
from cleave.viz.overlay_primitives import draw_panel_border, overlay_panel_surface
from cleave.viz.text_fit import wrap_text_to_width
from cleave.viz.theme import (
    ACTION,
    BORDER_WIDTH,
    DISABLED,
    FOCUS_ROW_BG_ALPHA,
    HIGHLIGHT,
    LABEL,
    MODAL_SCRIM_ALPHA,
    UI_SCALE,
    VALUE,
    scale_px,
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
_BAR_HEIGHT = scale_px(10, scale=UI_SCALE)
_TEXT_BUTTON_LABELS = ("Confirm", "Cancel")
_TEXT_BUTTON_GAP = scale_px(24, scale=UI_SCALE)
_EDITING_HINT = "press ESC to stop editing"
_CARET_WIDTH = 2


def _message_max_width(screen_w: int) -> int:
    return max(1, int(screen_w * _MESSAGE_MAX_SCREEN_FRACTION))


def _panel_min_width(screen_w: int) -> int:
    return max(1, int(screen_w * _PANEL_MIN_SCREEN_FRACTION))


def _message_lines(
    font: pygame.font.Font, message: str, *, screen_w: int
) -> list[str]:
    return wrap_text_to_width(font, message, _message_max_width(screen_w))


def bind_text_field_wrap(
    host: ModalHost, font: pygame.font.Font, screen_w: int
) -> None:
    """Give the host the same wrap field draw uses (content width cap)."""

    def wrap_draft(draft: str) -> list[str]:
        if not draft:
            return [""]
        lines = _message_lines(font, draft, screen_w=screen_w)
        return lines if lines else [""]

    host.set_text_field_wrap(wrap_draft)


def draw(
    surface: pygame.Surface,
    state: ModalViewState,
    *,
    font: pygame.font.Font,
    line_gap: int | None = None,
    text_alpha: int = 255,
    modal_host: ModalHost | None = None,
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

    if state.kind == ModalKind.TEXT:
        if modal_host is not None:
            bind_text_field_wrap(modal_host, font, sw)
        panel_w, panel_h = _measure_text_panel(
            font, state, line_gap=line_gap, screen_w=sw, screen_h=sh
        )
        panel_x = (sw - panel_w) // 2
        panel_y = (sh - panel_h) // 2
        panel = overlay_panel_surface((panel_w, panel_h))
        _draw_text_panel(
            panel,
            font,
            state,
            line_gap=line_gap,
            screen_w=sw,
            screen_h=sh,
            text_alpha=text_alpha,
            panel_w=panel_w,
        )
        draw_panel_border(panel, alpha=int(255 * text_alpha / 255))
        surface.blit(panel, (panel_x, panel_y))
        return

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

    has_bar = state.progress_fraction is not None
    if has_bar:
        if has_message or has_labeled:
            cur_y += line_h + line_gap
        content_w = panel_w - _PANEL_PAD_X * 2
        _draw_progress_bar(
            panel,
            x=_PANEL_PAD_X,
            y=cur_y,
            width=content_w,
            fraction=state.progress_fraction or 0.0,
            text_alpha=text_alpha,
        )
        cur_y += _BAR_HEIGHT

    if state.options:
        if has_message or has_labeled or has_bar:
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
    has_bar = state.progress_fraction is not None

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

    if has_bar:
        if has_message or has_labeled:
            content_h += line_h + line_gap
        content_h += _BAR_HEIGHT

    if state.options:
        if has_message or has_labeled or has_bar:
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


def _draw_progress_bar(
    surface: pygame.Surface,
    *,
    x: int,
    y: int,
    width: int,
    fraction: float,
    text_alpha: int,
) -> None:
    if text_alpha < 2 or width <= 0:
        return
    bar = overlay_panel_surface((width, _BAR_HEIGHT), fill_alpha=255)
    inner_w = width - 2 * BORDER_WIDTH
    inner_h = _BAR_HEIGHT - 2 * BORDER_WIDTH
    fill_w = min(inner_w, int(round(inner_w * max(0.0, min(1.0, fraction)))))
    if fill_w > 0 and inner_h > 0:
        pygame.draw.rect(
            bar, VALUE, (BORDER_WIDTH, BORDER_WIDTH, fill_w, inner_h)
        )
    draw_panel_border(bar, alpha=int(255 * text_alpha / 255))
    surface.blit(bar, (x, y))


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


def _lines_block_height(count: int, line_h: int, line_gap: int) -> int:
    if count <= 0:
        return 0
    return count * line_h + (count - 1) * line_gap


def _text_cta_lines(state: ModalViewState) -> tuple[str, ...]:
    cta = state.cta if state.cta is not None else ""
    if state.editing:
        return (cta, _EDITING_HINT)
    return (cta,)


def _text_field_lines(
    font: pygame.font.Font,
    state: ModalViewState,
    *,
    screen_w: int,
) -> list[str]:
    draft = state.draft if state.draft is not None else ""
    if state.single_line:
        return [draft]
    if not draft:
        return [""]
    lines = _message_lines(font, draft, screen_w=screen_w)
    return lines if lines else [""]


def _text_button_widths(font: pygame.font.Font) -> tuple[int, int]:
    return (
        font.size(_option_text(_TEXT_BUTTON_LABELS[0]))[0],
        font.size(_option_text(_TEXT_BUTTON_LABELS[1]))[0],
    )


def _text_buttons_width(font: pygame.font.Font) -> int:
    confirm_w, cancel_w = _text_button_widths(font)
    return confirm_w + _TEXT_BUTTON_GAP + cancel_w


def _text_max_field_lines(
    *,
    line_h: int,
    line_gap: int,
    screen_h: int | None,
    cta_line_count: int,
) -> int | None:
    if screen_h is None:
        return None
    max_panel_h = max(1, int(screen_h * _MESSAGE_MAX_SCREEN_FRACTION))
    cta_h = _lines_block_height(cta_line_count, line_h, line_gap)
    section_gap = line_h + line_gap
    overhead = _PANEL_PAD_Y * 2 + cta_h + section_gap * 2 + line_h
    max_field_h = max(line_h, max_panel_h - overhead)
    stride = line_h + line_gap
    return max(1, (max_field_h + line_gap) // stride)


def _visible_field_lines(
    lines: list[str], caret_line: int, max_lines: int | None
) -> tuple[list[str], int]:
    if max_lines is None or len(lines) <= max_lines:
        return lines, max(0, min(caret_line, max(0, len(lines) - 1)))
    caret_line = max(0, min(caret_line, len(lines) - 1))
    start = max(0, min(caret_line - max_lines + 1, len(lines) - max_lines))
    return lines[start : start + max_lines], caret_line - start


def _single_line_scroll_x(
    font: pygame.font.Font,
    line: str,
    column: int,
    content_w: int,
) -> int:
    """Horizontal offset so the caret stays inside the field clip.

    Prefers showing the start of the string until the caret would leave the
    right edge. Empty and non-overflowing lines do not scroll.
    """
    if not line or content_w <= 0:
        return 0
    text_w = font.size(line)[0]
    if text_w + _CARET_WIDTH <= content_w:
        return 0
    column = max(0, min(column, len(line)))
    caret_x = font.size(line[:column])[0]
    visible_caret_w = max(0, content_w - _CARET_WIDTH)
    return max(0, caret_x - visible_caret_w)


def _measure_text_panel(
    font: pygame.font.Font,
    state: ModalViewState,
    *,
    line_gap: int,
    screen_w: int,
    screen_h: int | None = None,
) -> tuple[int, int]:
    line_h = font.get_linesize()
    section_gap = line_h + line_gap
    wrap_w = _message_max_width(screen_w)

    cta_lines = _text_cta_lines(state)
    cta_w = max((font.size(line)[0] for line in cta_lines), default=0)
    cta_h = _lines_block_height(len(cta_lines), line_h, line_gap)

    field_lines = _text_field_lines(font, state, screen_w=screen_w)
    field_w = max((font.size(line)[0] for line in field_lines), default=0)
    field_w += _CARET_WIDTH
    field_w = min(field_w, wrap_w)
    caret_line, _ = caret_line_column(
        state.draft if state.draft is not None else "",
        field_lines,
        state.caret_index,
    )
    max_field_lines = _text_max_field_lines(
        line_h=line_h,
        line_gap=line_gap,
        screen_h=screen_h,
        cta_line_count=len(cta_lines),
    )
    visible_lines, _ = _visible_field_lines(
        field_lines, caret_line, max_field_lines
    )
    field_h = _lines_block_height(len(visible_lines), line_h, line_gap)

    buttons_w = _text_buttons_width(font)
    buttons_h = line_h

    content_w = max(cta_w, field_w, buttons_w)
    content_h = cta_h + section_gap + field_h + section_gap + buttons_h
    return (
        max(content_w + _PANEL_PAD_X * 2, _panel_min_width(screen_w)),
        content_h + _PANEL_PAD_Y * 2,
    )


def _blit_text_line(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    *,
    x: int,
    y: int,
    text_alpha: int,
    clip_w: int | None = None,
    scroll_x: int = 0,
) -> None:
    if text_alpha < 2 or not text:
        return
    line_surf = font.render(text, True, color)
    line_surf.set_alpha(text_alpha)
    scroll_x = max(0, scroll_x)
    blit_x = x - scroll_x
    needs_clip = clip_w is not None and (
        scroll_x > 0 or line_surf.get_width() > clip_w
    )
    if needs_clip:
        prev_clip = surface.get_clip()
        surface.set_clip(pygame.Rect(x, y, clip_w, line_surf.get_height()))
        surface.blit(line_surf, (blit_x, y))
        surface.set_clip(prev_clip)
    else:
        surface.blit(line_surf, (blit_x, y))


def _draw_field_caret(
    panel: pygame.Surface,
    font: pygame.font.Font,
    *,
    field_x: int,
    field_y: int,
    line: str,
    column: int,
    line_index: int,
    line_h: int,
    line_gap: int,
    text_alpha: int,
    scroll_x: int = 0,
) -> None:
    if text_alpha < 2:
        return
    column = max(0, min(column, len(line)))
    x = field_x + font.size(line[:column])[0] - max(0, scroll_x)
    y = field_y + line_index * (line_h + line_gap)
    pygame.draw.rect(panel, HIGHLIGHT, (x, y, _CARET_WIDTH, line_h))


def _draw_text_buttons(
    panel: pygame.Surface,
    font: pygame.font.Font,
    state: ModalViewState,
    *,
    y: int,
    panel_w: int,
    text_alpha: int,
) -> None:
    line_h = font.get_linesize()
    confirm_w, cancel_w = _text_button_widths(font)
    total_w = confirm_w + _TEXT_BUTTON_GAP + cancel_w
    content_w = panel_w - _PANEL_PAD_X * 2
    row_x = _PANEL_PAD_X + max(0, (content_w - total_w) // 2)
    buttons_focused = state.focus_region == TextFocusRegion.BUTTONS
    field_focused = state.focus_region == TextFocusRegion.FIELD
    widths = (confirm_w, cancel_w)
    x = row_x
    for index, label in enumerate(_TEXT_BUTTON_LABELS):
        width = widths[index]
        focused = buttons_focused and state.button_index == index
        if focused:
            color = HIGHLIGHT
        elif field_focused:
            color = DISABLED
        else:
            color = VALUE
        if focused and text_alpha >= 2:
            tint_alpha = int(FOCUS_ROW_BG_ALPHA * text_alpha / 255)
            blit_tint(
                panel,
                (x, y, width, line_h),
                HIGHLIGHT,
                alpha=tint_alpha,
            )
        _blit_text_line(
            panel,
            font,
            _option_text(label),
            color,
            x=x,
            y=y,
            text_alpha=text_alpha,
        )
        x += width + _TEXT_BUTTON_GAP


def _draw_text_panel(
    panel: pygame.Surface,
    font: pygame.font.Font,
    state: ModalViewState,
    *,
    line_gap: int,
    screen_w: int,
    text_alpha: int,
    panel_w: int,
    screen_h: int | None = None,
) -> None:
    line_h = font.get_linesize()
    section_gap = line_h + line_gap
    x = _PANEL_PAD_X
    content_w = panel_w - _PANEL_PAD_X * 2
    cur_y = _PANEL_PAD_Y

    cta_lines = _text_cta_lines(state)
    for index, line in enumerate(cta_lines):
        color = DISABLED if index > 0 else LABEL
        _blit_text_line(
            panel,
            font,
            line,
            color,
            x=x,
            y=cur_y,
            text_alpha=text_alpha,
            clip_w=content_w,
        )
        cur_y += line_h
        if index + 1 < len(cta_lines):
            cur_y += line_gap
    cur_y += section_gap

    draft = state.draft if state.draft is not None else ""
    field_lines = _text_field_lines(font, state, screen_w=screen_w)
    caret_line, caret_col = caret_line_column(draft, field_lines, state.caret_index)
    max_field_lines = _text_max_field_lines(
        line_h=line_h,
        line_gap=line_gap,
        screen_h=screen_h,
        cta_line_count=len(cta_lines),
    )
    visible_lines, visible_caret_line = _visible_field_lines(
        field_lines, caret_line, max_field_lines
    )
    field_h = _lines_block_height(len(visible_lines), line_h, line_gap)
    field_y = cur_y
    scroll_x = 0
    if state.single_line:
        field_line = visible_lines[0] if visible_lines else ""
        scroll_x = _single_line_scroll_x(font, field_line, caret_col, content_w)

    navigating_field = (
        not state.editing and state.focus_region == TextFocusRegion.FIELD
    )
    if navigating_field and text_alpha >= 2:
        tint_alpha = int(FOCUS_ROW_BG_ALPHA * text_alpha / 255)
        blit_tint(
            panel,
            _focus_highlight_rect(
                font,
                panel_width=panel.get_width(),
                y=field_y,
                line_h=field_h,
            ),
            HIGHLIGHT,
            alpha=tint_alpha,
        )

    for index, line in enumerate(visible_lines):
        _blit_text_line(
            panel,
            font,
            line,
            VALUE,
            x=x,
            y=cur_y,
            text_alpha=text_alpha,
            clip_w=content_w,
            scroll_x=scroll_x,
        )
        cur_y += line_h
        if index + 1 < len(visible_lines):
            cur_y += line_gap

    if state.editing and state.caret_visible:
        caret_line_text = (
            visible_lines[visible_caret_line] if visible_lines else ""
        )
        prev_clip = panel.get_clip()
        panel.set_clip(pygame.Rect(x, field_y, content_w, field_h))
        _draw_field_caret(
            panel,
            font,
            field_x=x,
            field_y=field_y,
            line=caret_line_text,
            column=caret_col,
            line_index=visible_caret_line,
            line_h=line_h,
            line_gap=line_gap,
            text_alpha=text_alpha,
            scroll_x=scroll_x,
        )
        panel.set_clip(prev_clip)

    cur_y = field_y + field_h + section_gap
    _draw_text_buttons(
        panel,
        font,
        state,
        y=cur_y,
        panel_w=panel_w,
        text_alpha=text_alpha,
    )
