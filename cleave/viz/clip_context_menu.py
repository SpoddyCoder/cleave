"""Context menu section for a timeline row's selected clip.

Go to the clip's start, split it at the playhead or at the right-clicked
time, set its cut in, cut out, and role from submenus, and delete it. Each
choice calls the same ``ClipEditor`` method as the strip's clip keys and the
inspector's clip rows. Blend is left to the inspector. ``add_clip_entry`` is the row's item for adding a clip at a clicked
time in a gap. Cut out needs an end cue of the clip's own, so it is disabled
on a clip that butts the next one or runs to the song end.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from cleave.cue_roles import CUE_ROLES, CueRole
from cleave.cut_types import CUT_TYPES, CutType
from cleave.timeline import MIN_CLIP_SEC
from cleave.viz.context_menu import ContextMenuEntry, ContextMenuItem, ContextSubmenu
from cleave.viz.session import TuningSession
from cleave.viz.timeline_clip_edits import (
    ClipEditor,
    clip_edits_allowed,
    cut_out_unavailable_hint,
)

_ROLE_OPTIONS: tuple[CueRole | None, ...] = (None, *CUE_ROLES)

T = TypeVar("T")


def clip_menu_entries(
    editor: ClipEditor,
    slot: str,
    seek_to: Callable[[float], None],
    playhead_sec: Callable[[], float],
    split_at_playhead: Callable[[], None],
    split_t: float | None = None,
) -> tuple[ContextMenuEntry, ...]:
    """Items for *slot*'s selected clip, or () when it has none.

    *split_t* is the right-clicked time Split here splits at; None (a menu
    opened from the keyboard) lists it disabled.
    """
    session = editor.session
    clip = editor.selected(slot)
    if clip is None:
        return ()
    edit_hint = _edit_hint(session)
    editable = edit_hint is None
    cut_out_hint = edit_hint
    if editable and not clip.has_end_cue:
        cut_out_hint = cut_out_unavailable_hint(clip)
    playhead = playhead_sec()
    can_split = _inside(clip.start, clip.end, playhead)
    split_hint = edit_hint
    if editable and not can_split:
        split_hint = "Move the playhead inside this clip"
    can_split_here = split_t is not None and _inside(clip.start, clip.end, split_t)
    split_here_hint = edit_hint
    if editable and not can_split_here:
        split_here_hint = (
            "Right-click inside the clip to split there"
            if split_t is None
            else "Too close to the clip's edge"
        )
    start = clip.start
    return (
        ContextMenuItem(
            id="timeline.clip.go_to",
            label="Go to clip start",
            run=lambda: seek_to(start),
            shortcut="Enter",
        ),
        ContextMenuItem(
            id="timeline.clip.split",
            label="Split at playhead",
            run=split_at_playhead,
            enabled=editable and can_split,
            shortcut="Ctrl+K",
            hint=split_hint,
        ),
        ContextMenuItem(
            id="timeline.clip.split_here",
            label="Split here",
            run=lambda: editor.split_at(slot, split_t) if split_t is not None else None,
            enabled=editable and can_split_here,
            hint=split_here_hint,
        ),
        ContextSubmenu(
            id="timeline.clip.cut_in",
            label="Cut in",
            items=_options(
                "timeline.clip.cut_in",
                CUT_TYPES,
                _cut_value(clip.cut_in),
                _cut_label,
                lambda cut: editor.set_cut_in(slot, cut),
            ),
            enabled=editable,
            shortcut="C",
            hint=edit_hint,
        ),
        ContextSubmenu(
            id="timeline.clip.cut_out",
            label="Cut out",
            items=_options(
                "timeline.clip.cut_out",
                CUT_TYPES,
                _cut_value(clip.cut_out),
                _cut_label,
                lambda cut: editor.set_cut_out(slot, cut),
            ),
            enabled=editable and clip.has_end_cue,
            shortcut="Shift+C",
            hint=cut_out_hint,
        ),
        ContextSubmenu(
            id="timeline.clip.role",
            label="Role",
            items=_options(
                "timeline.clip.role",
                _ROLE_OPTIONS,
                clip.role,
                _role_label,
                lambda role: editor.set_role(slot, role),
            ),
            enabled=editable,
            shortcut="O",
            hint=edit_hint,
        ),
        ContextMenuItem(
            id="timeline.clip.delete",
            label="Delete clip",
            run=lambda: editor.delete_selected(slot),
            enabled=editable,
            shortcut="Delete",
            hint=edit_hint,
        ),
    )


def add_clip_entry(
    editor: ClipEditor,
    slot: str,
    t_sec: float,
    add_clip_at: Callable[[str, float], None],
) -> ContextMenuItem:
    """Item that adds a clip on *slot* from *t_sec*."""
    edit_hint = _edit_hint(editor.session)
    return ContextMenuItem(
        id="timeline.clip.add",
        label="Add clip here",
        run=lambda: add_clip_at(slot, t_sec),
        enabled=edit_hint is None,
        hint=edit_hint,
    )


def _inside(start: float, end: float, t_sec: float) -> bool:
    # A split leaves both parts at least MIN_CLIP_SEC long (ClipEditor.split_at).
    return start + MIN_CLIP_SEC <= t_sec <= end - MIN_CLIP_SEC


def _edit_hint(session: TuningSession) -> str | None:
    if clip_edits_allowed(session):
        return None
    if session.timeline.recording:
        return "Stop recording to edit clips"
    return "Unlock the timeline to edit clips"


def _options(
    id_prefix: str,
    options: tuple[T, ...],
    current: T,
    label: Callable[[T], str],
    write: Callable[[T], None],
) -> tuple[ContextMenuItem, ...]:
    return tuple(
        ContextMenuItem(
            id=f"{id_prefix}.{option if option is not None else 'none'}",
            label=label(option),
            run=lambda option=option: write(option),
            checked=option == current,
        )
        for option in options
    )


def _cut_value(cut: CutType | None) -> CutType:
    return cut if cut in CUT_TYPES else "none"


def _cut_label(cut: CutType) -> str:
    return cut.capitalize()


def _role_label(role: CueRole | None) -> str:
    return "None" if role is None else role.capitalize()
