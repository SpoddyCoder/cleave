"""Right-click menu for a timeline strip row.

Show or hide the layer, override its visibility, release every override,
and arm it for recording. Each item calls the same ``TimelineControls``
path as its key, and a disabled item says why in its hint.
"""

from __future__ import annotations

from typing import Protocol

from cleave.viz.context_menu import (
    CONTEXT_SEPARATOR,
    ContextMenuEntry,
    ContextMenuItem,
    ContextMenuProvider,
)
from cleave.viz.session import TuningSession

# Layer number keys reach the first eight rows.
_LAYER_KEY_ROWS = 8


class TimelineRowMenuActions(Protocol):
    def row_slot(self, row: int) -> str | None: ...

    def row_visible(self, row: int) -> bool: ...

    def row_visibility_toggleable(self, row: int) -> bool: ...

    def row_arm_available(self, row: int) -> bool: ...

    def toggle_row_visibility(self, row: int) -> None: ...

    def toggle_override(self, slot: str) -> None: ...

    def release_all_overrides(self) -> None: ...

    def toggle_arm_row(self, row: int) -> None: ...


def timeline_row_menu(
    actions: TimelineRowMenuActions,
    session: TuningSession,
    row: int,
) -> ContextMenuProvider:
    """Provider for *row*'s menu; empty once the row has no layer."""

    def entries() -> tuple[ContextMenuEntry, ...]:
        return timeline_row_menu_entries(actions, session, row)

    return entries


def timeline_row_menu_entries(
    actions: TimelineRowMenuActions,
    session: TuningSession,
    row: int,
) -> tuple[ContextMenuEntry, ...]:
    slot = actions.row_slot(row)
    if slot is None:
        return ()
    tl = session.timeline
    recording = bool(tl.recording)
    overridden = slot in tl.override_slots

    toggleable = actions.row_visibility_toggleable(row)
    if toggleable:
        visibility_hint = None
    elif recording:
        visibility_hint = "Arm this row to record show / hide"
    else:
        visibility_hint = "Turn on Override visibility to show or hide by hand"
    visibility = ContextMenuItem(
        id="timeline.row.visibility",
        label="Hide layer" if actions.row_visible(row) else "Show layer",
        run=lambda: actions.toggle_row_visibility(row),
        enabled=toggleable,
        shortcut=str(row + 1) if row < _LAYER_KEY_ROWS else None,
        hint=visibility_hint,
    )

    override = ContextMenuItem(
        id="timeline.row.override",
        label="Override visibility",
        run=lambda: actions.toggle_override(slot),
        enabled=not recording,
        checked=overridden,
        shortcut="Shift+Enter",
        hint="Stop recording to change overrides" if recording else None,
    )

    any_override = bool(tl.override_slots)
    if recording:
        release_hint: str | None = "Stop recording to change overrides"
    elif not any_override:
        release_hint = "No row is overridden"
    else:
        release_hint = None
    release_all = ContextMenuItem(
        id="timeline.row.release_overrides",
        label="Release all overrides",
        run=actions.release_all_overrides,
        enabled=any_override and not recording,
        hint=release_hint,
    )

    can_arm = actions.row_arm_available(row)
    arm = ContextMenuItem(
        id="timeline.row.arm",
        label="Arm for recording",
        run=lambda: actions.toggle_arm_row(row),
        enabled=can_arm,
        checked=slot in tl.armed_slots,
        shortcut="A",
        hint=None if can_arm else "Unlock the timeline to arm",
    )

    return (
        visibility,
        CONTEXT_SEPARATOR,
        override,
        release_all,
        CONTEXT_SEPARATOR,
        arm,
    )
