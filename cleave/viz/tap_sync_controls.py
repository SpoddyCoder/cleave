"""Calibrate tap timing: measure tap latency from Enter presses on a click track."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cleave.config import CleaveConfig
from cleave.config_schema.editor import (
    MAX_TAP_LATENCY_MS,
    MIN_TAP_LATENCY_MS,
    clamp_tap_latency_ms,
)
from cleave.viz.calibration_clicks import CalibrationClicks
from cleave.viz.info_panel import InfoPanelViewState
from cleave.viz.modal import FormField, FormSpec, FormValues, ModalHost
from cleave.viz.tap_sync import (
    MIN_KEPT_TAPS,
    SETTLED_SEC,
    accept_tap_for_accent,
    estimate_tap_latency,
    metronome_accent_times,
    push_tap_delta,
    tap_estimate_settled,
)

_TAP_SYNC_CONFIRM_TITLE = "Calibrate tap timing"
_TAP_SYNC_CONFIRM_BODY = (
    "Press Enter on each long low tone until your timing settles."
)

_APPLY_TITLE = "Detected tap latency"
# Matches the Settings > Preview tap latency row: 10 ms, 50 ms large.
_LATENCY_STEP_MS = 10
_LATENCY_LARGE_STEPS = 5
_LATENCY_HELP = (
    "Plus means you tap after the beat, minus before it.",
)


def format_tap_latency_ms(ms: int) -> str:
    return f"{ms:+d} ms"


def latency_options_ms(detected_ms: int) -> tuple[int, ...]:
    """Every 10 ms across the tap range, plus the measured value in order."""
    steps = range(MIN_TAP_LATENCY_MS, MAX_TAP_LATENCY_MS + 1, _LATENCY_STEP_MS)
    return tuple(sorted({*steps, clamp_tap_latency_ms(detected_ms)}))


@dataclass(frozen=True)
class TapSyncProgressView:
    kept: int
    margin_ms: int | None
    estimate_ms: int | None


def _ms(sec: float) -> int:
    return int(round(sec * 1000.0))


def tap_sync_info_panel(progress: TapSyncProgressView) -> InfoPanelViewState:
    """Copy for the detection box shown while calibration is listening."""
    margin_text = (
        "--" if progress.margin_ms is None else f"+/-{progress.margin_ms} ms"
    )
    estimate_text = (
        "--"
        if progress.estimate_ms is None
        else format_tap_latency_ms(progress.estimate_ms)
    )
    return InfoPanelViewState(
        title_lines=(
            "Detection in progress",
            "Tap Enter on the long low tone",
        ),
        body_lines=(
            f"Taps: {progress.kept} (needs {MIN_KEPT_TAPS})",
            f"Settled to: {margin_text} (needs +/-{_ms(SETTLED_SEC)} ms)",
            f"Estimate: {estimate_text}",
        ),
        footer_line="Esc to cancel",
    )


class TapSyncControls:
    """Thin controller for tap timing calibration."""

    def __init__(
        self,
        cfg: CleaveConfig,
        clicks: CalibrationClicks,
        modal_host: ModalHost,
        *,
        on_notification: Callable[[str], None],
        on_apply_tap_latency: Callable[[int], None],
    ) -> None:
        self.cfg = cfg
        self._clicks = clicks
        self._modal_host = modal_host
        self._on_notification = on_notification
        self._on_apply_tap_latency = on_apply_tap_latency
        self._active = False
        self._awaiting_confirm = False
        self._tap_deltas: list[float] = []
        self._last_accent_index: int | None = None
        self._metronome_accent_times: tuple[float, ...] = ()
        self._on_close: Callable[[], None] | None = None

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
        estimate = estimate_tap_latency(self._tap_deltas)
        return TapSyncProgressView(
            kept=estimate.kept,
            margin_ms=(
                None if estimate.margin_sec is None else _ms(estimate.margin_sec)
            ),
            estimate_ms=(
                None if estimate.latency_sec is None else _ms(estimate.latency_sec)
            ),
        )

    def prompt_start(self, *, on_close: Callable[[], None] | None = None) -> None:
        """Ask to start, then listen for taps.

        *on_close* runs once when calibration ends: applied, dismissed, or
        cancelled at the start prompt or while listening.
        """
        self._on_close = on_close
        self._clicks.pause_transport()
        self._modal_host.prompt_confirm(
            _TAP_SYNC_CONFIRM_TITLE,
            "Start",
            self._begin_calibration,
            self._closed,
            body=_TAP_SYNC_CONFIRM_BODY,
        )

    def _begin_calibration(self) -> None:
        schedule = self._clicks.begin()
        self._metronome_accent_times = metronome_accent_times(schedule)
        self._active = True
        self._awaiting_confirm = False
        self._tap_deltas.clear()
        self._last_accent_index = None

    def cancel(self) -> None:
        if not self._active:
            return
        self._clicks.restore_ui()
        self._finish_calibration()
        self._closed()

    def _finish_calibration(self) -> None:
        self._active = False
        self._awaiting_confirm = False
        self._tap_deltas.clear()
        self._last_accent_index = None
        self._metronome_accent_times = ()
        self._clicks.stop_clicks()

    def record_tap(self) -> None:
        if not self._active or self._awaiting_confirm:
            return
        tap = self._clicks.playback.player.raw_audible_position_sec()
        accent_index, delta = accept_tap_for_accent(
            tap,
            self._metronome_accent_times,
            self._last_accent_index,
        )
        if accent_index is None or delta is None:
            return
        self._last_accent_index = accent_index
        self._tap_deltas = push_tap_delta(self._tap_deltas, delta)
        if tap_estimate_settled(estimate_tap_latency(self._tap_deltas)):
            self._prompt_apply_detected_latency()

    def _proposed_latency_ms(self) -> int:
        latency_sec = estimate_tap_latency(self._tap_deltas).latency_sec
        if latency_sec is None:
            return 0
        return clamp_tap_latency_ms(latency_sec * 1000.0)

    def _prompt_apply_detected_latency(self) -> None:
        self._clicks.end()
        self._awaiting_confirm = True
        latency_ms = self._proposed_latency_ms()
        options = latency_options_ms(latency_ms)
        current_ms = self.cfg.editor.tap_latency_ms

        def apply(values: FormValues) -> None:
            self._apply_detected_latency(options[values["latency"]])

        self._modal_host.prompt_form(
            FormSpec(
                title=_APPLY_TITLE,
                fields=(
                    FormField(
                        "latency",
                        "tap latency",
                        tuple(format_tap_latency_ms(ms) for ms in options),
                        options.index(latency_ms),
                        help=_LATENCY_HELP,
                        stepper=True,
                        large_step=_LATENCY_LARGE_STEPS,
                    ),
                ),
                confirm_label="Apply",
                on_confirm=apply,
                on_cancel=self._dismiss_without_apply,
                info=lambda _values: f"Now {format_tap_latency_ms(current_ms)}",
            )
        )

    def _apply_detected_latency(self, latency_ms: int) -> None:
        self._on_apply_tap_latency(latency_ms)
        self._finish_calibration()
        self._on_notification(
            f"Tap latency set to {format_tap_latency_ms(latency_ms)}"
        )
        self._closed()

    def _dismiss_without_apply(self) -> None:
        self._finish_calibration()
        self._closed()

    def _closed(self) -> None:
        on_close = self._on_close
        self._on_close = None
        if on_close is not None:
            on_close()

    def handle_keydown(self, event) -> bool:
        import pygame

        if self._awaiting_confirm:
            return False
        if event.key == pygame.K_ESCAPE:
            self.cancel()
            return True
        if event.key == pygame.K_RETURN:
            self.record_tap()
            return True
        return False
