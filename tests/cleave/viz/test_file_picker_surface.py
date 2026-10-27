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
    LEGEND,
    FilePicker,
    PickerFocus,
    PickerRow,
    PickerRowKind,
)
from cleave.viz.file_picker_surface import (
    FILE_PICKER_WINDOW,
    FilePickerSurface,
    PickerPointerKind,
    apply_picker_pointer,
    legend_rows,
    location_text,
    row_text,
    shortcut_chip_layout,
    shortcut_is_current,
    shortcut_is_selected,
    visible_slice,
)
from cleave.viz.material_icons import FOLDER_GLYPH

Rect = tuple[int, int, int, int]
_DISPLAY = (1280, 720)


def _width(text: str) -> int:
    return len(text) * 8


def _center(rect: Rect) -> tuple[int, int]:
    x, y, width, height = rect
    return (x + width // 2, y + height // 2)


def _motion(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)
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


def _frame(host: object, surface: FilePickerSurface, events=(), dt: float = 1.0 / 60.0) -> None:
    for event in events:
        host.process_mouse_event(event)
    host.begin_frame(dt)
    try:
        surface.draw()
    finally:
        host.end_frame()


def _draw_names() -> list[str]:
    return [str(draw_list._owner_name) for draw_list in imgui.get_draw_data().cmd_lists]


def test_visible_slice_shows_everything_when_it_fits() -> None:
    assert visible_slice(5, 0, 12) == (0, 5)


def test_visible_slice_keeps_selection_on_screen() -> None:
    start, end = visible_slice(100, 90, 10)
    assert start <= 90 < end
    assert end - start == 10


def test_visible_slice_clamps_at_the_end() -> None:
    assert visible_slice(100, 99, 10) == (90, 100)


def test_visible_slice_empty_listing() -> None:
    assert visible_slice(0, 0, 10) == (0, 0)


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


def test_location_text_keeps_the_path_tail() -> None:
    path = "/home/user/very/long/nested/directory/structure/projects/song"
    fitted = location_text(path, 24, len)
    assert fitted.startswith("…")
    assert fitted.endswith("song")
    assert len(fitted) <= 24
    assert not fitted.endswith("…")


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
    rows = legend_rows(LEGEND, 80, _width)
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


def test_wheel_over_the_list_steps_the_selection(tmp_path: Path) -> None:
    (tmp_path / "song.wav").write_bytes(b"RIFF")
    picker = FilePicker(current=tmp_path)
    surface = FilePickerSurface(picker.view_state())

    with _host() as host:
        _frame(host, surface)
        pos = _center(surface.row_rects[0])
        # ImGui applies a wheel event on the next frame when a mouse-position
        # event is queued ahead of it.
        _frame(host, surface, (_motion(pos), _wheel(-1)))
        _frame(host, surface)

    assert surface.intent is not None
    assert surface.intent.kind is PickerPointerKind.SCROLL_ROWS
    apply_picker_pointer(picker, surface.intent)
    assert picker.selected_index == 1
    assert picker.focus is PickerFocus.LIST


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
