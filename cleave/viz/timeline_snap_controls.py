"""Snap cues dialog and cue rewrite for beats, bars, and song markers."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from cleave.timeline import (
    SongMarkerSnapMode,
    empty_lane,
    snap_lane_to_beats,
    snap_lanes_to_song_markers,
)
from cleave.timeline_presets.song_marker_snap import (
    SONG_MARKER_SNAP_PROXIMITY_OPTIONS,
    song_marker_snap_proximity_label,
)
from cleave.viz.modal import (
    FormField,
    FormFieldKind,
    FormSpec,
    FormValues,
    ModalHost,
)
from cleave.viz.session import TuningSession
from cleave.viz.timeline_history import TimelineHistory

SONG_MARKER_SNAP_SCOPE_EACH_LAYER = "each_layer"
SONG_MARKER_SNAP_SCOPE_CLOSEST_WINS = "closest_wins"
_ALL_CLOSEST_LABEL = "Closest Wins"
_EACH_LAYER_LABEL = "All Layers"
_TARGET_BEATS = "beats"
_TARGET_BARS = "bars"
_TARGET_SONG_MARKERS = "song markers"
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
        return f"Layer {layer_z_order.index(scope) + 1}"
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
        history: TimelineHistory | None = None,
    ) -> None:
        self.session = session
        self._modal = modal_host
        self._history = history if history is not None else TimelineHistory(session)
        self._beat_times = tuple(beat_times)
        self._bar_times = tuple(bar_times)
        self._on_notification = on_notification
        self._last_target = _TARGET_BARS
        self._last_proximity = _DEFAULT_PROXIMITY
        self._last_scope = SONG_MARKER_SNAP_SCOPE_EACH_LAYER

    def prompt_cues(self) -> None:
        """Open Snap cues on the last target."""
        if self._blocked():
            return
        self._prompt(self._last_target)

    def prompt_song_markers(self) -> None:
        """Open Snap cues on song markers."""
        if self._blocked():
            return
        if not self.session.song_markers.times:
            self._notify("No song markers to snap to")
            return
        self._prompt(_TARGET_SONG_MARKERS)

    def _blocked(self) -> bool:
        tl = self.session.timeline
        if tl.locked or tl.recording:
            return True
        if not any(lane.cues for lane in tl.lanes.values()):
            self._notify("No timeline cues to snap")
            return True
        return False

    def _prompt(self, target: str) -> None:
        targets = [_TARGET_BEATS, _TARGET_BARS]
        if self.session.song_markers.times:
            targets.append(_TARGET_SONG_MARKERS)
        target_options = tuple(targets)
        if target not in target_options:
            target = _TARGET_BARS
        layer_z_order = tuple(self.session.layer_z_order)
        scopes = song_marker_snap_scope_options(layer_z_order)
        scope = self._last_scope if self._last_scope in scopes else (
            SONG_MARKER_SNAP_SCOPE_EACH_LAYER
        )

        def on_song_markers(values: FormValues) -> bool:
            return target_options[values["target"]] == _TARGET_SONG_MARKERS

        def resolved(values: FormValues) -> tuple[str, float, str]:
            return (
                target_options[values["target"]],
                SONG_MARKER_SNAP_PROXIMITY_OPTIONS[values["proximity"]],
                scopes[values["scope"]],
            )

        def confirm(values: FormValues) -> None:
            chosen, proximity, chosen_scope = resolved(values)
            self._last_target = chosen
            self._last_proximity = proximity
            self._last_scope = chosen_scope
            with self._history.recording("Snap cues"):
                if chosen == _TARGET_SONG_MARKERS:
                    self._snap_song_markers(proximity=proximity, scope=chosen_scope)
                elif chosen == _TARGET_BARS:
                    self._snap_to_bars()
                else:
                    self._snap_to_beats()

        self._modal.prompt_form(
            FormSpec(
                title="Snap cues",
                fields=(
                    FormField(
                        "target",
                        "snap to",
                        FormFieldKind.SEGMENT,
                        target_options,
                        target_options.index(target),
                    ),
                    FormField(
                        "proximity",
                        "proximity",
                        FormFieldKind.STEP,
                        tuple(
                            song_marker_snap_proximity_label(option)
                            for option in SONG_MARKER_SNAP_PROXIMITY_OPTIONS
                        ),
                        SONG_MARKER_SNAP_PROXIMITY_OPTIONS.index(self._last_proximity),
                        on_song_markers,
                    ),
                    FormField(
                        "scope",
                        "layers",
                        FormFieldKind.STEP,
                        tuple(
                            song_marker_snap_scope_label(option, layer_z_order)
                            for option in scopes
                        ),
                        scopes.index(scope),
                        on_song_markers,
                    ),
                ),
                confirm_label="Snap cues",
                on_confirm=confirm,
                info=lambda values: self._move_info(*resolved(values)),
            )
        )

    def _move_info(self, target: str, proximity: float, scope: str) -> str | None:
        """How many cues the draft would move, from a dry run."""
        tl = self.session.timeline
        total = sum(len(lane.cues) for lane in tl.lanes.values())
        if target == _TARGET_SONG_MARKERS:
            layer_z_order = tuple(self.session.layer_z_order)
            slots, mode = resolve_song_marker_snap(scope, layer_z_order)
            _updated, moved = snap_lanes_to_song_markers(
                tl.lanes,
                self.session.song_markers.times,
                proximity=proximity,
                layer_z_order=layer_z_order,
                slots=slots,
                mode=mode,
            )
            return f"Moves {moved} of {total} cues."
        grid = self._bar_times if target == _TARGET_BARS else self._beat_times
        if not grid:
            return None
        moved = 0
        for lane in tl.lanes.values():
            snapped = {cue.t for cue in snap_lane_to_beats(lane, grid).cues}
            moved += sum(1 for cue in lane.cues if cue.t not in snapped)
        return f"Moves {moved} of {total} cues."

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
