"""Tests for tap-to-sync controller orchestration."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from cleave.viz.focus_nav import MainFocus, TimelineFocus
from cleave.viz.modal import ModalHost
from cleave.viz.mix_player import FREQUENCY_HZ, NUM_CHANNELS, MixPlayer
from cleave.viz.playback import PlaybackState
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.tap_sync import CONSISTENCY_WINDOW, METRONOME_BPM, metronome_accent_times
from cleave.viz.tap_sync_controls import (
    TapSyncControls,
    TapSyncProgressView,
    TapSyncUiSnapshot,
    _TAP_SYNC_CONFIRM_MESSAGE,
)
from tests.support.viz import make_test_cfg
from tests.support.viz import keydown


def _make_controls(
    *,
    duration_sec: float = 8.0,
    modal: ModalHost | None = None,
    ui_events: list[str] | None = None,
) -> tuple[TapSyncControls, PlaybackState, ModalHost, list[str], list[str]]:
    modal_host = modal if modal is not None else ModalHost()
    frame_count = int(FREQUENCY_HZ * duration_sec)
    pcm = np.zeros(frame_count * NUM_CHANNELS, dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ)
    playback = PlaybackState(player=player, paused=True)
    notifications: list[str] = []
    ui_log = ui_events if ui_events is not None else []
    snapshot_store: list[TapSyncUiSnapshot] = []

    def on_begin() -> TapSyncUiSnapshot:
        ui_log.append("hide")
        snapshot = TapSyncUiSnapshot(
            help_visible=True,
            timeline_panel_open=True,
            focus_cursor=TimelineFocus(1),
            overlay_visible=True,
        )
        snapshot_store.append(snapshot)
        return snapshot

    def on_restore(snapshot: TapSyncUiSnapshot) -> None:
        ui_log.append("restore")
        assert snapshot == snapshot_store[-1]

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
        on_calibration_ui_begin=on_begin,
        on_calibration_ui_restore=on_restore,
    )
    return controls, playback, modal_host, notifications, ui_log


def _start_calibration(
    controls: TapSyncControls,
    modal: ModalHost,
    ui_log: list[str],
) -> tuple[float, ...]:
    controls.prompt_start()
    modal.handle_keydown(keydown(pygame.K_RETURN))
    assert ui_log == ["hide"]
    return controls._metronome_accent_times


def _tap_on_accents(
    controls: TapSyncControls,
    playback: PlaybackState,
    accent_times: tuple[float, ...],
    *,
    delay_sec: float,
    count: int,
) -> None:
    for accent_time in accent_times[:count]:
        playback.player.seek(accent_time + delay_sec)
        controls.record_tap()


def test_prompt_start_pauses_playback_when_playing() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls()
    playback.paused = False

    controls.prompt_start()

    assert playback.paused
    assert modal.view_state() is not None
    assert ui_log == []


def test_prompt_start_leaves_paused_when_already_paused() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls()
    assert playback.paused

    controls.prompt_start()

    assert playback.paused
    assert modal.view_state() is not None


def test_confirm_modal_cancel_leaves_transport_paused() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls()
    playback.paused = False

    controls.prompt_start()
    modal.handle_keydown(keydown(pygame.K_LEFT))
    modal.handle_keydown(keydown(pygame.K_RETURN))

    assert playback.paused
    assert not controls.active
    assert ui_log == []


def test_prompt_start_opens_confirm_modal_without_signals() -> None:
    controls, _playback, modal, _notifications, ui_log = _make_controls()

    controls.prompt_start()

    view = modal.view_state()
    assert view is not None
    assert view.message == _TAP_SYNC_CONFIRM_MESSAGE
    assert view.options == ("Yes", "Cancel")
    assert not controls.active
    assert ui_log == []


def test_confirm_starts_click_only_metronome_calibration() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls(duration_sec=4.0)

    accent_times = _start_calibration(controls, modal, ui_log)

    schedule = playback.player._click_schedule
    assert schedule is not None
    assert controls.active
    assert controls.showing_progress
    assert controls.progress_view() is not None
    assert playback.paused
    assert not playback.player._clock.paused
    assert playback.player._click_only is True
    assert accent_times == tuple(time_sec for time_sec, accented in schedule if accented)
    quarter = 60.0 / METRONOME_BPM
    for index, (time_sec, accented) in enumerate(schedule):
        assert accented == (index % 4 == 0)
        if index > 0:
            assert time_sec - schedule[index - 1][0] == pytest.approx(quarter)


def test_cancel_restores_normal_playback_and_ui() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls()

    _start_calibration(controls, modal, ui_log)
    controls.cancel()

    assert not controls.active
    assert playback.paused
    assert playback.player._clock.paused
    assert playback.player._click_only is False
    assert playback.player._click_schedule is None
    assert ui_log == ["hide", "restore"]


def test_consistent_taps_open_apply_modal_with_mean_delay() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls(duration_sec=8.0)
    playback.player.seek(0.0)
    delay_sec = 0.2

    accent_times = _start_calibration(controls, modal, ui_log)
    _tap_on_accents(
        controls,
        playback,
        accent_times,
        delay_sec=delay_sec,
        count=4,
    )

    view = modal.view_state()
    assert view is not None
    assert view.message == "Detected wireless delay: 200 ms. Apply?"
    assert controls.active
    assert controls.awaiting_apply
    assert not controls.showing_progress
    assert playback.player._click_schedule is None
    assert playback.player._click_only is False
    assert playback.paused
    assert playback.player._clock.paused
    assert ui_log == ["hide", "restore"]


def test_inconsistent_taps_do_not_lock_in() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls(duration_sec=8.0)
    playback.player.seek(0.0)

    accent_times = _start_calibration(controls, modal, ui_log)
    delays = (0.10, 0.20, 0.30, 0.40)
    for accent_time, delay_sec in zip(accent_times[:4], delays, strict=True):
        playback.player.seek(accent_time + delay_sec)
        controls.record_tap()

    assert modal.view_state() is None
    assert controls.active
    assert not controls.awaiting_apply
    assert playback.player._click_schedule is not None
    assert ui_log == ["hide"]


def test_double_tap_same_accent_is_ignored() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls(duration_sec=8.0)
    playback.player.seek(0.0)

    accent_times = _start_calibration(controls, modal, ui_log)
    playback.player.seek(accent_times[0] + 0.2)
    controls.record_tap()
    controls.record_tap()
    for accent_time in accent_times[1:4]:
        playback.player.seek(accent_time + 0.2)
        controls.record_tap()

    assert len(controls._streak_deltas) == 4
    assert len(controls._taps) == 4
    view = modal.view_state()
    assert view is not None
    assert view.message == "Detected wireless delay: 200 ms. Apply?"
    assert ui_log == ["hide", "restore"]


def test_quiet_quarter_tap_is_ignored() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls(duration_sec=8.0)
    playback.player.seek(0.0)

    accent_times = _start_calibration(controls, modal, ui_log)
    playback.player.seek(accent_times[0] + 0.2)
    controls.record_tap()
    playback.player.seek(accent_times[0] + 0.7)
    controls.record_tap()

    assert len(controls._streak_deltas) == 1
    assert controls.progress_view() == TapSyncProgressView(
        streak=1,
        spread_ms=None,
        estimate_ms=200,
    )


def test_apply_modal_yes_sets_residual_delay_and_leaves_transport_paused() -> None:
    controls, playback, modal, notifications, ui_log = _make_controls(duration_sec=8.0)
    playback.player.seek(0.0)

    accent_times = _start_calibration(controls, modal, ui_log)
    _tap_on_accents(
        controls,
        playback,
        accent_times,
        delay_sec=0.2,
        count=4,
    )
    modal.handle_keydown(keydown(pygame.K_RETURN))

    assert not controls.active
    assert playback.paused
    assert playback.player._clock.paused
    assert playback.player._click_only is False
    assert controls.cfg.editor.residual_delay_ms == pytest.approx(200, abs=1)
    assert any("Wireless delay set" in msg for msg in notifications)


def test_apply_modal_cancel_exits_without_applying() -> None:
    controls, playback, modal, notifications, ui_log = _make_controls(duration_sec=8.0)
    original_delay = controls.cfg.editor.residual_delay_ms
    playback.player.seek(0.0)

    accent_times = _start_calibration(controls, modal, ui_log)
    _tap_on_accents(
        controls,
        playback,
        accent_times,
        delay_sec=0.2,
        count=4,
    )
    modal.handle_keydown(keydown(pygame.K_LEFT))
    modal.handle_keydown(keydown(pygame.K_RETURN))

    assert not controls.active
    assert playback.paused
    assert playback.player._clock.paused
    assert playback.player._click_only is False
    assert controls.cfg.editor.residual_delay_ms == original_delay
    assert not any("Wireless delay set" in msg for msg in notifications)


def test_progress_view_updates_with_streak() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls(duration_sec=8.0)
    playback.player.seek(0.0)

    accent_times = _start_calibration(controls, modal, ui_log)
    assert controls.progress_view() == TapSyncProgressView(
        streak=0,
        spread_ms=None,
        estimate_ms=None,
    )

    playback.player.seek(accent_times[0] + 0.2)
    controls.record_tap()
    assert controls.progress_view() == TapSyncProgressView(
        streak=1,
        spread_ms=None,
        estimate_ms=200,
    )

    for accent_time in accent_times[1:3]:
        playback.player.seek(accent_time + 0.2)
        controls.record_tap()

    assert controls.progress_view() == TapSyncProgressView(
        streak=3,
        spread_ms=0,
        estimate_ms=200,
    )


def test_progress_view_shows_spread_with_two_or_more_deltas() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls(duration_sec=8.0)
    _start_calibration(controls, modal, ui_log)
    controls._streak_deltas = [0.20, 0.21]
    assert controls.progress_view() == TapSyncProgressView(
        streak=2,
        spread_ms=10,
        estimate_ms=205,
    )


def test_progress_view_shows_spread_when_streak_buffer_full() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls(duration_sec=8.0)
    _start_calibration(controls, modal, ui_log)
    controls._streak_deltas = [0.20, 0.21, 0.19, 0.20]
    assert controls.progress_view() == TapSyncProgressView(
        streak=4,
        spread_ms=20,
        estimate_ms=200,
    )


def test_wide_spread_resets_streak_before_lock() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls(duration_sec=8.0)
    playback.player.seek(0.0)
    accent_times = _start_calibration(controls, modal, ui_log)
    delays = (0.18, 0.20, 0.22, 0.24)
    for accent_time, delay_sec in zip(accent_times[:4], delays, strict=True):
        playback.player.seek(accent_time + delay_sec)
        controls.record_tap()

    assert controls.progress_view() == TapSyncProgressView(
        streak=2,
        spread_ms=20,
        estimate_ms=230,
    )
    assert modal.view_state() is None


def test_streak_resets_after_inconsistent_tap() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls(duration_sec=8.0)
    playback.player.seek(0.0)
    accent_times = _start_calibration(controls, modal, ui_log)

    for accent_time in accent_times[:2]:
        playback.player.seek(accent_time + 0.2)
        controls.record_tap()
    assert controls.progress_view() == TapSyncProgressView(
        streak=2,
        spread_ms=0,
        estimate_ms=200,
    )

    playback.player.seek(accent_times[2] + 0.5)
    controls.record_tap()
    assert controls.progress_view() == TapSyncProgressView(
        streak=1,
        spread_ms=None,
        estimate_ms=500,
    )


def test_tuning_controls_begin_and_restore_ui_snapshot() -> None:
    from tests.support.viz import make_controls

    controls = make_controls()
    controls.bind_tap_sync_overlay(
        get_visible=lambda: True,
        hide=lambda: None,
        show=lambda: None,
    )
    session = controls.session
    session.help_visible = True
    session.timeline.panel_open = True
    controls.focus_cursor = TimelineFocus(0)

    snapshot = controls._begin_tap_sync_calibration_ui()

    assert snapshot.help_visible is True
    assert snapshot.timeline_panel_open is True
    assert isinstance(snapshot.focus_cursor, TimelineFocus)
    assert session.help_visible is False
    assert session.timeline.panel_open is False
    assert isinstance(controls.focus_cursor, MainFocus)
    assert controls.focus_cursor.descriptor.kind == RowKind.RENDER_TIMELINE_HEADER

    controls._restore_tap_sync_calibration_ui(snapshot)

    assert session.help_visible is True
    assert session.timeline.panel_open is True
    assert isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.focus_cursor.row == 0


def test_accent_times_from_schedule_match_calibration() -> None:
    from cleave.viz.tap_sync import build_metronome_schedule

    schedule = build_metronome_schedule(0.0, 8.0)
    bar_sec = 4.0 * 60.0 / METRONOME_BPM
    expected = tuple(click.time_sec for click in schedule if click.accented)
    assert metronome_accent_times(schedule) == pytest.approx(expected)
    assert expected[1] - expected[0] == pytest.approx(bar_sec)
    assert CONSISTENCY_WINDOW == 4
