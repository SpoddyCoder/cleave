"""Logo artwork: sizes, the theme-matched ink, the window icon, and headless draw."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pygame

from cleave.viz import brand
from cleave.viz.brand import (
    BRAND_INK,
    REVERSED_INK,
    Logo,
    draw_logo,
    ink_reversed,
    logo_aspect,
    logo_image,
    logo_path,
    logo_size,
    window_icon,
)
from cleave.viz.theme import palette_for_theme


def test_every_logo_ships_in_assets() -> None:
    for logo in Logo:
        assert logo_path(logo).is_file()


def test_full_logo_is_wide_and_mark_is_tall() -> None:
    assert logo_aspect(Logo.FULL) > 1.0
    assert logo_aspect(Logo.MARK) < 1.0


def test_logo_size_keeps_aspect_and_fits_max_width() -> None:
    width, height = logo_size(Logo.FULL, 100)
    assert height == 100
    assert width == round(100 * logo_aspect(Logo.FULL))
    width, height = logo_size(Logo.FULL, 100, max_width=50)
    assert width == 50
    assert height == round(50 / logo_aspect(Logo.FULL))


def test_navy_reverses_on_dark_themes_only() -> None:
    assert ink_reversed(palette_for_theme("ultraviolet").surface_bg)
    assert ink_reversed(palette_for_theme("ultraviolet").background)
    assert not ink_reversed(palette_for_theme("daylight").surface_bg)
    assert not ink_reversed(palette_for_theme("daylight").background)


def test_logo_image_reverses_navy_and_keeps_colours() -> None:
    size = logo_size(Logo.MARK, 64)
    plain = np.array(logo_image(Logo.MARK, size, reversed_ink=False))
    rev = np.array(logo_image(Logo.MARK, size, reversed_ink=True))
    assert plain.shape == (size[1], size[0], 4)
    solid = plain[..., 3] == 255
    navy = solid & np.all(plain[..., :3] == BRAND_INK, axis=-1)
    assert navy.any()
    assert np.all(rev[navy, :3] == REVERSED_INK)
    red = solid & np.all(plain[..., :3] == (255, 0, 0), axis=-1)
    assert red.any()
    assert np.all(rev[red, :3] == (255, 0, 0))


def test_window_icon_is_square() -> None:
    pygame.init()
    icon = window_icon()
    assert icon.get_width() == icon.get_height()


def test_draw_logo_headless_uploads_nothing() -> None:
    brand.enable_logo_textures(False)
    draw = MagicMock()
    draw_logo(draw, Logo.FULL, (0, 0, 100, 56), backdrop=(0, 0, 0))
    draw.add_image.assert_not_called()
