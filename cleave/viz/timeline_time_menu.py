"""Context menu items for a point in song time on the timeline strip.

A right-click on the ruler, or on a row away from any cue, gets these items
for the clicked time: seek there, play from there, and drop a song marker
there. A song marker under the pointer adds a delete item. The ruler also
lists Undo and Redo and the timeline commands (Generate, Snap, Set cut
type, Reset); a row keeps its menu short and leaves them out. Commands come
from ``commands.py`` through ``command_menu_item``, so they share the menu
bar's label, shortcut, and enabled state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from cleave.song_markers import format_marker_time
from cleave.viz.commands import (
    CommandContext,
    command_by_id,
    command_context,
    command_menu_item,
)
from cleave.viz.context_menu import (
    CONTEXT_SEPARATOR,
    ContextMenuEntry,
    ContextMenuItem,
)
from cleave.viz.editor_mode_controls import is_preset_curation_mode

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

_TIMELINE_COMMAND_IDS: tuple[str, ...] = (
    "timeline.generate",
    "timeline.snap_cues",
    "timeline.snap_to_markers",
    "timeline.set_cut_type",
    "timeline.reset",
)


class StripTransport(Protocol):
    @property
    def paused(self) -> bool: ...

    def seek_to(self, t_sec: float) -> None: ...

    def toggle_transport(self) -> None: ...


class TimelineTimeMenu:
    """Builds the time items for a clicked point on the strip."""

    def __init__(self, controls: TuningControls, transport: StripTransport) -> None:
        self._controls = controls
        self._transport = transport

    def entries(
        self, t_sec: float, tolerance_sec: float, *, commands: bool
    ) -> tuple[ContextMenuEntry, ...]:
        """Items at *t_sec*; *commands* adds Undo, Redo, and the timeline commands."""
        time_items = self._time_items(t_sec, tolerance_sec)
        if not commands:
            return time_items
        return (
            *time_items,
            CONTEXT_SEPARATOR,
            *self._history_items(),
            CONTEXT_SEPARATOR,
            *self._command_items(),
        )

    def _time_items(
        self, t_sec: float, tolerance_sec: float
    ) -> tuple[ContextMenuEntry, ...]:
        transport = self._transport
        markers = self._controls.song_markers
        recording = bool(self._controls.session.timeline.recording)

        def play_from_here() -> None:
            transport.seek_to(t_sec)
            if transport.paused:
                transport.toggle_transport()

        items: list[ContextMenuEntry] = [
            ContextMenuItem(
                id="timeline.time.seek",
                label="Seek here",
                run=lambda: transport.seek_to(t_sec),
            ),
            ContextMenuItem(
                id="timeline.time.play",
                label="Play from here",
                run=play_from_here,
            ),
            CONTEXT_SEPARATOR,
            ContextMenuItem(
                id="timeline.time.drop_marker",
                label="Drop song marker here",
                run=lambda: markers.drop_at(t_sec),
                enabled=not recording,
                shortcut="Ctrl+Enter",
                hint="Stop recording to drop markers" if recording else None,
            ),
        ]
        index = markers.marker_near(t_sec, tolerance_sec)
        if index is not None:
            marker_t = self._controls.session.song_markers.markers[index].time
            items.append(
                ContextMenuItem(
                    id="timeline.time.delete_marker",
                    label=f"Delete marker {format_marker_time(marker_t)}...",
                    run=lambda: markers.prompt_delete(index),
                )
            )
        return tuple(items)

    def _history_items(self) -> tuple[ContextMenuItem, ...]:
        controls = self._controls
        history = controls.timeline_history
        ctx = command_context(controls)
        undo_label = history.undo_label
        redo_label = history.redo_label
        return (
            command_menu_item(
                command_by_id("edit.undo"),
                controls,
                label=f"Undo {undo_label}" if undo_label else "Undo",
                disabled_hint=_history_hint(ctx, ctx.timeline_can_undo, "undo"),
            ),
            command_menu_item(
                command_by_id("edit.redo"),
                controls,
                label=f"Redo {redo_label}" if redo_label else "Redo",
                disabled_hint=_history_hint(ctx, ctx.timeline_can_redo, "redo"),
            ),
        )

    def _command_items(self) -> tuple[ContextMenuItem, ...]:
        controls = self._controls
        hint = _timeline_edit_hint(command_context(controls))
        return tuple(
            command_menu_item(command_by_id(command_id), controls, disabled_hint=hint)
            for command_id in _TIMELINE_COMMAND_IDS
        )


def _timeline_edit_hint(ctx: CommandContext) -> str | None:
    if is_preset_curation_mode(ctx.editor_mode):
        return "Leave preset curation to edit the timeline"
    if ctx.timeline_locked:
        return "Unlock the timeline to edit"
    return None


def _history_hint(ctx: CommandContext, available: bool, verb: str) -> str | None:
    edit_hint = _timeline_edit_hint(ctx)
    if edit_hint is not None:
        return edit_hint
    if ctx.timeline_recording:
        return f"Stop recording to {verb}"
    if not available:
        return f"Nothing to {verb}"
    return None
