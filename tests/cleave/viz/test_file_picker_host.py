"""Key mapping and event loop for the picker host, without a real window."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pygame
import pytest

from cleave.open_target import OpenTargetKind
from cleave.viz.file_picker import PickerAction
from cleave.viz.file_picker_host import (
    picker_action_for,
    run_file_picker,
    show_picker_error,
)
from cleave.project import PROJECT_FILENAME

_CTRL = pygame.KMOD_LCTRL


def _mock_window(width: int = 640, height: int = 480) -> MagicMock:
    window = MagicMock()
    window.quit_requested = False
    window.display_width = width
    window.display_height = height
    window.overlay_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    return window


def _keydown(key: int, mod: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod)


def test_arrow_and_page_mapping() -> None:
    assert picker_action_for(pygame.K_UP, 0) is PickerAction.MOVE_UP
    assert picker_action_for(pygame.K_DOWN, 0) is PickerAction.MOVE_DOWN
    assert picker_action_for(pygame.K_UP, _CTRL) is PickerAction.PAGE_UP
    assert picker_action_for(pygame.K_DOWN, _CTRL) is PickerAction.PAGE_DOWN
    assert picker_action_for(pygame.K_PAGEUP, 0) is PickerAction.PAGE_UP
    assert picker_action_for(pygame.K_PAGEDOWN, 0) is PickerAction.PAGE_DOWN


def test_walk_and_confirm_mapping() -> None:
    assert picker_action_for(pygame.K_LEFT, 0) is PickerAction.PARENT
    assert picker_action_for(pygame.K_BACKSPACE, 0) is PickerAction.PARENT
    assert picker_action_for(pygame.K_RIGHT, 0) is PickerAction.ENTER
    assert picker_action_for(pygame.K_RETURN, 0) is PickerAction.ACCEPT
    assert picker_action_for(pygame.K_KP_ENTER, 0) is PickerAction.ACCEPT
    assert picker_action_for(pygame.K_TAB, 0) is PickerAction.TOGGLE_FOCUS
    assert picker_action_for(pygame.K_ESCAPE, 0) is PickerAction.CANCEL


def test_unmapped_key_is_ignored() -> None:
    assert picker_action_for(pygame.K_q, 0) is None
    assert picker_action_for(pygame.K_v, _CTRL) is None


def _run_with_events(
    window: MagicMock,
    events: list[list[pygame.event.Event]],
    start: Path,
):
    """Drive the loop with one batch of events per iteration."""
    batches = list(events)

    def next_batch() -> list[pygame.event.Event]:
        return batches.pop(0) if batches else []

    with (
        patch("pygame.event.get", side_effect=next_batch),
        patch("pygame.display.flip"),
        patch("cleave.viz.file_picker_host._present"),
        patch("cleave.viz.file_picker.projects_dir", return_value=start),
    ):
        return run_file_picker(window)


@pytest.fixture(autouse=True)
def _pygame_ready() -> None:
    pygame.init()


def test_loop_accepts_a_wav(tmp_path: Path) -> None:
    song = tmp_path / "song.wav"
    song.write_bytes(b"RIFF")
    window = _mock_window()

    target = _run_with_events(
        window,
        [[_keydown(pygame.K_DOWN)], [_keydown(pygame.K_RETURN)]],
        tmp_path,
    )

    assert target is not None
    assert target.kind is OpenTargetKind.AUDIO
    assert target.path == song
    window.close.assert_not_called()


def test_loop_accepts_a_project(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    (project / PROJECT_FILENAME).write_text("slug: song\n")
    window = _mock_window()

    target = _run_with_events(
        window,
        [[_keydown(pygame.K_DOWN)], [_keydown(pygame.K_RETURN)]],
        tmp_path,
    )

    assert target is not None
    assert target.kind is OpenTargetKind.PROJECT


def test_escape_cancels(tmp_path: Path) -> None:
    window = _mock_window()
    assert _run_with_events(window, [[_keydown(pygame.K_ESCAPE)]], tmp_path) is None


def test_window_close_stops_the_loop(tmp_path: Path) -> None:
    window = _mock_window()
    quit_event = pygame.event.Event(pygame.QUIT)

    assert _run_with_events(window, [[quit_event]], tmp_path) is None
    assert window.quit_requested


def test_show_picker_error_any_key_returns_true(tmp_path: Path) -> None:
    window = _mock_window()
    batches = [[], [_keydown(pygame.K_SPACE)]]

    with (
        patch("pygame.event.get", side_effect=lambda: batches.pop(0)),
        patch("cleave.viz.file_picker_host._present"),
    ):
        assert show_picker_error(window, "demucs blew up") is True
    assert not window.quit_requested


def test_show_picker_error_quit_returns_false() -> None:
    window = _mock_window()
    batches = [[pygame.event.Event(pygame.QUIT)]]

    with (
        patch("pygame.event.get", side_effect=lambda: batches.pop(0)),
        patch("cleave.viz.file_picker_host._present"),
    ):
        assert show_picker_error(window, "boom") is False
    assert window.quit_requested
