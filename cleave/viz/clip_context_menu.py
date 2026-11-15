"""Context menu section for a timeline row's selected clip.

Go to the clip's start, set its cut in, cut out, blend, and role from
submenus, split it at the playhead, and delete it. Each choice calls the
same ``ClipEditor`` method as the strip's clip keys and the inspector's clip
rows. ``add_clip_entry`` is the row's item for adding a clip at a clicked
time in a gap. Cut out needs an end cue of the clip's own, so it is disabled
on a clip that butts the next one or runs to the song end.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from cleave.blend_modes import BLEND_MODES, BlendMode
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

_BLEND_OPTIONS: tuple[BlendMode | None, ...] = (None, *BLEND_MODES)
_ROLE_OPTIONS: tuple[CueRole | None, ...] = (None, *CUE_ROLES)

T = TypeVar("T")


def clip_menu_entries(
    editor: ClipEditor,
    slot: str,
    seek_to: Callable[[float], None],
    playhead_sec: Callable[[], float],
    split_at_playhead: Callable[[], None],
) -> tuple[ContextMenuEntry, ...]:
    """Items for *slot*'s selected clip, or () when it has none."""
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
    can_split = clip.start + MIN_CLIP_SEC <= playhead <= clip.end - MIN_CLIP_SEC
    split_hint = edit_hint
    if editable and not can_split:
        split_hint = "Move the playhead inside this clip"
    start = clip.start
    return (
        ContextMenuItem(
            id="timeline.clip.go_to",
            label="Go to clip start",
            run=lambda: seek_to(start),
            shortcut="Enter",
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
            id="timeline.clip.blend",
            label="Blend",
            items=_options(
                "timeline.clip.blend",
                _BLEND_OPTIONS,
                clip.blend,
                _blend_label,
                lambda blend: editor.set_blend(slot, blend),
            ),
            enabled=editable,
            shortcut="B",
            hint=edit_hint,
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
            id="timeline.clip.split",
            label="Split at playhead",
            run=split_at_playhead,
            enabled=editable and can_split,
            shortcut="Ctrl+K",
            hint=split_hint,
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
    """Item that adds a clip on *slot* from *t_sec*, as a double-click there does."""
    edit_hint = _edit_hint(editor.session)
    return ContextMenuItem(
        id="timeline.clip.add",
        label="Add clip here",
        run=lambda: add_clip_at(slot, t_sec),
        enabled=edit_hint is None,
        shortcut="Double-click",
        hint=edit_hint,
    )


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


def _blend_label(blend: BlendMode | None) -> str:
    # No clip blend holds the layer's own blend mode.
    return "Layer blend" if blend is None else blend


def _role_label(role: CueRole | None) -> str:
    return "None" if role is None else role.capitalize()
