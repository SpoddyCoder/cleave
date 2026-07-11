"""Timeline beat-snap confirm modal and cue rewrite."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from cleave.timeline import empty_lane, snap_lane_to_beats
from cleave.viz.modal import ModalHost
from cleave.viz.session import TuningSession


class TimelineSnapController:
    """Prompt for and apply beat snapping to committed timeline cues."""

    def __init__(
        self,
        session: TuningSession,
        modal_host: ModalHost,
        beat_times: Sequence[float],
        *,
        on_notification: Callable[[str], None] | None = None,
    ) -> None:
        self.session = session
        self._modal = modal_host
        self._beat_times = tuple(beat_times)
        self._on_notification = on_notification

    def prompt(self) -> None:
        tl = self.session.timeline
        if tl.recording:
            return
        if not any(lane.cues for lane in tl.lanes.values()):
            self._notify("No timeline cues to snap")
            return
        if not self._beat_times:
            self._notify("No beats available; re-run separate")
            return
        self._modal.prompt_yes_no(
            "Do you want to snap all timeline cues to nearest beat?",
            on_confirm=self._snap,
            cancel_label="CANCEL",
        )

    def _snap(self) -> None:
        tl = self.session.timeline
        for slot in list(tl.lanes):
            tl.lanes[slot] = snap_lane_to_beats(
                tl.lanes.get(slot) or empty_lane(),
                self._beat_times,
            )
        self._notify("Snapped timeline cues to beats")

    def _notify(self, message: str) -> None:
        if self._on_notification is not None:
            self._on_notification(message)
