"""Draw the file picker view state as a centered overlay panel.

Same chrome rules as the modal: `overlay_primitives` plus theme roles, and no
import of `tuning_panel_draw` or the live help content.
"""

from __future__ import annotations

import pygame

from cleave.viz.file_picker import (
    PickerFocus,
    PickerRow,
    PickerRowKind,
    PickerViewState,
)
from cleave.viz.overlay_primitives import draw_panel_border, overlay_panel_surface
from cleave.viz.text_fit import fit_path_label_to_width, fit_text_to_width
from cleave.viz.theme import (
    ACTION,
    DISABLED,
    ERROR_NOTIFICATION,
    FOCUS_ROW_BG_ALPHA,
    HIGHLIGHT,
    LABEL,
    MODAL_SCRIM_ALPHA,
    VALUE,
    tuning_ui_metrics,
)
from cleave.viz.ui_tint import blit_tint

# Panel size as a fraction of the viewport.
_PANEL_WIDTH_FRACTION = 0.6
_PANEL_HEIGHT_FRACTION = 0.7

_PROJECT_SUFFIX = "  [project]"
_DIRECTORY_SUFFIX = "/"
_SHORTCUT_SEPARATOR = "   "
_SHORTCUT_HIGHLIGHT_PAD = 4

_tuning_ui = tuning_ui_metrics()
_PANEL_PAD_X = _tuning_ui.modal_panel_pad_x
_PANEL_PAD_Y = _tuning_ui.modal_panel_pad_y


