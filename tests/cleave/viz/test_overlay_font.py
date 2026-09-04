"""Bundled DejaVu overlay font coverage."""

from __future__ import annotations

from unittest.mock import patch

import pygame

from cleave.paths import resource_dir
from cleave.viz.overlay_primitives import overlay_font, overlay_font_path

_TREE_GLYPHS = "▶▼└─▲…"


def _opaque_pixel_count(surface: pygame.Surface) -> int:
    count = 0
    for y in range(surface.get_height()):
        for x in range(surface.get_width()):
            if surface.get_at((x, y))[0] > 0:
                count += 1
    return count


def test_overlay_font_path_uses_resource_dir() -> None:
    assert overlay_font_path() == resource_dir() / "assets/fonts/DejaVuSansMono.ttf"
    assert overlay_font_path(bold=True) == (
        resource_dir() / "assets/fonts/DejaVuSansMono-Bold.ttf"
    )


def test_overlay_font_skips_sysfont() -> None:
    from cleave.viz import overlay_primitives

    overlay_primitives._font_cache.clear()
    with patch("pygame.font.SysFont") as sys_font:
        font = overlay_font(16)
        sys_font.assert_not_called()
    assert font.get_height() > 0


def test_overlay_font_renders_tree_glyphs() -> None:
    font = overlay_font(16)
    for glyph in _TREE_GLYPHS:
        metrics = font.metrics(glyph)[0]
        assert metrics is not None, glyph
        assert metrics[4] > 0, glyph
        surf = font.render(glyph, True, (255, 255, 255))
        assert _opaque_pixel_count(surf) > 0, glyph


def test_overlay_font_bold_uses_bold_face() -> None:
    regular = overlay_font(24)
    bold = overlay_font(24, bold=True)
    assert not regular.get_bold()
    assert bold.get_bold()
    regular_px = pygame.image.tostring(
        regular.render("M", True, (255, 255, 255)), "RGBA"
    )
    bold_px = pygame.image.tostring(bold.render("M", True, (255, 255, 255)), "RGBA")
    assert regular_px != bold_px
