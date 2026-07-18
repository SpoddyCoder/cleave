"""Tap-to-sync calibration orchestration for latency compensation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from cleave.config import CleaveConfig
from cleave.config_schema import clamp_residual_latency_ms
from cleave.user_config import persist_editor_settings
from cleave.viz.focus_nav import FocusCursor
from cleave.viz.modal import ModalHost
from cleave.viz.playback import PlaybackState, toggle_pause
from cleave.viz.tap_sync import (
    accept_tap_for_accent,
    append_streak_delta,
    build_metronome_schedule,
    delta_spread_sec,
    mean_latency_from_deltas,
    metronome_accent_times,
    streak_ready_to_lock,
)
from cleave.viz.transport_clock import MAX_RESIDUAL_LATENCY_SEC

_TAP_SYNC_CONFIRM_MESSAGE = (
    "Measure Latency: "
    "A 140 BPM click track will play. "
    "Tap Space on each bar beat (beat 1) until the latency is detected."
)


@dataclass(frozen=True)
class TapSyncUiSnapshot:
    help_visible: bool
    timeline_panel_open: bool
    focus_cursor: FocusCursor
    overlay_visible: bool


@dataclass(frozen=True)
class TapSyncProgressView:
    streak: int
    spread_ms: int | None
    estimate_ms: int | None


class TapSyncControls:
    """Thin controller for measure-latency calibration."""

    def __init__(
        self,
        cfg: CleaveConfig,
        playback: PlaybackState,
        duration_sec: float,
        modal_host: ModalHost,
        *,
        on_notification: Callable[[str], None],
        on_apply_residual_latency: Callable[[], None],
        on_calibration_ui_begin: Callable[[], TapSyncUiSnapshot],
        on_calibration_ui_restore: Callable[[TapSyncUiSnapshot], None],
    ) -> None:
        self.cfg = cfg
        self.playback = playback
        self.duration_sec = duration_sec
        self._modal_host = modal_host
        self._on_notification = on_notification
        self._on_apply_residual_latency = on_apply_residual_latency
        self._on_calibration_ui_begin = on_calibration_ui_begin
        self._on_calibration_ui_restore = on_calibration_ui_restore
        self._active = False
        self._awaiting_confirm = False
        self._taps: list[float] = []
        self._streak_deltas: list[float] = []
        self._last_accent_index: int | None = None
        self._metronome_accent_times: tuple[float, ...] = ()
        self._ui_snapshot: TapSyncUiSnapshot | None = None

    @property
    def active(self) -> bool:
        return self._active

    @property
    def awaiting_apply(self) -> bool:
        return self._awaiting_confirm

    @property
    def showing_progress(self) -> bool:
        return self._active and not self._awaiting_confirm

    def progress_view(self) -> TapSyncProgressView | None:
        if not self.showing_progress:
            return None
        spread_sec = delta_spread_sec(self._streak_deltas)
        spread_ms = (
            None if spread_sec is None else int(round(spread_sec * 1000.0))
        )
        estimate_ms = None
        if self._streak_deltas:
            estimate_sec = mean_latency_from_deltas(self._streak_deltas)
            estimate_ms = int(round(estimate_sec * 1000.0))
        return TapSyncProgressView(
            streak=len(self._streak_deltas),
            spread_ms=spread_ms,
            estimate_ms=estimate_ms,
        )

    def _pause_transport(self) -> None:
        if not self.playback.paused:
            toggle_pause(self.playback, self.duration_sec)

    def _run_click_device_while_transport_paused(self) -> None:
        """Run SDL audio for metronome clicks while transport stays paused."""
        self.playback.player.pause(False)

    def _stop_click_device_leave_transport_paused(self) -> None:
        self.playback.paused = True
        self.playback.player.pause(True)

    def prompt_start(self) -> None:
        self._pause_transport()
        self._modal_host.prompt_yes_no(
            _TAP_SYNC_CONFIRM_MESSAGE,
            on_confirm=self._begin_calibration,
            cancel_label="Cancel",
        )

    def _begin_calibration(self) -> None:
        self._pause_transport()
        self._ui_snapshot = self._on_calibration_ui_begin()
        start_sec = self.playback.player.file_position_sec()
        schedule = build_metronome_schedule(start_sec, self.duration_sec)
        self._metronome_accent_times = metronome_accent_times(schedule)
        click_schedule = tuple(
            (click.time_sec, click.accented) for click in schedule
        )
        self._active = True
        self._awaiting_confirm = False
        self._taps.clear()
        self._streak_deltas.clear()
        self._last_accent_index = None
        self.playback.player.set_click_only(True)
        self.playback.player.set_click_schedule(click_schedule)
        self._run_click_device_while_transport_paused()

    def cancel(self) -> None:
        if not self._active:
            return
        self._restore_calibration_ui()
        self._finish_calibration()

    def _restore_calibration_ui(self) -> None:
        snapshot = self._ui_snapshot
        self._ui_snapshot = None
        if snapshot is not None:
            self._on_calibration_ui_restore(snapshot)

    def _finish_calibration(self) -> None:
        self._active = False
        self._awaiting_confirm = False
        self._taps.clear()
        self._streak_deltas.clear()
        self._last_accent_index = None
        self._metronome_accent_times = ()
        self.playback.player.set_click_schedule(None)
        self.playback.player.set_click_only(False)
        self._stop_click_device_leave_transport_paused()

    def record_tap(self) -> None:
        if not self._active or self._awaiting_confirm:
            return
        tap = self.playback.player.audible_position_zero_residual_latency_sec()
        accent_index, delta = accept_tap_for_accent(
            tap,
            self._metronome_accent_times,
            self._last_accent_index,
        )
        if accent_index is None or delta is None:
            return
        self._last_accent_index = accent_index
        self._taps.append(tap)
        self._streak_deltas = append_streak_delta(self._streak_deltas, delta)
        if streak_ready_to_lock(self._streak_deltas):
            self._prompt_apply_detected_latency()

    def _proposed_latency_sec(self) -> float:
        return max(
            0.0,
            min(mean_latency_from_deltas(self._streak_deltas), MAX_RESIDUAL_LATENCY_SEC),
        )

    def _prompt_apply_detected_latency(self) -> None:
        self.playback.player.set_click_schedule(None)
        self.playback.player.set_click_only(False)
        self._stop_click_device_leave_transport_paused()
        self._restore_calibration_ui()
        self._awaiting_confirm = True
        latency_ms = clamp_residual_latency_ms(
            int(round(self._proposed_latency_sec() * 1000.0))
        )
        self._modal_host.prompt_yes_no(
            f"Detected latency: {latency_ms} ms. Apply?",
            on_confirm=lambda: self._apply_detected_latency(latency_ms),
            on_cancel=self._dismiss_without_apply,
            cancel_label="Cancel",
        )

    def _apply_detected_latency(self, latency_ms: int) -> None:
        self.cfg.editor = replace(self.cfg.editor, residual_latency_ms=latency_ms)
        self._on_apply_residual_latency()
        persist_editor_settings(self.cfg)
        self._finish_calibration()
        self._on_notification(f"Latency compensation set to {latency_ms} ms")

    def _dismiss_without_apply(self) -> None:
        self._finish_calibration()

    def handle_keydown(self, event) -> bool:
        import pygame

        if self._awaiting_confirm:
            return False
        if event.key == pygame.K_ESCAPE:
            self.cancel()
            return True
        if event.key == pygame.K_SPACE:
            self.record_tap()
            return True
        return False
