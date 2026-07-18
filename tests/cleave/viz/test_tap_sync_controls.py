"""Tests for tap-to-sync controller orchestration."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from cleave.viz.modal import ModalHost
from cleave.viz.mix_player import FREQUENCY_HZ, MixPlayer
from cleave.viz.playback import PlaybackState
from cleave.viz.tap_sync_controls import TapSyncControls, _TAP_SYNC_CONFIRM_MESSAGE
from tests.support.viz import make_test_cfg
from tests.support.viz import keydown


def _make_controls(
    *,
    duration_sec: float = 8.0,
    modal: ModalHost | None = None,
) -> tuple[TapSyncControls, PlaybackState, ModalHost, list[str]]:
    modal_host = modal if modal is not None else ModalHost()
    pcm = np.zeros(int(FREQUENCY_HZ * duration_sec), dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ)
    playback = PlaybackState(player=player, paused=True)
    notifications: list[str] = []
    cfg = make_test_cfg()
    controls = TapSyncControls(
        cfg,
        playback,
        duration_sec=duration_sec,
        modal_host=modal_host,
        on_notification=notifications.append,
        on_apply_residual_delay=lambda: player.set_residual_delay_sec(
            cfg.editor.residual_delay_ms / 1000.0
        ),
    )
    return controls, playback, modal_host, notifications


def _start_calibration(
    controls: TapSyncControls,
    modal: ModalHost,
) -> tuple[float, ...]:
    controls.prompt_start()
    modal.handle_keydown(keydown(pygame.K_RETURN))
    return controls._metronome_click_times


def _tap_on_clicks(
    controls: TapSyncControls,
    playback: PlaybackState,
    click_times: tuple[float, ...],
    *,
    delay_sec: float,
    count: int,
) -> None:
    for click_time in click_times[:count]:
        playback.player.seek(click_time + delay_sec)
        controls.record_tap()


def test_prompt_start_opens_confirm_modal_without_signals() -> None:
    controls, _playback, modal, _notifications = _make_controls()

    controls.prompt_start()

    view = modal.view_state()
    assert view is not None
    assert view.message == _TAP_SYNC_CONFIRM_MESSAGE
    assert view.options == ("Yes", "Cancel")
    assert not controls.active


def test_confirm_starts_click_only_metronome_calibration() -> None:
    controls, playback, modal, _notifications = _make_controls(duration_sec=4.0)

    click_times = _start_calibration(controls, modal)

    schedule = playback.player._click_schedule
    assert schedule is not None
    assert controls.active
    assert not playback.paused
    assert playback.player._click_only is True
    assert click_times == tuple(time_sec for time_sec, _ in schedule)
    for index, (time_sec, accented) in enumerate(schedule):
        assert accented == (index % 4 == 0)
        if index > 0:
            assert time_sec - schedule[index - 1][0] == pytest.approx(0.5)


def test_cancel_restores_normal_playback() -> None:
    controls, playback, modal, _notifications = _make_controls()

    _start_calibration(controls, modal)
    controls.cancel()

    assert not controls.active
    assert playback.player._click_only is False
    assert playback.player._click_schedule is None


def test_consistent_taps_open_apply_modal_with_mean_delay() -> None:
    controls, playback, modal, _notifications = _make_controls(duration_sec=4.0)
    playback.player.seek(0.0)
    delay_sec = 0.2

    click_times = _start_calibration(controls, modal)
    _tap_on_clicks(
        controls,
        playback,
        click_times,
        delay_sec=delay_sec,
        count=4,
    )

    view = modal.view_state()
    assert view is not None
    assert view.message == "Detected wireless delay: 200 ms. Apply?"
    assert controls.active
    assert controls._awaiting_confirm
    assert playback.player._click_schedule is None
    assert playback.player._click_only is True
    assert playback.paused


def test_inconsistent_taps_do_not_lock_in() -> None:
    controls, playback, modal, _notifications = _make_controls(duration_sec=4.0)
    playback.player.seek(0.0)

    click_times = _start_calibration(controls, modal)
    delays = (0.10, 0.20, 0.30, 0.40)
    for click_time, delay_sec in zip(click_times[:4], delays, strict=True):
        playback.player.seek(click_time + delay_sec)
        controls.record_tap()

    assert modal.view_state() is None
    assert controls.active
    assert not controls._awaiting_confirm
    assert playback.player._click_schedule is not None


def test_double_tap_same_click_is_ignored() -> None:
    controls, playback, modal, _notifications = _make_controls(duration_sec=4.0)
    playback.player.seek(0.0)

    click_times = _start_calibration(controls, modal)
    playback.player.seek(click_times[0] + 0.2)
    controls.record_tap()
    controls.record_tap()
    playback.player.seek(click_times[1] + 0.2)
    controls.record_tap()
    playback.player.seek(click_times[2] + 0.2)
    controls.record_tap()
    playback.player.seek(click_times[3] + 0.2)
    controls.record_tap()

    assert len(controls._deltas) == 4
    assert len(controls._taps) == 4
    view = modal.view_state()
    assert view is not None
    assert view.message == "Detected wireless delay: 200 ms. Apply?"


def test_apply_modal_yes_sets_residual_delay_and_restores_playback() -> None:
    controls, playback, modal, notifications = _make_controls(duration_sec=4.0)
    playback.player.seek(0.0)

    click_times = _start_calibration(controls, modal)
    _tap_on_clicks(
        controls,
        playback,
        click_times,
        delay_sec=0.2,
        count=4,
    )
    modal.handle_keydown(keydown(pygame.K_RETURN))

    assert not controls.active
    assert playback.player._click_only is False
    assert controls.cfg.editor.residual_delay_ms == pytest.approx(200, abs=1)
    assert any("Wireless delay set" in msg for msg in notifications)


def test_apply_modal_cancel_exits_without_applying() -> None:
    controls, playback, modal, notifications = _make_controls(duration_sec=4.0)
    original_delay = controls.cfg.editor.residual_delay_ms
    playback.player.seek(0.0)

    click_times = _start_calibration(controls, modal)
    _tap_on_clicks(
        controls,
        playback,
        click_times,
        delay_sec=0.2,
        count=4,
    )
    modal.handle_keydown(keydown(pygame.K_LEFT))
    modal.handle_keydown(keydown(pygame.K_RETURN))

    assert not controls.active
    assert playback.player._click_only is False
    assert controls.cfg.editor.residual_delay_ms == original_delay
    assert not any("Wireless delay set" in msg for msg in notifications)
