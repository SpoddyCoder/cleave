"""Song-marker drop, snap, and delete for live tuning."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pygame

from cleave.song_markers import (
    SongMarker,
    SongMarkerType,
    format_marker_time,
    marker_index_near,
    place_marker,
    snap_markers,
)
from cleave.timeline import snap_placement_time
from cleave.viz.modal import FormField, FormSpec, FormValues, ModalHost
from cleave.viz.playback import PlaybackState, tap_sec
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.session import TuningSession

_TARGET_BEATS = "beats"
_TARGET_BARS = "bars"
_SNAP_TARGETS = (_TARGET_BEATS, _TARGET_BARS)
_SNAP_HELP = (
    "Moves the song markers you have already placed onto the grid. Markers before or after the detected beats stay put, and markers that land on the same time merge. Clips do not move. Ctrl+Z does not undo this.",
)
_SNAP_TARGET_HELP = ("Where the song markers move to.",)
_SNAP_TARGET_OPTION_HELP = {
    _TARGET_BEATS: "each marker moves to the nearest beat.",
    _TARGET_BARS: "each marker moves to the nearest bar.",
}
# A marker closer than this to its grid point counts as already there.
_SNAP_EPS_SEC = 1e-6


class SongMarkerController:
    """Mutations for project-scoped song markers."""

    def __init__(
        self,
        session: TuningSession,
        modal_host: ModalHost,
        beat_times: Sequence[float],
        bar_times: Sequence[float],
        playback: PlaybackState,
        duration_sec: float,
        *,
        on_notification: Callable[[str], None] | None = None,
        on_focus_marker: Callable[[int | None], None] | None = None,
    ) -> None:
        self.session = session
        self._modal = modal_host
        self._beat_times = tuple(beat_times)
        self._bar_times = tuple(bar_times)
        self._playback = playback
        self._duration_sec = duration_sec
        self._on_notification = on_notification
        self._on_focus_marker = on_focus_marker
        self._last_snap_target = _TARGET_BARS

    def sync_focus(self, descriptor: RowDescriptor) -> None:
        if (
            descriptor.kind == RowKind.SONG_MARKER_ITEM
            and descriptor.marker_index is not None
        ):
            self.select(descriptor.marker_index)

    def select(self, index: int) -> None:
        """Select marker *index* and start its strip flash when it changes."""
        markers = self.session.song_markers
        if index < 0 or index >= len(markers.markers):
            return
        if markers.selected_index == index:
            return
        markers.selected_index = index
        markers.selected_flash_start_ms = pygame.time.get_ticks()

    def set_type(self, index: int, marker_type: SongMarkerType) -> None:
        """Give marker *index* *marker_type*."""
        markers = self.session.song_markers
        if index < 0 or index >= len(markers.markers):
            return
        current = markers.markers[index]
        if marker_type == current.marker_type:
            return
        markers.markers[index] = SongMarker(current.time, marker_type)

    def drop(self) -> None:
        """Drop or replace a song marker where the user tapped (session until Save)."""
        self.drop_at(tap_sec(self._playback, self._duration_sec))

    def drop_at(
        self, t_sec: float, marker_type: SongMarkerType | None = None
    ) -> None:
        """Drop or replace a song marker at *t_sec*, snapped as placement snaps.

        Without *marker_type* a replaced marker keeps its type and a new one is
        plain.
        """
        if self.session.timeline.recording:
            return
        t = snap_placement_time(
            max(0.0, min(self._duration_sec, t_sec)),
            self.session.timeline.placement_snap,
            beat_times=self._beat_times,
            bar_times=self._bar_times,
            bar_phase=self.session.timeline.bar_phase_offset,
        )
        markers = self.session.song_markers
        prior_selected_time: float | None = None
        if (
            markers.selected_index is not None
            and 0 <= markers.selected_index < len(markers.markers)
        ):
            prior_selected_time = markers.markers[markers.selected_index].time
        new_markers, replaced_index, replaced_time = place_marker(
            markers.markers, t, marker_type=marker_type
        )
        markers.markers = list(new_markers)
        # Never activate the newly placed marker; keep prior selection by time.
        if prior_selected_time is None:
            if markers.selected_index is not None and (
                markers.selected_index < 0
                or markers.selected_index >= len(markers.markers)
            ):
                markers.selected_index = None
        elif (
            replaced_time is not None
            and replaced_time == prior_selected_time
            and replaced_index is not None
        ):
            markers.selected_index = replaced_index
        else:
            try:
                markers.selected_index = next(
                    i
                    for i, m in enumerate(new_markers)
                    if m.time == prior_selected_time
                )
            except StopIteration:
                markers.selected_index = None
        if self._on_notification is None:
            return
        if replaced_index is not None:
            assert replaced_time is not None
            self._on_notification(
                f"Song marker replaced "
                f"{format_marker_time(replaced_time)} -> "
                f"{format_marker_time(new_markers[replaced_index].time)}"
            )
        else:
            self._on_notification(f"Song marker {format_marker_time(t)}")

    def prompt_snap(self) -> None:
        """Open Snap song markers: move the placed markers to beats or bars."""
        if self.session.timeline.locked or self.session.timeline.recording:
            return
        if not self.session.song_markers.markers:
            self._notify("No song markers to snap")
            return
        targets = tuple(t for t in _SNAP_TARGETS if self._grid_for(t))
        if not targets:
            self._notify("No beats available; re-run separate")
            return
        target = (
            self._last_snap_target if self._last_snap_target in targets else targets[0]
        )

        def confirm(values: FormValues) -> None:
            self._last_snap_target = targets[values["target"]]
            self._snap(self._last_snap_target)

        self._modal.prompt_form(
            FormSpec(
                title="Snap song markers",
                fields=(
                    FormField(
                        "target",
                        "snap to",
                        targets,
                        targets.index(target),
                        help=_SNAP_TARGET_HELP,
                        option_help=tuple(
                            _SNAP_TARGET_OPTION_HELP[option] for option in targets
                        ),
                    ),
                ),
                confirm_label="Snap markers",
                on_confirm=confirm,
                info=lambda values: self._snap_info(targets[values["target"]]),
                help=_SNAP_HELP,
            )
        )

    def _grid_for(self, target: str) -> tuple[float, ...]:
        return self._bar_times if target == _TARGET_BARS else self._beat_times

    def _snapped(
        self, target: str
    ) -> tuple[tuple[SongMarker, ...], tuple[int, ...], int]:
        """The markers on *target*'s grid, their new indices, and how many move."""
        bar_phase = self.session.timeline.bar_phase_offset
        mode = "bar" if target == _TARGET_BARS else "beat"
        markers = self.session.song_markers.markers
        snapped, new_indices = snap_markers(
            markers,
            lambda t: snap_placement_time(
                t,
                mode,
                beat_times=self._beat_times,
                bar_times=self._bar_times,
                bar_phase=bar_phase,
            ),
        )
        moved = sum(
            1
            for marker, index in zip(markers, new_indices)
            if abs(snapped[index].time - marker.time) > _SNAP_EPS_SEC
        )
        return snapped, new_indices, moved

    def _snap_info(self, target: str) -> str:
        total = len(self.session.song_markers.markers)
        snapped, _new_indices, moved = self._snapped(target)
        merged = total - len(snapped)
        merges = f", merges {merged}" if merged else ""
        return f"(moves {moved} of {total} song markers{merges})"

    def _snap(self, target: str) -> None:
        markers = self.session.song_markers
        snapped, new_indices, moved = self._snapped(target)
        if moved == 0:
            self._notify(f"No song markers to move onto {target}")
            return
        selected = markers.selected_index
        if selected is not None:
            markers.selected_index = (
                new_indices[selected] if 0 <= selected < len(new_indices) else None
            )
        markers.markers = list(snapped)
        noun = "song marker" if moved == 1 else "song markers"
        self._notify(f"Snapped {moved} {noun} to {target}")

    def _notify(self, message: str) -> None:
        if self._on_notification is not None:
            self._on_notification(message)

    def marker_near(self, t_sec: float, tolerance_sec: float) -> int | None:
        """Index of the marker nearest *t_sec* within *tolerance_sec*, or None."""
        return marker_index_near(self.session.song_markers.times, t_sec, tolerance_sec)

    def prompt_delete(self, index: int) -> None:
        markers = self.session.song_markers
        if index < 0 or index >= len(markers.markers):
            return
        label = format_marker_time(markers.markers[index].time)
        self._modal.prompt_confirm(
            f"Delete song marker {label}?",
            "Delete marker",
            lambda: self.confirm_delete(index),
            destructive=True,
        )

    def confirm_delete(self, index: int) -> None:
        markers = self.session.song_markers
        if index < 0 or index >= len(markers.markers):
            return
        removed = markers.markers.pop(index)
        markers.selected_flash_start_ms = None
        if not markers.markers:
            markers.selected_index = None
        elif markers.selected_index is None:
            pass
        elif markers.selected_index == index:
            markers.selected_index = min(index, len(markers.markers) - 1)
        elif markers.selected_index > index:
            markers.selected_index -= 1
        if self._on_notification is not None:
            self._on_notification(
                f"Song marker removed {format_marker_time(removed.time)}"
            )
        if self._on_focus_marker is None:
            return
        self._on_focus_marker(markers.selected_index)
