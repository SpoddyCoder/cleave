"""Menu bar focus, highlight, and activation. No GL window."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pygame

from cleave.viz.commands import MENUS, SEPARATOR, Command, CommandContext, Menu
from cleave.viz.menu_bar import MenuBarState, menu_index_for_mnemonic, menu_mnemonic
from cleave.viz.shell_focus import ShellRegion

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


def test_menu_mnemonics_are_the_unique_first_letters() -> None:
    letters = tuple(menu_mnemonic(menu.label).upper() for menu in MENUS)
    assert letters == ("F", "P", "L", "R", "T", "S", "H")
    assert len(set(letters)) == len(letters)
    assert MENUS[0].label == "File"
    assert menu_index_for_mnemonic(MENUS, "F") == 0
    assert menu_index_for_mnemonic(MENUS, "f") == 0
    assert menu_index_for_mnemonic(MENUS, "q") is None
    assert menu_mnemonic("") == ""


def test_open_menu_focuses_dropdown_and_stays_open() -> None:
    runs: list[tuple[str, bool]] = []
    menus = _menus(runs)
    state = MenuBarState()
    state.note_alt_keydown()
    state.open_menu(0, menus)
    assert state.focused
    assert state.menu_index == 0
    assert state.dropdown_open
    assert state.highlighted_command(menus).id == "disabled"
    assert state.complete_alt_tap() is False
    assert state.focused
    assert state.dropdown_open
    state.open_menu(0, menus)
    assert state.focused
    assert state.dropdown_open
    assert state.menu_index == 0
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


def _at(pos: tuple[int, int], kind: int) -> pygame.event.Event:
    if kind == pygame.MOUSEMOTION:
        return pygame.event.Event(
            pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)
        )
    return pygame.event.Event(kind, pos=pos, button=1)


def _open_shell(overlay: _Overlay, menu: MenuBarState, controls: object | None = None):
    from cleave.viz.imgui_host import ImGuiHost
    from cleave.viz.shell_host import ShellHost, menu_bar_height_px

    if controls is None:
        controls = _shell_controls()
    return ShellHost(
        ImGuiHost.create(),
        overlay,
        menu,
        controls,
        menu_bar_height_px(),
    )


def test_mouse_switches_and_closes_an_open_top_menu() -> None:
    """A click on another label must complete while the dropdown is open."""
    from unittest.mock import patch

    from cleave.viz import imgui_host

    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu)
    anchors: dict[int, tuple[float, float]] = {}
    draw_bar = host._draw_bar

    def remember(state: MenuBarState):
        rule_y, found, menus = draw_bar(state)
        anchors.clear()
        anchors.update(found)
        return rule_y, found, menus

    host._draw_bar = remember
    host.imgui.display_size = (1280, 720)

    def draw() -> None:
        from cleave.viz.shell_host import draw_shell_frame

        draw_shell_frame(host, menu, CommandContext(), overlay.visibility, 1.0 / 60.0)

    def click(index: int) -> None:
        x, y = anchors[index]
        pos = (int(x) + 8, int(y) - 8)
        host.process_event(_at(pos, pygame.MOUSEMOTION))
        draw()
        host.process_event(_at(pos, pygame.MOUSEBUTTONDOWN))
        draw()
        host.process_event(_at(pos, pygame.MOUSEBUTTONUP))
        draw()

    try:
        host.process_event(_at((20, 10), pygame.MOUSEMOTION))
        draw()
        click(0)
        assert menu.dropdown_open
        assert menu.menu_index == 0
        click(1)
        assert menu.dropdown_open
        assert menu.menu_index == 1
        click(1)
        assert not menu.dropdown_open
    finally:
        host.imgui.destroy()


def test_shell_host_imports_without_a_context() -> None:
    from imgui_bundle import imgui

    from cleave.viz import shell_host
    from cleave.viz.imgui_host import RENDERER_CLASS

    assert shell_host.ShellHost.__name__ == "ShellHost"
    assert RENDERER_CLASS.__name__ == "ProgrammablePipelineRenderer"
    assert not imgui.get_current_context()


def test_menu_bar_height_px_needs_no_gl_context() -> None:
    from imgui_bundle import imgui

    from cleave.viz.shell_host import menu_bar_height_px
    from cleave.viz.theme import tuning_ui_metrics

    assert imgui.get_current_context() is None
    height = menu_bar_height_px()
    assert height == max(1, round(float(tuning_ui_metrics().font_size) + 16.0))
    assert imgui.get_current_context() is None


def _draw_list_has_color(draw_list: object, color: int) -> bool:
    for vtx in draw_list.vtx_buffer:
        if int(vtx.col) == color:
            return True
    return False


def _content_lists(lists: list) -> list:
    """Window lists in paint order. The foreground list is not one of them."""
    return [
        draw_list
        for draw_list in lists
        if "Foreground" not in str(draw_list._owner_name)
    ]


def _color_u32(rgb: tuple[int, int, int]) -> int:
    from imgui_bundle import imgui

    return int(
        imgui.get_color_u32(
            imgui.ImVec4(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, 1.0)
        )
    )


def _assert_chrome_last(lists: list) -> list:
    content = _content_lists(lists)
    names = [draw_list._owner_name for draw_list in content]
    assert names[-1] == "##shell-chrome", names
    for name in (
        "##MainMenuBar",
        "##shell-transport",
        "##shell-navigator",
        "##shell-inspector",
    ):
        assert names.index(name) < names.index("##shell-chrome"), names
    foreground = [
        draw_list
        for draw_list in lists
        if "Foreground" in str(draw_list._owner_name)
    ]
    return foreground


def test_open_menu_paints_over_the_transport_rule() -> None:
    """The transport rule stays on its window, under a later menu popup."""
    from imgui_bundle import imgui

    from cleave.viz import imgui_host, shell_host
    from cleave.viz.shell_host import draw_shell_frame
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.theme import BORDER_COLOR, TRANSPORT_RULE

    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    controls = _shell_controls()
    controls.build_view_state = lambda **_kwargs: None
    controls.focus_cursor = None
    controls.shell_focus = SimpleNamespace(region=ShellRegion.NAVIGATOR)
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu, controls)
    try:
        host.imgui.display_size = (1280, 720)
        height = shell_host.menu_bar_height_px()
        host.set_layout(ShellLayout.compute(1280, 720, height, height, 0))
        host.process_event(_motion(4))
        host._draw_navigator = lambda: None
        host._draw_inspector = lambda _state: None
        # The font atlas is built on the first frame. Open the menu after that.
        draw_shell_frame(host, menu, CommandContext(), 1.0, 1.0 / 60.0)
        menu.open_menu(0, MENUS)
        # The popup's first frame is hidden while it measures. The next frame paints it.
        draw_shell_frame(host, menu, CommandContext(), 1.0, 1.0 / 60.0)
        draw_shell_frame(host, menu, CommandContext(), 1.0, 1.0 / 60.0)
        assert host.menu_bar_height_px == height
        lists = list(imgui.get_draw_data().cmd_lists)
        content = _content_lists(lists)
        names = [draw_list._owner_name for draw_list in content]
        foreground = _assert_chrome_last(lists)
        transport_at = names.index("##shell-transport")
        popup_at = names.index("##cleave-menu")
        chrome_at = names.index("##shell-chrome")
        assert transport_at < popup_at < chrome_at
        grey = _color_u32(TRANSPORT_RULE)
        white = _color_u32(BORDER_COLOR)
        on_transport = _draw_list_has_color(content[transport_at], grey)
        on_popup = _draw_list_has_color(content[popup_at], grey)
        on_chrome = _draw_list_has_color(content[chrome_at], grey)
        rule_on_chrome = _draw_list_has_color(content[chrome_at], white)
        rule_on_foreground = any(
            _draw_list_has_color(draw_list, white) for draw_list in foreground
        )
        del lists, content
    finally:
        host.imgui.destroy()
    assert on_transport
    assert not on_popup
    assert not on_chrome
    assert rule_on_chrome
    assert not rule_on_foreground


def test_open_menu_paints_over_the_focus_ring() -> None:
    """The row highlight stays on its panel, under a later menu popup."""
    from imgui_bundle import imgui

    from cleave.viz import imgui_host, shell_host
    from cleave.viz.shell_host import draw_shell_frame
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.theme import BORDER_COLOR, HIGHLIGHT

    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    controls = _shell_controls()
    controls.build_view_state = lambda **_kwargs: None
    controls.focus_cursor = None
    controls.shell_focus = SimpleNamespace(region=ShellRegion.NAVIGATOR)
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu, controls)
    try:
        host.imgui.display_size = (1280, 720)
        height = shell_host.menu_bar_height_px()
        host.set_layout(ShellLayout.compute(1280, 720, height, height, 80))
        host.process_event(_motion(4))
        controls.session.timeline = SimpleNamespace(panel_open=True)
        controls.shell_focus.region = ShellRegion.TIMELINE

        def draw_focused_row() -> None:
            imgui.selectable("Focused##row", True)
            shell_host._draw_item_focus_ring()

        host._draw_navigator = draw_focused_row
        host._draw_inspector = lambda _state: None
        # The font atlas is built on the first frame. The strip border is on
        # chrome while the strip has focus; an open menu takes that focus.
        draw_shell_frame(host, menu, CommandContext(), 1.0, 1.0 / 60.0)
        strip_lists = list(imgui.get_draw_data().cmd_lists)
        strip_content = _content_lists(strip_lists)
        strip_names = [draw_list._owner_name for draw_list in strip_content]
        strip_foreground = _assert_chrome_last(strip_lists)
        gold = _color_u32(HIGHLIGHT)
        white = _color_u32(BORDER_COLOR)
        strip_on_chrome = _draw_list_has_color(
            strip_content[strip_names.index("##shell-chrome")], gold
        )
        strip_on_foreground = any(
            _draw_list_has_color(draw_list, gold) for draw_list in strip_foreground
        )
        rule_on_foreground = any(
            _draw_list_has_color(draw_list, white) for draw_list in strip_foreground
        )
        del strip_lists, strip_content
        controls.shell_focus.region = ShellRegion.NAVIGATOR
        menu.open_menu(0, MENUS)
        # The popup's first frame is hidden while it measures. The next frame paints it.
        draw_shell_frame(host, menu, CommandContext(), 1.0, 1.0 / 60.0)
        draw_shell_frame(host, menu, CommandContext(), 1.0, 1.0 / 60.0)
        lists = list(imgui.get_draw_data().cmd_lists)
        content = _content_lists(lists)
        names = [draw_list._owner_name for draw_list in content]
        foreground = _assert_chrome_last(lists)
        nav_at = names.index("##shell-navigator")
        popup_at = names.index("##cleave-menu")
        chrome_at = names.index("##shell-chrome")
        assert nav_at < popup_at < chrome_at
        ring_on_nav = _draw_list_has_color(content[nav_at], gold)
        ring_on_popup = _draw_list_has_color(content[popup_at], gold)
        ring_on_chrome = _draw_list_has_color(content[chrome_at], gold)
        ring_on_foreground = any(
            _draw_list_has_color(draw_list, gold) for draw_list in foreground
        )
        del lists, content
    finally:
        host.imgui.destroy()
    assert strip_on_chrome
    assert not strip_on_foreground
    assert not rule_on_foreground
    assert ring_on_nav
    assert not ring_on_popup
    assert not ring_on_chrome
    assert not ring_on_foreground


class _Overlay:
    def __init__(self) -> None:
        self.visibility = 0.0

    def notify_input(self) -> None:
        self.visibility = 1.0


def _shell_controls() -> SimpleNamespace:
    return SimpleNamespace(session=SimpleNamespace(layer_z_order=()))


def _motion(y: int) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEMOTION,
        pos=(2, y),
        rel=(0, 0),
        buttons=(0, 0, 0),
    )
