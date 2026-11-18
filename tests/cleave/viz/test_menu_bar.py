"""Menu bar focus, highlight, and activation. No GL window."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pygame
import pytest

from cleave.viz.modal import ModalHost
from cleave.viz.context_menu import ContextMenuState
from cleave.viz.inline_edit import InlineEditController
from cleave.viz.commands import (
    MENUS,
    SEPARATOR,
    Command,
    CommandContext,
    Menu,
    MenuSeparator,
)
from cleave.viz.menu_bar import MenuBarState, menu_index_for_mnemonic, menu_mnemonic
from cleave.viz.shell_focus import ShellRegion

_LABELS = ("File", "Project", "Layers", "Timeline", "Settings", "Help")


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
    assert letters == ("F", "E", "V", "P", "S", "H")
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


def test_click_top_opens_without_a_keyboard_row() -> None:
    runs: list[tuple[str, bool]] = []
    menus = _menus(runs)
    state = MenuBarState()
    state.click_top(0, menus)
    assert state.focused
    assert state.dropdown_open
    assert state.menu_index == 0
    assert state.highlighted_command(menus) is None
    assert state.item_index not in range(len(menus[0].items))
    state.click_top(0, menus)
    assert not state.dropdown_open
    assert state.focused


def test_hover_top_opens_and_never_closes() -> None:
    menus = _menus([])
    state = MenuBarState()
    state.hover_top(0, menus)
    assert state.focused
    assert state.dropdown_open
    assert state.menu_index == 0
    assert state.item_index == -1
    state.hover_top(0, menus)
    assert state.dropdown_open
    state.click_top(0, menus)
    assert state.dropdown_open
    state.click_top(0, menus)
    assert not state.dropdown_open


def test_hover_item_moves_the_highlight_and_none_clears_it() -> None:
    menus = _menus([])
    state = MenuBarState()
    state.hover_item(2)
    assert state.item_index == 0
    state.click_top(0, menus)
    state.hover_item(2)
    assert state.highlighted_command(menus) is menus[0].items[2]
    state.hover_item(None)
    assert state.item_index == -1
    assert state.highlighted_command(menus) is None


def test_arrow_after_click_top_selects_an_end_command() -> None:
    runs: list[tuple[str, bool]] = []
    menus = _menus(runs)
    down = MenuBarState()
    down.click_top(0, menus)
    assert down.highlighted_command(menus) is None
    assert _press(down, pygame.K_DOWN, menus, runs)
    assert down.highlighted_command(menus).id == "disabled"

    up = MenuBarState()
    up.click_top(0, menus)
    assert _press(up, pygame.K_UP, menus, runs)
    assert up.highlighted_command(menus).id == "enabled"


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
    from cleave.viz.shell_host import ShellHost
    from cleave.viz.shell_menu_bar import menu_bar_height_px

    if controls is None:
        controls = _shell_controls()
    return ShellHost(
        ImGuiHost.create(),
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
    draw_bar = host.menu_bar.draw_bar

    def remember(state: MenuBarState, ctx: CommandContext):
        rule_y, found, menus = draw_bar(state, ctx)
        anchors.clear()
        anchors.update(found)
        return rule_y, found, menus

    host.menu_bar.draw_bar = remember
    host.imgui.display_size = (1280, 720)

    def draw() -> None:
        from cleave.viz.shell_host import draw_shell_frame

        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)

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

    from cleave.viz.shell_menu_bar import menu_bar_height_px
    from cleave.viz.theme import tuning_ui_metrics, ui_chrome_px

    assert imgui.get_current_context() is None
    height = menu_bar_height_px()
    pad_y = round(ui_chrome_px(8.0))
    assert height == max(1, round(float(tuning_ui_metrics().font_size) + 2.0 * pad_y))
    assert imgui.get_current_context() is None


def _draw_list_has_color(draw_list: object, color: int) -> bool:
    for vtx in draw_list.vtx_buffer:
        if int(vtx.col) == color:
            return True
    return False


def _color_span_x(draw_list: object, color: int) -> float:
    """Width covered by vertices of *color*. Zero when the colour is absent."""
    xs = [
        float(vtx.pos.x)
        for vtx in draw_list.vtx_buffer
        if int(vtx.col) == color
    ]
    if len(xs) < 2:
        return 0.0
    return max(xs) - min(xs)


def _content_lists(lists: list) -> list:
    """Window lists in paint order. The foreground list is not one of them."""
    return [
        draw_list
        for draw_list in lists
        if "Foreground" not in str(draw_list._owner_name)
    ]


def _color_bounds(
    draw_list: object, color: int | tuple[int, ...]
) -> tuple[float, float, float, float] | None:
    """Bounds of every vertex in *color*, or in any of several colours."""
    wanted = {color} if isinstance(color, int) else set(color)
    xs: list[float] = []
    ys: list[float] = []
    for vtx in draw_list.vtx_buffer:
        if int(vtx.col) not in wanted:
            continue
        xs.append(float(vtx.pos.x))
        ys.append(float(vtx.pos.y))
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _lit_fill() -> tuple[int, int]:
    """Top and bottom of the lit row gradient: an open title or menu row."""
    from cleave.viz.row_paint import RowState, row_look

    look = row_look(RowState.LIT)
    return _color_u32(look.start[0]), _color_u32(look.end[0])


def _ink_runs_on_fill(draw_list: object, ink: int, fill: int | tuple[int, ...]) -> int:
    """X-separated runs of *ink* strictly inside the *fill* bounds.

    Glyphs in one label sit closer together than the menu's check, label,
    and shortcut columns, so those three parts are three runs.
    """
    box = _color_bounds(draw_list, fill)
    if box is None:
        return 0
    x0, y0, x1, y1 = box
    xs = sorted(
        float(vtx.pos.x)
        for vtx in draw_list.vtx_buffer
        if int(vtx.col) == ink
        and x0 < float(vtx.pos.x) < x1
        and y0 < float(vtx.pos.y) < y1
    )
    if not xs:
        return 0
    runs = 1
    for previous, current in zip(xs, xs[1:]):
        if current - previous > 14.0:
            runs += 1
    return runs


def _ink_on_fill(draw_list: object, ink: int, fill: int | tuple[int, ...]) -> int:
    """Vertices of *ink* strictly inside the *fill* bounds."""
    box = _color_bounds(draw_list, fill)
    if box is None:
        return 0
    x0, y0, x1, y1 = box
    count = 0
    for vtx in draw_list.vtx_buffer:
        if int(vtx.col) != ink:
            continue
        x = float(vtx.pos.x)
        y = float(vtx.pos.y)
        if x0 < x < x1 and y0 < y < y1:
            count += 1
    return count


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
    """The transport rule stays on its window, under a later menu popup.

    Menu separators use the same colour, so the popup may contain it. The
    rule is the span as wide as the transport window; a separator is not.
    """
    from imgui_bundle import imgui

    from cleave.viz import imgui_host, shell_menu_bar
    from cleave.viz.shell_host import draw_shell_frame
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.theme import palette

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
        height = shell_menu_bar.menu_bar_height_px()
        host.set_layout(ShellLayout.compute(1280, 720, height, height, 0))
        host.process_event(_motion(4))
        host.navigator.draw = lambda _frame: None
        host.navigator.visible_nodes = lambda: ()
        host.inspector.draw = lambda _state: None
        # The font atlas is built on the first frame. Open the menu after that.
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        menu.open_menu(0, MENUS)
        # The popup's first frame is hidden while it measures. The next frame paints it.
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        assert host.menu_bar_height_px == height
        lists = list(imgui.get_draw_data().cmd_lists)
        content = _content_lists(lists)
        names = [draw_list._owner_name for draw_list in content]
        foreground = _assert_chrome_last(lists)
        transport_at = names.index("##shell-transport")
        popup_at = names.index("##cleave-menu")
        chrome_at = names.index("##shell-chrome")
        assert transport_at < popup_at < chrome_at
        grey = _color_u32(palette().transport_rule)
        on_transport = _draw_list_has_color(content[transport_at], grey)
        transport_span = _color_span_x(content[transport_at], grey)
        popup_span = _color_span_x(content[popup_at], grey)
        rule_on_chrome = _draw_list_has_color(content[chrome_at], grey)
        rule_on_foreground = any(
            _draw_list_has_color(draw_list, grey) for draw_list in foreground
        )
        del lists, content
    finally:
        host.imgui.destroy()
    assert on_transport
    assert transport_span > popup_span
    assert rule_on_chrome
    assert not rule_on_foreground


def test_open_menu_paints_over_the_focus_ring() -> None:
    """The row highlight stays on its panel, under a later menu popup."""
    from imgui_bundle import imgui

    from cleave.viz import imgui_host, shell_menu_bar, shell_widgets
    from cleave.viz.shell_host import draw_shell_frame
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.theme import palette

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
        height = shell_menu_bar.menu_bar_height_px()
        host.set_layout(ShellLayout.compute(1280, 720, height, height, 80))
        host.process_event(_motion(4))
        controls.session.timeline = SimpleNamespace(panel_open=True)
        controls.shell_focus.region = ShellRegion.TIMELINE

        def draw_focused_row(_frame: object) -> None:
            imgui.selectable("Focused##row", True)
            shell_widgets.draw_item_focus_ring()

        host.navigator.draw = draw_focused_row

        host.navigator.visible_nodes = lambda: ()
        host.inspector.draw = lambda _state: None
        # The font atlas is built on the first frame. The strip border shares
        # the panel border window, under the menu popup; an open menu takes focus.
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        strip_lists = list(imgui.get_draw_data().cmd_lists)
        strip_content = _content_lists(strip_lists)
        strip_names = [draw_list._owner_name for draw_list in strip_content]
        strip_foreground = _assert_chrome_last(strip_lists)
        gold = _color_u32(palette().highlight)
        panel_ring = _color_u32(palette().panel_focus_edge)
        ring = _color_u32(palette().row_focus_edge)
        white = _color_u32(palette().surface_edge)
        strip_on_border = _draw_list_has_color(
            strip_content[strip_names.index("##shell-focus-border")], panel_ring
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
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        lists = list(imgui.get_draw_data().cmd_lists)
        content = _content_lists(lists)
        names = [draw_list._owner_name for draw_list in content]
        foreground = _assert_chrome_last(lists)
        nav_at = names.index("##shell-navigator")
        popup_at = names.index("##cleave-menu")
        chrome_at = names.index("##shell-chrome")
        assert nav_at < popup_at < chrome_at
        ring_on_nav = _draw_list_has_color(content[nav_at], ring)
        # The current menu row's yellow marker bar is near the menu bar. The
        # navigator ring is lower, on its own list, not copied onto the popup.
        popup_gold = _color_bounds(content[popup_at], gold)
        nav_gold = _color_bounds(content[nav_at], ring)
        popup_above_ring = (
            popup_gold is not None
            and nav_gold is not None
            and popup_gold[3] < nav_gold[1]
        )
        ring_on_chrome = _draw_list_has_color(content[chrome_at], gold)
        ring_on_foreground = any(
            _draw_list_has_color(draw_list, gold) for draw_list in foreground
        )
        del lists, content
    finally:
        host.imgui.destroy()
    assert strip_on_border
    assert not strip_on_foreground
    assert not rule_on_foreground
    assert ring_on_nav
    assert popup_above_ring
    assert not ring_on_chrome
    assert not ring_on_foreground


def test_menu_underline_and_popup_row_are_snug() -> None:
    """The mnemonic sits two pixels under the letter, and the row fill is centered."""
    from imgui_bundle import imgui

    from cleave.viz import imgui_host
    from cleave.viz.shell_host import draw_shell_frame
    from cleave.viz.theme import palette

    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu)
    host.imgui.display_size = (1280, 720)
    host.process_event(_motion(4))
    menu.open_menu(0, MENUS)
    try:
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        draw_shell_frame(host, menu, CommandContext(), 1.0 / 60.0)
        lists = list(imgui.get_draw_data().cmd_lists)
        by_name = {draw_list._owner_name: draw_list for draw_list in lists}
        bar = by_name["##MainMenuBar"]
        popup = by_name["##cleave-menu"]
        ink = _color_u32(palette().value)
        fill = _lit_fill()
        underline_gap = _underline_gap(bar, ink)
        row_gap_above, row_gap_below = _popup_row_ink_gaps(popup, ink, fill)
        top_gap = _popup_first_row_gap(popup, fill)
        style = imgui.get_style()
        # The same gap as under the last row: the padding less the unpadded
        # highlight overhang below.
        expected_top = float(style.window_padding.y) - (
            float(style.item_spacing.y) - float(int(style.item_spacing.y * 0.5))
        )
    finally:
        host.imgui.destroy()
    assert underline_gap == pytest.approx(2.0, abs=0.51)
    assert row_gap_above == pytest.approx(row_gap_below, abs=0.51)
    assert top_gap == pytest.approx(expected_top, abs=1.0)


def _row_fill(draw_list: object, y: float, *, opaque: bool = False) -> int | None:
    """Packed colour of the row-sized translucent (or *opaque*) quad covering *y*."""
    buf = draw_list.vtx_buffer
    idx = draw_list.idx_buffer
    found: int | None = None
    for i in range(0, len(idx), 6):
        ids = [int(idx[i + k]) for k in range(4)]
        color = int(buf[ids[0]].col)
        alpha = (color >> 24) & 255
        if alpha == 0 or (alpha == 255) != opaque:
            continue
        xs = [float(buf[j].pos.x) for j in ids]
        ys = [float(buf[j].pos.y) for j in ids]
        if max(xs) - min(xs) < 20 or not 8 <= max(ys) - min(ys) <= 40:
            continue
        if min(ys) <= y <= max(ys):
            found = color
    return found


def test_popup_hover_takes_the_lit_row() -> None:
    """Popup mouse-hover moves the lit row, like a context menu.

    Unselected panel rows keep the theme header hover wash.
    """
    from cleave.viz import imgui_host, shell_menu_bar
    from cleave.viz.shell_focus import ShellFocusState
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.theme import palette

    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    controls = _shell_controls()
    controls.build_view_state = lambda **_kwargs: None
    controls.focus_cursor = None
    controls.shell_focus = ShellFocusState(
        region=ShellRegion.NAVIGATOR, selected_id="missing"
    )
    controls.navigator = SimpleNamespace(select=lambda *_args, **_kwargs: None)
    controls.settings = SimpleNamespace(
        set_shell_column_widths=lambda *_args, **_kwargs: None
    )

    def draw_nav(_frame: object) -> None:
        from imgui_bundle import imgui

        imgui.selectable("Nav row", False)

    def draw_inspector(_state: object) -> None:
        from imgui_bundle import imgui

        imgui.selectable("Inspector row", False)

    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu, controls)
    host.imgui.display_size = (1280, 720)
    host.navigator.draw = draw_nav
    host.navigator.visible_nodes = lambda: ()
    host.inspector.draw = draw_inspector
    try:
        height = shell_menu_bar.menu_bar_height_px()
        host.set_layout(ShellLayout.compute(1280, 720, height, height, 280))
        host.process_event(_motion(8))
        _paint_shell(host, menu, CommandContext(), frames=1)
        layout = host.layout
        assert layout is not None
        nx, ny, _nw, _nh = layout.navigator
        nav_y = ny + 12
        host.process_event(_at((nx + 40, nav_y), pygame.MOUSEMOTION))
        lists = _paint_shell(host, menu, CommandContext(), frames=2)
        nav = next(item for item in lists if item._owner_name == "##shell-navigator")
        nav_fill = _row_fill(nav, nav_y)
        ix, iy, _iw, _ih = layout.inspector
        insp_y = iy + 12
        host.process_event(_at((ix + 40, insp_y), pygame.MOUSEMOTION))
        lists = _paint_shell(host, menu, CommandContext(), frames=2)
        inspector = next(
            item for item in lists if item._owner_name == "##shell-inspector"
        )
        inspector_fill = _row_fill(inspector, insp_y)
        menu.click_top(0, MENUS)
        _paint_shell(host, menu, CommandContext(), frames=2)
        from imgui_bundle import imgui

        lists = list(imgui.get_draw_data().cmd_lists)
        popup = next(item for item in lists if item._owner_name == "##cleave-menu")
        xs = [float(vtx.pos.x) for vtx in popup.vtx_buffer]
        ys = [float(vtx.pos.y) for vtx in popup.vtx_buffer]
        popup_y = int(min(ys) + 40)
        host.process_event(
            _at((int((min(xs) + max(xs)) / 2), popup_y), pygame.MOUSEMOTION)
        )
        lists = _paint_shell(host, menu, CommandContext(), frames=2)
        popup = next(item for item in lists if item._owner_name == "##cleave-menu")
        popup_fill = _row_fill(popup, popup_y, opaque=True)
        theme_hover = _color_u32_alpha(palette().hover, palette().hover_bg_alpha / 255.0)
        opaque = _lit_fill()[0]
    finally:
        host.imgui.destroy()
    assert nav_fill == theme_hover
    assert inspector_fill == theme_hover
    assert popup_fill == opaque
    assert menu.item_index >= 0


def _underline_gap(draw_list: object, ink: int) -> float:
    """Pixels between the open title's ink and the mnemonic underline."""
    bands: dict[float, list[float]] = {}
    for vtx in draw_list.vtx_buffer:
        if int(vtx.col) != ink:
            continue
        x = float(vtx.pos.x)
        if not 4.0 <= x <= 70.0:
            continue
        y = round(float(vtx.pos.y), 1)
        bands.setdefault(y, []).append(x)
    word_span = 0.0
    word_bottom = 0.0
    underline_top: float | None = None
    for y, xs in bands.items():
        span = max(xs) - min(xs)
        if span > word_span:
            word_span = span
            word_bottom = y
    for y, xs in bands.items():
        span = max(xs) - min(xs)
        if y <= word_bottom or span > word_span * 0.5:
            continue
        underline_top = y if underline_top is None else min(underline_top, y)
    assert underline_top is not None
    return underline_top - word_bottom


