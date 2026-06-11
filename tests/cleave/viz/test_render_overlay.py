"""Tests for render-only text overlay drawing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame

from cleave.config import (
    RenderOverlayBackgroundConfig,
    RenderOverlayBorderConfig,
    RenderOverlayConfig,
    RenderOverlayFontConfig,
)
from cleave.easing import smoothstep
from cleave.viz.render_overlay import (
    _background_pixel_alpha,
    build_panel_surface,
    composite_render_overlay,
    overlay_visible_alpha,
    panel_position,
)
from cleave.viz.theme import FADE_DURATION_SEC


def _overlay_cfg(
    *,
    enabled: bool = True,
    start: float = 10.0,
    display_time: float = 30.0,
    position: str = "bottom-left",
    margin: int = 10,
    padding: int = 10,
    font_size: int = 10,
    opacity: float = 1.0,
    border_width: int = 2,
) -> RenderOverlayConfig:
    return RenderOverlayConfig(
        enabled=enabled,
        title="Title",
        body="Line one\nLine two",
        start=start,
        display_time=display_time,
        position=position,  # type: ignore[arg-type]
        font=RenderOverlayFontConfig(size=font_size, colour=(255, 170, 0)),
        background=RenderOverlayBackgroundConfig(
            margin=margin,
            padding=padding,
            colour=(34, 51, 68),
            opacity=opacity,
            border=RenderOverlayBorderConfig(colour=(200, 100, 50), width=border_width),
        ),
    )


def test_overlay_visible_alpha_before_start() -> None:
    cfg = _overlay_cfg(start=10.0, display_time=30.0)
    assert overlay_visible_alpha(9.9, cfg) == 0.0


def test_overlay_visible_alpha_fade_in() -> None:
    cfg = _overlay_cfg(start=10.0, display_time=30.0)
    fade = FADE_DURATION_SEC
    assert overlay_visible_alpha(10.0, cfg) == 0.0
    assert overlay_visible_alpha(10.0 + fade * 0.5, cfg) == smoothstep(0.5)
    assert overlay_visible_alpha(10.0 + fade, cfg) == 1.0


def test_overlay_visible_alpha_mid_hold() -> None:
    cfg = _overlay_cfg(start=10.0, display_time=30.0)
    assert overlay_visible_alpha(25.0, cfg) == 1.0


def test_overlay_visible_alpha_fade_out() -> None:
    cfg = _overlay_cfg(start=10.0, display_time=30.0)
    fade = FADE_DURATION_SEC
    end = 10.0 + 30.0
    assert overlay_visible_alpha(end - fade, cfg) == 1.0
    assert overlay_visible_alpha(end - fade * 0.5, cfg) == smoothstep(0.5)
    assert overlay_visible_alpha(end, cfg) == 0.0


def test_overlay_visible_alpha_after_window() -> None:
    cfg = _overlay_cfg(start=10.0, display_time=30.0)
    assert overlay_visible_alpha(41.0, cfg) == 0.0


def test_overlay_visible_alpha_disabled() -> None:
    cfg = _overlay_cfg(enabled=False)
    assert overlay_visible_alpha(25.0, cfg) == 0.0


def test_panel_position_corners() -> None:
    cfg = _overlay_cfg(margin=20, position="top-left")
    assert panel_position(cfg, 100, 50, 1280, 720) == (20, 20)

    cfg = _overlay_cfg(margin=20, position="top-right")
    assert panel_position(cfg, 100, 50, 1280, 720) == (1160, 20)

    cfg = _overlay_cfg(margin=20, position="bottom-left")
    assert panel_position(cfg, 100, 50, 1280, 720) == (20, 650)

    cfg = _overlay_cfg(margin=20, position="bottom-right")
    assert panel_position(cfg, 100, 50, 1280, 720) == (1160, 650)


def test_panel_position_centre_ignores_margin() -> None:
    cfg = _overlay_cfg(margin=99, position="centre")
    assert panel_position(cfg, 200, 100, 1280, 720) == (540, 310)


def test_title_font_size_and_bold() -> None:
    pygame.init()
    cfg = _overlay_cfg(font_size=10)
    with patch("cleave.viz.render_overlay.pygame.font.SysFont") as sys_font:
        body_font = MagicMock()
        title_font = MagicMock()
        body_font.get_linesize.return_value = 12
        title_font.get_linesize.return_value = 14
        body_font.render.return_value = pygame.Surface((40, 12), pygame.SRCALPHA)
        title_font.render.return_value = pygame.Surface((50, 14), pygame.SRCALPHA)
        sys_font.side_effect = [body_font, title_font]

        build_panel_surface(cfg)

    assert sys_font.call_args_list[0].args == ("monospace", 10)
    assert sys_font.call_args_list[1].args == ("monospace", 12)
    assert sys_font.call_args_list[1].kwargs == {"bold": True}


def test_border_alpha_matches_background() -> None:
    pygame.init()
    cfg = _overlay_cfg(opacity=0.5, border_width=2)
    panel = build_panel_surface(cfg)
    expected_alpha = _background_pixel_alpha(cfg)

    bg_colour = cfg.background.colour
    found_bg = False
    found_border = False
    border_colour = cfg.background.border.colour
    width, height = panel.get_size()

    for y in range(height):
        for x in range(width):
            r, g, b, a = panel.get_at((x, y))
            if (r, g, b) == bg_colour and a == expected_alpha:
                found_bg = True
            if (r, g, b) == border_colour and a == expected_alpha:
                found_border = True

    assert expected_alpha == int(round(255 * 0.5))
    assert found_bg
    assert found_border


def test_composite_render_overlay_noop_before_start() -> None:
    compositor = MagicMock()
    cfg = _overlay_cfg(start=10.0)
    composite_render_overlay(
        compositor, cfg, 5.0, 1280, 720, panel=MagicMock()
    )
    compositor.upload_overlay_texture.assert_not_called()
    compositor.draw_overlay.assert_not_called()


def test_composite_render_overlay_draws_when_visible() -> None:
    pygame.init()
    compositor = MagicMock()
    compositor.upload_overlay_texture.return_value = 99
    cfg = _overlay_cfg(start=0.0, display_time=30.0)
    panel = build_panel_surface(cfg)

    composite_render_overlay(compositor, cfg, 15.0, 1280, 720, panel=panel)

    compositor.upload_overlay_texture.assert_called_once()
    compositor.draw_overlay.assert_called_once_with(
        99,
        panel_position(cfg, panel.get_width(), panel.get_height(), 1280, 720)[0],
        panel_position(cfg, panel.get_width(), panel.get_height(), 1280, 720)[1],
        panel.get_width(),
        panel.get_height(),
        alpha=1.0,
    )
