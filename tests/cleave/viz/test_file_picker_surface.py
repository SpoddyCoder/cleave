"""Headless ImGui file picker: layout helpers and pointer hits. No GL window."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pygame
import pytest
from imgui_bundle import imgui

from cleave.open_target import OpenTargetKind
from cleave.viz.file_picker import (
    QUIT_LABEL,
    FilePicker,
    PickerAction,
    PickerFocus,
    PickerRow,
    PickerRowKind,
    picker_legend,
)
from cleave.viz.file_picker_surface import (
    FILE_PICKER_LIST,
    FILE_PICKER_WINDOW,
    FilePickerSurface,
    PickerPointerIntent,
    PickerPointerKind,
    apply_picker_pointer,
    legend_rows,
    location_text,
    location_text_lift,
    picker_list_height,
    row_text,
    shortcut_chip_layout,
    shortcut_is_current,
    shortcut_is_selected,
    visible_row_range,
    wheel_scroll_px,
)
from cleave.viz.imgui_theme import rgba
from cleave.viz.material_icons import (
    ARROW_DOWNWARD_GLYPH,
    ARROW_UPWARD_GLYPH,
    FOLDER_GLYPH,
)
from cleave.viz.theme import (
    FOCUS_BORDER_ALPHA,
    FOCUS_WASH_ALPHA,
    HIGHLIGHT,
    HOVER,
    HOVER_BG_ALPHA,
    LABEL,
    PRESET_ICON,
    VALUE,
    tuning_ui_metrics,
)

Rect = tuple[int, int, int, int]
_DISPLAY = (1280, 720)


def _width(text: str) -> int:
    return len(text) * 8


def _center(rect: Rect) -> tuple[int, int]:
    x, y, width, height = rect
    return (x + width // 2, y + height // 2)


def _motion(
    pos: tuple[int, int], rel: tuple[int, int] = (0, 0)
) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEMOTION, pos=pos, rel=rel, buttons=(0, 0, 0)
    )


def _down(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def _up(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)


def _wheel(y: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=y)


@contextmanager
def _host() -> Iterator[object]:
    pygame.init()
    from cleave.viz import imgui_host
    from cleave.viz.imgui_host import ImGuiHost

    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = ImGuiHost.create()
    host.display_size = _DISPLAY
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


def _frame(
    host: object,
    surface: FilePickerSurface,
    events=(),
    dt: float = 1.0 / 60.0,
    *,
    picker: FilePicker | None = None,
) -> None:
    for event in events:
        host.process_mouse_event(event)
    if picker is not None:
        surface.view = picker.view_state()
    host.begin_frame(dt)
    try:
        surface.draw()
    finally:
        host.end_frame()


def _draw_names() -> list[str]:
    return [str(draw_list._owner_name) for draw_list in imgui.get_draw_data().cmd_lists]


def test_visible_row_range_covers_rows_that_intersect_the_view() -> None:
    assert visible_row_range(0, 50, 10, 20) == (0, 5)
    assert visible_row_range(15, 50, 10, 20) == (1, 7)


def test_visible_row_range_empty_listing() -> None:
    assert visible_row_range(0, 50, 10, 0) == (0, 0)


def test_wheel_scroll_px_moves_three_rows_per_notch() -> None:
    assert wheel_scroll_px(1.0, 10) == -30
    assert wheel_scroll_px(-1.0, 10) == 30
    assert wheel_scroll_px(0.0, 10) == 0


def test_row_text_marks_directories_and_projects() -> None:
    directory = PickerRow(
        label="music", kind=PickerRowKind.DIRECTORY, target=Path("/music")
    )
    project = PickerRow(
        label="song", kind=PickerRowKind.PROJECT, target=Path("/song")
    )
    audio = PickerRow(
        label="song.wav", kind=PickerRowKind.AUDIO, target=Path("/song.wav")
    )

    assert row_text(directory) == "music/"
    assert "project" in row_text(project)
    assert row_text(audio) == "song.wav"


def _vertex_ys(color: int) -> list[float]:
    found: list[float] = []
    for draw_list in _picker_draw_lists():
        for index in range(draw_list.vtx_buffer.size()):
            vertex = draw_list.vtx_buffer[index]
            if int(vertex.col) == color:
                found.append(float(vertex.pos.y))
    return found


def test_location_text_keeps_the_path_tail() -> None:
    path = "/home/user/very/long/nested/directory/structure/projects/song"
    fitted = location_text(path, 24, len)
    assert fitted.startswith("…")
    assert fitted.endswith("song")
    assert len(fitted) <= 24
    assert not fitted.endswith("…")


def test_location_text_lines_up_with_the_folder_icon(tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        font = imgui.get_io().font_default
        icon = font.find_glyph(ord(FOLDER_GLYPH))
        cap = font.find_glyph(ord("A"))
        lift = location_text_lift()
        icon_ys = _vertex_ys(_pack(PRESET_ICON))
        icon_top, icon_bottom = min(icon_ys), max(icon_ys)
        path_ys = [
            y
            for y in _vertex_ys(_pack(VALUE))
            if icon_top - 8.0 <= y <= icon_bottom + 8.0
        ]

    assert lift == int(round((icon.y0 + icon.y1) / 2 - (cap.y0 + cap.y1) / 2))
    assert lift < 0
    assert icon_ys and path_ys
    assert abs((min(path_ys) - min(icon_ys)) - (lift + cap.y0 - icon.y0)) <= 1.0


def test_shortcut_chip_layout_and_selection(tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    picker.focus = PickerFocus.SHORTCUTS
    picker.selected_shortcut = 1
    view = picker.view_state()

    chips = shortcut_chip_layout(view, content_w=800, text_width=_width)
    assert len(chips) == len(view.shortcuts)
    assert chips[0][1] == "[Projects]"
    assert chips[1][2] > chips[0][2]
    assert shortcut_is_selected(view, 1)
    assert not shortcut_is_selected(view, 0)

    picker.focus = PickerFocus.LIST
    assert not shortcut_is_selected(picker.view_state(), 1)


def test_shortcut_chips_that_do_not_fit_are_omitted(tmp_path: Path) -> None:
    view = FilePicker(current=tmp_path).view_state()
    assert shortcut_chip_layout(view, content_w=30, text_width=_width) == ()


def test_projects_shortcut_is_current_on_first_show(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path / "cleave"))
    view = FilePicker().view_state()
    assert view.focus is PickerFocus.LIST
    assert view.active_shortcut == 0
    assert not shortcut_is_selected(view, 0)
    assert shortcut_is_current(view, 0)


def test_legend_wraps_to_a_second_line() -> None:
    rows = legend_rows(picker_legend(QUIT_LABEL), 80, _width)
    assert len(rows) >= 2
    assert rows[0][0] == ("Enter", "open")
    assert rows[-1][-1] == ("Esc", "quit")


def test_panel_row_and_chip_rects(tmp_path: Path) -> None:
    (tmp_path / "song.wav").write_bytes(b"RIFF")
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        assert any(FILE_PICKER_WINDOW in name for name in _draw_names())
        panel = surface.panel_rect
        assert panel is not None
        width, height = _DISPLAY
        assert panel[2] == int(width * 0.6)
        assert panel[3] == int(height * 0.7)
        assert panel[0] == (width - panel[2]) // 2
        assert panel[1] == (height - panel[3]) // 2
        assert surface.row_indices == (0, 1)
        assert len(surface.row_rects) == 2
        assert surface.row_rects[1][1] > surface.row_rects[0][1]
        assert surface.chip_indices
        assert surface.chip_rects[0][1] < surface.row_rects[0][1]
        assert len(surface.chip_rects) == len(surface.chip_indices)
        for rect in surface.row_rects:
            assert panel[0] <= rect[0]
            assert rect[0] + rect[2] <= panel[0] + panel[2]


def _pack(role: tuple[int, int, int], alpha: float = 1.0) -> int:
    return int(imgui.get_color_u32(rgba(role, alpha)))


def _picker_draw_lists():
    prefix = FILE_PICKER_WINDOW
    return [
        draw_list
        for draw_list in imgui.get_draw_data().cmd_lists
        if str(draw_list._owner_name).startswith(prefix)
    ]


def _color_counts() -> dict[int, int]:
    found: dict[int, int] = {}
    for draw_list in _picker_draw_lists():
        for index in range(draw_list.vtx_buffer.size()):
            color = int(draw_list.vtx_buffer[index].col)
            found[color] = found.get(color, 0) + 1
    return found


def _vertices_near(
    color: int, *, x: float | None = None, y: float | None = None, slack: float = 1.5
) -> int:
    """Count vertices of *color* sitting on one edge of a highlight rect."""
    found = 0
    for draw_list in _picker_draw_lists():
        for index in range(draw_list.vtx_buffer.size()):
            vtx = draw_list.vtx_buffer[index]
            if int(vtx.col) != color:
                continue
            if x is not None and abs(float(vtx.pos.x) - x) > slack:
                continue
            if y is not None and abs(float(vtx.pos.y) - y) > slack:
                continue
            found += 1
    return found


def _hover() -> int:
    return _pack(HOVER, HOVER_BG_ALPHA / 255.0)


def _wash_and_border() -> tuple[int, int]:
    return (
        _pack(HIGHLIGHT, FOCUS_WASH_ALPHA / 255.0),
        _pack(HIGHLIGHT, FOCUS_BORDER_ALPHA / 255.0),
    )


def _above(panel: Rect) -> tuple[int, int]:
    return (panel[0] + panel[2] // 2, panel[1] - 8)


def _off_item_positions(
    surface: FilePickerSurface, panel: Rect
) -> tuple[tuple[int, int], ...]:
    """Points on the title, path, legend, and outside the panel."""
    chip_bottom = max(rect[1] + rect[3] for rect in surface.chip_rects)
    row_top = min(rect[1] for rect in surface.row_rects)
    assert chip_bottom < row_top
    center_x = panel[0] + panel[2] // 2
    return (
        (center_x, panel[1] + 4),
        (center_x, (chip_bottom + row_top) // 2),
        (center_x, panel[1] + panel[3] - 8),
        _above(panel),
    )


def _assert_outline_inside_clip(
    color: int, *, x: float | None = None, y: float | None = None, slack: float = 1.5
) -> None:
    """Border vertices on one edge of a highlight must sit inside their clip."""
    found = 0
    for draw_list in _picker_draw_lists():
        vertices = draw_list.vtx_buffer
        indices = draw_list.idx_buffer
        for cmd_index in range(draw_list.cmd_buffer.size()):
            cmd = draw_list.cmd_buffer[cmd_index]
            clip = cmd.clip_rect
            base = int(cmd.vtx_offset)
            start = int(cmd.idx_offset)
            for offset in range(int(cmd.elem_count)):
                vertex = vertices[base + int(indices[start + offset])]
                if int(vertex.col) != color:
                    continue
                px, py = float(vertex.pos.x), float(vertex.pos.y)
                if x is not None and abs(px - x) > slack:
                    continue
                if y is not None and abs(py - y) > slack:
                    continue
                found += 1
                assert clip.x <= px <= clip.z
                assert clip.y <= py <= clip.w
    assert found > 0


def _shortcut_slot(surface: FilePickerSurface, picker: FilePicker, label: str) -> int:
    model = next(
        index
        for index, shortcut in enumerate(picker.shortcuts)
        if shortcut.label == label
    )
    return surface.chip_indices.index(model)


def test_row_highlight_outline_is_not_clipped(tmp_path: Path) -> None:
    (tmp_path / "song.wav").write_bytes(b"RIFF")
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        _wash, border = _wash_and_border()
        top = surface.row_rects[0]
        _assert_outline_inside_clip(border, x=float(top[0]))
        _assert_outline_inside_clip(border, y=float(top[1]))
        _assert_outline_inside_clip(border, x=float(top[0] + top[2]))
        _assert_outline_inside_clip(border, y=float(top[1] + top[3]))

        pos = _center(surface.row_rects[1])
        _frame(host, surface, (_motion(pos),))
        lower = surface.row_rects[1]
        _assert_outline_inside_clip(border, x=float(lower[0]))
        _assert_outline_inside_clip(border, y=float(lower[1]))


def test_hover_washes_a_row_and_the_selection_stays(tmp_path: Path) -> None:
    (tmp_path / "song.wav").write_bytes(b"RIFF")
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface, picker=picker)
        pos = _center(surface.row_rects[1])
        _frame(host, surface, (_motion(pos, rel=(1, 0)),), picker=picker)
        intent = surface.intent
        colors = _color_counts()
        wash, border = _wash_and_border()
        hovered = surface.row_rects[1]
        selected = surface.row_rects[0]
        # The bottom edge: the top one sits next to the selected row's.
        hovered_bottom = float(hovered[1] + hovered[3])
        hovered_hover = _vertices_near(_hover(), y=hovered_bottom)
        hovered_wash = _vertices_near(wash, y=hovered_bottom)
        hovered_border = _vertices_near(border, y=hovered_bottom)
        selected_wash = _vertices_near(wash, y=float(selected[1]))
        selected_border = _vertices_near(border, y=float(selected[1]))

    assert intent is None
    assert picker.selected_index == 0
    assert colors.get(wash, 0) == 4
    assert hovered_hover == 2
    assert hovered_wash == 0
    assert hovered_border == 0
    assert selected_wash == 2
    assert selected_border > 0


def test_hover_washes_a_shortcut_and_the_row_stays_selected(
    tmp_path: Path,
) -> None:
    (tmp_path / "song.wav").write_bytes(b"RIFF")
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface, picker=picker)
        chip = surface.chip_rects[_shortcut_slot(surface, picker, "Home")]
        _frame(host, surface, (_motion(_center(chip), rel=(1, 0)),), picker=picker)
        intent = surface.intent
        wash, border = _wash_and_border()
        row = surface.row_rects[0]
        chip_hover = _vertices_near(_hover(), x=float(chip[0]))
        chip_wash = _vertices_near(wash, x=float(chip[0]))
        row_wash = _vertices_near(wash, y=float(row[1]))
        row_border = _vertices_near(border, y=float(row[1]))

    assert intent is None
    assert picker.current == tmp_path
    assert chip_hover == 2
    assert chip_wash == 0
    assert row_wash == 2
    assert row_border > 0


def test_selection_stays_lit_wherever_the_pointer_goes(tmp_path: Path) -> None:
    (tmp_path / "song.wav").write_bytes(b"RIFF")
    picker = FilePicker(current=tmp_path)
    picker.select_row(1)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface, picker=picker)
        panel = surface.panel_rect
        assert panel is not None
        wash, border = _wash_and_border()
        positions = _off_item_positions(surface, panel) + (
            _center(surface.button_rects[0]),
        )
        for pos in positions:
            moved = FilePickerSurface(picker.view_state())
            _frame(host, moved, (_motion(pos, rel=(1, 0)),), picker=picker)
            selected = moved.row_rects[1]
            assert _vertices_near(wash, y=float(selected[1])) == 2
            assert _vertices_near(border, y=float(selected[1])) > 0
            assert _vertices_near(wash, y=float(moved.row_rects[0][1])) == 0



def test_shortcuts_draw_in_the_value_colour(tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        chip = surface.chip_rects[_shortcut_slot(surface, picker, "Home")]
        value_on_chip = _vertices_near(_pack(VALUE), y=float(chip[1]), slack=40.0)
        label_on_chip = sum(
            1
            for draw_list in _picker_draw_lists()
            for index in range(draw_list.vtx_buffer.size())
            if int(draw_list.vtx_buffer[index].col) == _pack(LABEL)
            and chip[1] <= float(draw_list.vtx_buffer[index].pos.y) <= chip[1] + chip[3]
        )

    assert value_on_chip > 0
    assert label_on_chip == 0

def test_keyboard_row_draws_the_focus_outline(tmp_path: Path) -> None:
    (tmp_path / "song.wav").write_bytes(b"RIFF")
    picker = FilePicker(current=tmp_path)
    picker.handle(PickerAction.MOVE_DOWN)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        wash, border = _wash_and_border()
        selected = surface.row_rects[1]
        colors = _color_counts()
        selected_wash = _vertices_near(wash, y=float(selected[1]))
        selected_border = _vertices_near(border, y=float(selected[1]))

    assert picker.selected_index == 1
    assert colors.get(wash, 0) == 4
    assert selected_wash == 2
    assert selected_border > 0


def test_keyboard_shortcut_draws_the_focus_outline(tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    picker.focus = PickerFocus.SHORTCUTS
    picker.selected_shortcut = 0
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        wash, border = _wash_and_border()
        chip = surface.chip_rects[_shortcut_slot(surface, picker, "Projects")]
        row = surface.row_rects[0]
        chip_wash = _vertices_near(wash, x=float(chip[0]))
        chip_border = _vertices_near(border, x=float(chip[0]))
        row_wash = _vertices_near(wash, y=float(row[1]))
        row_border = _vertices_near(border, y=float(row[1]))

    assert chip_wash == 2
    assert chip_border > 0
    # The listing keeps its chosen row, without the focus outline.
    assert row_wash == 2
    assert row_border == 0


def test_click_selects_a_row(tmp_path: Path) -> None:
    song = tmp_path / "song.wav"
    song.write_bytes(b"RIFF")
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        pos = _center(surface.row_rects[1])
        _frame(host, surface, (_motion(pos), _down(pos)))

    assert surface.intent is not None
    assert surface.intent.kind is PickerPointerKind.SELECT_ROW
    assert surface.intent.index == 1
    assert apply_picker_pointer(picker, surface.intent) is None
    assert picker.selected_index == 1
    assert picker.focus is PickerFocus.LIST
    assert picker.current == tmp_path
    assert picker.selected_row is not None
    assert picker.selected_row.target == song


def test_double_click_opens_audio(tmp_path: Path) -> None:
    song = tmp_path / "song.wav"
    song.write_bytes(b"RIFF")
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        pos = _center(surface.row_rects[1])
        _frame(host, surface, (_motion(pos), _down(pos)), dt=0.05)
        assert surface.intent is not None
        assert surface.intent.kind is PickerPointerKind.SELECT_ROW
        apply_picker_pointer(picker, surface.intent)
        _frame(host, surface, (_up(pos),), dt=0.05)
        _frame(host, surface, (_down(pos),), dt=0.05)

    assert surface.intent is not None
    assert surface.intent.kind is PickerPointerKind.OPEN_ROW
    target = apply_picker_pointer(picker, surface.intent)
    assert target is not None
    assert target.kind is OpenTargetKind.AUDIO
    assert target.path == song



def test_picker_list_height_fits_rows_up_to_the_room() -> None:
    assert picker_list_height(3, 20, 500) == 60
    assert picker_list_height(0, 20, 500) == 20
    assert picker_list_height(40, 20, 500) == 500


def _legend_top(panel: Rect) -> int:
    metrics = tuning_ui_metrics()
    step = imgui.get_text_line_height() + metrics.line_gap
    return panel[1] + panel[3] - metrics.modal_panel_pad_y - int(step) * 2


def test_open_and_quit_buttons_follow_the_last_row(tmp_path: Path) -> None:
    (tmp_path / "song.wav").write_bytes(b"RIFF")
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        panel = surface.panel_rect
        assert panel is not None
        open_rect, quit_rect = surface.button_rects
        last = surface.row_rects[-1]
        step = int(imgui.get_text_line_height()) + tuning_ui_metrics().line_gap
        legend_top = _legend_top(panel)

    assert open_rect[0] < quit_rect[0]
    assert last[1] + last[3] <= open_rect[1] <= last[1] + last[3] + step
    assert open_rect[1] + open_rect[3] < legend_top
    pad_x = tuning_ui_metrics().modal_panel_pad_x
    assert quit_rect[0] + quit_rect[2] == panel[0] + panel[2] - pad_x


def test_buttons_move_with_the_listing(tmp_path: Path) -> None:
    for index in range(4):
        (tmp_path / f"dir{index}").mkdir()
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        longer = surface.button_rects[0][1]
        picker.navigate_to(tmp_path / "dir0")
        shorter = FilePickerSurface(picker.view_state())
        _frame(host, shorter)
        moved = shorter.button_rects[0][1]

    assert moved < longer


def test_long_list_scrolls_above_the_buttons(tmp_path: Path) -> None:
    for index in range(80):
        (tmp_path / f"dir{index:02d}").mkdir()
    surface = FilePickerSurface(FilePicker(current=tmp_path).view_state())

    with _host() as host:
        _frame(host, surface)
        window = _list_window()
        assert window is not None
        list_bottom = float(window.pos.y + window.size.y)
        panel = surface.panel_rect
        assert panel is not None
        buttons = surface.button_rects
        legend_top = _legend_top(panel)

    assert window.scrollbar_y is True
    assert all(rect[1] >= list_bottom for rect in buttons)
    assert all(rect[1] + rect[3] < legend_top for rect in buttons)


def test_open_button_opens_the_selected_row(tmp_path: Path) -> None:
    song = tmp_path / "song.wav"
    song.write_bytes(b"RIFF")
    picker = FilePicker(current=tmp_path)
    picker.select_row(1)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        pos = _center(surface.button_rects[0])
        _frame(host, surface, (_motion(pos), _down(pos)), dt=0.05)

    assert surface.intent == PickerPointerIntent(PickerPointerKind.OPEN_SELECTED)
    target = apply_picker_pointer(picker, surface.intent)
    assert target is not None
    assert target.path == song


def test_quit_button_cancels(tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        pos = _center(surface.button_rects[1])
        _frame(host, surface, (_motion(pos), _down(pos)), dt=0.05)

    assert surface.intent == PickerPointerIntent(PickerPointerKind.CANCEL)
    assert apply_picker_pointer(picker, surface.intent) is None
    assert picker.cancelled

def _list_window():
    ctx = imgui.get_current_context()
    prefix = f"{FILE_PICKER_WINDOW}/{FILE_PICKER_LIST}"
    for window in ctx.windows:
        if str(window.name).startswith(prefix):
            return window
    return None


def test_long_list_shows_a_scrollbar(tmp_path: Path) -> None:
    for index in range(40):
        (tmp_path / f"dir{index:02d}").mkdir()
    surface = FilePickerSurface(FilePicker(current=tmp_path).view_state())

    with _host() as host:
        _frame(host, surface)
        window = _list_window()

    assert window is not None
    assert window.scrollbar_y is True


def test_wheel_over_a_long_list_scrolls(tmp_path: Path) -> None:
    for index in range(40):
        (tmp_path / f"dir{index:02d}").mkdir()
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        pos = _center(surface.row_rects[0])
        _frame(host, surface, (_motion(pos), _wheel(-1)))
        _frame(host, surface)

    assert surface.row_indices[0] > 0
    assert surface.intent is None
    assert picker.selected_index == 0
    assert picker.focus is PickerFocus.LIST


def test_short_list_has_no_scrollbar(tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        window = _list_window()

    assert window is not None
    assert window.scrollbar_y is False


def test_scrollbar_track_click_scrolls(tmp_path: Path) -> None:
    for index in range(40):
        (tmp_path / f"dir{index:02d}").mkdir()
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        window = _list_window()
        assert window is not None
        rect = imgui.internal.get_window_scrollbar_rect(
            window, imgui.internal.Axis.y
        )
        click = (
            int((rect.min.x + rect.max.x) / 2),
            int(rect.max.y - 8),
        )
        _frame(host, surface, (_motion(click), _down(click)))
        _frame(host, surface, (_up(click),))
        _frame(host, surface)

    assert surface.row_indices[0] > 0
    assert picker.selected_index == 0


def test_a_new_directory_opens_at_the_top(tmp_path: Path) -> None:
    for index in range(40):
        (tmp_path / f"dir{index:02d}").mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        pos = _center(surface.row_rects[0])
        _frame(host, surface, (_motion(pos), _wheel(-1)))
        _frame(host, surface)
        assert surface.row_indices[0] > 0
        picker.navigate_to(elsewhere)
        opened = FilePickerSurface(picker.view_state())
        _frame(host, opened)

    assert opened.row_indices[0] == 0


def test_wheel_outside_the_list_records_nothing(tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        panel = surface.panel_rect
        assert panel is not None
        above = (panel[0] + panel[2] // 2, panel[1] - 8)
        _frame(host, surface, (_motion(above), _wheel(-1)))
        _frame(host, surface)

    assert surface.intent is None
    assert picker.selected_index == 0


def test_click_shortcut_jumps(tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        home = surface.chip_indices.index(
            next(
                index
                for index, shortcut in enumerate(picker.shortcuts)
                if shortcut.label == "Home"
            )
        )
        pos = _center(surface.chip_rects[home])
        _frame(host, surface, (_motion(pos), _down(pos)))

    assert surface.intent is not None
    assert surface.intent.kind is PickerPointerKind.GOTO_SHORTCUT
    assert apply_picker_pointer(picker, surface.intent) is None
    assert picker.current == Path.home()


def test_long_listing_keeps_the_selection_on_screen(tmp_path: Path) -> None:
    for index in range(40):
        (tmp_path / f"dir{index:02d}").mkdir()
    picker = FilePicker(current=tmp_path)
    last = len(picker.rows) - 1
    picker.select_row(last)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)

    assert last in surface.row_indices
    assert surface.row_indices[0] > 0


def test_folder_glyph_is_in_the_font() -> None:
    with _host() as host:
        host.begin_frame(1.0 / 60.0)
        host.end_frame()
        glyph = imgui.get_io().font_default.find_glyph_no_fallback(ord(FOLDER_GLYPH))
        missing = imgui.get_io().font_default.find_glyph_no_fallback(ord(FOLDER_GLYPH) + 1)

    assert glyph is not None
    assert glyph.x1 > glyph.x0
    assert missing is None


def test_directory_arrow_glyphs_are_in_the_font() -> None:
    with _host() as host:
        host.begin_frame(1.0 / 60.0)
        host.end_frame()
        font = imgui.get_io().font_default
        up = font.find_glyph_no_fallback(ord(ARROW_UPWARD_GLYPH))
        down = font.find_glyph_no_fallback(ord(ARROW_DOWNWARD_GLYPH))

    assert up is not None and up.x1 > up.x0
    assert down is not None and down.x1 > down.x0
