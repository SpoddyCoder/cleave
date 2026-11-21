"""The first-run latency setup prompt and the calibrations it chains."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from unittest.mock import MagicMock, patch

import pygame
import pytest

from cleave.config_schema.first_run import FirstRunState
from cleave.viz.latency_setup_controls import (
    AUDIO_FIELD_ID,
    LATENCY_SETUP_TITLE,
    TAP_FIELD_ID,
    LatencySetupFlow,
)
from cleave.viz.modal import ModalHost
from tests.support.viz import keydown


@pytest.fixture(autouse=True)
def persist() -> Iterator[MagicMock]:
    with (
        patch(
            "cleave.viz.latency_setup_controls.saved_first_run_state",
            return_value=FirstRunState(welcome_done=True),
        ),
        patch("cleave.viz.latency_setup_controls.persist_first_run_state") as mock,
    ):
        yield mock


class _Calibrations:
    """Fake calibrations that log their start and close when told.

    ``log`` also records when playback is held and resumed.
    """

    def __init__(self) -> None:
        self.log: list[str] = []
        self.pending: list[Callable[[], None]] = []

    def hold_playback(self) -> Callable[[], None]:
        self.log.append("pause")
        return lambda: self.log.append("resume")

    def starter(self, name: str) -> Callable[[Callable[[], None]], None]:
        def start(done: Callable[[], None]) -> None:
            self.log.append(name)
            self.pending.append(done)

        return start

    def close_current(self) -> None:
        self.pending.pop(0)()


def _make(
    *, busy: bool = False
) -> tuple[LatencySetupFlow, ModalHost, _Calibrations, list[bool]]:
    host = ModalHost()
    calibrations = _Calibrations()
    busy_flag = [busy]
    flow = LatencySetupFlow(
        host,
        measure_audio_latency=calibrations.starter("audio"),
        calibrate_tap_timing=calibrations.starter("tap"),
        busy=lambda: busy_flag[0],
        hold_playback=calibrations.hold_playback,
    )
    return flow, host, calibrations, busy_flag


def _open(flow: LatencySetupFlow, host: ModalHost, cal: _Calibrations) -> None:
    flow.request()
    flow.tick()
    view = host.view_state()
    assert view is not None
    assert view.message == LATENCY_SETUP_TITLE
    cal.log.clear()


def test_prompt_offers_both_calibrations_switched_on() -> None:
    flow, host, cal, _busy = _make()
    _open(flow, host, cal)

    view = host.view_state()
    assert view is not None
    assert view.options == ("OK", "Cancel")
    assert host._form_state is not None
    assert host._form_state.values == {AUDIO_FIELD_ID: 1, TAP_FIELD_ID: 1}
    assert not flow.pending


def test_request_pauses_playback_before_the_prompt_opens() -> None:
    flow, host, cal, _busy = _make(busy=True)

    flow.request()
    flow.request()

    assert cal.log == ["pause"]
    assert flow.active
    assert host.view_state() is None


def test_waits_for_an_open_dialog_or_calibration() -> None:
    flow, host, _cal, busy = _make(busy=True)
    flow.request()
    flow.tick()
    assert host.view_state() is None
    assert flow.pending

    busy[0] = False
    host.prompt_notice("Something else")
    flow.tick()
    assert host.view_state().message == "Something else"

    host.dismiss()
    flow.tick()
    assert host.view_state().message == LATENCY_SETUP_TITLE


def test_cancel_marks_done_and_runs_nothing(persist: MagicMock) -> None:
    flow, host, cal, _busy = _make()
    _open(flow, host, cal)

    host.handle_keydown(keydown(pygame.K_ESCAPE))

    assert cal.log == ["resume"]
    assert not flow.active
    assert host.view_state() is None
    state = persist.call_args.args[0]
    assert state == FirstRunState(welcome_done=True, latency_setup_done=True)


def test_ok_runs_audio_then_tap_one_after_the_other(persist: MagicMock) -> None:
    flow, host, cal, _busy = _make()
    _open(flow, host, cal)

    host.activate_option(0)

    assert persist.call_args.args[0].latency_setup_done is True
    assert cal.log == ["audio"]
    cal.close_current()
    assert cal.log == ["audio", "tap"]
    assert flow.active
    cal.close_current()
    assert cal.log == ["audio", "tap", "resume"]
    assert cal.pending == []
    assert not flow.active


@pytest.mark.parametrize(
    ("audio", "tap", "expected"),
    [
        (1, 0, ["audio", "resume"]),
        (0, 1, ["tap", "resume"]),
        (0, 0, ["resume"]),
    ],
)
def test_ok_runs_only_the_chosen_calibrations(
    audio: int, tap: int, expected: list[str]
) -> None:
    flow, host, cal, _busy = _make()
    _open(flow, host, cal)
    host.set_form_value(0, audio)
    host.set_form_value(1, tap)

    host.activate_option(0)
    while cal.pending:
        cal.close_current()

    assert cal.log == expected
