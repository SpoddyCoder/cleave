"""Tests for visualizer boot loading screen."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame
import pytest

from cleave.viz.loading import (
    LoadingWindow,
    compose_loading_surface,
    clamp_loading_fraction,
    draw_loading_screen,
    loading_bar_width,
    loading_content_layout,
    open_loading_window,
)
from cleave.viz.overlay_primitives import overlay_font
from cleave.viz.theme import BACKGROUND, BORDER_WIDTH, LABEL, VALUE
from tests.support.compositor_mock import recording_compositor

_MESSAGE_FONT_SIZE = 28


def test_clamp_loading_fraction() -> None:
    assert clamp_loading_fraction(0.0) == 0.0
    assert clamp_loading_fraction(1.0) == 1.0
    assert clamp_loading_fraction(0.25) == 0.25
    assert clamp_loading_fraction(-0.5) == 0.0
    assert clamp_loading_fraction(1.5) == 1.0


def test_message_only_layout_is_centered() -> None:
    layout = loading_content_layout(1280, 720, (200, 40))
    assert layout.message_xy == ((1280 - 200) // 2, (720 - 40) // 2)
    assert layout.detail_xy is None
    assert layout.bar_rect is None
    assert layout.fill_rect is None


def test_detail_stacks_under_message_and_recenters() -> None:
    layout = loading_content_layout(
        1280, 720, (200, 40), detail_size=(100, 20), line_gap=8
    )
    stack_h = 40 + 8 + 20
    top = (720 - stack_h) // 2
    assert layout.message_xy == ((1280 - 200) // 2, top)
    assert layout.detail_xy == ((1280 - 100) // 2, top + 40 + 8)
    assert layout.bar_rect is None


def test_fraction_none_omits_bar() -> None:
    layout = loading_content_layout(
        1280, 720, (200, 40), detail_size=(80, 16), fraction=None
    )
    assert layout.bar_rect is None
    assert layout.fill_rect is None


def test_bar_below_text_when_fraction_set() -> None:
    layout = loading_content_layout(
        1280,
        720,
        (200, 40),
        detail_size=(80, 16),
        fraction=0.5,
        line_gap=8,
        bar_gap=16,
        bar_width=400,
        bar_height=12,
    )
    stack_h = 40 + 8 + 16 + 16 + 12
    top = (720 - stack_h) // 2
    bar_y = top + 40 + 8 + 16 + 16
    bar_x = (1280 - 400) // 2
    assert layout.bar_rect == (bar_x, bar_y, 400, 12)
    inner_w = 400 - 2 * BORDER_WIDTH
    inner_h = 12 - 2 * BORDER_WIDTH
    assert layout.fill_rect == (
        bar_x + BORDER_WIDTH,
        bar_y + BORDER_WIDTH,
        int(round(inner_w * 0.5)),
        inner_h,
    )


def test_zero_fraction_has_track_without_fill() -> None:
    layout = loading_content_layout(
        640, 360, (100, 20), fraction=0.0, bar_width=200, bar_height=12
    )
    assert layout.bar_rect is not None
    assert layout.fill_rect is None


def test_full_fraction_fill_matches_inner_width() -> None:
    layout = loading_content_layout(
        640, 360, (100, 20), fraction=1.0, bar_width=200, bar_height=12
    )
    assert layout.bar_rect is not None
    assert layout.fill_rect is not None
    _x, _y, bar_w, bar_h = layout.bar_rect
    _fx, _fy, fill_w, fill_h = layout.fill_rect
    assert fill_w == bar_w - 2 * BORDER_WIDTH
    assert fill_h == bar_h - 2 * BORDER_WIDTH


def test_out_of_range_fraction_clamps_fill() -> None:
    over = loading_content_layout(
        640, 360, (100, 20), fraction=2.0, bar_width=200, bar_height=12
    )
    full = loading_content_layout(
        640, 360, (100, 20), fraction=1.0, bar_width=200, bar_height=12
    )
    under = loading_content_layout(
        640, 360, (100, 20), fraction=-1.0, bar_width=200, bar_height=12
    )
    assert over.fill_rect == full.fill_rect
    assert under.fill_rect is None
    assert under.bar_rect is not None


def test_default_bar_width_is_display_fraction() -> None:
    assert loading_bar_width(1280) == int(round(1280 * 0.4))


@patch("cleave.viz.loading.pygame.display.flip")
@patch("cleave.viz.loading.glClear")
@patch("cleave.viz.loading.glClearColor")
@patch("cleave.viz.loading.glViewport")
@patch("cleave.viz.loading.glBindFramebuffer")
def test_draw_loading_screen_uploads_overlay_and_flips(
    _mock_bind: MagicMock,
    _mock_viewport: MagicMock,
    _mock_clear_color: MagicMock,
    _mock_clear: MagicMock,
    mock_flip: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.upload_overlay_texture.return_value = 9

    draw_loading_screen(compositor, "Building layers...", 1280, 720)

    upload_surface = compositor.upload_overlay_texture.call_args[0][0]
    assert upload_surface.get_size() == (1280, 720)
    compositor.draw_overlay.assert_called_once_with(9, 0, 0, 1280, 720)
    mock_flip.assert_called_once()


@patch("cleave.viz.loading.pygame.display.flip")
@patch("cleave.viz.loading.glClear")
@patch("cleave.viz.loading.glClearColor")
@patch("cleave.viz.loading.glViewport")
@patch("cleave.viz.loading.glBindFramebuffer")
def test_draw_loading_screen_accepts_optional_progress_kwargs(
    _mock_bind: MagicMock,
    _mock_viewport: MagicMock,
    _mock_clear_color: MagicMock,
    _mock_clear: MagicMock,
    mock_flip: MagicMock,
) -> None:
    pygame.init()
    compositor = recording_compositor()
    compositor.upload_overlay_texture.return_value = 3

    draw_loading_screen(
        compositor,
        "Downloading htdemucs",
        640,
        360,
        fraction=0.4,
        detail="12 MB of 30 MB",
    )

    upload_surface = compositor.upload_overlay_texture.call_args[0][0]
    assert upload_surface.get_size() == (640, 360)
    compositor.draw_overlay.assert_called_once_with(3, 0, 0, 640, 360)
    mock_flip.assert_called_once()


def _has_rgb(surface: pygame.Surface, rgb: tuple[int, int, int]) -> bool:
    w, h = surface.get_size()
    for y in range(h):
        for x in range(w):
            if surface.get_at((x, y))[:3] == rgb:
                return True
    return False


def test_compose_detail_uses_label_colour() -> None:
    pygame.init()
    with_detail = compose_loading_surface(
        "Loading...", 640, 360, detail="Downloading htdemucs"
    )
    without = compose_loading_surface("Loading...", 640, 360)
    assert _has_rgb(with_detail, LABEL)
    assert not _has_rgb(without, LABEL)


def test_compose_draws_bar_fill_and_empty_track() -> None:
    pygame.init()
    message = "Loading..."
    surface = compose_loading_surface(message, 640, 360, fraction=0.5)
    layout = loading_content_layout(
        640, 360, overlay_font(_MESSAGE_FONT_SIZE).size(message), fraction=0.5
    )
    assert layout.bar_rect is not None
    assert layout.fill_rect is not None
    fx, fy, fw, fh = layout.fill_rect
    fill_sample = surface.get_at((fx + max(0, fw // 2), fy + max(0, fh // 2)))
    assert fill_sample[:3] == VALUE

    bx, by, bw, bh = layout.bar_rect
    empty_x = fx + fw + 4
    if empty_x < bx + bw - BORDER_WIDTH - 1:
        empty_sample = surface.get_at((empty_x, fy + max(0, fh // 2)))
        assert empty_sample[:3] == BACKGROUND
    border_sample = surface.get_at((bx, by + bh // 2))
    assert border_sample[:3] == VALUE


@patch("cleave.viz.loading.draw_loading_screen")
@patch("cleave.viz.loading.GlCompositor")
@patch("cleave.viz.loading.pygame.display.set_caption")
@patch("cleave.viz.loading.pygame.display.set_mode")
def test_open_loading_window_uses_editor_defaults(
    mock_set_mode: MagicMock,
    mock_set_caption: MagicMock,
    mock_gl: MagicMock,
    mock_draw: MagicMock,
) -> None:
    from cleave.config_schema.editor import editor_display_size
    from cleave.gl_color_format import RGBA8

    compositor = MagicMock()
    mock_gl.return_value = compositor
    pygame.init()
    window = open_loading_window()
    width, height = editor_display_size()
    mock_set_mode.assert_called_once_with(
        (width, height), pygame.OPENGL | pygame.DOUBLEBUF
    )
    mock_set_caption.assert_called_once_with("Cleave")
    mock_gl.assert_called_once_with(
        width,
        height,
        display_width=width,
        display_height=height,
        color_format=RGBA8,
    )
    compositor.init.assert_called_once()
    mock_draw.assert_called_once()
    assert mock_draw.call_args.args[1] == "Loading..."
    assert window.display_width == width
    assert window.display_height == height
    assert window.quit_requested is False


@patch("cleave.viz.loading.draw_loading_screen")
def test_loading_window_update_draws_and_returns_true(
    mock_draw: MagicMock,
) -> None:
    pygame.init()
    compositor = MagicMock()
    window = LoadingWindow(
        compositor=compositor,
        display_width=640,
        display_height=360,
        overlay_surface=pygame.Surface((640, 360), pygame.SRCALPHA),
    )
    with patch("cleave.viz.loading.pygame.event.get", return_value=[]):
        assert window.update("Separating stems...") is True
    mock_draw.assert_called_once_with(
        compositor,
        "Separating stems...",
        640,
        360,
        fraction=None,
        detail=None,
    )
    assert window.quit_requested is False


@patch("cleave.viz.loading.draw_loading_screen")
def test_loading_window_update_quit_skips_draw(
    mock_draw: MagicMock,
) -> None:
    pygame.init()
    compositor = MagicMock()
    window = LoadingWindow(
        compositor=compositor,
        display_width=640,
        display_height=360,
        overlay_surface=pygame.Surface((640, 360), pygame.SRCALPHA),
    )
    quit_event = MagicMock()
    quit_event.type = pygame.QUIT
    with patch("cleave.viz.loading.pygame.event.get", return_value=[quit_event]):
        assert window.update("Loading...") is False
    assert window.quit_requested is True
    mock_draw.assert_not_called()


@patch("cleave.viz.loading._set_gl_mode")
def test_adopt_display_size_resizes_only_when_changed(
    mock_set_mode: MagicMock,
) -> None:
    pygame.init()
    compositor = MagicMock()
    window = LoadingWindow(
        compositor=compositor,
        display_width=640,
        display_height=360,
        overlay_surface=pygame.Surface((640, 360), pygame.SRCALPHA),
    )
    window.adopt_display_size(640, 360)
    mock_set_mode.assert_not_called()
    window.adopt_display_size(1280, 720)
    mock_set_mode.assert_called_once_with(1280, 720)
    assert window.display_width == 1280
    assert window.display_height == 720
    assert window.overlay_surface.get_size() == (1280, 720)


@patch("cleave.viz.loading.pygame.quit")
@patch("cleave.viz.loading.pygame.display.set_mode")
def test_set_gl_mode_raises_launch_error(
    mock_set_mode: MagicMock,
    mock_quit: MagicMock,
) -> None:
    from cleave.viz import LaunchError
    from cleave.viz.loading import _set_gl_mode

    mock_set_mode.side_effect = pygame.error("no gl")
    with pytest.raises(LaunchError, match="failed to open OpenGL window"):
        _set_gl_mode(640, 360)
    mock_quit.assert_called_once()