def _popup_first_row_gap(draw_list: object, fill: tuple[int, ...]) -> float:
    """Pixels from the popup background top to the first row's highlight."""
    from cleave.viz.theme import palette

    background = _color_bounds(draw_list, _color_u32(palette().surface_bg))
    box = _color_bounds(draw_list, fill)
    assert background is not None and box is not None
    return box[1] - background[1]


def _popup_row_ink_gaps(
    draw_list: object, ink: int, fill: tuple[int, ...]
) -> tuple[float, float]:
    """Padding from the highlighted row fill to the label's font box.

    Descenders sit inside the same box, so the gaps use the line height
    rather than the lowest ink pixel.
    """
    from imgui_bundle import imgui

    box = _color_bounds(draw_list, fill)
    assert box is not None
    x0, y0, _x1, y1 = box
    tops = [
        float(vtx.pos.y)
        for vtx in draw_list.vtx_buffer
        if int(vtx.col) == ink and x0 < float(vtx.pos.x) < _x1
    ]
    assert tops
    size = imgui.get_style().font_size_base
    font = imgui.get_io().font_default.get_font_baked(size)
    label = next(
        item.label
        for item in MENUS[0].items
        if not isinstance(item, MenuSeparator)
    )
    min_y0 = min(
        font.find_glyph(ord(char)).y0
        for char in label
        if not char.isspace()
    )
    text_top = min(tops) - min_y0
    return (text_top - y0), (y1 - (text_top + size))


