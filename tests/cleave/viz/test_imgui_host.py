"""ImGui host renderer selection, lifetime, and skipped-frame input. No GL window."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pygame

from cleave.viz.commands import CommandContext
from cleave.viz.menu_bar import MenuBarState


class _FakeRenderer:
    def shutdown(self) -> None:
        return None

    def render(self, _draw_data: object) -> None:
        return None


def _open_shell(menu: MenuBarState):
    from cleave.viz.imgui_host import ImGuiHost
    from cleave.viz.shell_host import ShellHost, menu_bar_height_px

    controls = SimpleNamespace(
        session=SimpleNamespace(layer_z_order=()),
        disarm_value_nudge=MagicMock(),
    )
    return ShellHost(
        ImGuiHost.create(),
        menu,
        controls,
        menu_bar_height_px(),
    )


def _motion(y: int) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEMOTION,
        pos=(2, y),
        rel=(0, 0),
        buttons=(0, 0, 0),
    )


def test_gl_renderer_waits_until_native_context_is_installed() -> None:
    """A null PyOpenGL context stays headless until a native context is bound."""
    import OpenGL.platform as gl_platform

    from cleave.viz import imgui_host

    plat = gl_platform.PLATFORM
    saved = (
        gl_platform.GetCurrentContext,
        gl_platform.CurrentContextIsValid,
        plat.GetCurrentContext,
        plat.CurrentContextIsValid,
    )

    def zero() -> int:
        return 0

    def live() -> int:
        return 1

    try:
        imgui_host._install_pyopengl_context(zero)
        with patch.object(imgui_host, "_native_context_getter", return_value=None):
            assert imgui_host._select_renderer_class() is imgui_host._HeadlessRenderer
        with patch.object(imgui_host, "_native_context_getter", return_value=live):
            selected = imgui_host._select_renderer_class()
        assert gl_platform.GetCurrentContext() == 1
        assert selected is imgui_host.RENDERER_CLASS
        assert selected.__name__ == "ProgrammablePipelineRenderer"
    finally:
        (
            gl_platform.GetCurrentContext,
            gl_platform.CurrentContextIsValid,
            plat.GetCurrentContext,
            plat.CurrentContextIsValid,
        ) = saved


def test_create_uses_programmable_renderer_when_gl_context_is_current() -> None:
    from imgui_bundle import imgui

    from cleave.viz import imgui_host

    with (
        patch.object(imgui_host, "_gl_context_current", return_value=True),
        patch.object(imgui_host, "RENDERER_CLASS", _FakeRenderer),
    ):
        host = _open_shell(MenuBarState())
    try:
        assert isinstance(host.imgui.renderer, _FakeRenderer)
    finally:
        host.imgui.destroy()
    assert not imgui.get_current_context()


def test_shell_frames_build_the_font_atlas_without_gl() -> None:
    """Headless frames must build the font atlas before the context is destroyed."""
    from imgui_bundle import imgui

    from cleave.viz import imgui_host
    from cleave.viz.shell_host import draw_shell_frame

    menu = MenuBarState()
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(menu)
    try:
        assert isinstance(host.imgui.renderer, imgui_host._HeadlessRenderer)
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        host.process_event(_motion(host.menu_bar_height_px + 8))
        host.process_event(_motion(0))
        # One menu-bar frame, then destroy, makes the next context assert on
        # the menu buttons. A second frame leaves Dear ImGui settled.
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        assert imgui.get_io().fonts.is_built()
    finally:
        host.imgui.destroy()
    assert not imgui.get_current_context()




def test_ui_scale_change_rebuilds_the_font_atlas_on_the_next_frame() -> None:
    from imgui_bundle import imgui

    from cleave.config_schema.editor import DEFAULT_UI_SCALE
    from cleave.viz import imgui_host
    from cleave.viz.shell_host import draw_shell_frame
    from cleave.viz.theme import set_ui_scale_percent, tuning_ui_metrics

    menu = MenuBarState()
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(menu)
    try:
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        base_size = imgui.get_io().font_default.font_size
        base_pad = imgui.get_style().item_spacing.x
        assert base_size == tuning_ui_metrics().font_size
        set_ui_scale_percent(200)
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        assert imgui.get_io().font_default.font_size == tuning_ui_metrics().font_size
        assert imgui.get_io().font_default.font_size > base_size
        assert imgui.get_style().item_spacing.x == base_pad * 2
        assert imgui.get_io().fonts.is_built()
    finally:
        set_ui_scale_percent(DEFAULT_UI_SCALE)
        host.imgui.destroy()


def test_frames_use_the_pushed_display_size_not_the_pygame_surface() -> None:
    """A resized GL window keeps its old pygame surface size; the host trusts the push."""
    from imgui_bundle import imgui

    from cleave.viz import imgui_host
    from cleave.viz.imgui_host import ImGuiHost

    pygame.init()
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = ImGuiHost.create()
    try:
        host.set_display_size(1234, 567)
        stale = MagicMock()
        stale.get_size.return_value = (640, 360)
        with patch.object(imgui_host.pygame.display, "get_surface", return_value=stale):
            for _ in range(2):
                host.begin_frame(1.0 / 60.0)
                size = imgui.get_io().display_size
                host.end_frame()
        assert (size.x, size.y) == (1234.0, 567.0)
    finally:
        host.destroy()
