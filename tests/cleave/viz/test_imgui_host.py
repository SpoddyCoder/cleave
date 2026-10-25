"""ImGui host renderer selection, lifetime, and skipped-frame input. No GL window."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pygame

from cleave.viz.commands import CommandContext
from cleave.viz.menu_bar import MenuBarState


class _Overlay:
    def __init__(self) -> None:
        self.visibility = 0.0

    def notify_input(self) -> None:
        self.visibility = 1.0


class _FakeRenderer:
    def shutdown(self) -> None:
        return None

    def render(self, _draw_data: object) -> None:
        return None


def _open_shell(overlay: _Overlay, menu: MenuBarState):
    from cleave.viz.imgui_host import ImGuiHost
    from cleave.viz.shell_host import ShellHost, menu_bar_height_px

    controls = SimpleNamespace(session=SimpleNamespace(layer_z_order=()))
    return ShellHost(
        ImGuiHost.create(),
        overlay,
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
        host = _open_shell(_Overlay(), MenuBarState())
    try:
        assert isinstance(host.imgui.renderer, _FakeRenderer)
    finally:
        host.imgui.destroy()
    assert not imgui.get_current_context()


def test_top_strip_motion_wakes_overlay_and_draw_without_gl() -> None:
    """The crash: visibility leaves 0, then new_frame runs with no font atlas."""
    from imgui_bundle import imgui

    from cleave.viz import imgui_host
    from cleave.viz.shell_host import draw_shell_frame

    overlay = _Overlay()
    menu = MenuBarState()
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu)
    try:
        assert isinstance(host.imgui.renderer, imgui_host._HeadlessRenderer)
        draw_shell_frame(
            host, menu, CommandContext(), overlay.visibility, 1.0 / 60.0
        )
        host.process_event(_motion(host.menu_bar_height_px + 8))
        assert overlay.visibility == 0.0
        host.process_event(_motion(0))
        assert overlay.visibility == 1.0
        draw_shell_frame(
            host, menu, CommandContext(), overlay.visibility, 1.0 / 60.0
        )
        # One menu-bar frame, then destroy, makes the next context assert on
        # the menu buttons. A second frame leaves Dear ImGui settled.
        draw_shell_frame(
            host, menu, CommandContext(), overlay.visibility, 1.0 / 60.0
        )
        assert imgui.get_io().fonts.is_built()
    finally:
        host.imgui.destroy()
    assert not imgui.get_current_context()


def test_skipped_frame_discards_queued_buttons() -> None:
    from cleave.viz import imgui_host
    from cleave.viz.shell_host import draw_shell_frame

    overlay = _Overlay()
    menu = MenuBarState()
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu)
    try:
        host.imgui.process_mouse_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(4, 4), button=1)
        )
        assert host.imgui.queued_buttons
        with patch.object(
            host.imgui, "begin_frame", side_effect=AssertionError("frame started")
        ):
            draw_shell_frame(host, menu, CommandContext(), 0.0, 1.0 / 60.0)
        assert host.imgui.queued_buttons == []
    finally:
        host.imgui.destroy()
