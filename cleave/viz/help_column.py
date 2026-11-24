"""Scrollable help column drawn inside the shell help window."""

from __future__ import annotations

import math

from imgui_bundle import imgui

from cleave.viz.help_content import (
    DescriptionSection,
    HelpContent,
    HelpEntry,
    HelpSection,
    control_groups,
)
from cleave.viz.imgui_theme import padded_row_spacing_y, rgba
from cleave.viz.theme import palette
from cleave.viz.title_bar import paint_title_bar


def _groups(
    section: HelpContent,
) -> tuple[tuple[str | None, tuple[HelpEntry, ...]], ...]:
    """Entries under their sub-heading; a description's options have none."""
    if isinstance(section, HelpSection):
        return control_groups(section)
    return ((None, section.entries),) if section.entries else ()


def help_column_text(sections: tuple[HelpContent, ...]) -> str:
    """Plain text of the titles, lines, sub-headings, keys, and descriptions the column draws."""
    parts: list[str] = []
    for section in sections:
        parts.append(section.title)
        if isinstance(section, DescriptionSection):
            parts.extend(section.lines)
        for subheading, entries in _groups(section):
            if subheading is not None:
                parts.append(subheading)
            for key, description in entries:
                parts.append(key)
                parts.append(description)
    return "\n".join(parts)


def draw_help_column(sections: tuple[HelpContent, ...]) -> None:
    """Draw *sections* in the current ImGui window."""
    if not sections:
        return
    start_x = imgui.get_cursor_pos().x
    avail = max(1.0, imgui.get_content_region_avail().x)
    wrap_x = start_x + avail
    key_w = 0.0
    for section in sections:
        for _subheading, entries in _groups(section):
            for key, _description in entries:
                key_w = max(key_w, imgui.calc_text_size(key).x)
    gap = imgui.calc_text_size("  ").x
    for index, section in enumerate(sections):
        if index:
            imgui.dummy(imgui.ImVec2(0.0, imgui.get_text_line_height()))
        _draw_heading(section.title, wrap_x)
        if isinstance(section, DescriptionSection):
            for position, line in enumerate(section.lines):
                if position:
                    # Half a line between paragraphs.
                    imgui.dummy(imgui.ImVec2(0.0, imgui.get_text_line_height() * 0.5))
                _draw_wrapped(line, palette().value, wrap_x)
            if section.lines and section.entries:
                imgui.dummy(imgui.ImVec2(0.0, imgui.get_text_line_height()))
        for position, (subheading, entries) in enumerate(_groups(section)):
            if position:
                # Half a line between sub-headings.
                imgui.dummy(imgui.ImVec2(0.0, imgui.get_text_line_height() * 0.5))
            key_x = start_x
            if subheading is not None:
                _draw_wrapped(subheading, palette().subheading, wrap_x)
                key_x += gap
            for key, description in entries:
                _draw_key_value(key, description, key_x, key_w, gap, wrap_x)


def _draw_heading(text: str, wrap_x: float) -> None:
    """A section title in value on a title bar the column's full width.

    The bar is a padded row's height per line and reaches into the window
    padding as far as the window clips its content.
    """
    pad_y = padded_row_spacing_y() * 0.5
    pad_x = math.floor(imgui.get_style().window_padding.x * 0.5)
    local = imgui.get_cursor_pos()
    imgui.set_cursor_pos_y(local.y + pad_y)
    origin = imgui.get_cursor_screen_pos()
    width = max(1.0, wrap_x - local.x)
    text_h = imgui.calc_text_size(text, wrap_width=width).y
    paint_title_bar(
        imgui.get_window_draw_list(),
        origin.x - pad_x,
        origin.y - pad_y,
        origin.x + width + pad_x,
        origin.y + text_h + pad_y,
    )
    _draw_wrapped(text, palette().on_accent, wrap_x)
    imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() + pad_y)


def _draw_wrapped(text: str, color: tuple[int, int, int], wrap_x: float) -> None:
    imgui.push_text_wrap_pos(wrap_x)
    imgui.text_colored(rgba(color), text)
    imgui.pop_text_wrap_pos()


def _draw_key_value(
    key: str,
    description: str,
    key_x: float,
    key_w: float,
    gap: float,
    wrap_x: float,
) -> None:
    row_y = imgui.get_cursor_pos().y
    imgui.set_cursor_pos(imgui.ImVec2(key_x, row_y))
    imgui.text_colored(rgba(palette().label), key)
    imgui.set_cursor_pos(imgui.ImVec2(key_x + key_w + gap, row_y))
    _draw_wrapped(description, palette().value, wrap_x)
