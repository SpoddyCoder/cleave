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
    build_live_overlay_config,
    build_panel_surface,
    composite_render_overlay,
    composite_render_overlay_with_alpha,
    live_overlay_alpha,
    overlay_visible_alpha,
    panel_position,
    panel_surface_key,
)
from cleave.viz.controls import RenderOverlayRuntime
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


def test_live_overlay_alpha_disabled() -> None:
    cfg = _overlay_cfg(start=10.0, display_time=30.0)
    assert live_overlay_alpha(25.0, cfg, enabled=False, solo=False) == 0.0
    assert live_overlay_alpha(25.0, cfg, enabled=False, solo=True) == 0.0


def test_live_overlay_alpha_solo_always_on() -> None:
    cfg = _overlay_cfg(start=10.0, display_time=30.0)
    assert live_overlay_alpha(0.0, cfg, enabled=True, solo=True) == 1.0
    assert live_overlay_alpha(9.9, cfg, enabled=True, solo=True) == 1.0
    assert live_overlay_alpha(41.0, cfg, enabled=True, solo=True) == 1.0


def test_live_overlay_alpha_timed_window_unchanged() -> None:
    cfg = _overlay_cfg(start=10.0, display_time=30.0)
    for t_sec in (9.9, 10.0, 15.0, 25.0, 40.0, 41.0):
        assert live_overlay_alpha(t_sec, cfg, enabled=True, solo=False) == overlay_visible_alpha(
            t_sec, cfg
        )


def test_build_live_overlay_config_overrides_runtime_fields() -> None:
    base = _overlay_cfg(
        enabled=False,
        start=1.0,
        display_time=2.0,
        position="top-left",
        font_size=8,
        opacity=0.25,
        border_width=1,
    )
    runtime = RenderOverlayRuntime(
        enabled=True,
        expanded=False,
        position="bottom-right",
        font_size=14,
        opacity_pct=75,
        border_width=4,
        start=20.0,
        display_time=40.0,
    )
    merged = build_live_overlay_config(base, runtime)
    assert merged.enabled is True
    assert merged.title == base.title
    assert merged.body == base.body
    assert merged.start == 20.0
    assert merged.display_time == 40.0
    assert merged.position == "bottom-right"
    assert merged.font.size == 14
    assert merged.font.colour == base.font.colour
    assert merged.background.margin == base.background.margin
    assert merged.background.padding == base.background.padding
    assert merged.background.colour == base.background.colour
    assert merged.background.opacity == 0.75
    assert merged.background.border.colour == base.background.border.colour
    assert merged.background.border.width == 4


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
    border_width = cfg.background.border.width

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
    assert panel.get_at((0, 0))[:3] == border_colour
    assert panel.get_at((border_width, border_width))[:3] == bg_colour


def test_border_grows_outward_not_inward() -> None:
    pygame.init()
    cfg_no_border = _overlay_cfg(border_width=0)
    cfg_border = _overlay_cfg(border_width=4)
    panel_none = build_panel_surface(cfg_no_border)
    panel_border = build_panel_surface(cfg_border)
    w0, h0 = panel_none.get_size()
    w1, h1 = panel_border.get_size()
    assert w1 == w0 + 8
    assert h1 == h0 + 8


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


def test_composite_render_overlay_with_alpha_uses_precomputed_alpha() -> None:
    pygame.init()
    compositor = MagicMock()
    compositor.upload_overlay_texture.return_value = 42
    cfg = _overlay_cfg(start=10.0, display_time=30.0)
    panel = build_panel_surface(cfg)

    composite_render_overlay_with_alpha(
        compositor, cfg, 0.5, 1280, 720, panel=panel
    )

    compositor.draw_overlay.assert_called_once()
    assert compositor.draw_overlay.call_args.kwargs["alpha"] == 0.5


def test_panel_surface_key_ignores_position() -> None:
    cfg_a = _overlay_cfg(position="top-left")
    cfg_b = _overlay_cfg(position="bottom-right")
    assert panel_surface_key(cfg_a) == panel_surface_key(cfg_b)
