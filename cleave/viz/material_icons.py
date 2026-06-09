"""Material Icons rendering for the live tuning overlay."""

from __future__ import annotations

import pygame

from cleave.paths import repo_root

FONT_PATH = repo_root() / "assets/fonts/MaterialIcons-Regular.ttf"

FOLDER_GLYPH = "\ue2c7"
FILE_GLYPH = "\ue24d"
SKIP_PREVIOUS_GLYPH = "\ue045"
PLAY_GLYPH = "\ue037"
PAUSE_GLYPH = "\ue034"
SKIP_NEXT_GLYPH = "\ue044"
LOCK_GLYPH = "\ue897"
VISIBILITY_GLYPH = "\ue8f4"
VISIBILITY_OFF_GLYPH = "\ue8f5"

_SUFFIX_ICON_GAP = 4
_LABEL_SUFFIX_GAP = 4

_font_cache: dict[int, pygame.font.Font] = {}


def material_font(size: int) -> pygame.font.Font:
    if size not in _font_cache:
        _font_cache[size] = pygame.font.Font(str(FONT_PATH), size)
    return _font_cache[size]


def _icon_height(line_height: int) -> int:
    return line_height + 1


def _bar_width(h: int) -> int:
    return max(2, (h + 4) // 7)


def _triangle_width(h: int) -> int:
    return (h * 3) // 4


def _transport_slot_width(icon_h: int) -> int:
    bar_w = _bar_width(icon_h)
    inner_gap = max(1, bar_w // 2)
    tri_w = _triangle_width(icon_h)
    return max(tri_w, 2 * bar_w + inner_gap, bar_w + inner_gap + tri_w)


def render_glyph(
    glyph: str,
    *,
    color: tuple[int, int, int],
    line_height: int,
) -> pygame.Surface:
    icon_h = _icon_height(line_height)
    font = material_font(icon_h)
    glyph_surf = font.render(glyph, True, color)
    surf = pygame.Surface((glyph_surf.get_width(), line_height), pygame.SRCALPHA)
    y = (line_height - glyph_surf.get_height()) // 2
    surf.blit(glyph_surf, (0, y))
    return surf


def render_transport_icons(
    *,
    color: tuple[int, int, int],
    line_height: int,
    paused: bool,
) -> pygame.Surface:
    icon_h = _icon_height(line_height)
    gap = max(8, line_height // 2)
    slot_w = _transport_slot_width(icon_h)
    total_w = 3 * slot_w + 2 * gap
    surf = pygame.Surface((total_w, line_height), pygame.SRCALPHA)

    center_glyph = PAUSE_GLYPH if paused else PLAY_GLYPH
    glyphs = (SKIP_PREVIOUS_GLYPH, center_glyph, SKIP_NEXT_GLYPH)
    font = material_font(icon_h)

    for i, glyph in enumerate(glyphs):
        glyph_surf = font.render(glyph, True, color)
        slot_x = i * (slot_w + gap)
        x = slot_x + (slot_w - glyph_surf.get_width()) // 2
        y = (line_height - glyph_surf.get_height()) // 2
        surf.blit(glyph_surf, (x, y))
    return surf


def row_icon_prefix_width(line_height: int) -> int:
    icon_h = _icon_height(line_height)
    font = material_font(icon_h)
    return font.size(FOLDER_GLYPH)[0] + _LABEL_SUFFIX_GAP


def _suffix_icon_width(line_height: int, glyph: str) -> int:
    icon_h = _icon_height(line_height)
    font = material_font(icon_h)
    return font.size(glyph)[0]


VISIBILITY_ICON_PAD_X = 2


def visibility_icon_slot_width(line_height: int) -> int:
    """Fixed eye slot width (glyph plus horizontal pad for solo background)."""
    return _suffix_icon_width(line_height, VISIBILITY_GLYPH) + VISIBILITY_ICON_PAD_X * 2


def visibility_icon_prefix_width(line_height: int) -> int:
    return visibility_icon_slot_width(line_height) + _LABEL_SUFFIX_GAP


def track_header_lock_suffix_width(line_height: int) -> int:
    return _SUFFIX_ICON_GAP + _suffix_icon_width(line_height, LOCK_GLYPH)
