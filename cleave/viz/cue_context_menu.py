"""Context menu section for a timeline row's selected cue.

Go to the cue, and set its cut, blend, and role from submenus. Each choice
calls the same ``timeline_cue_edits`` function as the strip's cue keys and
the inspector's cue rows. A start cue (on) takes all three; an end cue (off)
takes only a cut.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from cleave.blend_modes import BLEND_MODES, BlendMode
from cleave.cue_roles import CUE_ROLES, CueRole
from cleave.cut_types import CUT_TYPES, CutType
from cleave.timeline import SlotCue, cue_editable_for_blend_role
from cleave.viz.context_menu import ContextMenuEntry, ContextMenuItem, ContextSubmenu
from cleave.viz.session import TuningSession
from cleave.viz.timeline_cue_edits import (
    cue_edits_allowed,
    selected_cue,
    set_cue_blend,
    set_cue_cut,
    set_cue_role,
)

_BLEND_OPTIONS: tuple[BlendMode | None, ...] = (None, *BLEND_MODES)
_ROLE_OPTIONS: tuple[CueRole | None, ...] = (None, *CUE_ROLES)
_END_CUE_HINT = "An end cue takes only a cut"

T = TypeVar("T")


def cue_menu_entries(
    session: TuningSession,
    slot: str,
    seek_to: Callable[[float], None],
) -> tuple[ContextMenuEntry, ...]:
    """Items for *slot*'s selected cue, or () when it has none."""
    cue = selected_cue(session, slot)
    if cue is None:
        return ()
    edit_hint = _edit_hint(session)
    editable = edit_hint is None
    on_cue = cue_editable_for_blend_role(cue)
    blend_role_hint = edit_hint if not editable else (None if on_cue else _END_CUE_HINT)
    cue_t = cue.t
    return (
        ContextMenuItem(
            id="timeline.cue.go_to",
            label="Go to cue",
            run=lambda: seek_to(cue_t),
            shortcut="Enter",
        ),
        ContextSubmenu(
            id="timeline.cue.cut",
            label="Cut",
            items=_options(
                "timeline.cue.cut",
                CUT_TYPES,
                _cut_value(cue),
                _cut_label,
                lambda cut: set_cue_cut(session, slot, cut),
            ),
            enabled=editable,
            shortcut="C",
            hint=edit_hint,
        ),
        ContextSubmenu(
            id="timeline.cue.blend",
            label="Blend",
            items=_options(
                "timeline.cue.blend",
                _BLEND_OPTIONS,
                cue.blend,
                _blend_label,
                lambda blend: set_cue_blend(session, slot, blend),
            ),
            enabled=editable and on_cue,
            shortcut="B",
            hint=blend_role_hint,
        ),
        ContextSubmenu(
            id="timeline.cue.role",
            label="Role",
            items=_options(
                "timeline.cue.role",
                _ROLE_OPTIONS,
                cue.role,
                _role_label,
                lambda role: set_cue_role(session, slot, role),
            ),
            enabled=editable and on_cue,
            shortcut="O",
            hint=blend_role_hint,
        ),
    )


def _edit_hint(session: TuningSession) -> str | None:
    if cue_edits_allowed(session):
        return None
    if session.timeline.recording:
        return "Stop recording to edit cues"
    return "Unlock the timeline to edit cues"


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


def _cut_value(cue: SlotCue) -> CutType:
    return cue.cut if cue.cut in CUT_TYPES else "none"


def _cut_label(cut: CutType) -> str:
    return cut.capitalize()


def _blend_label(blend: BlendMode | None) -> str:
    # No cue blend holds the layer's own blend mode.
    return "Layer blend" if blend is None else blend


def _role_label(role: CueRole | None) -> str:
    return "None" if role is None else role.capitalize()
