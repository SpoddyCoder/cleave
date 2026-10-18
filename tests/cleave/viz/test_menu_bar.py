"""Menu bar focus, highlight, and activation. No GL window."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pygame

from cleave.viz.commands import SEPARATOR, Command, CommandContext, Menu
from cleave.viz.menu_bar import MenuBarState

_LABELS = ("File", "Project", "Layers", "Render", "Timeline", "Settings", "Help")


def _command(command_id: str, runs: list[tuple[str, bool]], *, enabled: bool = True) -> Command:
    def run(_controls: object) -> None:
        runs.append((command_id, False))

    return Command(
        id=command_id,
        label=command_id,
        kind="command",
        enabled=lambda _ctx, allowed=enabled: allowed,
        run=run,
    )


def _menus(runs: list[tuple[str, bool]]) -> tuple[Menu, ...]:
    first = Menu(
        "File",
        (
            _command("disabled", runs, enabled=False),
            SEPARATOR,
            _command("enabled", runs),
        ),
    )
    rest = tuple(
        Menu(label, (_command(label.lower(), runs),)) for label in _LABELS[1:]
    )
    return (first, *rest)


def _press(state: MenuBarState, key: int, menus: tuple[Menu, ...], runs: list) -> bool:
    return state.handle_keydown(key, menus, CommandContext(), None)


def test_arrows_wrap_and_skip_separators() -> None:
    runs: list[tuple[str, bool]] = []
    menus = _menus(runs)
    state = MenuBarState()
    state.focus()
    assert state.menu_index == 0
    assert not state.dropdown_open

    assert _press(state, pygame.K_LEFT, menus, runs)
    assert state.menu_index == len(menus) - 1
    assert _press(state, pygame.K_RIGHT, menus, runs)
    assert state.menu_index == 0
    assert _press(state, pygame.K_RIGHT, menus, runs)
    assert state.menu_index == 1
    assert _press(state, pygame.K_LEFT, menus, runs)
    assert state.menu_index == 0

    assert _press(state, pygame.K_DOWN, menus, runs)
    assert state.dropdown_open
    assert state.highlighted_command(menus).id == "disabled"
    assert _press(state, pygame.K_DOWN, menus, runs)
    assert state.highlighted_command(menus).id == "enabled"
    assert _press(state, pygame.K_DOWN, menus, runs)
    assert state.highlighted_command(menus).id == "disabled"
    assert _press(state, pygame.K_UP, menus, runs)
    assert state.highlighted_command(menus).id == "enabled"
    assert runs == []


def test_enter_runs_command_after_closing_menu() -> None:
    seen: list[bool] = []

    def run(_controls: object) -> None:
        seen.append(state.dropdown_open or state.focused)

    command = Command(
        id="go",
        label="Go",
        kind="command",
        run=run,
    )
    menus = (Menu("File", (command,)),)
    state = MenuBarState()
    state.focus()
    assert state.handle_keydown(pygame.K_DOWN, menus, CommandContext(), None)
    assert state.dropdown_open
    assert state.handle_keydown(pygame.K_RETURN, menus, CommandContext(), None)
    assert seen == [False]
    assert not state.dropdown_open
    assert not state.focused


def test_esc_closes_dropdown_then_bar() -> None:
    runs: list[tuple[str, bool]] = []
    menus = _menus(runs)
    state = MenuBarState()
    state.focus()
    _press(state, pygame.K_DOWN, menus, runs)
    assert state.dropdown_open
    assert _press(state, pygame.K_ESCAPE, menus, runs)
    assert not state.dropdown_open
    assert state.focused
    assert _press(state, pygame.K_ESCAPE, menus, runs)
    assert not state.focused

    state.focus()
    assert not state.dropdown_open
    assert _press(state, pygame.K_ESCAPE, menus, runs)
    assert not state.focused


def test_disabled_enter_does_not_run() -> None:
    runs: list[tuple[str, bool]] = []
    menus = _menus(runs)
    state = MenuBarState()
    state.focus()
    _press(state, pygame.K_DOWN, menus, runs)
    assert state.highlighted_command(menus).id == "disabled"
    assert _press(state, pygame.K_RETURN, menus, runs)
    assert runs == []
    assert state.dropdown_open
    assert state.focused
    assert state.highlighted_command(menus).id == "disabled"


def test_click_uses_the_same_close_then_run_path() -> None:
    runs: list[tuple[str, bool]] = []
    menus = _menus(runs)
    state = MenuBarState()
    state.click_item(0, 0, menus, CommandContext(), None)
    assert runs == []
    assert state.dropdown_open
    assert state.highlighted_command(menus).id == "disabled"

    state.click_item(0, 2, menus, CommandContext(), None)
    assert runs == [("enabled", False)]
    assert not state.dropdown_open
    assert not state.focused


def test_shell_host_imports_without_a_context() -> None:
    from imgui_bundle import imgui

    from cleave.viz.shell_host import RENDERER_CLASS

    assert RENDERER_CLASS.__name__ == "ProgrammablePipelineRenderer"
    assert not imgui.get_current_context()


def test_menu_bar_height_px_needs_no_gl_context() -> None:
    from imgui_bundle import imgui

    from cleave.viz.shell_host import menu_bar_height_px
    from cleave.viz.theme import tuning_ui_metrics

    assert imgui.get_current_context() is None
    height = menu_bar_height_px()
    assert height == max(1, round(float(tuning_ui_metrics().font_size) + 6.0))
    assert imgui.get_current_context() is None


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


def _shell_controls() -> SimpleNamespace:
    return SimpleNamespace(session=SimpleNamespace(layer_z_order=()))


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

    from cleave.viz import shell_host

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
        shell_host._install_pyopengl_context(zero)
        with patch.object(shell_host, "_native_context_getter", return_value=None):
            assert shell_host._select_renderer_class() is shell_host._HeadlessRenderer
        with patch.object(shell_host, "_native_context_getter", return_value=live):
            selected = shell_host._select_renderer_class()
        assert gl_platform.GetCurrentContext() == 1
        assert selected is shell_host.RENDERER_CLASS
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

    from cleave.viz import shell_host

    with (
        patch.object(shell_host, "_gl_context_current", return_value=True),
        patch.object(shell_host, "RENDERER_CLASS", _FakeRenderer),
    ):
        host = shell_host.ShellHost.create(
            _Overlay(), MenuBarState(), _shell_controls()
        )
    try:
        assert isinstance(host._renderer, _FakeRenderer)
    finally:
        host.destroy()
    assert not imgui.get_current_context()


def test_top_strip_motion_wakes_overlay_and_draw_without_gl() -> None:
    """The crash: visibility leaves 0, then new_frame runs with no font atlas."""
    from imgui_bundle import imgui

    from cleave.viz import shell_host

    overlay = _Overlay()
    menu = MenuBarState()
    with patch.object(shell_host, "_gl_context_current", return_value=False):
        host = shell_host.ShellHost.create(overlay, menu, _shell_controls())
    try:
        assert isinstance(host._renderer, shell_host._HeadlessRenderer)
        host.draw(menu, CommandContext(), overlay.visibility, 1.0 / 60.0)
        host.process_event(_motion(host.menu_bar_height_px + 8))
        assert overlay.visibility == 0.0
        host.process_event(_motion(0))
        assert overlay.visibility == 1.0
        host.draw(menu, CommandContext(), overlay.visibility, 1.0 / 60.0)
        assert imgui.get_io().fonts.is_built()
    finally:
        host.destroy()
    assert not imgui.get_current_context()
