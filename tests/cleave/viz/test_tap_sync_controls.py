"""Tests for Calibrate tap timing orchestration."""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from cleave.viz.focus_nav import MainFocus, TimelineFocus
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.modal import ModalHost
from cleave.viz.mix_player import FREQUENCY_HZ, NUM_CHANNELS, MixPlayer
from cleave.viz.playback import PlaybackState
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.tap_sync import (
    MIN_KEPT_TAPS,
    METRONOME_BPM,
    TAP_HISTORY,
    metronome_accent_times,
)
from dataclasses import replace

from cleave.config_schema.editor import MAX_TAP_LATENCY_MS, MIN_TAP_LATENCY_MS
from cleave.viz.calibration_clicks import CalibrationClicks, CalibrationUiSnapshot
from cleave.viz.tap_sync_controls import (
    TapSyncControls,
    TapSyncProgressView,
    latency_options_ms,
    tap_sync_info_panel,
    _TAP_SYNC_CONFIRM_BODY,
    _TAP_SYNC_CONFIRM_TITLE,
)
from tests.support.viz import make_test_cfg
from tests.support.viz import keydown


def _make_controls(
    *,
    duration_sec: float = 14.0,
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
    snapshot_store: list[CalibrationUiSnapshot] = []

    def on_begin() -> CalibrationUiSnapshot:
        ui_log.append("hide")
        snapshot = CalibrationUiSnapshot(
            help_visible=True,
            timeline_panel_open=True,
            focus_cursor=TimelineFocus(1),
            shell_region=ShellRegion.NAVIGATOR,
        )
        snapshot_store.append(snapshot)
        return snapshot

    def on_restore(snapshot: CalibrationUiSnapshot) -> None:
        ui_log.append("restore")
        assert snapshot == snapshot_store[-1]

    cfg = make_test_cfg()
    clicks = CalibrationClicks(
        playback,
        duration_sec,
        on_ui_begin=on_begin,
        on_ui_restore=on_restore,
    )

    def apply_tap_latency(ms: int) -> None:
        cfg.editor = replace(cfg.editor, tap_latency_ms=ms)
        player.set_tap_latency_sec(ms / 1000.0)

    controls = TapSyncControls(
        cfg,
        clicks,
        modal_host,
        on_notification=notifications.append,
        on_apply_tap_latency=apply_tap_latency,
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
    latency_sec: float,
    count: int,
) -> None:
    for accent_time in accent_times[:count]:
        playback.player.seek(accent_time + latency_sec)
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
    assert view.message == _TAP_SYNC_CONFIRM_TITLE
    assert view.body == _TAP_SYNC_CONFIRM_BODY
    assert view.options == ("Start", "Cancel")
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


def test_consistent_taps_open_apply_modal_with_mean_latency() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls()
    playback.player.seek(0.0)
    latency_sec = 0.2

    accent_times = _start_calibration(controls, modal, ui_log)
    _tap_on_accents(
        controls,
        playback,
        accent_times,
        latency_sec=latency_sec,
        count=MIN_KEPT_TAPS,
    )

    view = modal.view_state()
    assert view is not None
    assert view.message == "Detected tap latency"
    assert view.form_rows[0].options[view.form_rows[0].value] == "+200 ms"
    assert controls.active
    assert controls.awaiting_apply
    assert not controls.showing_progress
    assert playback.player._click_schedule is None
    assert playback.player._click_only is False
    assert playback.paused
    assert playback.player._clock.paused
    assert ui_log == ["hide", "restore"]


def test_inconsistent_taps_do_not_lock_in() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls()
    playback.player.seek(0.0)

    accent_times = _start_calibration(controls, modal, ui_log)
    latencies = (0.10, 0.20, 0.30, 0.40, 0.50, 0.60)
    for accent_time, latency_sec in zip(
        accent_times[:MIN_KEPT_TAPS], latencies, strict=True
    ):
        playback.player.seek(accent_time + latency_sec)
        controls.record_tap()

    assert modal.view_state() is None
    assert controls.active
    assert not controls.awaiting_apply
    assert playback.player._click_schedule is not None
    assert ui_log == ["hide"]


def test_double_tap_same_accent_is_ignored() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls()
    playback.player.seek(0.0)

    accent_times = _start_calibration(controls, modal, ui_log)
    playback.player.seek(accent_times[0] + 0.2)
    controls.record_tap()
    controls.record_tap()
    for accent_time in accent_times[1:MIN_KEPT_TAPS]:
        playback.player.seek(accent_time + 0.2)
        controls.record_tap()

    assert len(controls._tap_deltas) == MIN_KEPT_TAPS
    view = modal.view_state()
    assert view is not None
    assert view.message == "Detected tap latency"
    assert view.form_rows[0].options[view.form_rows[0].value] == "+200 ms"
    assert ui_log == ["hide", "restore"]


def test_quiet_quarter_tap_is_ignored() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls()
    playback.player.seek(0.0)

    accent_times = _start_calibration(controls, modal, ui_log)
    playback.player.seek(accent_times[0] + 0.2)
    controls.record_tap()
    playback.player.seek(accent_times[0] + 0.7)
    controls.record_tap()

    assert len(controls._tap_deltas) == 1
    assert controls.progress_view() == TapSyncProgressView(
        kept=1,
        margin_ms=None,
        estimate_ms=200,
    )


def test_apply_modal_yes_sets_tap_latency_and_leaves_transport_paused() -> None:
    controls, playback, modal, notifications, ui_log = _make_controls()
    playback.player.seek(0.0)

    accent_times = _start_calibration(controls, modal, ui_log)
    _tap_on_accents(
        controls,
        playback,
        accent_times,
        latency_sec=0.2,
        count=MIN_KEPT_TAPS,
    )
    modal.handle_keydown(keydown(pygame.K_RETURN))

    assert not controls.active
    assert playback.paused
    assert playback.player._clock.paused
    assert playback.player._click_only is False
    assert controls.cfg.editor.tap_latency_ms == pytest.approx(200, abs=1)
    assert playback.player._clock.tap_latency_sec == pytest.approx(0.2, abs=0.001)
    assert any("Tap latency set to +200 ms" in msg for msg in notifications)


def test_apply_modal_cancel_exits_without_applying() -> None:
    controls, playback, modal, notifications, ui_log = _make_controls()
    original_latency = controls.cfg.editor.tap_latency_ms
    playback.player.seek(0.0)

    accent_times = _start_calibration(controls, modal, ui_log)
    _tap_on_accents(
        controls,
        playback,
        accent_times,
        latency_sec=0.2,
        count=MIN_KEPT_TAPS,
    )
    modal.handle_keydown(keydown(pygame.K_ESCAPE))

    assert not controls.active
    assert playback.paused
    assert playback.player._clock.paused
    assert playback.player._click_only is False
    assert controls.cfg.editor.tap_latency_ms == original_latency
    assert not any("Tap latency set" in msg for msg in notifications)


def test_progress_view_counts_kept_taps_and_margin() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls()
    playback.player.seek(0.0)
    accent_times = _start_calibration(controls, modal, ui_log)
    assert controls.progress_view() == TapSyncProgressView(
        kept=0, margin_ms=None, estimate_ms=None
    )

    playback.player.seek(accent_times[0] + 0.2)
    controls.record_tap()
    assert controls.progress_view() == TapSyncProgressView(
        kept=1, margin_ms=None, estimate_ms=200
    )

    controls._tap_deltas = [0.18, 0.22]
    assert controls.progress_view() == TapSyncProgressView(
        kept=2, margin_ms=20, estimate_ms=200
    )


def test_a_stray_tap_does_not_reset_progress() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls()
    playback.player.seek(0.0)
    accent_times = _start_calibration(controls, modal, ui_log)
    offsets = (0.20, 0.20, 0.55, 0.20, 0.20, 0.20)
    for accent_time, offset in zip(accent_times[:6], offsets, strict=True):
        playback.player.seek(accent_time + offset)
        controls.record_tap()
    assert modal.view_state() is None
    assert controls.progress_view() == TapSyncProgressView(
        kept=5, margin_ms=0, estimate_ms=200
    )

    playback.player.seek(accent_times[6] + 0.2)
    controls.record_tap()
    view = modal.view_state()
    assert view is not None
    assert view.form_rows[0].options[view.form_rows[0].value] == "+200 ms"


def test_loose_taps_lock_once_the_estimate_settles() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls(
        duration_sec=40.0
    )
    playback.player.seek(0.0)
    accent_times = _start_calibration(controls, modal, ui_log)
    offsets = [0.18, 0.22] * (TAP_HISTORY // 2)
    taps = 0
    for accent_time, offset in zip(accent_times, offsets):
        playback.player.seek(accent_time + offset)
        controls.record_tap()
        taps += 1
        if controls.awaiting_apply:
            break
    assert controls.awaiting_apply
    assert MIN_KEPT_TAPS < taps < TAP_HISTORY
    view = modal.view_state()
    assert view.form_rows[0].options[view.form_rows[0].value] == "+200 ms"


def test_tuning_controls_begin_and_restore_ui_snapshot() -> None:
    from tests.support.viz import make_controls

    controls = make_controls()
    session = controls.session
    session.help_visible = True
    session.timeline.panel_open = True
    controls.focus_cursor = TimelineFocus(0)

    snapshot = controls._begin_calibration_ui()

    assert snapshot.help_visible is True
    assert snapshot.timeline_panel_open is True
    assert isinstance(snapshot.focus_cursor, TimelineFocus)
    assert session.help_visible is False
    assert session.timeline.panel_open is False
    assert isinstance(controls.focus_cursor, MainFocus)
    assert controls.focus_cursor.descriptor.kind == RowKind.TIMELINE_HEADER

    controls._restore_calibration_ui(snapshot)

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
    assert MIN_KEPT_TAPS == 6


def test_enter_records_tap_space_does_not() -> None:
    controls, playback, modal, _notifications, ui_log = _make_controls()
    accent_times = _start_calibration(controls, modal, ui_log)
    playback.player.seek(accent_times[0] + 0.2)

    assert controls.handle_keydown(keydown(pygame.K_SPACE)) is False
    assert controls.progress_view().kept == 0

    assert controls.handle_keydown(keydown(pygame.K_RETURN)) is True
    assert controls.progress_view().kept == 1
    assert "Enter" in _TAP_SYNC_CONFIRM_BODY


def test_tap_sync_info_panel_uses_dashes_when_estimate_and_spread_are_missing() -> None:
    panel = tap_sync_info_panel(
        TapSyncProgressView(kept=0, margin_ms=None, estimate_ms=None)
    )
    assert panel.title_lines == (
        "Detection in progress",
        "Tap Enter on the long low tone",
    )
    assert panel.body_lines == (
        f"Taps: 0 (needs {MIN_KEPT_TAPS})",
        "Settled to: -- (needs +/-7 ms)",
        "Estimate: --",
    )
    assert panel.footer_line == "Esc to cancel"


def test_tap_sync_info_panel_formats_populated_estimate_and_spread() -> None:
    panel = tap_sync_info_panel(
        TapSyncProgressView(kept=3, margin_ms=12, estimate_ms=205)
    )
    assert panel.body_lines == (
        f"Taps: 3 (needs {MIN_KEPT_TAPS})",
        "Settled to: +/-12 ms (needs +/-7 ms)",
        "Estimate: +205 ms",
    )


def test_apply_dialog_steps_from_the_measured_value_before_applying() -> None:
    controls, playback, modal, notifications, ui_log = _make_controls()
    playback.player.seek(0.0)
    accent_times = _start_calibration(controls, modal, ui_log)
    _tap_on_accents(controls, playback, accent_times, latency_sec=0.2, count=MIN_KEPT_TAPS)
    view = modal.view_state()
    assert view.form_rows[0].stepper is True
    assert view.form_info == "(now +0 ms)"
    modal.handle_keydown(keydown(pygame.K_RIGHT))
    modal.handle_keydown(keydown(pygame.K_PAGEDOWN))
    modal.handle_keydown(keydown(pygame.K_RETURN))
    assert controls.cfg.editor.tap_latency_ms == 160
    assert any("+160 ms" in msg for msg in notifications)


def test_taps_ahead_of_the_beat_propose_a_negative_latency() -> None:
    controls, playback, modal, notifications, ui_log = _make_controls()
    playback.player.seek(1.0)
    accent_times = _start_calibration(controls, modal, ui_log)
    _tap_on_accents(
        controls, playback, accent_times, latency_sec=-0.03, count=MIN_KEPT_TAPS
    )
    view = modal.view_state()
    assert view is not None
    assert view.form_rows[0].options[view.form_rows[0].value] == "-30 ms"
    modal.handle_keydown(keydown(pygame.K_RETURN))
    assert controls.cfg.editor.tap_latency_ms == -30
    assert any("-30 ms" in msg for msg in notifications)


def test_latency_options_step_by_ten_and_keep_the_measured_value() -> None:
    options = latency_options_ms(187)
    assert options[0] == MIN_TAP_LATENCY_MS
    assert options[:3] == (-250, -240, -230)
    assert options[options.index(187) - 1 : options.index(187) + 2] == (180, 187, 190)
    assert options[-1] == MAX_TAP_LATENCY_MS
    assert latency_options_ms(200).count(200) == 1
