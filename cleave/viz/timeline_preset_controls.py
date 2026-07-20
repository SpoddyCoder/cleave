"""Timeline preset confirm modal and clear+apply orchestration."""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence

from cleave.timeline import TimelineLane, copy_lane, empty_lane, shift_bars_by_beats
from cleave.timeline_presets import (
    build_arc_cues,
    build_breathing_cues,
    build_dialogue_cues,
    build_pulse_cues,
)
from cleave.timeline_presets.characters import timeline_preset_kind_display
from cleave.timeline_presets.crescendo import (
    CRESCENDO_MIN_MARKERS,
    CrescendoTarget,
    apply_crescendo,
    normalize_crescendo_markers,
    timeline_preset_crescendo_display,
)
from cleave.timeline_presets.density import (
    density_bias_for,
    timeline_preset_density_display,
)
from cleave.viz.modal import ModalHost, ModalOption
from cleave.viz.session import TuningSession

_CANCEL_LABEL = "Cancel"
_RESET_PROMPT_MESSAGE = "Reset timeline?"

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
        beat_times: Sequence[float] = (),
        bar_times: Sequence[float] = (),
        *,
        on_notification: Callable[[str], None] | None = None,
    ) -> None:
        self.session = session
        self._modal = modal_host
        self._beat_times = tuple(beat_times)
        self._bar_times = tuple(bar_times)
        self._on_notification = on_notification

    def prompt(self, duration_sec: float) -> None:
        if self.session.timeline.locked:
            return
        dismiss = lambda: None
        self._modal.prompt_yes_no(
            self._apply_prompt_message(),
            on_confirm=lambda: self._confirm_apply(duration_sec),
            on_cancel=dismiss,
            cancel_label=_CANCEL_LABEL,
        )

    def _apply_prompt_message(self) -> str:
        tl = self.session.timeline
        choice_lines = (
            f"character: {timeline_preset_kind_display(tl.timeline_preset_kind)}",
            f"crescendo: {timeline_preset_crescendo_display(tl.timeline_preset_crescendo)}",
            f"density: {timeline_preset_density_display(tl.timeline_preset_density)}",
        )
        return "\n".join(("Apply timeline preset?", *choice_lines))

    def prompt_reset(self) -> None:
        if self.session.timeline.locked:
            return
        dismiss = lambda: None
        options = [
            ModalOption("All Off", lambda: self._reset(all_on=False)),
            ModalOption("All On", lambda: self._reset(all_on=True)),
            ModalOption(_CANCEL_LABEL, dismiss),
        ]
        self._modal.prompt_choice(_RESET_PROMPT_MESSAGE, options, on_dismiss=dismiss)

    def _confirm_apply(self, duration_sec: float) -> None:
        tl = self.session.timeline
        kind = tl.timeline_preset_kind
        crescendo = tl.timeline_preset_crescendo
        if crescendo is not None:
            markers = normalize_crescendo_markers(
                self.session.song_markers.times,
                duration_sec,
            )
            if len(markers) < CRESCENDO_MIN_MARKERS:
                crescendo = None
        self._apply(kind, duration_sec, crescendo=crescendo)

    def _apply(
        self,
        kind: str,
        duration_sec: float,
        *,
        crescendo: CrescendoTarget | None,
    ) -> None:
        if not self._bar_times:
            self._notify("No bars available; re-run separate")
            return
        if not self._beat_times:
            self._notify("No beats available; re-run separate")
            return
        builder, message = _KIND_BUILDERS[kind]
        grid = shift_bars_by_beats(
            self._bar_times,
            self._beat_times,
            self.session.timeline.bar_phase_offset,
        )
        if not grid:
            self._notify("No bars available; re-run separate")
            return
        self._clear_timeline_state()
        tl = self.session.timeline
        tl.enabled = True
        slots = list(self.session.layer_z_order)
        markers = list(self.session.song_markers.times)
        rng = random.Random()
        built = builder(
            slots,
            duration_sec,
            rng,
            bar_times=grid,
            song_marker_times=markers,
            density_bias=density_bias_for(tl.timeline_preset_density),
        )
        if crescendo is not None:
            built = apply_crescendo(
                built,
                slots,
                duration_sec=duration_sec,
                bar_times=grid,
                song_marker_times=markers,
                target=crescendo,
                rng=rng,
            )
            message = f"{message} (crescendo)"
        for slot in slots:
            tl.lanes[slot] = copy_lane(built.get(slot, empty_lane()))
        self._notify(message)

    def _reset(self, *, all_on: bool) -> None:
        self._clear_timeline_state()
        tl = self.session.timeline
        tl.enabled = True
        tl.lanes = {
            slot: TimelineLane(baseline=all_on, cues=[])
            for slot in self.session.layer_z_order
        }
        message = (
            "Reset timeline: all layers on"
            if all_on
            else "Reset timeline: all layers off"
        )
        self._notify(message)

    def _clear_timeline_state(self) -> None:
        tl = self.session.timeline
        tl.lanes = {
            slot: empty_lane() for slot in self.session.layer_z_order
        }
        tl.record_buffer = {}
        tl.recording = False
        tl.record_start_sec = None
        tl.record_baseline = {}
        tl.record_slot_start_sec = {}
        tl.record_high_water_mark = None
        tl.armed_slots.clear()
        tl.override_slots.clear()
        tl.override_visible.clear()
        tl.preview_active = False
        tl.monitor.clear()
        tl.arm_flash_start_ms.clear()

    def _notify(self, message: str) -> None:
        if self._on_notification is not None:
            self._on_notification(message)
