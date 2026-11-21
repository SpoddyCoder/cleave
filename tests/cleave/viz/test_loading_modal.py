"""Loading-window modal runner, without a GL window."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame
import pytest

from cleave.viz.loading_modal import run_modal, show_notice
from cleave.viz.modal import ModalHost, ModalOption


@pytest.fixture(autouse=True)
def _pygame_ready() -> None:
    pygame.init()


def _window() -> MagicMock:
    window = MagicMock()
    window.quit_requested = False
    return window


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0)


def _run_with(batches: list[list[pygame.event.Event]], fn):
    pending = list(batches)
    with (
        patch(
            "pygame.event.get",
            side_effect=lambda: pending.pop(0) if pending else [],
        ),
        patch("cleave.viz.loading_modal.present_frame") as present,
    ):
        return fn(), present


def test_run_modal_ends_on_button() -> None:
    window = _window()
    host = ModalHost()
    chosen: list[str] = []
    host.prompt_buttons(
        "Pick",
        [ModalOption("A", lambda: chosen.append("a")), ModalOption("B", lambda: chosen.append("b"))],
    )
    result, present = _run_with(
        [[], [_keydown(pygame.K_RIGHT)], [_keydown(pygame.K_RETURN)]],
        lambda: run_modal(window, host),
    )
    assert result is True
    assert chosen == ["b"]
    assert present.call_count >= 2


def test_run_modal_quit_returns_false() -> None:
    window = _window()
    host = ModalHost()
    host.prompt_notice("Hi")
    result, _present = _run_with(
        [[pygame.event.Event(pygame.QUIT)]], lambda: run_modal(window, host)
    )
    assert result is False
    assert window.quit_requested
    assert host.active


def test_mouse_events_reach_imgui() -> None:
    window = _window()
    motion = pygame.event.Event(pygame.MOUSEMOTION, pos=(1, 1), rel=(1, 1), buttons=(0, 0, 0))
    result, _present = _run_with(
        [[motion], [_keydown(pygame.K_ESCAPE)]],
        lambda: show_notice(window, "Title", "Body"),
    )
    assert result is True
    window.imgui.process_mouse_event.assert_called_once_with(motion)


def test_split_prompt_starts_on_four_and_reports_the_pick() -> None:
    from cleave.viz.modal import ModalHost
    from cleave.viz.stem_count_prompt import (
        NEW_PROJECT_STEMS_TITLE,
        SplitChoice,
        prompt_split,
    )

    picked: list[SplitChoice] = []
    cancelled: list[bool] = []
    host = ModalHost()

    def ask() -> None:
        prompt_split(
            host, NEW_PROJECT_STEMS_TITLE, picked.append, lambda: cancelled.append(True)
        )

    def key(code: int) -> None:
        host.handle_keydown(pygame.event.Event(pygame.KEYDOWN, key=code, mod=0))

    ask()
    view = host.view_state()
    assert view is not None
    assert view.options == ("4 stems", "4 stems HQ", "6 stems", "Cancel")
    assert view.focus_index == 0
    key(pygame.K_RIGHT)
    key(pygame.K_RETURN)
    assert picked == [SplitChoice(4, high_quality=True)]
    assert not host.active

    ask()
    key(pygame.K_RIGHT)
    key(pygame.K_RIGHT)
    key(pygame.K_RETURN)
    assert picked[-1] == SplitChoice(6)

    ask()
    key(pygame.K_ESCAPE)
    assert cancelled == [True]
    assert len(picked) == 2


def test_project_split_reads_the_manifest(tmp_path) -> None:
    from cleave.project import write_manifest
    from cleave.viz.stem_count_prompt import SplitChoice, project_split

    def split_with(model: str) -> SplitChoice:
        write_manifest(
            tmp_path,
            slug="song",
            mix_filename="song.wav",
            original_path=tmp_path / "song.wav",
            demucs_model=model,
        )
        return project_split(tmp_path)

    assert split_with("htdemucs") == SplitChoice(4)
    assert split_with("htdemucs_ft") == SplitChoice(4, high_quality=True)
    assert split_with("htdemucs_6s") == SplitChoice(6)


def test_split_prompt_starts_on_the_given_default() -> None:
    from cleave.viz.modal import ModalHost
    from cleave.viz.stem_count_prompt import SplitChoice, prompt_split

    host = ModalHost()
    prompt_split(host, "t", lambda _c: None, default=SplitChoice(4, high_quality=True))
    view = host.view_state()
    assert view is not None and view.focus_index == 1
