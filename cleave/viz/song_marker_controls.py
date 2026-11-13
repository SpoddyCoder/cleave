"""Song-marker drop and delete for live tuning."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pygame

from cleave.song_markers import (
    SongMarker,
    SongMarkerType,
    format_marker_time,
    marker_index_near,
    place_marker,
    song_marker_gesture_warning,
)
from cleave.timeline import snap_placement_time
from cleave.viz.modal import ModalHost
from cleave.viz.playback import PlaybackState, current_sec
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.session import TuningSession


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
        """Give marker *index* *marker_type*, warning when the gesture is malformed."""
        markers = self.session.song_markers
        if index < 0 or index >= len(markers.markers):
            return
        current = markers.markers[index]
        if marker_type == current.marker_type:
            return
        markers.markers[index] = SongMarker(current.time, marker_type)
        warning = song_marker_gesture_warning(markers.markers, index)
        if warning is not None and self._on_notification is not None:
            self._on_notification(warning)

    def drop(self) -> None:
        """Drop or replace a song marker at the playhead (session until Save)."""
        self.drop_at(current_sec(self._playback, self._duration_sec))

    def drop_at(self, t_sec: float) -> None:
        """Drop or replace a song marker at *t_sec*, snapped as placement snaps."""
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
            markers.markers, t
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
