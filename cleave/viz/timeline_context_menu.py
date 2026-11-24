"""Right-click menu for a timeline strip row.

Override the row's visibility, release every override, arm it for
recording, and solo its layer. Each item calls the same ``TimelineControls``
path as its key, and a disabled item says why in its hint. With a clip
selected on the row, the menu opens with that clip's items
(``clip_context_menu``); a right-click in a gap opens with Add clip here
instead. Either way the clicked time's items follow (``timeline_time_menu``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from cleave.viz.context_menu import (
    CONTEXT_SEPARATOR,
    ContextMenuEntry,
    ContextMenuItem,
    ContextMenuProvider,
)
from cleave.viz.clip_context_menu import add_clip_entry, clip_menu_entries
from cleave.viz.session import TuningSession
from cleave.viz.timeline_clip_edits import ClipEditor

class TimelineRowMenuActions(Protocol):
    @property
    def clip_editor(self) -> ClipEditor: ...

    def row_slot(self, row: int) -> str | None: ...

    def row_arm_available(self, row: int) -> bool: ...

    def row_solo(self, row: int) -> bool: ...

    def toggle_row_solo(self, row: int) -> None: ...

    def toggle_override(self, slot: str) -> None: ...

    def release_all_overrides(self) -> None: ...

    def toggle_arm_row(self, row: int) -> None: ...

    def seek_to(self, t_sec: float) -> None: ...

    def add_clip_at(self, slot: str, t_sec: float) -> None: ...

    def split_at_playhead(self) -> None: ...

    def playhead_sec(self) -> float: ...

    def browse_clip_preset(self, slot: str) -> None: ...

    def browse_list_preset(self, slot: str, index: int) -> None: ...

    def convert_to_each_clip(self, slot: str) -> None: ...


def timeline_row_menu(
    actions: TimelineRowMenuActions,
    session: TuningSession,
    row: int,
    *,
    clip: bool = True,
    time_entries: Callable[[], tuple[ContextMenuEntry, ...]] | None = None,
    add_clip_t: float | None = None,
    split_t: float | None = None,
) -> ContextMenuProvider:
    """Provider for *row*'s menu; empty once the row has no layer.

    *clip* False leaves out the selected clip's items; *split_t* is the
    right-clicked time its Split here splits at. *add_clip_t* leads with Add
    clip here at that time. *time_entries* follow, above the row's own
    items.
    """

    def entries() -> tuple[ContextMenuEntry, ...]:
        return timeline_row_menu_entries(
            actions,
            session,
            row,
            clip=clip,
            time_entries=time_entries,
            add_clip_t=add_clip_t,
            split_t=split_t,
        )

    return entries


def timeline_row_menu_entries(
    actions: TimelineRowMenuActions,
    session: TuningSession,
    row: int,
    *,
    clip: bool = True,
    time_entries: Callable[[], tuple[ContextMenuEntry, ...]] | None = None,
    add_clip_t: float | None = None,
    split_t: float | None = None,
) -> tuple[ContextMenuEntry, ...]:
    slot = actions.row_slot(row)
    if slot is None:
        return ()
    tl = session.timeline
    recording = bool(tl.recording)
    overridden = slot in tl.override_slots

    armed = slot in tl.armed_slots
    if recording:
        override_hint: str | None = "Stop recording to change overrides"
    elif armed:
        override_hint = "Disarm this row to override it"
    else:
        override_hint = None
    override = ContextMenuItem(
        id="timeline.row.override",
        label="Override visibility",
        run=lambda: actions.toggle_override(slot),
        enabled=override_hint is None,
        checked=overridden,
        shortcut="Shift+Enter",
        hint=override_hint,
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
        hint=None
        if can_arm
        else "Unlock the timeline to arm"
        if tl.locked
        else "Unlock the layer to arm",
    )
    solo = ContextMenuItem(
        id="timeline.row.solo",
        label="Solo layer",
        run=lambda: actions.toggle_row_solo(row),
        checked=actions.row_solo(row),
    )

    clip_entries = (
        clip_menu_entries(
            actions.clip_editor,
            slot,
            actions.seek_to,
            actions.playhead_sec,
            actions.split_at_playhead,
            split_t,
            browse_preset=lambda: actions.browse_clip_preset(slot),
            browse_list_preset=lambda index: actions.browse_list_preset(slot, index),
            convert_to_each_clip=lambda: actions.convert_to_each_clip(slot),
        )
        if clip
        else ()
    )
    add_entries: tuple[ContextMenuEntry, ...] = ()
    if add_clip_t is not None:
        add_entries = (
            add_clip_entry(actions.clip_editor, slot, add_clip_t, actions.add_clip_at),
        )
    timed = time_entries() if time_entries is not None else ()
    edit_entries = (*clip_entries, *add_entries)
    lead = (
        *edit_entries,
        *((CONTEXT_SEPARATOR,) if edit_entries and timed else ()),
        *timed,
    )
    return (
        *lead,
        *((CONTEXT_SEPARATOR,) if lead else ()),
        override,
        release_all,
        CONTEXT_SEPARATOR,
        arm,
        solo,
    )
