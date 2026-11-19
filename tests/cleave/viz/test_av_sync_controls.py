"""Tests for Measure audio latency (flash and beep)."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pygame
import pytest

from cleave.viz.av_sync_controls import (
    FLASH_SEC,
    AvSyncControls,
    audio_latency_options_ms,
)
from cleave.viz.calibration_clicks import CalibrationClicks, CalibrationUiSnapshot
from cleave.viz.focus_nav import TimelineFocus
from cleave.viz.mix_player import FREQUENCY_HZ, NUM_CHANNELS, MixPlayer
from cleave.viz.modal import ModalHost
from cleave.viz.playback import PlaybackState
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.tap_sync import METRONOME_BEATS_PER_BAR, METRONOME_QUARTER_SEC
from tests.support.viz import keydown, make_test_cfg


def _make(
    *, audio_latency_ms: int = 0
) -> tuple[AvSyncControls, PlaybackState, ModalHost, list[str], list[str], list[int]]:
    modal = ModalHost()
    duration_sec = 14.0
    pcm = np.zeros(int(FREQUENCY_HZ * duration_sec) * NUM_CHANNELS, dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ)
    player.set_audio_latency_sec(audio_latency_ms / 1000.0)
    playback = PlaybackState(player=player, paused=True)
    notifications: list[str] = []
    ui_log: list[str] = []
    applied: list[int] = []

    def on_begin() -> CalibrationUiSnapshot:
        ui_log.append("hide")
        return CalibrationUiSnapshot(
            help_visible=False,
            timeline_panel_open=False,
            focus_cursor=TimelineFocus(0),
            shell_region=ShellRegion.NAVIGATOR,
        )

    clicks = CalibrationClicks(
        playback,
        duration_sec,
        on_ui_begin=on_begin,
        on_ui_restore=lambda _snapshot: ui_log.append("restore"),
    )
    cfg = make_test_cfg()
    cfg.editor = replace(cfg.editor, audio_latency_ms=audio_latency_ms)

    def apply(ms: int) -> None:
        applied.append(ms)
        cfg.editor = replace(cfg.editor, audio_latency_ms=ms)
        player.set_audio_latency_sec(ms / 1000.0)

    controls = AvSyncControls(
        cfg,
        clicks,
        modal,
        on_notification=notifications.append,
        on_preview_audio_latency=lambda ms: player.set_audio_latency_sec(ms / 1000.0),
        on_apply_audio_latency=apply,
    )
    return controls, playback, modal, notifications, ui_log, applied


def test_start_plays_one_beep_per_bar_with_transport_paused() -> None:
    controls, playback, modal, _notes, ui_log, _applied = _make()
    playback.paused = False

    controls.prompt_start()

    assert controls.active
    assert playback.paused
    assert not playback.player._clock.paused
    assert playback.player._click_only is True
    schedule = playback.player._click_schedule
    assert schedule is not None
    assert all(accented for _t, accented in schedule)
    bar_sec = METRONOME_QUARTER_SEC * METRONOME_BEATS_PER_BAR
    assert schedule[1][0] - schedule[0][0] == pytest.approx(bar_sec)
    view = modal.view_state()
    assert view is not None
    assert view.message == "Measure audio latency"
    assert view.form_rows[0].stepper is True
    assert ui_log == ["hide"]


def test_stepping_moves_the_live_latency_without_saving() -> None:
    controls, playback, modal, _notes, _ui_log, applied = _make(audio_latency_ms=40)
    controls.prompt_start()

    modal.handle_keydown(keydown(pygame.K_RIGHT))
    assert playback.player._clock.audio_latency_sec == pytest.approx(0.05)
    modal.handle_keydown(keydown(pygame.K_PAGEUP))
    assert playback.player._clock.audio_latency_sec == pytest.approx(0.10)
    assert applied == []
    assert controls.cfg.editor.audio_latency_ms == 40


def test_apply_saves_the_value_and_ends_the_test() -> None:
    controls, playback, modal, notes, ui_log, applied = _make(audio_latency_ms=40)
    controls.prompt_start()
    modal.handle_keydown(keydown(pygame.K_RIGHT))
    modal.handle_keydown(keydown(pygame.K_RETURN))

    assert applied == [50]
    assert notes == ["Audio latency set to 50 ms"]
    assert not controls.active
    assert playback.paused
    assert playback.player._clock.paused
    assert playback.player._click_only is False
    assert playback.player._click_schedule is None
    assert ui_log == ["hide", "restore"]


def test_cancel_restores_the_previous_latency() -> None:
    controls, playback, modal, notes, ui_log, applied = _make(audio_latency_ms=40)
    controls.prompt_start()
    modal.handle_keydown(keydown(pygame.K_PAGEUP))
    modal.handle_keydown(keydown(pygame.K_ESCAPE))

    assert applied == []
    assert notes == []
    assert playback.player._clock.audio_latency_sec == pytest.approx(0.04)
    assert not controls.active
    assert playback.player._click_schedule is None
    assert ui_log == ["hide", "restore"]


def test_flash_follows_the_audible_beep() -> None:
    controls, playback, _modal, _notes, _ui_log, _applied = _make()
    playback.player.seek(1.0)
    controls.prompt_start()
    beat = playback.player._click_schedule[0][0]

    playback.player.seek(beat - 0.01)
    playback.player.pause(True)
    assert controls.flash_level() == 0.0
    playback.player.seek(beat + FLASH_SEC / 2)
    assert controls.flash_level() == 1.0
    playback.player.seek(beat + FLASH_SEC + 0.01)
    assert controls.flash_level() == 0.0


def test_audio_latency_delays_the_flash() -> None:
    controls, playback, _modal, _notes, _ui_log, _applied = _make()
    playback.player.seek(1.0)
    controls.prompt_start()
    beat = playback.player._click_schedule[0][0]
    playback.player.pause(True)
    playback.player.set_audio_latency_sec(0.2)

    playback.player.seek(beat + FLASH_SEC / 2)
    assert controls.flash_level() == 0.0
    playback.player.seek(beat + 0.2 + FLASH_SEC / 2)
    assert controls.flash_level() == 1.0


def test_no_flash_when_inactive() -> None:
    controls, _playback, _modal, _notes, _ui_log, _applied = _make()
    assert controls.flash_level() == 0.0


def test_options_keep_the_current_value() -> None:
    options = audio_latency_options_ms(45)
    assert options[:2] == (0, 10)
    assert 45 in options
    assert audio_latency_options_ms(50).count(50) == 1
