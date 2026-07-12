"""Timeline beat/bar/song-marker snap confirm modal and cue rewrite."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from cleave.timeline import (
    SongMarkerSnapMode,
    empty_lane,
    snap_lane_to_beats,
    snap_lanes_to_song_markers,
)
from cleave.viz.modal import ModalHost, ModalOption
from cleave.viz.session import TuningSession

_CANCEL_LABEL = "Cancel"
_ALL_CLOSEST_LABEL = "All layers (closest wins)"
_EACH_LAYER_LABEL = "Each layer"


class TimelineSnapController:
    """Prompt for and apply beat/bar/song-marker snapping to committed cues."""

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

    def prompt_song_markers(self) -> None:
        tl = self.session.timeline
        if tl.locked:
            return
        if tl.recording:
            return
        markers = tuple(self.session.song_markers.times)
        if not markers:
            self._notify("No song markers to snap to")
            return
        if not any(lane.cues for lane in tl.lanes.values()):
            self._notify("No timeline cues to snap")
            return
        proximity = tl.song_marker_snap_proximity
        message = (
            f"Snap closest cues within {proximity:.1f}s to song markers?"
        )
        dismiss = lambda: None
        options: list[ModalOption] = []
        for i, slot in enumerate(self.session.layer_z_order):
            label = f"Layer {i + 1}"
            options.append(
                ModalOption(
                    label,
                    lambda s=slot: self._snap_song_markers(
                        slots=(s,),
                        mode="each_layer",
                    ),
                )
            )
        options.append(
            ModalOption(
                _ALL_CLOSEST_LABEL,
                lambda: self._snap_song_markers(
                    slots=tuple(self.session.layer_z_order),
                    mode="closest_wins",
                ),
            )
        )
        options.append(
            ModalOption(
                _EACH_LAYER_LABEL,
                lambda: self._snap_song_markers(
                    slots=tuple(self.session.layer_z_order),
                    mode="each_layer",
                ),
            )
        )
        options.append(ModalOption(_CANCEL_LABEL, dismiss))
        self._modal.prompt_choice(message, options, on_dismiss=dismiss)

    def _snap_song_markers(
        self,
        *,
        slots: Sequence[str],
        mode: SongMarkerSnapMode,
    ) -> None:
        tl = self.session.timeline
        if not any((tl.lanes.get(slot) or empty_lane()).cues for slot in slots):
            self._notify("No timeline cues to snap")
            return
        updated, moved = snap_lanes_to_song_markers(
            tl.lanes,
            self.session.song_markers.times,
            proximity=tl.song_marker_snap_proximity,
            layer_z_order=tuple(self.session.layer_z_order),
            slots=slots,
            mode=mode,
        )
        for slot in slots:
            if slot in updated:
                tl.lanes[slot] = updated[slot]
        if moved == 0:
            self._notify("No cues within snap proximity")
            return
        noun = "cue" if moved == 1 else "cues"
        self._notify(f"Snapped {moved} {noun} to song markers")

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
