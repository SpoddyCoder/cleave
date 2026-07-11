"""Timeline preset choice modal and clear+apply orchestration."""

from __future__ import annotations

import random
from collections.abc import Callable

from cleave.timeline import copy_lane, empty_lane
from cleave.timeline_presets import (
    build_arc_cues,
    build_breathing_cues,
    build_dialogue_cues,
    build_pulse_cues,
)
from cleave.viz.modal import ModalHost, ModalOption
from cleave.viz.session import TuningSession

_CANCEL_LABEL = "Cancel"
_PROMPT_MESSAGE = "Which timeline preset do you wish to apply?"

_KIND_BUILDERS = {
    "breathing": (build_breathing_cues, "Applied Breathing timeline preset"),
    "dialogue": (build_dialogue_cues, "Applied Dialogue timeline preset"),
    "arc": (build_arc_cues, "Applied Arc timeline preset"),
    "pulse": (build_pulse_cues, "Applied Pulse timeline preset"),
}


class TimelinePresetController:
    """Prompt for and apply procedural timeline presets from the tuning panel."""

    def __init__(
        self,
        session: TuningSession,
        modal_host: ModalHost,
        *,
        on_notification: Callable[[str], None] | None = None,
    ) -> None:
        self.session = session
        self._modal = modal_host
        self._on_notification = on_notification

    def prompt(self, duration_sec: float) -> None:
        dismiss = lambda: None
        options = [
            ModalOption(
                "Breathing",
                lambda: self._apply("breathing", duration_sec),
            ),
            ModalOption(
                "Dialogue",
                lambda: self._apply("dialogue", duration_sec),
            ),
            ModalOption(
                "Arc",
                lambda: self._apply("arc", duration_sec),
            ),
            ModalOption(
                "Pulse",
                lambda: self._apply("pulse", duration_sec),
            ),
            ModalOption(_CANCEL_LABEL, dismiss),
        ]
        self._modal.prompt_choice(_PROMPT_MESSAGE, options, on_dismiss=dismiss)

    def _apply(self, kind: str, duration_sec: float) -> None:
        builder, message = _KIND_BUILDERS[kind]
        self._clear_timeline_state()
        tl = self.session.timeline
        tl.enabled = True
        built = builder(
            list(self.session.layer_z_order),
            duration_sec,
            random.Random(),
        )
        for slot in self.session.layer_z_order:
            tl.lanes[slot] = copy_lane(built.get(slot, empty_lane()))
        if self._on_notification is not None:
            self._on_notification(message)

    def _clear_timeline_state(self) -> None:
        tl = self.session.timeline
        tl.lanes = {
            slot: empty_lane() for slot in self.session.layer_z_order
        }
        tl.record_buffer = {}
        tl.recording = False
        tl.record_start_sec = None
        tl.record_baseline = {}
        tl.record_high_water_mark = None
        tl.armed_slots.clear()
        tl.override_slots.clear()
        tl.override_visible.clear()
        tl.preview_active = False
        tl.monitor.clear()
        tl.arm_flash_start_ms.clear()
