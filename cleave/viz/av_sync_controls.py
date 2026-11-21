"""Measure audio latency: line a flash up with a beep by eye and ear."""

from __future__ import annotations

import bisect
from collections.abc import Callable

from cleave.config import CleaveConfig
from cleave.config_schema.editor import (
    MAX_AUDIO_LATENCY_MS,
    clamp_audio_latency_ms,
)
from cleave.viz.calibration_clicks import CalibrationClicks
from cleave.viz.modal import FormField, FormSpec, FormValues, ModalHost

# Long enough to catch at least a few frames at 60 Hz.
FLASH_SEC = 0.08

_TITLE = "Measure audio latency"
_BODY = (
    "Adjust until the flash and the beep land together."
)
# Matches the Settings > Preview audio latency row: 10 ms, 50 ms large.
_LATENCY_STEP_MS = 10
_LATENCY_LARGE_STEPS = 5
_LATENCY_HELP = (
    "Raise it if the flash comes first; lower it if the beep does.",
)


def audio_latency_options_ms(current_ms: int) -> tuple[int, ...]:
    """Every 10 ms from 0 to the maximum, plus the current value in order."""
    steps = range(0, MAX_AUDIO_LATENCY_MS + 1, _LATENCY_STEP_MS)
    return tuple(sorted({*steps, clamp_audio_latency_ms(current_ms)}))


class AvSyncControls:
    """Plays a beep each bar and flashes the preview on the audible beat.

    The flash reads the latency-corrected playhead, so each step of the
    dialog moves it at once; the user stops when it lands on the beep.
    """

    def __init__(
        self,
        cfg: CleaveConfig,
        clicks: CalibrationClicks,
        modal_host: ModalHost,
        *,
        on_notification: Callable[[str], None],
        on_preview_audio_latency: Callable[[int], None],
        on_apply_audio_latency: Callable[[int], None],
    ) -> None:
        self.cfg = cfg
        self._clicks = clicks
        self._modal_host = modal_host
        self._on_notification = on_notification
        self._on_preview_audio_latency = on_preview_audio_latency
        self._on_apply_audio_latency = on_apply_audio_latency
        self._active = False
        self._beat_times: tuple[float, ...] = ()
        self._on_close: Callable[[], None] | None = None

    @property
    def active(self) -> bool:
        return self._active

    def flash_level(self) -> float:
        """1.0 while the latest audible beep is under ``FLASH_SEC`` old."""
        if not self._active or not self._beat_times:
            return 0.0
        now = self._clicks.playback.player.audible_position_sec()
        index = bisect.bisect_right(self._beat_times, now) - 1
        if index < 0:
            return 0.0
        return 1.0 if now - self._beat_times[index] < FLASH_SEC else 0.0

    def prompt_start(self, *, on_close: Callable[[], None] | None = None) -> None:
        """Start the beeps and open the dialog.

        *on_close* runs once when the dialog closes, applied or cancelled.
        """
        self._on_close = on_close
        schedule = self._clicks.begin(accents_only=True)
        self._beat_times = tuple(click.time_sec for click in schedule)
        self._active = True
        saved_ms = self.cfg.editor.audio_latency_ms
        options = audio_latency_options_ms(saved_ms)

        def on_change(_field_id: str, values: FormValues) -> None:
            self._on_preview_audio_latency(options[values["latency"]])

        def apply(values: FormValues) -> None:
            latency_ms = options[values["latency"]]
            self._finish()
            self._on_apply_audio_latency(latency_ms)
            self._on_notification(f"Audio latency set to {latency_ms} ms")
            self._closed()

        def cancel() -> None:
            self._finish()
            self._on_preview_audio_latency(saved_ms)
            self._closed()

        self._modal_host.prompt_form(
            FormSpec(
                title=_TITLE,
                body=_BODY,
                fields=(
                    FormField(
                        "latency",
                        "audio latency",
                        tuple(f"{ms} ms" for ms in options),
                        options.index(saved_ms),
                        help=_LATENCY_HELP,
                        stepper=True,
                        large_step=_LATENCY_LARGE_STEPS,
                    ),
                ),
                confirm_label="Apply",
                on_confirm=apply,
                on_cancel=cancel,
                on_change=on_change,
                info=lambda _values: f"(now {saved_ms} ms)",
            )
        )

    def _finish(self) -> None:
        self._active = False
        self._beat_times = ()
        self._clicks.end()

    def _closed(self) -> None:
        on_close = self._on_close
        self._on_close = None
        if on_close is not None:
            on_close()
