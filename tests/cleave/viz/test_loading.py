"""Tests for visualizer boot loading screen."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pygame
import pytest
from OpenGL.GL import GL_COLOR_BUFFER_BIT, GL_FRAMEBUFFER
from imgui_bundle import imgui

from cleave.viz.imgui_theme import rgba
from cleave.viz.loading import (
    LoadingWindow,
    clamp_loading_fraction,
    draw_loading_content,
    loading_bar_width,
    loading_content_layout,
    open_loading_window,
    present_frame,
)
from cleave.viz.modal_surface import ImGuiTextMeasure
from cleave.viz.theme import BACKGROUND, BORDER_WIDTH, LABEL, VALUE


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


def _pack(role: tuple[int, int, int]) -> int:
    return int(imgui.get_color_u32(rgba(role)))


def _content_names() -> list[str]:
    lists = list(imgui.get_draw_data().cmd_lists)
    names = [str(draw_list._owner_name) for draw_list in lists]
    del lists
    return names


def _loading_quads() -> list[tuple[float, float, float, float, int]]:
    found: list[tuple[float, float, float, float, int]] = []
    lists = list(imgui.get_draw_data().cmd_lists)
    try:
        for draw_list in lists:
            if str(draw_list._owner_name) != "##loading":
                continue
            vtx = draw_list.vtx_buffer
            idx = draw_list.idx_buffer
            count = int(idx.size())
            step = 0
            while step + 6 <= count:
                ids = [int(idx[step + offset]) for offset in range(6)]
                unique = list(dict.fromkeys(ids))
                if len(unique) == 4:
                    xs = [float(vtx[vertex].pos.x) for vertex in unique]
                    ys = [float(vtx[vertex].pos.y) for vertex in unique]
                    colors = {int(vtx[vertex].col) for vertex in unique}
                    if len(colors) == 1:
                        found.append(
                            (
                                min(xs),
                                min(ys),
                                max(xs) - min(xs),
                                max(ys) - min(ys),
                                colors.pop(),
                            )
                        )
                step += 6
    finally:
        del lists
    return found


def _loading_colors() -> set[int]:
    found: set[int] = set()
    lists = list(imgui.get_draw_data().cmd_lists)
    try:
        for draw_list in lists:
            if str(draw_list._owner_name) != "##loading":
                continue
            vtx = draw_list.vtx_buffer
            for index in range(int(vtx.size())):
                found.add(int(vtx[index].col))
    finally:
        del lists
    return found


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


def _draw_frame(
    host: object,
    message: str,
    *,
    fraction: float | None = None,
    detail: str | None = None,
    size: tuple[int, int] = (640, 360),
) -> tuple[object, list[tuple[float, float, float, float, int]], set[int]]:
    host.display_size = size
    host.begin_frame(1.0 / 60.0)
    measure = ImGuiTextMeasure()
    detail_size = measure.size(detail) if detail else None
    layout = loading_content_layout(
        size[0],
        size[1],
        measure.size(message),
        detail_size=detail_size,
        fraction=fraction,
    )
    draw_loading_content(
        message,
        size[0],
        size[1],
        fraction=fraction,
        detail=detail,
    )
    host.end_frame()
    return layout, _loading_quads(), _loading_colors()


def test_loading_content_bar_fraction_and_detail() -> None:
    message = "Loading..."
    with _host() as host:
        half, quads, _colors = _draw_frame(host, message, fraction=0.5)
        assert half.fill_rect is not None
        _fx, _fy, fill_w, _fh = half.fill_rect
        value = _pack(VALUE)
        fills = [quad for quad in quads if quad[4] == value and abs(quad[2] - fill_w) <= 1.0]
        assert fills, quads

        empty, quads, _colors = _draw_frame(host, message, fraction=0.0)
        assert empty.bar_rect is not None
        assert empty.fill_rect is None
        bar_x, bar_y, bar_w, bar_h = empty.bar_rect
        tracks = [
            quad
            for quad in quads
            if abs(quad[2] - bar_w) <= 1.0 and abs(quad[3] - bar_h) <= 1.0
        ]
        assert tracks, quads
        inner_top = bar_y + BORDER_WIDTH
        inner_bottom = bar_y + bar_h - BORDER_WIDTH
        fills = [
            quad
            for quad in quads
            if quad[4] == value
            and quad[0] >= bar_x + BORDER_WIDTH - 1
            and inner_top - 1 <= quad[1]
            and quad[1] + quad[3] <= inner_bottom + 1
            and quad[2] > 1.0
        ]
        assert not fills

        missing, quads, _colors = _draw_frame(host, message, fraction=None)
        assert missing.bar_rect is None
        bar_w = loading_bar_width(640)
        assert not any(abs(quad[2] - bar_w) <= 1.0 for quad in quads)

        _layout, _quads, colors = _draw_frame(
            host, message, detail="Downloading htdemucs"
        )
        assert _pack(LABEL) in colors
        _layout, _quads, colors = _draw_frame(host, message)
        assert _pack(LABEL) not in colors
    assert not imgui.get_current_context()


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
    red, green, blue = BACKGROUND
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
def test_present_frame_scrim_precedes_loading_content(
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
        present_frame(
            window,
            lambda: draw_loading_content("Loading...", 640, 360),
            scrim=False,
        )
        assert "##loading-scrim" not in _content_names()
        assert "##loading" in _content_names()

        present_frame(
            window,
            lambda: draw_loading_content("Loading...", 640, 360),
            scrim=True,
        )
        names = _content_names()
        assert names.index("##loading-scrim") < names.index("##loading")


@patch("cleave.viz.imgui_host.ImGuiHost.create")
@patch("cleave.viz.loading.present_frame")
@patch("cleave.viz.loading.GlCompositor")
@patch("cleave.viz.loading.pygame.display.set_caption")
@patch("cleave.viz.loading.pygame.display.set_mode")
def test_open_loading_window_uses_editor_defaults(
    mock_set_mode: MagicMock,
    mock_set_caption: MagicMock,
    mock_gl: MagicMock,
    mock_draw: MagicMock,
    mock_imgui_create: MagicMock,
) -> None:
    from cleave.config_schema.editor import editor_display_size
    from cleave.gl_color_format import RGBA8

    compositor = MagicMock()
    mock_gl.return_value = compositor
    host = MagicMock()
    mock_imgui_create.return_value = host
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
    mock_imgui_create.assert_called_once()
    assert window.imgui is host
    mock_draw.assert_called_once()
    assert mock_draw.call_args.args[0] is window
    assert mock_draw.call_args.args[1].message == "Loading..."
    assert mock_draw.call_args.args[1].fraction is None
    assert mock_draw.call_args.args[1].detail is None
    assert mock_draw.call_args.kwargs["scrim"] is False
    assert window.display_width == width
    assert window.display_height == height
    assert window.quit_requested is False

    order: list[str] = []
    host.destroy.side_effect = lambda: order.append("destroy")
    with patch("cleave.viz.loading.pygame.quit", side_effect=lambda: order.append("quit")):
        window.close()
        assert order == ["destroy", "quit"]
        assert window.imgui is None
        window.release_imgui()
        window.close()
    host.destroy.assert_called_once()
    assert order == ["destroy", "quit", "quit"]


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
        assert window.update("Separating stems...", 0.4, "12 MB of 30 MB") is True
    mock_draw.assert_called_once()
    assert mock_draw.call_args.args[0] is window
    drawn = mock_draw.call_args.args[1]
    assert drawn.message == "Separating stems..."
    assert drawn.fraction == 0.4
    assert drawn.detail == "12 MB of 30 MB"
    assert mock_draw.call_args.kwargs["scrim"] is False
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
