"""Timeline beat/bar-snap confirm modal and cue rewrite."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from cleave.timeline import empty_lane, snap_lane_to_beats
from cleave.viz.modal import ModalHost
from cleave.viz.session import TuningSession


class TimelineSnapController:
    """Prompt for and apply beat/bar snapping to committed timeline cues."""

    def __init__(
        self,
        session: TuningSession,
        modal_host: ModalHost,
        beat_times: Sequence[float],
        bar_times: Sequence[float] = (),
        *,
        on_notification: Callable[[str], None] | None = None,
    ) -> None:
        self.session = session
        self._modal = modal_host
        self._beat_times = tuple(beat_times)
        self._bar_times = tuple(bar_times)
        self._on_notification = on_notification

    def prompt(self) -> None:
        self._prompt(
            self._beat_times,
            empty_grid_msg="No beats available; re-run separate",
            confirm_msg="Do you want to snap all timeline cues to nearest beat?",
            done_msg="Snapped timeline cues to beats",
        )

    def prompt_bars(self) -> None:
        self._prompt(
            self._bar_times,
            empty_grid_msg="No bars available; re-run separate",
            confirm_msg="Do you want to snap all timeline cues to nearest bar?",
            done_msg="Snapped timeline cues to bars",
        )

    def _prompt(
        self,
        grid: Sequence[float],
        *,
        empty_grid_msg: str,
        confirm_msg: str,
        done_msg: str,
    ) -> None:
        tl = self.session.timeline
        if tl.locked:
            return
        if tl.recording:
            return
        if not any(lane.cues for lane in tl.lanes.values()):
            self._notify("No timeline cues to snap")
            return
        if not grid:
            self._notify(empty_grid_msg)
            return
        self._modal.prompt_yes_no(
            confirm_msg,
            on_confirm=lambda: self._snap_to(grid, done_msg),
            cancel_label="CANCEL",
        )

    def _snap_to(self, grid: Sequence[float], notify_msg: str) -> None:
        tl = self.session.timeline
        for slot in list(tl.lanes):
            tl.lanes[slot] = snap_lane_to_beats(
                tl.lanes.get(slot) or empty_lane(),
                grid,
            )
        self._notify(notify_msg)

    def _notify(self, message: str) -> None:
        if self._on_notification is not None:
            self._on_notification(message)