def _color_u32_alpha(rgb: tuple[int, int, int], alpha: float) -> int:
    from imgui_bundle import imgui

    return int(
        imgui.get_color_u32(
            imgui.ImVec4(
                rgb[0] / 255.0,
                rgb[1] / 255.0,
                rgb[2] / 255.0,
                alpha,
            )
        )
    )


def _paint_shell(host, menu, ctx, *, frames: int = 2) -> list:
    from imgui_bundle import imgui

    from cleave.viz.shell_host import draw_shell_frame

    lists = []
    for _ in range(frames):
        draw_shell_frame(host, menu, ctx, 1.0 / 60.0)
        lists = list(imgui.get_draw_data().cmd_lists)
    return lists


def test_open_menu_ink_matches_the_mock() -> None:
    """Open title and the current row are white on the lit gradient.

    An unfocused check is action and its shortcut is muted. The transport
    bar has no highlight readout. On the current row the check is yellow,
    the label white, and the shortcut soft white.
    """
    from cleave.viz import imgui_host
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.theme import palette

    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    controls = _shell_controls()
    controls.build_view_state = lambda **_kwargs: None
    controls.focus_cursor = None
    controls.shell_focus = SimpleNamespace(region=ShellRegion.NAVIGATOR)
    view_index = next(
        index for index, item in enumerate(MENUS) if item.label == "View"
    )
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu, controls)
    try:
        from cleave.viz import imgui_host, shell_menu_bar

        host.imgui.display_size = (1280, 720)
        height = shell_menu_bar.menu_bar_height_px()
        host.set_layout(ShellLayout.compute(1280, 720, height, height, 0))
        host.process_event(_motion(4))
        host.navigator.draw = lambda _frame: None
        host.navigator.visible_nodes = lambda: ()
        host.inspector.draw = lambda _state: None
        ctx = CommandContext(fullscreen=True)
        _paint_shell(host, menu, ctx, frames=1)
        menu.open_menu(view_index, MENUS)
        menu.item_index = 6
        lists = _paint_shell(host, menu, ctx)
        content = _content_lists(lists)
        names = [draw_list._owner_name for draw_list in content]
        bar = content[names.index("##MainMenuBar")]
        popup = content[names.index("##cleave-menu")]
        transport = content[names.index("##shell-transport")]
        gold = _color_u32(palette().highlight)
        ink = _color_u32(palette().value)
        lit = _lit_fill()
        title_ink = _ink_on_fill(bar, ink, lit)
        row_ink = _ink_on_fill(popup, ink, lit)
        scope = _draw_list_has_color(transport, gold)
        unfocused_check = _draw_list_has_color(popup, _color_u32(palette().value))
        unfocused_shortcut = _draw_list_has_color(popup, _color_u32(palette().muted))
        unfocused_label = _draw_list_has_color(popup, _color_u32(palette().value))
        idle_title = _draw_list_has_color(bar, _color_u32(palette().label))
        shortcut_on_current = _ink_on_fill(popup, _color_u32(palette().muted), lit)
        # Full screen editor: check, label, and shortcut.
        menu.item_index = 4
        lists = _paint_shell(host, menu, ctx)
        content = _content_lists(lists)
        names = [draw_list._owner_name for draw_list in content]
        popup = content[names.index("##cleave-menu")]
        current_parts = (
            _ink_runs_on_fill(popup, gold, lit),
            _ink_runs_on_fill(popup, ink, lit),
            _ink_runs_on_fill(popup, _color_u32(palette().surface_text), lit),
        )
        del lists, content
    finally:
        host.imgui.destroy()
    assert title_ink > 4
    assert row_ink > 4
    assert not scope
    assert unfocused_check
    assert unfocused_shortcut
    assert unfocused_label
    assert idle_title
    assert shortcut_on_current == 0
    # Check, label, and shortcut.
    assert current_parts == (1, 1, 1)


