"""Tests for the live frame loop's window requests and UI frame."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cleave.viz.live_frame_loop import LiveFrameLoop, apply_window_requests
from cleave.viz.modal import ModalHost
from cleave.viz.modal_surface import ModalSurface
from cleave.viz.panel_notification import PanelNotificationActive
from cleave.viz.window_controls import WindowControls


class _FakeWindow:
    def __init__(self, fullscreen: bool = False) -> None:
        self.fullscreen = fullscreen
        self.toggles = 0

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        self.toggles += 1


def test_play_full_screen_takes_the_window_fullscreen_and_restores_it() -> None:
    controls = WindowControls()
    window = _FakeWindow()
    controls.request_play_fullscreen(True)
    apply_window_requests(controls, window, prompt_open=False)
    assert controls.play_fullscreen is True
    assert window.fullscreen is True
    assert controls.fullscreen is True

    controls.request_play_fullscreen(False)
    apply_window_requests(controls, window, prompt_open=False)
    assert controls.play_fullscreen is False
    assert window.fullscreen is False
    assert window.toggles == 2


def test_play_full_screen_leaves_full_screen_editor_on() -> None:
    controls = WindowControls()
    window = _FakeWindow(fullscreen=True)
    controls.request_play_fullscreen(True)
    apply_window_requests(controls, window, prompt_open=False)
    controls.request_play_fullscreen(False)
    apply_window_requests(controls, window, prompt_open=False)
    assert window.toggles == 0
    assert window.fullscreen is True


def test_a_prompt_returns_from_play_full_screen() -> None:
    controls = WindowControls()
    window = _FakeWindow()
    controls.request_play_fullscreen(True)
    apply_window_requests(controls, window, prompt_open=False)
    apply_window_requests(controls, window, prompt_open=True)
    assert controls.play_fullscreen is False
    assert window.fullscreen is False


class _FakeTopLayer:
    def __init__(self) -> None:
        self.pushed: list[object] = []
        self.lifted_rects: tuple[object, ...] = ()
        self.modal_active = False

    def push(self, surface: object) -> None:
        self.pushed.append(surface)
        if isinstance(surface, ModalSurface):
            self.modal_active = True


def _quiet_controls() -> MagicMock:
    controls = MagicMock()
    controls.window = WindowControls()
    controls.navigator.history_targets.return_value = (None, None)
    controls.tap_sync.showing_progress = False
    controls.av_sync.flash_level.return_value = 0.0
    controls.project_switch.active = False
    controls.notification_active.return_value = PanelNotificationActive(
        persistent_message=None,
        persistent_elapsed_sec=0.0,
        message=None,
        remaining_sec=0.0,
        elapsed_sec=0.0,
    )
    return controls


def _loop_with_fake_shell(rt: MagicMock) -> tuple[LiveFrameLoop, SimpleNamespace]:
    shell = SimpleNamespace(
        top_layer=_FakeTopLayer(), transport_notice_clicked=True, layout=None
    )
    with (
        patch("cleave.viz.live_frame_loop.build_shell", return_value=shell),
        patch("cleave.viz.live_frame_loop.pygame"),
    ):
        loop = LiveFrameLoop(rt, MagicMock(), MagicMock())
    return loop, shell


@patch("cleave.viz.live_frame_loop.current_sec", return_value=12.0)
@patch("cleave.viz.live_frame_loop.draw_shell_frame")
def test_draw_ui_pushes_an_active_modal_and_keeps_its_toast(
    draw_shell_frame: MagicMock, _current_sec: MagicMock
) -> None:
    rt = MagicMock()
    rt.controls = _quiet_controls()
    rt.modal_host = ModalHost()
    rt.seed.signals = None
    rt.seed.duration_sec = 120.0
    rt.modal_host.prompt_confirm("Discard changes?", "Discard", lambda: None)
    loop, shell = _loop_with_fake_shell(rt)
    assert rt.shell_host is shell

    loop.draw_ui()

    assert [type(s) for s in shell.top_layer.pushed] == [ModalSurface]
    draw_shell_frame.assert_called_once()
    readout = draw_shell_frame.call_args.args[4]
    assert readout.position_sec == 12.0
    # The modal owns the click, so a click on the toast does not dismiss it.
    rt.controls.dismiss_notification.assert_not_called()
    assert rt.modal_host.active


@patch("cleave.viz.live_frame_loop.draw_shell_frame")
def test_draw_ui_while_playing_full_screen_draws_only_the_play_frame(
    draw_shell_frame: MagicMock,
) -> None:
    rt = MagicMock()
    rt.controls = _quiet_controls()
    rt.controls.window.play_fullscreen = True
    rt.modal_host = ModalHost()
    loop, shell = _loop_with_fake_shell(rt)
    shell.draw_play_frame = MagicMock()

    loop.draw_ui()

    shell.draw_play_frame.assert_called_once()
    draw_shell_frame.assert_not_called()
    assert shell.top_layer.pushed == []
