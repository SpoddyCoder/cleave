"""System font discovery for overlay cards."""

from __future__ import annotations

import pygame

_font_names_cache: tuple[str, ...] | None = None
_LATIN_PROBE_SIZE = 24


def _has_latin_glyphs(name: str) -> bool:
    """True when *name* provides distinct Latin glyphs (not tofu placeholders)."""
    try:
        font = pygame.font.SysFont(name, _LATIN_PROBE_SIZE)
    except Exception:
        return False
    a = font.metrics("A")[0]
    i = font.metrics("i")[0]
    if a is None or i is None:
        return False
    return a != i


def overlay_system_fonts() -> tuple[str, ...]:
    """Sorted Latin-capable pygame/SDL font names on this machine."""
    global _font_names_cache
    if _font_names_cache is None:
        if not pygame.font.get_init():
            pygame.font.init()
        _font_names_cache = tuple(
            sorted(
                name
                for name in pygame.font.get_fonts()
                if _has_latin_glyphs(name)
            )
        )
    return _font_names_cache


def overlay_font_display(name: str) -> str:
    """Font name with ``(position/total)`` when *name* is in the Latin font list."""
    fonts = overlay_system_fonts()
    if not fonts:
        return name
    try:
        position = fonts.index(name) + 1
    except ValueError:
        return name
    return f"{name} ({position}/{len(fonts)})"


def cycle_overlay_font(current: str, *, forward: bool) -> str:
    fonts = overlay_system_fonts()
    if not fonts:
        return current
    try:
        index = fonts.index(current)
    except ValueError:
        index = 0
    if forward:
        return fonts[(index + 1) % len(fonts)]
    return fonts[(index - 1) % len(fonts)]