def test_navigator_row_is_focused_only_while_that_region_is_active() -> None:
    from cleave.viz import imgui_host, row_paint, shell_menu_bar, shell_navigator
    from cleave.viz.row_paint import RowState
    from cleave.viz.navigator import NavNode
    from cleave.viz.shell_focus import ShellFocusState
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.theme import palette

    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    nodes = (
        NavNode("settings", "Settings", 0, None, locked=True),
        NavNode("settings.ui", "UI", 1, None, parent_id="settings"),
        NavNode("project", "Project", 0, None),
    )
    focus = ShellFocusState(region=ShellRegion.NAVIGATOR, selected_id="settings")
    controls = _shell_controls()
    controls.build_view_state = lambda **_kwargs: None
    controls.focus_cursor = None
    controls.shell_focus = focus
    controls.navigator = SimpleNamespace(select=lambda *_args, **_kwargs: None)
    rings: list[RowState] = []
    real_paint = row_paint.paint_row

    def spy_paint(draw, rect, state, *, bar=True) -> None:
        rings.append(state)
        real_paint(draw, rect, state, bar=bar)

    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu, controls)
    try:
        host.imgui.display_size = (1280, 720)
        height = shell_menu_bar.menu_bar_height_px()
        # Tall enough for all three rows: the navigator clips rows that
        # overflow its padding, and a missing child row has no label ink.
        host.set_layout(
            ShellLayout.compute(1280, 720, height, height, 0, nav_content_h=200)
        )
        host.process_event(_motion(4))
        host.inspector.draw = lambda _state: None
        with (
            patch.object(row_paint, "paint_row", spy_paint),
            patch.object(shell_navigator, "build_navigator", return_value=nodes),
        ):
            _paint_shell(host, menu, CommandContext(), frames=1)
            rings.clear()
            lists = _paint_shell(host, menu, CommandContext(), frames=1)
            active_rings = list(rings)
            content = _content_lists(lists)
            names = [draw_list._owner_name for draw_list in content]
            nav = content[names.index("##shell-navigator")]
            colors = {int(vtx.col) for vtx in nav.vtx_buffer}
            band = _color_u32_alpha(palette().row_select_tint, palette().row_focused_alpha[0])
            has_band = band in colors
            has_value = _color_u32(palette().value) in colors
            has_label = _color_u32(palette().label) in colors
            has_lock = _color_u32(palette().lock_icon) in colors
            del lists, content, colors
            focus.region = ShellRegion.INSPECTOR
            rings.clear()
            _paint_shell(host, menu, CommandContext(), frames=1)
            inspector_rings = list(rings)
            menu.focused = True
            focus.region = ShellRegion.NAVIGATOR
            rings.clear()
            _paint_shell(host, menu, CommandContext(), frames=1)
            # The open menu's title is lit; the navigator row stays selected.
            menu_rings = [state for state in rings if state is not RowState.LIT]
    finally:
        host.imgui.destroy()
    # The selected row is focused while the navigator holds the keys, and
    # only selected otherwise.
    assert active_rings == [RowState.FOCUSED]
    assert inspector_rings == [RowState.SELECTED]
    assert menu_rings == [RowState.SELECTED]
    assert has_band
    assert has_value
    assert has_label
    assert has_lock


