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

SONG_MARKER_SNAP_SCOPE_EACH_LAYER = "each_layer"
SONG_MARKER_SNAP_SCOPE_CLOSEST_WINS = "closest_wins"
_ALL_CLOSEST_LABEL = "closest wins"
_EACH_LAYER_LABEL = "all layers"
_CANCEL_LABEL = "Cancel"
_GRID_CANCEL_LABEL = "CANCEL"
_GRID_PROMPT = "Snap cues to?"
_PROXIMITY_PROMPT = "Snap proximity?"
_SCOPE_PROMPT = "Layer scope?"
SONG_MARKER_SNAP_PROXIMITY_OPTIONS: tuple[float, ...] = (
    0.5,
    1.0,
    2.0,
    5.0,
    10.0,
    15.0,
    30.0,
)
_DEFAULT_PROXIMITY = 5.0


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


def song_marker_snap_proximity_label(proximity: float) -> str:
    return f"{proximity:.1f}s"


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

    def prompt_grid(self) -> None:
        tl = self.session.timeline
        if tl.locked:
            return
        if tl.recording:
            return
        if not any(lane.cues for lane in tl.lanes.values()):
            self._notify("No timeline cues to snap")
            return
        dismiss = lambda: None
        self._modal.prompt_choice(
            _GRID_PROMPT,
            [
                ModalOption("BEATS", self._snap_to_beats),
                ModalOption("BARS", self._snap_to_bars),
                ModalOption(_GRID_CANCEL_LABEL, dismiss),
            ],
            on_dismiss=dismiss,
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
        self._prompt_song_marker_proximity()

    def _prompt_song_marker_proximity(self) -> None:
        dismiss = lambda: None
        default_index = SONG_MARKER_SNAP_PROXIMITY_OPTIONS.index(_DEFAULT_PROXIMITY)
        options = [
            ModalOption(
                song_marker_snap_proximity_label(proximity),
                lambda p=proximity: self._prompt_song_marker_scope(p),
            )
            for proximity in SONG_MARKER_SNAP_PROXIMITY_OPTIONS
        ]
        options.append(ModalOption(_CANCEL_LABEL, dismiss))
        self._modal.prompt_choice(
            _PROXIMITY_PROMPT,
            options,
            on_dismiss=dismiss,
            initial_focus_index=default_index,
        )

    def _prompt_song_marker_scope(self, proximity: float) -> None:
        layer_z_order = tuple(self.session.layer_z_order)
        scopes = song_marker_snap_scope_options(layer_z_order)
        dismiss = lambda: None
        default_scope = SONG_MARKER_SNAP_SCOPE_EACH_LAYER
        try:
            default_index = scopes.index(default_scope)
        except ValueError:
            default_index = 0
        options = [
            ModalOption(
                song_marker_snap_scope_label(scope, layer_z_order),
                lambda s=scope: self._snap_song_markers(
                    proximity=proximity,
                    scope=s,
                ),
            )
            for scope in scopes
        ]
        options.append(ModalOption(_CANCEL_LABEL, dismiss))
        self._modal.prompt_choice(
            _SCOPE_PROMPT,
            options,
            on_dismiss=dismiss,
            initial_focus_index=default_index,
        )

    def _snap_song_markers(
        self,
        *,
        proximity: float,
        scope: str,
    ) -> None:
        tl = self.session.timeline
        layer_z_order = tuple(self.session.layer_z_order)
        slots, mode = resolve_song_marker_snap(scope, layer_z_order)
        if not any((tl.lanes.get(slot) or empty_lane()).cues for slot in slots):
            self._notify("No timeline cues to snap")
            return
        updated, moved = snap_lanes_to_song_markers(
            tl.lanes,
            self.session.song_markers.times,
            proximity=proximity,
            layer_z_order=layer_z_order,
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

    def _snap_to_beats(self) -> None:
        self._snap_to(
            self._beat_times,
            empty_grid_msg="No beats available; re-run separate",
            done_msg="Snapped timeline cues to beats",
        )

    def _snap_to_bars(self) -> None:
        self._snap_to(
            self._bar_times,
            empty_grid_msg="No bars available; re-run separate",
            done_msg="Snapped timeline cues to bars",
        )

    def _snap_to(
        self,
        grid: Sequence[float],
        *,
        empty_grid_msg: str,
        done_msg: str,
    ) -> None:
        if not grid:
            self._notify(empty_grid_msg)
            return
        tl = self.session.timeline
        for slot in list(tl.lanes):
            tl.lanes[slot] = snap_lane_to_beats(
                tl.lanes.get(slot) or empty_lane(),
                grid,
            )
        self._notify(done_msg)

    def _notify(self, message: str) -> None:
        if self._on_notification is not None:
            self._on_notification(message)
