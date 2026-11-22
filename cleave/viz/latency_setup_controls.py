"""First-run latency setup: offer both latency calibrations, then run them in turn.

The prompt shows once, the first time the editor opens a project. Both
calibrations start switched on. OK runs the chosen ones one after the other
(Measure audio latency, then Calibrate tap timing); Cancel runs neither.
Either answer marks the step done in the user config. Playback holds paused
from the moment the prompt is requested (before the editor starts the audio)
until the last chosen calibration closes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import yaml

from cleave.user_config import persist_first_run_state, saved_first_run_state
from cleave.viz.modal import FormField, FormSpec, FormValues, ModalHost

LATENCY_SETUP_TITLE = "Set up audio latency"
_BODY = (
    "This is your first project setup, so we recommend configuring the "
    "audio latency settings now for best results. Two latency settings keep "
    "the visuals and your taps in time with the music on this computer."
)
_LATER_HELP = (
    "You can run either one later from the Settings menu.",
)
_OFF_ON = ("Off", "On")
AUDIO_FIELD_ID = "audio_latency"
TAP_FIELD_ID = "tap_timing"


def _mark_done() -> None:
    try:
        persist_first_run_state(
            replace(saved_first_run_state(), latency_setup_done=True)
        )
    except (OSError, ValueError, yaml.YAMLError):
        return


Calibration = Callable[[Callable[[], None]], None]
"""Start one calibration; the argument runs when it closes."""


class LatencySetupFlow:
    """The latency setup prompt and the queue of calibrations it starts.

    :meth:`request` arms it and pauses playback; :meth:`tick` opens it once no
    other dialog or calibration is on screen, so it waits behind anything that
    opened first. Playback resumes when the step ends.
    """

    def __init__(
        self,
        modal_host: ModalHost,
        *,
        measure_audio_latency: Calibration,
        calibrate_tap_timing: Calibration,
        busy: Callable[[], bool],
        hold_playback: Callable[[], Callable[[], None]],
    ) -> None:
        self._modal_host = modal_host
        self._measure_audio_latency = measure_audio_latency
        self._calibrate_tap_timing = calibrate_tap_timing
        self._busy = busy
        self._hold_playback = hold_playback
        self._resume: Callable[[], None] | None = None
        self._pending = False

    @property
    def pending(self) -> bool:
        return self._pending

    @property
    def active(self) -> bool:
        """True from :meth:`request` until the last calibration closes."""
        return self._resume is not None

    def request(self) -> None:
        if self.active:
            return
        self._pending = True
        self._resume = self._hold_playback()

    def tick(self) -> None:
        if not self._pending or self._modal_host.active or self._busy():
            return
        self._pending = False
        self._prompt()

    def _prompt(self) -> None:
        def confirm(values: FormValues) -> None:
            _mark_done()
            queue: list[Calibration] = []
            if values.get(AUDIO_FIELD_ID) == 1:
                queue.append(self._measure_audio_latency)
            if values.get(TAP_FIELD_ID) == 1:
                queue.append(self._calibrate_tap_timing)
            self._run_next(queue)

        self._modal_host.prompt_form(
            FormSpec(
                title=LATENCY_SETUP_TITLE,
                body=_BODY,
                fields=(
                    FormField(
                        id=AUDIO_FIELD_ID,
                        label="Audio latency - visuals in time with the sound",
                        options=_OFF_ON,
                        value=1,
                        help=(
                            "Measure audio latency: line a flash up with a beep "
                            "so the visuals land with the sound you hear.",
                            *_LATER_HELP,
                        ),
                    ),
                    FormField(
                        id=TAP_FIELD_ID,
                        label="Tap timing - your taps in time with the beat",
                        options=_OFF_ON,
                        value=1,
                        help=(
                            "Calibrate tap timing: tap Enter on a click track so "
                            "recorded taps land on the beat.",
                            *_LATER_HELP,
                        ),
                    ),
                ),
                confirm_label="OK",
                on_confirm=confirm,
                on_cancel=self._cancel,
                help=(_BODY, *_LATER_HELP),
            )
        )

    def _cancel(self) -> None:
        _mark_done()
        self._end()

    def _run_next(self, queue: list[Calibration]) -> None:
        if not queue:
            self._end()
            return
        start = queue.pop(0)
        start(lambda: self._run_next(queue))

    def _end(self) -> None:
        resume = self._resume
        self._resume = None
        if resume is not None:
            resume()