def test_focused_inspector_label_is_value() -> None:
    from imgui_bundle import imgui

    from cleave.viz import imgui_host, shell_host, shell_menu_bar
    from cleave.viz.focus_nav import MainFocus
    from cleave.viz.inspector import build_inspector_rows
    from cleave.viz.row_kinds import RowDescriptor, RowKind
    from cleave.viz.shell_focus import ShellFocusState
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.theme import palette
    from cleave.viz.tuning_view_state import TuningViewState

    view = TuningViewState(
        layer_z_order=(),
        tracks={},
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.OVERLAYS_HEADER)),
        move_mode_slot=None,
    )
    rows = build_inspector_rows(view, "post_fx.fade")
    group = next(row for row in rows if row.is_heading)
    field = next(row for row in rows if not row.is_heading and not row.command_ids)
    focus = ShellFocusState(
        region=ShellRegion.INSPECTOR,
        selected_id="post_fx.fade",
        inspector_cursor=field.descriptor,
    )
    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    controls = _shell_controls()
    controls.build_view_state = lambda **_kwargs: None
    controls.focus_cursor = None
    controls.shell_focus = focus
    controls.inline_edit = InlineEditController()
    controls.inspector = SimpleNamespace(
        focus_row=lambda *_args, **_kwargs: None,
        activate=lambda *_args, **_kwargs: None,
    )
    text_pushes: list[tuple[float, float, float, float]] = []
    real_push = shell_host.imgui.push_style_color

    def spy_push(idx, color):
        if int(idx) == int(imgui.Col_.text):
            text_pushes.append((color.x, color.y, color.z, color.w))
        return real_push(idx, color)

    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu, controls)
    try:
        host.imgui.display_size = (1280, 720)
        height = shell_menu_bar.menu_bar_height_px()
        host.set_layout(ShellLayout.compute(1280, 720, height, height, 280))
        host.process_event(_motion(4))
        host.navigator.draw = lambda _frame: None
        host.navigator.visible_nodes = lambda: ()
        seen: dict[str, list] = {}

        def draw_inspector(_state) -> None:
            start = len(text_pushes)
            host.inspector.draw_row(view, group)
            seen["group"] = list(text_pushes[start:])
            start = len(text_pushes)
            host.inspector.draw_row(view, field)
            seen["field"] = list(text_pushes[start:])

        host.inspector.draw = draw_inspector
        with patch.object(shell_host.imgui, "push_style_color", spy_push):
            _paint_shell(host, menu, CommandContext(), frames=1)
            lists = _paint_shell(host, menu, CommandContext(), frames=1)
        content = _content_lists(lists)
        names = [draw_list._owner_name for draw_list in content]
        inspector = content[names.index("##shell-inspector")]
        colors = {int(vtx.col) for vtx in inspector.vtx_buffer}
        focus_wash = _color_u32_alpha(palette().row_select_tint, palette().row_focused_alpha[0])
        selected_wash = _color_u32_alpha(palette().row_select_tint, palette().row_selected_alpha[0])
        has_focus_wash = focus_wash in colors
        has_selected_wash = selected_wash in colors
        has_value = _color_u32(palette().value) in colors
        highlight = (
            palette().value[0] / 255.0,
            palette().value[1] / 255.0,
            palette().value[2] / 255.0,
            1.0,
        )
        label = (
            palette().label[0] / 255.0,
            palette().label[1] / 255.0,
            palette().label[2] / 255.0,
            1.0,
        )
        field_push = list(seen["field"])
        group_push = list(seen["group"])
        focus.inspector_cursor = group.descriptor
        text_pushes.clear()
        with patch.object(shell_host.imgui, "push_style_color", spy_push):
            _paint_shell(host, menu, CommandContext(), frames=1)
        focused_group_push = list(seen["group"])
        unfocused_field = list(seen["field"])
        del lists, content, colors
    finally:
        host.imgui.destroy()
    assert group_push == []
    assert len(field_push) == 1
    assert field_push[0] == pytest.approx(highlight)
    assert has_focus_wash
    assert not has_selected_wash
    assert has_value
    assert focused_group_push == []
    assert len(unfocused_field) == 1
    assert unfocused_field[0] == pytest.approx(label)


