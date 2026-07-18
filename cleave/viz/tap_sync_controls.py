"""Tap-to-sync calibration orchestration for wireless delay."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace

from cleave.config import CleaveConfig
from cleave.config_schema import clamp_residual_delay_ms
from cleave.user_config import persist_editor_settings
from cleave.viz.playback import PlaybackState, toggle_pause
from cleave.viz.tap_sync import MIN_TAP_COUNT, infer_residual_delay_sec


class TapSyncControls:
    """Thin controller for sync-by-ear calibration."""

    def __init__(
        self,
        cfg: CleaveConfig,
        playback: PlaybackState,
        duration_sec: float,
        beat_times: Sequence[float],
        *,
        on_notification: Callable[[str], None],
        on_apply_residual_delay: Callable[[], None],
    ) -> None:
        self.cfg = cfg
        self.playback = playback
        self.duration_sec = duration_sec
        self._beat_times = tuple(beat_times)
        self._on_notification = on_notification
        self._on_apply_residual_delay = on_apply_residual_delay
        self._active = False
        self._taps: list[float] = []

    @property
    def active(self) -> bool:
        return self._active

    def start(self) -> None:
        if not self._beat_times:
            self._on_notification("No beats; re-run separate")
            return
        self._active = True
        self._taps.clear()
        self.playback.player.set_click_beats(self._beat_times)
        if self.playback.paused:
            toggle_pause(self.playback, self.duration_sec)

    def cancel(self) -> None:
        if not self._active:
            return
        self._active = False
        self._taps.clear()
        self.playback.player.set_click_beats(None)

    def record_tap(self) -> None:
        if not self._active:
            return
        tap = self.playback.player.audible_position_zero_residual_sec()
        self._taps.append(tap)

    def accept(self) -> bool:
        if not self._active:
            return False
        if len(self._taps) < MIN_TAP_COUNT:
            self._on_notification(f"Need at least {MIN_TAP_COUNT} taps")
            return True
        delay_sec = infer_residual_delay_sec(self._taps, self._beat_times)
        delay_ms = clamp_residual_delay_ms(int(round(delay_sec * 1000.0)))
        self.cfg.editor = replace(self.cfg.editor, residual_delay_ms=delay_ms)
        self._on_apply_residual_delay()
        persist_editor_settings(self.cfg)
        self.cancel()
        self._on_notification(f"Wireless delay set to {delay_ms} ms")
        return True

    def handle_keydown(self, event) -> bool:
        import pygame

        if event.key == pygame.K_ESCAPE:
            self.cancel()
            return True
        if event.key == pygame.K_SPACE:
            self.record_tap()
            return True
        if event.key == pygame.K_RETURN:
            return self.accept()
        return False
