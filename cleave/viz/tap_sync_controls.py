"""Tap-to-sync calibration orchestration for wireless delay."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from cleave.config import CleaveConfig
from cleave.config_schema import clamp_residual_delay_ms
from cleave.user_config import persist_editor_settings
from cleave.viz.modal import ModalHost
from cleave.viz.playback import PlaybackState, toggle_pause
from cleave.viz.tap_sync import (
    accept_tap_for_click,
    build_metronome_schedule,
    consecutive_deltas_consistent,
    mean_delay_from_deltas,
    metronome_click_times,
)
from cleave.viz.transport_clock import MAX_RESIDUAL_DELAY_SEC

_TAP_SYNC_CONFIRM_MESSAGE = (
    "Song and visuals pause for calibration. A 120 BPM click track plays: "
    "a loud click on beat 1 of each bar and quieter clicks on beats 2 to 4. "
    "Tap Space in time with each click until the delay is detected automatically. "
    "Esc cancels."
)


class TapSyncControls:
    """Thin controller for sync-by-ear calibration."""

    def __init__(
        self,
        cfg: CleaveConfig,
        playback: PlaybackState,
        duration_sec: float,
        modal_host: ModalHost,
        *,
        on_notification: Callable[[str], None],
        on_apply_residual_delay: Callable[[], None],
    ) -> None:
        self.cfg = cfg
        self.playback = playback
        self.duration_sec = duration_sec
        self._modal_host = modal_host
        self._on_notification = on_notification
        self._on_apply_residual_delay = on_apply_residual_delay
        self._active = False
        self._awaiting_confirm = False
        self._taps: list[float] = []
        self._deltas: list[float] = []
        self._last_click_index: int | None = None
        self._metronome_click_times: tuple[float, ...] = ()

    @property
    def active(self) -> bool:
        return self._active

    def prompt_start(self) -> None:
        self._modal_host.prompt_yes_no(
            _TAP_SYNC_CONFIRM_MESSAGE,
            on_confirm=self._begin_calibration,
            cancel_label="Cancel",
        )

    def _begin_calibration(self) -> None:
        start_sec = self.playback.player.file_position_sec()
        schedule = build_metronome_schedule(start_sec, self.duration_sec)
        self._metronome_click_times = metronome_click_times(schedule)
        click_schedule = tuple(
            (click.time_sec, click.accented) for click in schedule
        )
        self._active = True
        self._awaiting_confirm = False
        self._taps.clear()
        self._deltas.clear()
        self._last_click_index = None
        self.playback.player.set_click_only(True)
        self.playback.player.set_click_schedule(click_schedule)
        if self.playback.paused:
            toggle_pause(self.playback, self.duration_sec)

    def cancel(self) -> None:
        if not self._active:
            return
        self._finish_calibration()

    def _finish_calibration(self) -> None:
        self._active = False
        self._awaiting_confirm = False
        self._taps.clear()
        self._deltas.clear()
        self._last_click_index = None
        self._metronome_click_times = ()
        self.playback.player.set_click_schedule(None)
        self.playback.player.set_click_only(False)

    def record_tap(self) -> None:
        if not self._active or self._awaiting_confirm:
            return
        tap = self.playback.player.audible_position_zero_residual_sec()
        click_index, delta = accept_tap_for_click(
            tap,
            self._metronome_click_times,
            self._last_click_index,
        )
        if click_index is None or delta is None:
            return
        self._last_click_index = click_index
        self._taps.append(tap)
        self._deltas.append(delta)
        if consecutive_deltas_consistent(self._deltas):
            self._prompt_apply_detected_delay()

    def _proposed_delay_sec(self) -> float:
        return max(
            0.0,
            min(mean_delay_from_deltas(self._deltas), MAX_RESIDUAL_DELAY_SEC),
        )

    def _prompt_apply_detected_delay(self) -> None:
        self.playback.player.set_click_schedule(None)
        if not self.playback.paused:
            toggle_pause(self.playback, self.duration_sec)
        self._awaiting_confirm = True
        delay_ms = clamp_residual_delay_ms(
            int(round(self._proposed_delay_sec() * 1000.0))
        )
        self._modal_host.prompt_yes_no(
            f"Detected wireless delay: {delay_ms} ms. Apply?",
            on_confirm=lambda: self._apply_detected_delay(delay_ms),
            on_cancel=self._dismiss_without_apply,
            cancel_label="Cancel",
        )

    def _apply_detected_delay(self, delay_ms: int) -> None:
        self.cfg.editor = replace(self.cfg.editor, residual_delay_ms=delay_ms)
        self._on_apply_residual_delay()
        persist_editor_settings(self.cfg)
        self._finish_calibration()
        self._on_notification(f"Wireless delay set to {delay_ms} ms")

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