def test_preset_row_draws_two_lines_and_fits_the_filename() -> None:
    from cleave.viz import imgui_host, shell_host, shell_menu_bar
    from cleave.viz.inspector import InspectorRow
    from cleave.viz.row_kinds import RowDescriptor, RowKind
    from cleave.viz.shell_focus import ShellFocusState
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.theme import palette
    from tests.support.viz import minimal_view_state

    view = minimal_view_state()
    slot = next(iter(view.tracks))
    block = view.tracks[slot]
    block.preset_label = "very long milkdrop preset filename " * 8 + ".milk"
    block.preset_position = "3/9"
    block.preset_markers = "[F] [R:B]"
    block.preset_list_labels = ["listed.milk"]
    block.preset_list_markers = ["[B]"]
    preset = InspectorRow(
        RowDescriptor(RowKind.TRACK_PRESET, slot=slot), False, 0, True
    )
    stem = InspectorRow(RowDescriptor(RowKind.TRACK_STEM, slot=slot), False, 0, True)
    item = InspectorRow(
        RowDescriptor(RowKind.TRACK_PRESET_LIST_ITEM, slot=slot, preset_index=0),
        False,
        0,
        True,
    )
    controls = _shell_controls()
    controls.build_view_state = lambda **_kwargs: None
    controls.focus_cursor = None
    controls.shell_focus = ShellFocusState(
        region=ShellRegion.NAVIGATOR, selected_id="project"
    )
    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    heights: dict[str, float] = {}

    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        controls.inline_edit = InlineEditController()
        host = _open_shell(overlay, menu, controls)
    try:
        host.imgui.display_size = (1280, 720)
        height = shell_menu_bar.menu_bar_height_px()
        host.set_layout(ShellLayout.compute(1280, 720, height, height, 280))
        host.process_event(_motion(4))
        host.navigator.draw = lambda _frame: None
        host.navigator.visible_nodes = lambda: ()

        def draw_inspector(_state) -> None:
            imgui = shell_host.imgui
            top = imgui.get_cursor_pos().y
            host.inspector.draw_row(view, preset)
            middle = imgui.get_cursor_pos().y
            host.inspector.draw_row(view, stem)
            heights["preset"] = middle - top
            heights["stem"] = imgui.get_cursor_pos().y - middle
            # The stem row ends on its full-width selectable; the list item
            # ends on its narrow leading drag handle.
            heights["right"] = imgui.get_item_rect_max().x
            before_item = imgui.get_cursor_pos().y
            host.inspector.draw_row(view, item)
            heights["item"] = imgui.get_cursor_pos().y - before_item
            heights["line"] = imgui.get_text_line_height()

        host.inspector.draw = draw_inspector
        _paint_shell(host, menu, CommandContext(), frames=1)
        lists = _paint_shell(host, menu, CommandContext(), frames=1)
        content = _content_lists(lists)
        names = [draw_list._owner_name for draw_list in content]
        inspector = content[names.index("##shell-inspector")]
        bounds = _color_bounds(inspector, _color_u32(palette().value))
        del lists, content
    finally:
        host.imgui.destroy()
    assert heights["preset"] == pytest.approx(heights["stem"] + heights["line"])
    assert heights["item"] == pytest.approx(heights["preset"])
    assert bounds is not None
    assert bounds[2] <= heights["right"]


