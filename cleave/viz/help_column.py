"""Scrollable help column drawn inside the shell help window."""

from __future__ import annotations

from imgui_bundle import imgui

from cleave.viz.help_content import DescriptionSection, HelpContent
from cleave.viz.imgui_theme import rgba
from cleave.viz.theme import HIGHLIGHT, LABEL, VALUE


def help_column_text(sections: tuple[HelpContent, ...]) -> str:
    """Plain text of the titles, lines, keys, and descriptions the column draws."""
    parts: list[str] = []
    for section in sections:
        parts.append(section.title)
        if isinstance(section, DescriptionSection):
            parts.extend(section.lines)
        for key, description in section.entries:
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
        for key, _description in section.entries:
            key_w = max(key_w, imgui.calc_text_size(key).x)
    gap = imgui.calc_text_size("  ").x
    for index, section in enumerate(sections):
        if index:
            imgui.spacing()
        _draw_wrapped(section.title, HIGHLIGHT, wrap_x)
        if isinstance(section, DescriptionSection):
            for line in section.lines:
                _draw_wrapped(line, VALUE, wrap_x)
        for key, description in section.entries:
            _draw_key_value(key, description, start_x, key_w, gap, wrap_x)


def _draw_wrapped(text: str, color: tuple[int, int, int], wrap_x: float) -> None:
    imgui.push_text_wrap_pos(wrap_x)
    imgui.text_colored(rgba(color), text)
    imgui.pop_text_wrap_pos()


def _draw_key_value(
    key: str,
    description: str,
    start_x: float,
    key_w: float,
    gap: float,
    wrap_x: float,
) -> None:
    row_y = imgui.get_cursor_pos().y
    imgui.text_colored(rgba(LABEL), key)
    imgui.set_cursor_pos(imgui.ImVec2(start_x + key_w + gap, row_y))
    _draw_wrapped(description, VALUE, wrap_x)