def visible_slice(total: int, selected: int, capacity: int) -> tuple[int, int]:
    """Return the [start, end) row window that keeps *selected* on screen."""
    if capacity <= 0 or total <= 0:
        return 0, 0
    if total <= capacity:
        return 0, total
    start = min(max(0, selected - capacity // 2), total - capacity)
    return start, start + capacity


def location_text(font: pygame.font.Font, location: str, content_w: int) -> str:
    """Fit the browse path, keeping the tail so the current folder stays visible."""
    return fit_path_label_to_width(font, location, content_w)


def row_text(row: PickerRow) -> str:
    """Return the display text for *row*, including its kind marker."""
    if row.kind is PickerRowKind.PROJECT:
        return f"{row.label}{_DIRECTORY_SUFFIX}{_PROJECT_SUFFIX}"
    if row.kind is PickerRowKind.DIRECTORY:
        return f"{row.label}{_DIRECTORY_SUFFIX}"
    return row.label


def _row_color(row: PickerRow) -> tuple[int, int, int]:
    if row.kind is PickerRowKind.NOTE:
        return DISABLED
    if row.kind in (PickerRowKind.PARENT, PickerRowKind.DRIVE):
        return ACTION
    if row.kind is PickerRowKind.PROJECT:
        return HIGHLIGHT
    return VALUE


def shortcut_chip_text(label: str) -> str:
    """Return the bracketed header label for a shortcut."""
    return f"[{label}]"


def shortcut_is_selected(state: PickerViewState, index: int) -> bool:
    """True when the header has focus and *index* is the highlighted shortcut."""
    return state.focus is PickerFocus.SHORTCUTS and index == state.selected_shortcut


def shortcut_is_current(state: PickerViewState, index: int) -> bool:
    """True when *index* is the shortcut for the directory being listed."""
    return state.active_shortcut == index


def shortcut_chip_layout(
    font: pygame.font.Font,
    state: PickerViewState,
    *,
    x: int,
    content_w: int,
) -> tuple[tuple[int, str, int, int], ...]:
    """Return ``(index, text, x, width)`` for each shortcut that fits on the line."""
    chips: list[tuple[int, str, int, int]] = []
    cursor = x
    limit = x + content_w
    gap = font.size(_SHORTCUT_SEPARATOR)[0]
    for index, shortcut in enumerate(state.shortcuts):
        text = shortcut_chip_text(shortcut.label)
        width = font.size(text)[0]
        if cursor > x:
            cursor += gap
        if cursor + width > limit:
            break
        chips.append((index, text, cursor, width))
        cursor += width
    return tuple(chips)


def legend_item_prefix(key: str) -> str:
    """Return the LABEL-colored help prefix, including the colon and space."""
    return f"{key}: "


def legend_item_width(font: pygame.font.Font, key: str, label: str) -> int:
    """Return the pixel width of one ``key: label`` help item."""
    return font.size(f"{legend_item_prefix(key)}{label}")[0]


def legend_rows(
    font: pygame.font.Font,
    entries: tuple[tuple[str, str], ...],
    content_w: int,
) -> tuple[tuple[tuple[str, str], ...], ...]:
    """Pack help items onto as many lines as the panel width needs."""
    gap = font.size(_SHORTCUT_SEPARATOR)[0]
    rows: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    used = 0
    for entry in entries:
        width = legend_item_width(font, entry[0], entry[1])
        extra = 0 if not current else gap
        if current and used + extra + width > content_w:
            rows.append(current)
            current = [entry]
            used = width
            continue
        used += extra + width
        current.append(entry)
    if current:
        rows.append(current)
    return tuple(tuple(row) for row in rows)


def draw(
    surface: pygame.Surface,
    state: PickerViewState,
    *,
    font: pygame.font.Font,
    line_gap: int | None = None,
) -> None:
    """Draw the picker centered on *surface* over a full-viewport scrim."""
    if line_gap is None:
        line_gap = _tuning_ui.line_gap

    screen_w, screen_h = surface.get_width(), surface.get_height()
    scrim = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    scrim.fill((0, 0, 0, MODAL_SCRIM_ALPHA))
    surface.blit(scrim, (0, 0))

    panel_w = max(1, int(screen_w * _PANEL_WIDTH_FRACTION))
    panel_h = max(1, int(screen_h * _PANEL_HEIGHT_FRACTION))
    panel = overlay_panel_surface((panel_w, panel_h))
    content_w = max(1, panel_w - _PANEL_PAD_X * 2)
    line_h = font.get_linesize()
    step = line_h + line_gap

    cur_y = _PANEL_PAD_Y

    def _line(
        text: str,
        color: tuple[int, int, int],
        *,
        y: int,
        fit=fit_text_to_width,
    ) -> None:
        rendered = font.render(fit(font, text, content_w), True, color)
        panel.blit(rendered, (_PANEL_PAD_X, y))

    _line(state.title, LABEL, y=cur_y)
    cur_y += step
    _draw_shortcuts(
        panel,
        state,
        font=font,
        x=_PANEL_PAD_X,
        y=cur_y,
        content_w=content_w,
        line_h=line_h,
    )
    cur_y += step * 2
    _line(state.location, VALUE, y=cur_y, fit=location_text)
    cur_y += step

    footer = legend_rows(font, state.legend, content_w)
    footer_lines = len(footer) + (1 if state.status else 0)
    list_top = cur_y
    list_bottom = panel_h - _PANEL_PAD_Y - footer_lines * step
    capacity = max(1, int((list_bottom - list_top) // step))
    start, end = visible_slice(len(state.rows), state.selected_index, capacity)

    for index in range(start, end):
        row = state.rows[index]
        selected = (
            index == state.selected_index and state.focus is PickerFocus.LIST
        )
        if selected:
            blit_tint(
                panel,
                (_PANEL_PAD_X, cur_y, content_w, line_h),
                HIGHLIGHT,
                alpha=FOCUS_ROW_BG_ALPHA,
            )
        _line(row_text(row), HIGHLIGHT if selected else _row_color(row), y=cur_y)
        cur_y += step

    footer_y = panel_h - _PANEL_PAD_Y - footer_lines * step
    if state.status:
        _line(state.status, ERROR_NOTIFICATION, y=footer_y)
        footer_y += step
    for row in footer:
        _draw_legend_row(panel, font, row, x=_PANEL_PAD_X, y=footer_y)
        footer_y += step

    draw_panel_border(panel)
    surface.blit(panel, ((screen_w - panel_w) // 2, (screen_h - panel_h) // 2))


def _draw_shortcuts(
    surface: pygame.Surface,
    state: PickerViewState,
    *,
    font: pygame.font.Font,
    x: int,
    y: int,
    content_w: int,
    line_h: int,
) -> None:
    for index, text, chip_x, width in shortcut_chip_layout(
        font, state, x=x, content_w=content_w
    ):
        selected = shortcut_is_selected(state, index)
        current = shortcut_is_current(state, index)
        if selected:
            blit_tint(
                surface,
                (
                    chip_x - _SHORTCUT_HIGHLIGHT_PAD,
                    y,
                    width + _SHORTCUT_HIGHLIGHT_PAD * 2,
                    line_h,
                ),
                HIGHLIGHT,
                alpha=FOCUS_ROW_BG_ALPHA,
            )
        color = HIGHLIGHT if selected or current else ACTION
        rendered = font.render(text, True, color)
        surface.blit(rendered, (chip_x, y))


def _draw_legend_row(
    surface: pygame.Surface,
    font: pygame.font.Font,
    entries: tuple[tuple[str, str], ...],
    *,
    x: int,
    y: int,
) -> None:
    cursor = x
    gap = font.size(_SHORTCUT_SEPARATOR)[0]
    for index, (key, label) in enumerate(entries):
        if index:
            cursor += gap
        prefix_surf = font.render(legend_item_prefix(key), True, LABEL)
        value_surf = font.render(label, True, VALUE)
        surface.blit(prefix_surf, (cursor, y))
        cursor += prefix_surf.get_width()
        surface.blit(value_surf, (cursor, y))
        cursor += value_surf.get_width()
