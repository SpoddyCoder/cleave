"""Tests for the pre-project loading window and its progress dialog."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pygame
import pytest
from OpenGL.GL import GL_COLOR_BUFFER_BIT, GL_FRAMEBUFFER
from imgui_bundle import imgui

from cleave.viz.loading import (
    LoadingWindow,
    open_loading_window,
    SPLASH_SEC,
    present_frame,
    show_splash,
    splash_alpha,
)
from cleave.viz.progress_bar import clamp_fraction
from cleave.viz.theme import palette


def test_clamp_loading_fraction() -> None:
    assert clamp_fraction(0.0) == 0.0
    assert clamp_fraction(1.0) == 1.0
    assert clamp_fraction(0.25) == 0.25
    assert clamp_fraction(-0.5) == 0.0
    assert clamp_fraction(1.5) == 1.0


def _content_names() -> list[str]:
    lists = list(imgui.get_draw_data().cmd_lists)
    names = [str(draw_list._owner_name) for draw_list in lists]
    del lists
    return names


@contextmanager
def _host(size: tuple[int, int] = (640, 360)) -> Iterator[object]:
    from cleave.viz import imgui_host
    from cleave.viz.imgui_host import ImGuiHost

    pygame.init()
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = ImGuiHost.create()
    host.display_size = size
    try:
        yield host
    finally:
        try:
            # Destroying a context after a single frame breaks the next one.
            host.begin_frame(1.0 / 60.0)
            host.end_frame()
            host.begin_frame(1.0 / 60.0)
            host.end_frame()
        finally:
            host.destroy()


@patch("cleave.viz.loading.pygame.display.flip")
@patch("cleave.viz.loading.glClear")
@patch("cleave.viz.loading.glClearColor")
@patch("cleave.viz.loading.glViewport")
@patch("cleave.viz.loading.glBindFramebuffer")
def test_present_frame_clears_draws_and_flips(
    mock_bind: MagicMock,
    mock_viewport: MagicMock,
    mock_clear_color: MagicMock,
    mock_clear: MagicMock,
    mock_flip: MagicMock,
) -> None:
    pygame.init()
    order: list[str] = []
    host = MagicMock()
    host.begin_frame.side_effect = lambda _dt: order.append("begin")
    host.end_frame.side_effect = lambda: order.append("end")
    window = LoadingWindow(
        compositor=MagicMock(),
        display_width=640,
        display_height=360,
        overlay_surface=pygame.Surface((640, 360), pygame.SRCALPHA),
        imgui=host,
    )
    draw = MagicMock(side_effect=lambda: order.append("draw"))
    mock_clear.side_effect = lambda *_args: order.append("clear")
    mock_flip.side_effect = lambda: order.append("flip")

    present_frame(window, draw, scrim=False)

    mock_bind.assert_called_once_with(GL_FRAMEBUFFER, 0)
    mock_viewport.assert_called_once_with(0, 0, 640, 360)
    red, green, blue = palette().background
    mock_clear_color.assert_called_once_with(
        red / 255.0, green / 255.0, blue / 255.0, 1.0
    )
    mock_clear.assert_called_once_with(GL_COLOR_BUFFER_BIT)
    host.begin_frame.assert_called_once_with(1.0 / 60.0)
    draw.assert_called_once_with()
    host.end_frame.assert_called_once_with()
    mock_flip.assert_called_once_with()
    assert order == ["clear", "begin", "draw", "end", "flip"]


def test_present_frame_without_imgui_skips_draw() -> None:
    pygame.init()
    window = LoadingWindow(
        compositor=MagicMock(),
        display_width=640,
        display_height=360,
        overlay_surface=pygame.Surface((640, 360), pygame.SRCALPHA),
    )
    draw = MagicMock()
    present_frame(window, draw, scrim=True)
    draw.assert_not_called()


@patch("cleave.viz.loading.pygame.display.flip")
@patch("cleave.viz.loading.glClear")
@patch("cleave.viz.loading.glClearColor")
@patch("cleave.viz.loading.glViewport")
@patch("cleave.viz.loading.glBindFramebuffer")
def test_present_frame_scrim_precedes_drawn_content(
    _mock_bind: MagicMock,
    _mock_viewport: MagicMock,
    _mock_clear_color: MagicMock,
    _mock_clear: MagicMock,
    _mock_flip: MagicMock,
) -> None:
    with _host() as host:
        window = LoadingWindow(
            compositor=MagicMock(),
            display_width=640,
            display_height=360,
            overlay_surface=pygame.Surface((640, 360), pygame.SRCALPHA),
            imgui=host,
        )
        def draw() -> None:
            imgui.set_next_window_size(imgui.ImVec2(100.0, 100.0))
            imgui.begin("##content")
            # Surfaces drawn over the scrim raise themselves, as dialogs do.
            imgui.internal.bring_window_to_display_front(
                imgui.internal.get_current_window()
            )
            imgui.text("x")
            imgui.end()

        present_frame(window, draw, scrim=False)
        assert "##loading-scrim" not in _content_names()
        assert "##content" in _content_names()

        present_frame(window, draw, scrim=True)
        names = _content_names()
        assert names.index("##loading-scrim") < names.index("##content")


@patch("cleave.viz.loading.pygame.display.flip")
@patch("cleave.viz.loading.glClear")
@patch("cleave.viz.loading.glClearColor")
@patch("cleave.viz.loading.glViewport")
@patch("cleave.viz.loading.glBindFramebuffer")
def test_update_draws_progress_dialog(
    _mock_bind: MagicMock,
    _mock_viewport: MagicMock,
    _mock_clear_color: MagicMock,
    _mock_clear: MagicMock,
    _mock_flip: MagicMock,
) -> None:
    with _host() as host:
        window = LoadingWindow(
            compositor=MagicMock(),
            display_width=640,
            display_height=360,
            overlay_surface=pygame.Surface((640, 360), pygame.SRCALPHA),
            imgui=host,
        )
        with patch("cleave.viz.loading.pygame.event.get", return_value=[]):
            assert window.update("Creating project", "Separating stems…", 0.5)
        assert "##modal" in _content_names()

        with patch("cleave.viz.loading.pygame.event.get", return_value=[]):
            assert window.clear()
        assert "##modal" not in _content_names()




@patch("cleave.viz.imgui_host.ImGuiHost.create")
@patch("cleave.viz.loading.present_frame")
@patch("cleave.viz.loading.GlCompositor")
@patch("cleave.viz.loading.pygame.display.set_caption")
@patch("cleave.viz.loading._desktop_size", return_value=(3840, 2160))
@patch("cleave.viz.loading._maximise")
@patch("cleave.viz.loading.pygame.display.set_mode")
def test_open_loading_window_uses_default_window_geometry(
    mock_set_mode: MagicMock,
    mock_maximise: MagicMock,
    _mock_desktop: MagicMock,
    mock_set_caption: MagicMock,
    mock_gl: MagicMock,
    mock_draw: MagicMock,
    mock_imgui_create: MagicMock,
) -> None:
    from cleave.config_schema.window import WindowGeometry
    from cleave.gl_color_format import RGBA8
    from cleave.user_config import saved_window_geometry

    compositor = MagicMock()
    mock_gl.return_value = compositor
    host = MagicMock()
    mock_imgui_create.return_value = host
    pygame.init()
    window = open_loading_window()
    width, height = WindowGeometry().width, WindowGeometry().height
    mock_maximise.assert_not_called()
    mock_set_mode.assert_called_once_with(
        (width, height), pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE
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
    mock_imgui_create.assert_called_once()
    assert window.imgui is host
    mock_draw.assert_called_once()
    assert mock_draw.call_args.args[0] is window
    assert window.display_width == width
    assert window.display_height == height
    assert window.quit_requested is False

    order: list[str] = []
    host.destroy.side_effect = lambda: order.append("destroy")
    with patch("cleave.viz.loading.pygame.quit", side_effect=lambda: order.append("quit")):
        window.close()
        assert order == ["destroy", "quit"]
        assert window.imgui is None
        assert window.video_quit is True
        window.release_imgui()
        window.close()
    host.destroy.assert_called_once()
    assert order == ["destroy", "quit", "quit"]
    assert saved_window_geometry() == WindowGeometry(width=width, height=height)


def test_ensure_imgui_recreates_host_after_release() -> None:
    pygame.init()
    host = MagicMock()
    window = LoadingWindow(
        compositor=MagicMock(),
        display_width=640,
        display_height=360,
        overlay_surface=pygame.Surface((640, 360), pygame.SRCALPHA),
        imgui=host,
    )
    window.ensure_imgui()
    assert window.imgui is host
    window.release_imgui()
    assert window.imgui is None
    replacement = MagicMock()
    with patch("cleave.viz.imgui_host.ImGuiHost.create", return_value=replacement):
        window.ensure_imgui()
    assert window.imgui is replacement
    window.ensure_imgui()
    assert window.imgui is replacement


@patch("cleave.viz.loading.present_frame")
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
        assert window.update("Creating project", "Separating stems…", 0.4) is True
    mock_draw.assert_called_once()
    assert mock_draw.call_args.args[0] is window
    drawn = mock_draw.call_args.args[1]
    assert drawn.title == "Creating project"
    assert drawn.body == "Separating stems…"
    assert drawn.fraction == 0.4
    compositor.upload_overlay_texture.assert_not_called()
    assert window.quit_requested is False


@patch("cleave.viz.loading.present_frame")
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
        assert window.update("Opening project", "Loading…") is False
    assert window.quit_requested is True
    mock_draw.assert_not_called()


def _size_event(width: int, height: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.WINDOWSIZECHANGED, x=width, y=height)


def _resizable_window() -> tuple[LoadingWindow, MagicMock, MagicMock]:
    pygame.init()
    compositor = MagicMock()
    host = MagicMock()
    window = LoadingWindow(
        compositor=compositor,
        display_width=640,
        display_height=360,
        overlay_surface=pygame.Surface((640, 360), pygame.SRCALPHA),
        imgui=host,
    )
    return window, compositor, host


@patch("cleave.viz.loading._set_gl_mode")
def test_apply_pending_resize_applies_last_size_in_place(
    mock_set_mode: MagicMock,
) -> None:
    window, compositor, host = _resizable_window()
    window.note_event(_size_event(800, 600))
    window.note_event(_size_event(1280, 720))
    assert window.apply_pending_resize() is True
    mock_set_mode.assert_not_called()
    compositor.set_display_size.assert_called_once_with(1280, 720)
    host.set_display_size.assert_called_once_with(1280, 720)
    assert (window.display_width, window.display_height) == (1280, 720)
    assert window.overlay_surface.get_size() == (1280, 720)
    assert window.pending_size is None
    assert window.apply_pending_resize() is False


def test_apply_pending_resize_ignores_same_and_zero_sizes() -> None:
    window, compositor, host = _resizable_window()
    surface = window.overlay_surface
    window.note_event(_size_event(0, 0))
    assert window.apply_pending_resize() is False
    window.note_event(_size_event(640, 360))
    assert window.apply_pending_resize() is False
    compositor.set_display_size.assert_not_called()
    host.set_display_size.assert_not_called()
    assert window.overlay_surface is surface


def test_note_event_ignores_other_events() -> None:
    window, _compositor, _host = _resizable_window()
    window.note_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    assert window.pending_size is None


@patch("cleave.viz.loading.pygame.display.flip")
@patch("cleave.viz.loading._clear_display")
def test_present_frame_applies_pending_resize(
    mock_clear: MagicMock,
    _mock_flip: MagicMock,
) -> None:
    window, compositor, _host = _resizable_window()
    window.note_event(_size_event(1024, 768))
    present_frame(window, lambda: None)
    compositor.set_display_size.assert_called_once_with(1024, 768)
    mock_clear.assert_called_once_with(1024, 768)


def test_display_flags_make_the_window_resizable() -> None:
    from cleave.viz import loading

    assert loading._GL_DISPLAY_FLAGS & pygame.RESIZABLE


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


@patch("cleave.viz.imgui_host.ImGuiHost.create")
@patch("cleave.viz.loading.present_frame")
@patch("cleave.viz.loading.GlCompositor")
@patch("cleave.viz.loading.pygame.display.set_caption")
@patch("cleave.viz.loading._desktop_size", return_value=(1366, 768))
@patch("cleave.viz.loading._maximise")
@patch("cleave.viz.loading.sdl_window.set_minimum_size")
@patch("cleave.viz.loading.pygame.display.set_mode")
def test_open_loading_window_fits_saved_size_to_desktop_and_maximises(
    mock_set_mode: MagicMock,
    mock_min_size: MagicMock,
    mock_maximise: MagicMock,
    _mock_desktop: MagicMock,
    _mock_caption: MagicMock,
    _mock_gl: MagicMock,
    _mock_draw: MagicMock,
    _mock_imgui: MagicMock,
) -> None:
    from cleave.config_schema.window import WINDOW_DESKTOP_MARGIN, WindowGeometry
    from cleave.user_config import persist_window_geometry
    from cleave.viz.theme import set_ui_scale_percent

    persist_window_geometry(WindowGeometry(width=2560, height=1440))
    pygame.init()
    window = open_loading_window()
    try:
        fitted = (1366 - WINDOW_DESKTOP_MARGIN, 768 - WINDOW_DESKTOP_MARGIN)
        mock_set_mode.assert_called_once()
        assert mock_set_mode.call_args.args[0] == fitted
        mock_maximise.assert_called_once_with()
        assert window.maximised is True
        assert window.geometry() == WindowGeometry(*fitted, maximised=True)
        mock_min_size.assert_called_once_with(1024, 600)
    finally:
        set_ui_scale_percent(100)


@patch("cleave.viz.loading.sdl_window.window_flags", return_value=None)
def test_restored_size_ignores_sizes_while_maximised(_mock_flags: MagicMock) -> None:
    from cleave.config_schema.window import WindowGeometry

    window, _compositor, _host = _resizable_window()
    window.note_event(_size_event(1000, 700))
    window.note_event(pygame.event.Event(pygame.WINDOWMAXIMIZED))
    window.note_event(_size_event(1920, 1040))
    assert window.geometry() == WindowGeometry(1000, 700, maximised=True)
    assert window.pending_size == (1920, 1040)
    window.note_event(pygame.event.Event(pygame.WINDOWRESTORED))
    window.note_event(_size_event(1000, 700))
    assert window.geometry() == WindowGeometry(1000, 700, maximised=False)


def test_restored_size_reads_sdl_maximised_flag() -> None:
    from cleave.viz import sdl_window

    window, _compositor, _host = _resizable_window()
    window.restored_size = (900, 600)
    with patch(
        "cleave.viz.loading.sdl_window.window_flags",
        return_value=sdl_window.SDL_WINDOW_MAXIMIZED,
    ):
        # The size change can arrive before the maximise event.
        window.note_event(_size_event(1920, 1040))
    assert window.restored_size == (900, 600)
    assert window.maximised is True


@patch("cleave.viz.loading.sdl_window.set_minimum_size")
@patch("cleave.viz.loading._desktop_size", return_value=(5120, 1440))
def test_sync_minimum_size_follows_ui_scale(
    _mock_desktop: MagicMock, mock_min_size: MagicMock
) -> None:
    from cleave.viz.theme import set_ui_scale_percent

    window, _compositor, _host = _resizable_window()
    try:
        set_ui_scale_percent(100)
        window.sync_minimum_size()
        window.sync_minimum_size()
        mock_min_size.assert_called_once_with(1024, 600)
        set_ui_scale_percent(200)
        window.sync_minimum_size()
        assert mock_min_size.call_args.args == (2048, 1200)
    finally:
        set_ui_scale_percent(100)


def test_toggle_fullscreen_switches_desktop_fullscreen_and_back() -> None:
    window, _compositor, _host = _resizable_window()
    sdl_window_obj = MagicMock()
    window_cls = MagicMock()
    window_cls.from_display_module.return_value = sdl_window_obj
    with patch("pygame._sdl2.video.Window", window_cls):
        window.toggle_fullscreen()
        sdl_window_obj.set_fullscreen.assert_called_once_with(desktop=True)
        assert window.fullscreen is True
        window.toggle_fullscreen()
        sdl_window_obj.set_windowed.assert_called_once_with()
        assert window.fullscreen is False


def test_splash_fades_in_holds_and_fades_out() -> None:
    assert splash_alpha(0.0) == 0.0
    assert splash_alpha(SPLASH_SEC / 2) == 1.0
    assert splash_alpha(SPLASH_SEC) == 0.0
    assert 0.0 < splash_alpha(0.1) < 1.0


@patch("cleave.viz.loading.present_frame")
@patch("cleave.viz.loading.pygame.event.get")
def test_splash_ends_on_a_key(mock_get: MagicMock, mock_present: MagicMock) -> None:
    pygame.init()
    window = MagicMock()
    window.quit_requested = False
    mock_get.return_value = [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)]
    show_splash(window)
    mock_present.assert_not_called()
    window.clear.assert_called_once_with()
    assert window.quit_requested is False


@patch("cleave.viz.loading.present_frame")
@patch("cleave.viz.loading.pygame.event.get")
def test_splash_close_requests_quit(mock_get: MagicMock, mock_present: MagicMock) -> None:
    pygame.init()
    window = MagicMock()
    window.quit_requested = False
    mock_get.return_value = [pygame.event.Event(pygame.QUIT)]
    show_splash(window)
    assert window.quit_requested is True
    window.clear.assert_not_called()


def test_splash_draw_runs_in_an_imgui_frame() -> None:
    from cleave.viz.loading import _SplashDraw

    with _host() as host:
        host.begin_frame(1.0 / 60.0)
        base = imgui.get_font_size()
        _SplashDraw("tagline", "credit © 2031", "v1.0.0", 0.5)()
        assert imgui.get_font_size() == base
        host.end_frame()