@pytest.mark.parametrize(
    ("can_go_up", "index", "expected_parent_calls", "expected_child_calls"),
    (
        (True, 0, 1, 0),
        (False, 0, 0, 0),
        (True, 1, 0, 1),
    ),
)
def test_directory_nav_button_press_skips_the_row_action(
    can_go_up: bool,
    index: int,
    expected_parent_calls: int,
    expected_child_calls: int,
) -> None:
    from cleave.viz import (
        imgui_host,
        shell_host,
        shell_inspector_values,
        shell_menu_bar,
    )
    from cleave.viz.inspector import InspectorRow
    from cleave.viz.row_kinds import RowDescriptor, RowKind
    from cleave.viz.shell_focus import ShellFocusState
    from cleave.viz.shell_layout import ShellLayout
    from tests.support.viz import minimal_view_state

    view = minimal_view_state()
    slot = next(iter(view.tracks))
    block = view.tracks[slot]
    block.preset_dir_label = "packs/wave/"
    block.preset_dir_position = "2/5"
    block.preset_dir_can_go_up = can_go_up
    block.preset_dir_can_go_down = True
    row = InspectorRow(
        RowDescriptor(RowKind.TRACK_PRESET_DIR, slot=slot), False, 0, True
    )
    controls = _shell_controls()
    controls.build_view_state = lambda **_kwargs: None
    controls.focus_cursor = None
    controls.shell_focus = ShellFocusState(
        region=ShellRegion.NAVIGATOR, selected_id="project"
    )
    controls.inspector = MagicMock()
    controls.layer_mutations = MagicMock()
    controls.inline_edit = InlineEditController()
    controls.value_nudge = SimpleNamespace(armed=False, desc=None, forward=False)
    controls.session.layers = {slot: SimpleNamespace(locked=False, stem="drums")}
    controls.session.layer_z_order = (slot,)
    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    rects: list = []
    real_rects = shell_inspector_values.row_icon_boxes

    def spy_rects(*args, **kwargs):
        rects[:] = real_rects(*args, **kwargs)
        return tuple(rects)

    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu, controls)
    try:
        host.imgui.display_size = (1280, 720)
        height = shell_menu_bar.menu_bar_height_px()
        host.set_layout(ShellLayout.compute(1280, 720, height, height, 280))
        host.process_event(_motion(4))
        host.navigator.draw = lambda _frame: None
        host.navigator.visible_nodes = lambda: ()
        host.inspector.draw = lambda _state: host.inspector.draw_row(view, row)
        with patch.object(shell_inspector_values, "row_icon_boxes", spy_rects):
            _paint_shell(host, menu, CommandContext(), frames=1)
            tx, ty, tw, th = rects[index]
            pointer = shell_host.imgui.ImVec2(
                tx + tw * 0.5,
                ty + th * 0.5,
            )
            with (
                patch.object(shell_host.imgui, "get_mouse_pos", return_value=pointer),
                patch.object(shell_host.imgui, "is_item_activated", return_value=True),
                patch.object(
                    shell_host.imgui, "is_mouse_double_clicked", return_value=True
                ),
            ):
                _paint_shell(host, menu, CommandContext(), frames=1)
    finally:
        host.imgui.destroy()
    mutations = controls.layer_mutations
    assert mutations.parent_directory.call_count == expected_parent_calls
    assert mutations.enter_directory.call_count == expected_child_calls
    controls.inspector.activate.assert_not_called()


