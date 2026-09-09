"""File picker overlay drawing and row-window maths."""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

from cleave.viz import file_picker_overlay
from cleave.viz.file_picker import (
    LEGEND,
    FilePicker,
    PickerFocus,
    PickerRow,
    PickerRowKind,
)
from cleave.viz.overlay_primitives import overlay_font


def _font() -> pygame.font.Font:
    return overlay_font(20)


@pytest.fixture
def surface() -> pygame.Surface:
    pygame.init()
    return pygame.Surface((1280, 720), pygame.SRCALPHA)


def test_visible_slice_shows_everything_when_it_fits() -> None:
    assert file_picker_overlay.visible_slice(5, 0, 12) == (0, 5)


def test_visible_slice_keeps_selection_on_screen() -> None:
    start, end = file_picker_overlay.visible_slice(100, 90, 10)
    assert start <= 90 < end
    assert end - start == 10


def test_visible_slice_clamps_at_the_end() -> None:
    assert file_picker_overlay.visible_slice(100, 99, 10) == (90, 100)


def test_visible_slice_empty_listing() -> None:
    assert file_picker_overlay.visible_slice(0, 0, 10) == (0, 0)


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

    assert file_picker_overlay.row_text(directory) == "music/"
    assert "project" in file_picker_overlay.row_text(project)
    assert file_picker_overlay.row_text(audio) == "song.wav"


def test_draw_paints_a_centered_panel(
    surface: pygame.Surface, tmp_path: Path
) -> None:
    (tmp_path / "music").mkdir()
    picker = FilePicker(current=tmp_path)

    file_picker_overlay.draw(surface, picker.view_state(), font=_font())

    width, height = surface.get_size()
    assert surface.get_at((width // 2, height // 2))[3] > 0
    # Corner is scrim only, so it stays darker than the panel centre.
    assert surface.get_at((2, 2))[3] > 0


def test_draw_handles_status_line_and_shortcut_focus(
    surface: pygame.Surface, tmp_path: Path
) -> None:
    picker = FilePicker(current=tmp_path)
    picker.paste_path(str(tmp_path / "gone.wav"))
    picker.focus = PickerFocus.SHORTCUTS
    view = picker.view_state()
    assert view.status

    file_picker_overlay.draw(surface, view, font=_font())


def test_shortcut_chip_layout_and_selection(tmp_path: Path) -> None:
    picker = FilePicker(current=tmp_path)
    picker.focus = PickerFocus.SHORTCUTS
    picker.selected_shortcut = 1
    view = picker.view_state()
    font = _font()

    chips = file_picker_overlay.shortcut_chip_layout(
        font, view, x=0, content_w=800
    )
    assert len(chips) == len(view.shortcuts)
    assert chips[0][1] == "[Projects]"
    assert chips[1][2] > chips[0][2]
    assert file_picker_overlay.shortcut_is_selected(view, 1)
    assert not file_picker_overlay.shortcut_is_selected(view, 0)

    picker.focus = PickerFocus.LIST
    assert not file_picker_overlay.shortcut_is_selected(picker.view_state(), 1)


def test_draw_highlights_only_the_selected_shortcut(
    surface: pygame.Surface, tmp_path: Path
) -> None:
    from cleave.viz.theme import ACTION, HIGHLIGHT

    picker = FilePicker(current=tmp_path)
    picker.focus = PickerFocus.SHORTCUTS
    picker.selected_shortcut = 1
    view = picker.view_state()
    font = _font()

    file_picker_overlay.draw(surface, view, font=font)

    width, height = surface.get_size()
    panel_w = int(width * file_picker_overlay._PANEL_WIDTH_FRACTION)
    panel_x = (width - panel_w) // 2
    panel_y = (height - int(height * file_picker_overlay._PANEL_HEIGHT_FRACTION)) // 2
    pad_x = file_picker_overlay._PANEL_PAD_X
    pad_y = file_picker_overlay._PANEL_PAD_Y
    line_h = font.get_linesize()
    step = line_h + file_picker_overlay._tuning_ui.line_gap
    shortcut_y = panel_y + pad_y + step * 2
    chips = file_picker_overlay.shortcut_chip_layout(
        font, view, x=panel_x + pad_x, content_w=panel_w - pad_x * 2
    )
    sample_y = shortcut_y + line_h // 2

    def _has_color(chip_x: int, chip_w: int, color: tuple[int, int, int]) -> bool:
        for x in range(chip_x, chip_x + chip_w):
            pixel = surface.get_at((x, sample_y))
            if pixel[:3] == color:
                return True
        return False

    _, _, home_x, home_w = chips[1]
    _, _, projects_x, projects_w = chips[0]
    assert _has_color(home_x, home_w, HIGHLIGHT)
    assert _has_color(projects_x, projects_w, ACTION)
    assert not _has_color(projects_x, projects_w, HIGHLIGHT)


def test_draw_handles_drives_listing(surface: pygame.Surface) -> None:
    picker = FilePicker(current=Path("/"))
    picker.show_drives()

    file_picker_overlay.draw(surface, picker.view_state(), font=_font())


def test_legend_wraps_to_a_second_line() -> None:
    font = _font()
    lines = file_picker_overlay.legend_lines(font, LEGEND, 400)
    assert len(lines) >= 2
    assert "Enter open" in lines[0]
    assert "Esc quit" in lines[-1]
    assert all("…" not in line for line in lines)


def test_draw_legend_uses_label_color(
    surface: pygame.Surface, tmp_path: Path
) -> None:
    from cleave.viz.theme import ACTION, LABEL

    picker = FilePicker(current=tmp_path)
    font = _font()
    file_picker_overlay.draw(surface, picker.view_state(), font=font)

    width, height = surface.get_size()
    panel_w = int(width * file_picker_overlay._PANEL_WIDTH_FRACTION)
    panel_h = int(height * file_picker_overlay._PANEL_HEIGHT_FRACTION)
    panel_x = (width - panel_w) // 2
    panel_y = (height - panel_h) // 2
    pad_x = file_picker_overlay._PANEL_PAD_X
    pad_y = file_picker_overlay._PANEL_PAD_Y
    content_w = panel_w - pad_x * 2
    line_h = font.get_linesize()
    step = line_h + file_picker_overlay._tuning_ui.line_gap
    lines = file_picker_overlay.legend_lines(font, LEGEND, content_w)
    assert len(lines) >= 2

    footer_y = panel_y + panel_h - pad_y - len(lines) * step

    def _row_has(color: tuple[int, int, int], y: int) -> bool:
        for x in range(panel_x + pad_x, panel_x + pad_x + content_w):
            if surface.get_at((x, y))[:3] == color:
                return True
        return False

    assert _row_has(LABEL, footer_y + line_h // 2)
    assert _row_has(LABEL, footer_y + step + line_h // 2)
    assert not _row_has(ACTION, footer_y + line_h // 2)
