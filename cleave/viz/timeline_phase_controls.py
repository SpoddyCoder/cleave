"""Timeline bar-phase Left/Right nudge (±1 beat, sticky session offset)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from cleave.config_schema.timeline import TIMELINE_BAR_PHASE_BEATS
from cleave.timeline import empty_lane, shift_lane_cues_by_beats
from cleave.viz.edit_history import EditHistory
from cleave.viz.session import TuningSession


class TimelinePhaseController:
    """Nudge the session phase offset, and any committed cues with it, by ±1 beat."""

    def __init__(
        self,
        session: TuningSession,
        beat_times: Sequence[float],
        *,
        on_notification: Callable[[str], None] | None = None,
        history: EditHistory | None = None,
    ) -> None:
        self.session = session
        self._beat_times = tuple(beat_times)
        self._on_notification = on_notification
        self._history = history if history is not None else EditHistory(session)

    def nudge(self, *, forward: bool) -> None:
        tl = self.session.timeline
        if tl.locked:
            return
        if tl.recording:
            return
        if not self._beat_times:
            self._notify("No beats available; re-run separate")
            return
        delta = 1 if forward else -1
        with self._history.recording("Bar phase", merge_key="bar_phase") as edit:
            for slot in list(tl.lanes):
                tl.lanes[slot] = shift_lane_cues_by_beats(
                    tl.lanes.get(slot) or empty_lane(),
                    self._beat_times,
                    delta,
                )
            tl.bar_phase_offset = (
                tl.bar_phase_offset + delta
            ) % TIMELINE_BAR_PHASE_BEATS
        if edit.refused is not None:
            return
        self._notify(f"Bar phase +{tl.bar_phase_offset}")

    def _notify(self, message: str) -> None:
        if self._on_notification is not None:
            self._on_notification(message)