class _Overlay:
    def __init__(self) -> None:
        self.visibility = 0.0

    def notify_input(self) -> None:
        self.visibility = 1.0


def _shell_controls() -> SimpleNamespace:
    return SimpleNamespace(
        session=SimpleNamespace(
            layer_z_order=(),
            help_visible=False,
            timeline=SimpleNamespace(panel_open=False),
        ),
        value_nudge=SimpleNamespace(armed=False, desc=None, forward=False),
        disarm_value_nudge=MagicMock(),
        begin_value_nudge=MagicMock(),
        inline_edit=InlineEditController(),
        context_menu=ContextMenuState(),
        modal_host=ModalHost(),
        transport=MagicMock(),
        cfg=SimpleNamespace(project_slug="song"),
        config_dirty=False,
    )


def _motion(y: int) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEMOTION,
        pos=(2, y),
        rel=(0, 0),
        buttons=(0, 0, 0),
    )


def test_switching_menus_never_shows_the_last_menus_size() -> None:
    """A hover onto the next title shows its dropdown at its own size.

    A menu's first open measures off-screen; a menu seen before shows at its
    own size on the first frame back.
    """
    from imgui_bundle import imgui

    from cleave.viz import imgui_host, shell_menu_bar
    from cleave.viz.shell_layout import ShellLayout

    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    controls = _shell_controls()
    controls.build_view_state = lambda **_kwargs: None
    controls.focus_cursor = None
    controls.shell_focus = SimpleNamespace(region=ShellRegion.NAVIGATOR)
    file_index = next(i for i, item in enumerate(MENUS) if item.label == "File")
    view_index = next(i for i, item in enumerate(MENUS) if item.label == "View")
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu, controls)

    def popup() -> tuple[tuple[float, float], tuple[float, float]]:
        window = imgui.internal.find_window_by_name("##cleave-menu")
        return (window.pos.x, window.pos.y), (window.size.x, window.size.y)

    try:
        host.imgui.display_size = (1280, 720)
        height = shell_menu_bar.menu_bar_height_px()
        host.set_layout(ShellLayout.compute(1280, 720, height, height, 0))
        host.process_event(_motion(4))
        host.navigator.draw = lambda _frame: None
        host.navigator.visible_nodes = lambda: ()
        host.inspector.draw = lambda _state: None
        ctx = CommandContext()
        _paint_shell(host, menu, ctx, frames=1)
        menu.open_menu(file_index, MENUS)
        _paint_shell(host, menu, ctx, frames=3)
        _file_pos, file_size = popup()
        menu.open_menu(view_index, MENUS)
        _paint_shell(host, menu, ctx, frames=1)
        first_view_pos, _ = popup()
        _paint_shell(host, menu, ctx, frames=2)
        _view_pos, view_size = popup()
        menu.open_menu(file_index, MENUS)
        _paint_shell(host, menu, ctx, frames=1)
        back_pos, back_size = popup()
    finally:
        host.imgui.destroy()
    assert file_size != view_size
    assert first_view_pos[0] < 0 and first_view_pos[1] < 0
    assert back_pos[0] >= 0 and back_pos[1] >= 0
    assert back_size == file_size
