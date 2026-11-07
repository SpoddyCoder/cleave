"""SDL window helpers without a usable SDL library or window."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cleave.viz import sdl_window


def test_missing_library_makes_every_call_a_no_op() -> None:
    with patch.object(sdl_window, "_sdl", return_value=None):
        assert sdl_window.set_minimum_size(800, 500) is False
        assert sdl_window.window_flags() is None


def test_no_gl_window_makes_every_call_a_no_op() -> None:
    lib = MagicMock()
    lib.SDL_GL_GetCurrentWindow.return_value = None
    with patch.object(sdl_window, "_sdl", return_value=lib):
        assert sdl_window.set_minimum_size(800, 500) is False
        assert sdl_window.window_flags() is None
    lib.SDL_SetWindowMinimumSize.assert_not_called()


def test_calls_reach_the_current_gl_window() -> None:
    lib = MagicMock()
    lib.SDL_GL_GetCurrentWindow.return_value = 1234
    lib.SDL_GetWindowFlags.return_value = sdl_window.SDL_WINDOW_MAXIMIZED
    with patch.object(sdl_window, "_sdl", return_value=lib):
        assert sdl_window.set_minimum_size(800, 500) is True
        assert sdl_window.window_flags() == sdl_window.SDL_WINDOW_MAXIMIZED
    lib.SDL_SetWindowMinimumSize.assert_called_once_with(1234, 800, 500)


def test_bundled_sdl_library_loads() -> None:
    """pygame's own SDL2 resolves, so the binding works in this checkout."""
    assert sdl_window._sdl() is not None
