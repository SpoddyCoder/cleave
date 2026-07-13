"""Timeline beat/bar/song-marker snap confirm modal and cue rewrite."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from cleave.timeline import (
    SongMarkerSnapMode,
    empty_lane,
    snap_lane_to_beats,
    snap_lanes_to_song_markers,
)
from cleave.viz.modal import ModalHost
from cleave.viz.session import TuningSession

SONG_MARKER_SNAP_SCOPE_EACH_LAYER = "each_layer"
SONG_MARKER_SNAP_SCOPE_CLOSEST_WINS = "closest_wins"
_ALL_CLOSEST_LABEL = "closest wins"
_EACH_LAYER_LABEL = "all layers"


def song_marker_snap_scope_options(layer_z_order: Sequence[str]) -> tuple[str, ...]:
    return tuple(layer_z_order) + (
        SONG_MARKER_SNAP_SCOPE_CLOSEST_WINS,
        SONG_MARKER_SNAP_SCOPE_EACH_LAYER,
    )


def song_marker_snap_scope_label(
    scope: str,
    layer_z_order: Sequence[str],
) -> str:
    if scope == SONG_MARKER_SNAP_SCOPE_EACH_LAYER:
        return _EACH_LAYER_LABEL
    if scope == SONG_MARKER_SNAP_SCOPE_CLOSEST_WINS:
        return _ALL_CLOSEST_LABEL
    if scope in layer_z_order:
        return f"layer {layer_z_order.index(scope) + 1}"
    return _EACH_LAYER_LABEL


def cycle_song_marker_snap_scope(
    current: str,
    layer_z_order: Sequence[str],
    *,
    forward: bool,
) -> str:
    options = song_marker_snap_scope_options(layer_z_order)
    if not options:
        return SONG_MARKER_SNAP_SCOPE_EACH_LAYER
    try:
        index = options.index(current)
    except ValueError:
        index = len(options) - 1
    delta = 1 if forward else -1
    return options[(index + delta) % len(options)]


def resolve_song_marker_snap(
    scope: str,
    layer_z_order: Sequence[str],
) -> tuple[tuple[str, ...], SongMarkerSnapMode]:
    if scope == SONG_MARKER_SNAP_SCOPE_EACH_LAYER:
        return tuple(layer_z_order), "each_layer"
    if scope == SONG_MARKER_SNAP_SCOPE_CLOSEST_WINS:
        return tuple(layer_z_order), "closest_wins"
    if scope in layer_z_order:
        return (scope,), "each_layer"
    return tuple(layer_z_order), "each_layer"


def song_marker_snap_confirm_message(
    proximity: float,
    scope: str,
    layer_z_order: Sequence[str],
) -> str:
    scope_label = song_marker_snap_scope_label(scope, layer_z_order)
    return (
        f"Snap closest cues within {proximity:.1f}s to song markers "
        f"({scope_label})?"
    )


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
        layer_z_order = tuple(self.session.layer_z_order)
        proximity = tl.song_marker_snap_proximity
        scope = tl.song_marker_snap_scope
        message = song_marker_snap_confirm_message(
            proximity,
            scope,
            layer_z_order,
        )
        slots, mode = resolve_song_marker_snap(scope, layer_z_order)

        def on_confirm() -> None:
            self._snap_song_markers(slots=slots, mode=mode)

        self._modal.prompt_yes_no(
            message,
            on_confirm=on_confirm,
            cancel_label="CANCEL",
        )

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
