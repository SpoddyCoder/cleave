"""Timeline bar-phase Left/Right nudge (±1 beat, sticky session offset)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from cleave.timeline import empty_lane, shift_lane_cues_by_beats
from cleave.viz.session import TuningSession


class TimelinePhaseController:
    """Nudge all committed cue times by ±1 beat and update session phase offset."""

    def __init__(
        self,
        session: TuningSession,
        beat_times: Sequence[float],
        *,
        on_notification: Callable[[str], None] | None = None,
    ) -> None:
        self.session = session
        self._beat_times = tuple(beat_times)
        self._on_notification = on_notification

    def nudge(self, *, forward: bool) -> None:
        tl = self.session.timeline
        if tl.locked:
            return
        if tl.recording:
            return
        if not any(lane.cues for lane in tl.lanes.values()):
            self._notify("No timeline cues to shift")
            return
        if not self._beat_times:
            self._notify("No beats available; re-run separate")
            return
        delta = 1 if forward else -1
        for slot in list(tl.lanes):
            tl.lanes[slot] = shift_lane_cues_by_beats(
                tl.lanes.get(slot) or empty_lane(),
                self._beat_times,
                delta,
            )
        tl.bar_phase_offset = (tl.bar_phase_offset + delta) % 4
        self._notify(f"Bar phase +{tl.bar_phase_offset}")

    def _notify(self, message: str) -> None:
        if self._on_notification is not None:
            self._on_notification(message)
