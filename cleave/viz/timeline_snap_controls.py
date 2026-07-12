"""Timeline beat/bar-snap confirm modal and cue rewrite."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from cleave.timeline import (
    empty_lane,
    shift_bars_by_beats,
    snap_lane_to_beats,
)
from cleave.viz.modal import ModalHost, ModalOption
from cleave.viz.session import TuningSession

_CANCEL_LABEL = "Cancel"
_BAR_BEAT_OFFSETS = (0, 1, 2, 3)
_BAR_SNAP_MESSAGE = "Snap timeline cues to nearest bar (choose bar phase)"


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
        tl = self.session.timeline
        if tl.recording:
            return
        if not any(lane.cues for lane in tl.lanes.values()):
            self._notify("No timeline cues to snap")
            return
        if not self._beat_times:
            self._notify("No beats available; re-run separate")
            return
        if not self._bar_times:
            self._notify("No bars available; re-run separate")
            return
        dismiss = lambda: None
        options: list[ModalOption] = [
            ModalOption(
                f"{offset:+d}",
                lambda o=offset: self._snap_bars_at_offset(o),
            )
            for offset in _BAR_BEAT_OFFSETS
        ]
        options.append(ModalOption(_CANCEL_LABEL, dismiss))
        self._modal.prompt_choice(
            _BAR_SNAP_MESSAGE,
            options,
            on_dismiss=dismiss,
            initial_focus_index=_BAR_BEAT_OFFSETS.index(0),
        )

    def _snap_bars_at_offset(self, offset: int) -> None:
        grid = shift_bars_by_beats(
            self._bar_times,
            self._beat_times,
            offset,
        )
        label = f"{offset:+d}"
        notify_msg = f"Snapped timeline cues to bars ({label})"
        tl = self.session.timeline
        for slot in list(tl.lanes):
            tl.lanes[slot] = snap_lane_to_beats(
                tl.lanes.get(slot) or empty_lane(),
                grid,
            )
        self._notify(notify_msg)

    def _prompt(
        self,
        grid: Sequence[float],
        *,
        empty_grid_msg: str,
        confirm_msg: str,
        done_msg: str,
    ) -> None:
        tl = self.session.timeline
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
