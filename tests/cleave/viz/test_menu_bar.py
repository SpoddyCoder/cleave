"""Menu bar focus, highlight, and activation. No GL window."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pygame
import pytest

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
    draw_list: object, color: int
) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for vtx in draw_list.vtx_buffer:
        if int(vtx.col) != color:
            continue
        xs.append(float(vtx.pos.x))
        ys.append(float(vtx.pos.y))
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _ink_runs_on_fill(draw_list: object, ink: int, fill: int) -> int:
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


def _ink_on_fill(draw_list: object, ink: int, fill: int) -> int:
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
        transport_span = _color_span_x(content[transport_at], grey)
        popup_span = _color_span_x(content[popup_at], grey)
        on_chrome = _draw_list_has_color(content[chrome_at], grey)
        rule_on_chrome = _draw_list_has_color(content[chrome_at], white)
        rule_on_foreground = any(
            _draw_list_has_color(draw_list, white) for draw_list in foreground
        )
        del lists, content
    finally:
        host.imgui.destroy()
    assert on_transport
    assert transport_span > popup_span
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
        # The current menu row is opaque highlight near the menu bar. The
        # navigator ring is lower, on its own list, not copied onto the popup.
        popup_gold = _color_bounds(content[popup_at], gold)
        nav_gold = _color_bounds(content[nav_at], gold)
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
    assert strip_on_chrome
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
    from cleave.viz.theme import BACKGROUND, HIGHLIGHT

    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu)
    host.imgui.display_size = (1280, 720)
    host.process_event(_motion(4))
    menu.open_menu(0, MENUS)
    try:
        draw_shell_frame(host, menu, CommandContext(), 1.0, 1.0 / 60.0)
        draw_shell_frame(host, menu, CommandContext(), 1.0, 1.0 / 60.0)
        lists = list(imgui.get_draw_data().cmd_lists)
        by_name = {draw_list._owner_name: draw_list for draw_list in lists}
        bar = by_name["##MainMenuBar"]
        popup = by_name["##cleave-menu"]
        ink = _color_u32(BACKGROUND)
        fill = _color_u32(HIGHLIGHT)
        underline_gap = _underline_gap(bar, ink)
        row_gap_above, row_gap_below = _popup_row_ink_gaps(popup, ink, fill)
    finally:
        host.imgui.destroy()
    assert underline_gap == pytest.approx(2.0, abs=0.51)
    assert row_gap_above == pytest.approx(row_gap_below, abs=0.51)


def _row_fill(draw_list: object, y: float) -> int | None:
    """Packed colour of the row-sized translucent quad covering *y*."""
    buf = draw_list.vtx_buffer
    idx = draw_list.idx_buffer
    found: int | None = None
    for i in range(0, len(idx), 6):
        ids = [int(idx[i + k]) for k in range(4)]
        color = int(buf[ids[0]].col)
        alpha = (color >> 24) & 255
        if alpha == 0 or alpha == 255:
            continue
        xs = [float(buf[j].pos.x) for j in ids]
        ys = [float(buf[j].pos.y) for j in ids]
        if max(xs) - min(xs) < 20 or not 8 <= max(ys) - min(ys) <= 40:
            continue
        if min(ys) <= y <= max(ys):
            found = color
    return found


def test_popup_hover_matches_inspector_and_navigator() -> None:
    """Popup mouse-hover packs the same wash as an unselected panel row.

    That wash is the theme header hover. The gold selection wash is only for
    a selected navigator row, and the opaque highlight is only the keyboard row.
    """
    from cleave.viz import imgui_host, shell_host
    from cleave.viz.shell_focus import ShellFocusState
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.theme import HIGHLIGHT, HOVER, HOVER_BG_ALPHA, SELECTED_WASH_ALPHA

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

    def draw_nav() -> None:
        from imgui_bundle import imgui

        imgui.selectable("Nav row", False)

    def draw_inspector(_state: object) -> None:
        from imgui_bundle import imgui

        imgui.selectable("Inspector row", False)

    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu, controls)
    host.imgui.display_size = (1280, 720)
    host._draw_navigator = draw_nav
    host._draw_inspector = draw_inspector
    try:
        height = shell_host.menu_bar_height_px()
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
        popup_fill = _row_fill(popup, popup_y)
        theme_hover = _color_u32_alpha(HOVER, HOVER_BG_ALPHA / 255.0)
        selection = _color_u32_alpha(HIGHLIGHT, SELECTED_WASH_ALPHA / 255.0)
    finally:
        host.imgui.destroy()
    assert nav_fill == theme_hover
    assert inspector_fill == theme_hover
    assert popup_fill == nav_fill == inspector_fill
    assert popup_fill != selection


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


def _popup_row_ink_gaps(
    draw_list: object, ink: int, fill: int
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
    font = imgui.get_font()
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
    return (text_top - y0), (y1 - (text_top + font.font_size))


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
        draw_shell_frame(host, menu, ctx, 1.0, 1.0 / 60.0)
        lists = list(imgui.get_draw_data().cmd_lists)
    return lists


def test_open_menu_ink_matches_the_mock() -> None:
    """Open title and the current row use background ink on opaque highlight.

    An unfocused check is action, its shortcut is muted, and the scope
    readout is highlight. The Help row's label, check, and shortcut are
    background ink while that row is current.
    """
    from cleave.viz import imgui_host
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.theme import (
        ACTION,
        BACKGROUND,
        DISABLED,
        HIGHLIGHT,
        LABEL,
        MUTED,
        VALUE,
    )

    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    controls = _shell_controls()
    controls.build_view_state = lambda **_kwargs: None
    controls.focus_cursor = None
    controls.shell_focus = SimpleNamespace(region=ShellRegion.NAVIGATOR)
    help_index = next(index for index, item in enumerate(MENUS) if item.label == "Help")
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu, controls)
    try:
        from cleave.viz import shell_host

        host.imgui.display_size = (1280, 720)
        height = shell_host.menu_bar_height_px()
        host.set_layout(ShellLayout.compute(1280, 720, height, height, 0))
        host.process_event(_motion(4))
        host._draw_navigator = lambda: None
        host._draw_inspector = lambda _state: None
        ctx = CommandContext(help_visible=True)
        _paint_shell(host, menu, ctx, frames=1)
        menu.open_menu(help_index, MENUS)
        menu.item_index = 1
        lists = _paint_shell(host, menu, ctx)
        content = _content_lists(lists)
        names = [draw_list._owner_name for draw_list in content]
        bar = content[names.index("##MainMenuBar")]
        popup = content[names.index("##cleave-menu")]
        transport = content[names.index("##shell-transport")]
        gold = _color_u32(HIGHLIGHT)
        ink = _color_u32(BACKGROUND)
        title_ink = _ink_on_fill(bar, ink, gold)
        row_ink = _ink_on_fill(popup, ink, gold)
        scope = _draw_list_has_color(transport, gold)
        unfocused_check = _draw_list_has_color(popup, _color_u32(ACTION))
        unfocused_shortcut = _draw_list_has_color(popup, _color_u32(MUTED))
        unfocused_label = _draw_list_has_color(popup, _color_u32(VALUE))
        disabled = _draw_list_has_color(popup, _color_u32(DISABLED))
        idle_title = _draw_list_has_color(bar, _color_u32(LABEL))
        check_on_current = _ink_on_fill(popup, _color_u32(ACTION), gold)
        shortcut_on_current = _ink_on_fill(popup, _color_u32(MUTED), gold)
        menu.item_index = 0
        lists = _paint_shell(host, menu, ctx)
        content = _content_lists(lists)
        names = [draw_list._owner_name for draw_list in content]
        popup = content[names.index("##cleave-menu")]
        current_parts = _ink_runs_on_fill(popup, ink, gold)
        del lists, content
    finally:
        host.imgui.destroy()
    assert title_ink > 4
    assert row_ink > 4
    assert scope
    assert unfocused_check
    assert unfocused_shortcut
    assert unfocused_label
    assert disabled
    assert idle_title
    assert check_on_current == 0
    assert shortcut_on_current == 0
    assert current_parts == 3


def test_navigator_focus_ring_only_while_that_region_is_active() -> None:
    from cleave.viz import imgui_host, shell_host
    from cleave.viz.navigator import NavNode
    from cleave.viz.shell_focus import ShellFocusState
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.theme import (
        FOCUS_ROW_BG_ALPHA,
        HIGHLIGHT,
        LABEL,
        LOCK_ICON,
        SELECTED_WASH_ALPHA,
        VALUE,
    )

    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    nodes = (
        NavNode("settings", "Settings", 0, True, None, locked=True),
        NavNode("project", "Project", 0, True, None),
    )
    focus = ShellFocusState(region=ShellRegion.NAVIGATOR, selected_id="settings")
    controls = _shell_controls()
    controls.build_view_state = lambda **_kwargs: None
    controls.focus_cursor = None
    controls.shell_focus = focus
    controls.navigator = SimpleNamespace(select=lambda *_args, **_kwargs: None)
    rings: list[bool] = []
    real_ring = shell_host._draw_item_focus_ring

    def spy_ring() -> None:
        rings.append(True)
        real_ring()

    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = _open_shell(overlay, menu, controls)
    try:
        host.imgui.display_size = (1280, 720)
        height = shell_host.menu_bar_height_px()
        host.set_layout(ShellLayout.compute(1280, 720, height, height, 0))
        host.process_event(_motion(4))
        host._draw_inspector = lambda _state: None
        with (
            patch.object(shell_host, "_draw_item_focus_ring", spy_ring),
            patch.object(shell_host, "build_navigator", return_value=nodes),
        ):
            _paint_shell(host, menu, CommandContext(), frames=1)
            rings.clear()
            lists = _paint_shell(host, menu, CommandContext(), frames=1)
            active_rings = len(rings)
            content = _content_lists(lists)
            names = [draw_list._owner_name for draw_list in content]
            nav = content[names.index("##shell-navigator")]
            colors = {int(vtx.col) for vtx in nav.vtx_buffer}
            wash = _color_u32_alpha(HIGHLIGHT, SELECTED_WASH_ALPHA / 255.0)
            old_wash = _color_u32_alpha(HIGHLIGHT, FOCUS_ROW_BG_ALPHA / 255.0)
            has_wash = wash in colors
            has_old = old_wash in colors
            has_value = _color_u32(VALUE) in colors
            has_label = _color_u32(LABEL) in colors
            has_lock = _color_u32(LOCK_ICON) in colors
            del lists, content, colors
            focus.region = ShellRegion.INSPECTOR
            rings.clear()
            _paint_shell(host, menu, CommandContext(), frames=1)
            inspector_rings = len(rings)
            menu.focused = True
            focus.region = ShellRegion.NAVIGATOR
            rings.clear()
            _paint_shell(host, menu, CommandContext(), frames=1)
            menu_rings = len(rings)
    finally:
        host.imgui.destroy()
    assert active_rings == 1
    assert inspector_rings == 0
    assert menu_rings == 0
    assert has_wash
    assert not has_old
    assert has_value
    assert has_label
    assert has_lock


def test_focused_inspector_label_is_highlight() -> None:
    from imgui_bundle import imgui

    from cleave.viz import imgui_host, shell_host
    from cleave.viz.focus_nav import MainFocus
    from cleave.viz.inspector import build_inspector_rows
    from cleave.viz.row_kinds import RowDescriptor, RowKind
    from cleave.viz.shell_focus import ShellFocusState
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.theme import (
        FOCUS_ROW_BG_ALPHA,
        FOCUS_WASH_ALPHA,
        HIGHLIGHT,
        LABEL,
        SELECTED_WASH_ALPHA,
        VALUE,
    )
    from cleave.viz.tuning_view_state import TuningViewState

    view = TuningViewState(
        layer_z_order=(),
        tracks={},
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)),
        move_mode_slot=None,
    )
    rows = build_inspector_rows(view, "project", frozenset())
    group = next(row for row in rows if row.is_group)
    field = next(row for row in rows if not row.is_group and row.command_id is None)
    focus = ShellFocusState(
        region=ShellRegion.INSPECTOR,
        selected_id="project",
        inspector_cursor=field.descriptor,
    )
    overlay = _Overlay()
    overlay.visibility = 1.0
    menu = MenuBarState()
    controls = _shell_controls()
    controls.build_view_state = lambda **_kwargs: None
    controls.focus_cursor = None
    controls.shell_focus = focus
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
        height = shell_host.menu_bar_height_px()
        host.set_layout(ShellLayout.compute(1280, 720, height, height, 280))
        host.process_event(_motion(4))
        host._draw_navigator = lambda: None
        seen: dict[str, list] = {}

        def draw_inspector(_state) -> None:
            start = len(text_pushes)
            host._draw_inspector_row(view, group)
            seen["group"] = list(text_pushes[start:])
            start = len(text_pushes)
            host._draw_inspector_row(view, field)
            seen["field"] = list(text_pushes[start:])

        host._draw_inspector = draw_inspector
        with patch.object(shell_host.imgui, "push_style_color", spy_push):
            _paint_shell(host, menu, CommandContext(), frames=1)
            lists = _paint_shell(host, menu, CommandContext(), frames=1)
        content = _content_lists(lists)
        names = [draw_list._owner_name for draw_list in content]
        inspector = content[names.index("##shell-inspector")]
        colors = {int(vtx.col) for vtx in inspector.vtx_buffer}
        focus_wash = _color_u32_alpha(HIGHLIGHT, FOCUS_WASH_ALPHA / 255.0)
        selected_wash = _color_u32_alpha(HIGHLIGHT, SELECTED_WASH_ALPHA / 255.0)
        old_wash = _color_u32_alpha(HIGHLIGHT, FOCUS_ROW_BG_ALPHA / 255.0)
        has_focus_wash = focus_wash in colors
        has_selected_wash = selected_wash in colors
        has_old_wash = old_wash in colors
        has_value = _color_u32(VALUE) in colors
        highlight = (
            HIGHLIGHT[0] / 255.0,
            HIGHLIGHT[1] / 255.0,
            HIGHLIGHT[2] / 255.0,
            1.0,
        )
        label = (
            LABEL[0] / 255.0,
            LABEL[1] / 255.0,
            LABEL[2] / 255.0,
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
    assert not has_old_wash
    assert has_value
    assert focused_group_push == []
    assert len(unfocused_field) == 1
    assert unfocused_field[0] == pytest.approx(label)


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
        )
    )


def _motion(y: int) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEMOTION,
        pos=(2, y),
        rel=(0, 0),
        buttons=(0, 0, 0),
    )
