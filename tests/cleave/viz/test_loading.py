"""Tests for visualizer boot loading screen."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame

from cleave.viz.loading import draw_loading_screen
from tests.support.compositor_mock import recording_compositor


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
