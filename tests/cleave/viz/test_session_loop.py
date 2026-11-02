"""Session loop: one window, switch, failure, and quit."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cleave.open_target import OpenTarget, OpenTargetKind
from cleave.viz.file_picker import PickerMode
from cleave.viz.session_loop import run_editor_sessions


def _window() -> MagicMock:
    window = MagicMock()
    window.quit_requested = False
    window.video_quit = False
    return window


def _audio(path: Path | None = None) -> OpenTarget:
    return OpenTarget(path=path or Path("/song.wav"), kind=OpenTargetKind.AUDIO)


def _project(path: Path | None = None) -> OpenTarget:
    return OpenTarget(path=path or Path("/projects/song"), kind=OpenTargetKind.PROJECT)


def test_switch_relaunches_without_closing_between_sessions() -> None:
    window = _window()
    audio = _audio()
    project_dir = Path("/projects/song")
    switched = _project(project_dir)
    launches: list[Path] = []

    def separate(path: Path, **kwargs: object) -> Path:
        assert window.close.call_count == 0
        assert path == audio.path
        assert kwargs["high_quality"] is True
        assert kwargs["beat_detection_stem"] == "vocals"
        assert kwargs["on_progress"] is window.update
        return project_dir

    def launch(host: MagicMock, project: Path, *, config: Path | None = None) -> OpenTarget | None:
        assert host is window
        assert window.close.call_count == 0
        assert config == Path("viz.yaml")
        launches.append(project)
        if len(launches) == 1:
            return switched
        return None

    with (
        patch("cleave.separate.run_separate", side_effect=separate) as run_separate,
        patch("cleave.viz.continue_launch", side_effect=launch),
        patch("cleave.viz.file_picker_host.run_file_picker") as picker,
    ):
        run_editor_sessions(
            window,
            audio,
            config=Path("viz.yaml"),
            high_quality=True,
            beat_detection_stem="vocals",
        )

    assert launches == [project_dir, switched.path]
    run_separate.assert_called_once()
    picker.assert_not_called()
    window.ensure_imgui.assert_called()
    window.close.assert_called_once()


def test_separate_failure_returns_to_new_project_picker() -> None:
    window = _window()
    audio = _audio()

    def show_error(host: MagicMock, message: str) -> bool:
        assert host.close.call_count == 0
        assert message == "demucs blew up"
        return True

    with (
        patch("cleave.separate.run_separate", side_effect=RuntimeError("demucs blew up")),
        patch("cleave.viz.continue_launch") as launch,
        patch("cleave.viz.file_picker_host.show_picker_error", side_effect=show_error),
        patch("cleave.viz.file_picker_host.run_file_picker", return_value=None) as picker,
    ):
        run_editor_sessions(window, audio, config=None)

    launch.assert_not_called()
    picker.assert_called_once_with(window, mode=PickerMode.NEW_PROJECT)
    window.close.assert_called_once()


def test_launch_failure_returns_to_open_project_picker() -> None:
    from cleave.viz import LaunchError

    window = _window()
    project = _project()

    def show_error(host: MagicMock, message: str) -> bool:
        assert host.close.call_count == 0
        assert message == "no projectM"
        return True

    with (
        patch("cleave.separate.run_separate") as separate,
        patch("cleave.viz.continue_launch", side_effect=LaunchError("no projectM")),
        patch("cleave.viz.file_picker_host.show_picker_error", side_effect=show_error),
        patch("cleave.viz.file_picker_host.run_file_picker", return_value=None) as picker,
    ):
        run_editor_sessions(window, project, config=None)

    separate.assert_not_called()
    picker.assert_called_once_with(window, mode=PickerMode.OPEN_PROJECT)
    window.close.assert_called_once()


def test_cold_start_audio_failure_returns_to_new_project_picker() -> None:
    window = _window()

    def show_error(host: MagicMock, _message: str) -> bool:
        assert host.close.call_count == 0
        return True

    with (
        patch(
            "cleave.viz.file_picker_host.run_file_picker",
            side_effect=[_audio(), None],
        ) as picker,
        patch("cleave.separate.run_separate", side_effect=RuntimeError("nope")),
        patch("cleave.viz.file_picker_host.show_picker_error", side_effect=show_error),
        patch("cleave.viz.continue_launch") as launch,
    ):
        run_editor_sessions(window, None, config=None)

    launch.assert_not_called()
    assert picker.call_args_list[0].kwargs["mode"] is PickerMode.COLD_START
    assert picker.call_args_list[1].kwargs["mode"] is PickerMode.NEW_PROJECT
    window.close.assert_called_once()


def test_quit_closes_the_window_once() -> None:
    window = _window()
    project = _project()

    with (
        patch("cleave.viz.continue_launch", return_value=None) as launch,
        patch("cleave.viz.file_picker_host.run_file_picker") as picker,
        patch("cleave.separate.run_separate") as separate,
    ):
        run_editor_sessions(window, project, config=None)

    launch.assert_called_once_with(window, project.path, config=None)
    picker.assert_not_called()
    separate.assert_not_called()
    window.close.assert_called_once()


def test_cold_start_cancel_closes_once_and_does_not_launch() -> None:
    window = _window()

    with (
        patch("cleave.viz.file_picker_host.run_file_picker", return_value=None) as picker,
        patch("cleave.viz.continue_launch") as launch,
        patch("cleave.separate.run_separate") as separate,
    ):
        run_editor_sessions(window, None, config=None)

    picker.assert_called_once_with(window, mode=PickerMode.COLD_START)
    launch.assert_not_called()
    separate.assert_not_called()
    window.close.assert_called_once()


def test_video_quit_during_launch_reraises_without_closing() -> None:
    window = _window()

    def launch(*_args: object, **_kwargs: object) -> None:
        window.video_quit = True
        raise RuntimeError("display dead")

    with (
        patch("cleave.viz.continue_launch", side_effect=launch),
        patch("cleave.viz.file_picker_host.show_picker_error") as show_error,
        pytest.raises(RuntimeError, match="display dead"),
    ):
        run_editor_sessions(window, _project(), config=None)

    show_error.assert_not_called()
    window.close.assert_not_called()
