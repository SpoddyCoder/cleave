"""Timeline beat/bar-snap confirm modal and cue rewrite."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from cleave.timeline import bar_times_at_phase, empty_lane, snap_lane_to_beats
from cleave.viz.modal import ModalHost, ModalOption
from cleave.viz.session import TuningSession

_CANCEL_LABEL = "Cancel"
_BEATS_PER_BAR = 4
_BAR_SNAP_MESSAGE = "Snap timeline cues to nearest bar (choose phase offset)"


class TimelineSnapController:
    """Prompt for and apply beat/bar snapping to committed timeline cues."""

    def __init__(
        self,
        session: TuningSession,
        modal_host: ModalHost,
        beat_times: Sequence[float],
        bar_times: Sequence[float] = (),
        *,
        bar_phase: int | None = None,
        on_notification: Callable[[str], None] | None = None,
    ) -> None:
        self.session = session
        self._modal = modal_host
        self._beat_times = tuple(beat_times)
        self._bar_times = tuple(bar_times)
        self._bar_phase = (
            bar_phase
            if bar_phase is not None
            else _infer_bar_phase(self._beat_times, self._bar_times)
        )
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
        options: list[ModalOption] = []
        for offset in range(_BEATS_PER_BAR):
            options.append(
                ModalOption(
                    f"+{offset}",
                    lambda o=offset: self._snap_bars_at_offset(o),
                )
            )
        options.append(ModalOption(_CANCEL_LABEL, dismiss))
        self._modal.prompt_choice(
            _BAR_SNAP_MESSAGE,
            options,
            on_dismiss=dismiss,
        )

    def _snap_bars_at_offset(self, offset: int) -> None:
        phase = (self._bar_phase + offset) % _BEATS_PER_BAR
        grid = bar_times_at_phase(
            self._beat_times, phase, beats_per_bar=_BEATS_PER_BAR
        )
        self._snap_to(grid, f"Snapped timeline cues to bars (+{offset})")

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


def _infer_bar_phase(
    beat_times: Sequence[float],
    bar_times: Sequence[float],
) -> int:
    if not bar_times or not beat_times:
        return 0
    first = bar_times[0]
    for i, t in enumerate(beat_times):
        if t == first:
            return i % _BEATS_PER_BAR
    return 0
