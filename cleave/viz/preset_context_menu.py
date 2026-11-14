"""Right-click menu for a preset row in the inspector.

The directory row offers a Jump to directory submenu of the library
collections (favourites, roles, blacklisted). A preset list entry offers Audition, Move up and down, Remove, Add current
preset, Populate, then Favourite, Blacklist, and a Role submenu. The layer's
current preset row offers Add to preset list and the same curation items.
Each item calls the same path as its key, and a disabled item says why in
its hint.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from cleave.cue_roles import CUE_ROLES, CueRole
from cleave.preset_library import COLLECTION_LABEL

from cleave.viz.context_menu import (
    ContextMenuEntry,
    ContextMenuItem,
    ContextMenuProvider,
    ContextSubmenu,
    join_groups,
)
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import section_lock_blocks_mutation

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

PRESET_MENU_KINDS = frozenset(
    {RowKind.TRACK_PRESET_DIR, RowKind.TRACK_PRESET, RowKind.TRACK_PRESET_LIST_ITEM}
)

_LOCK_HINT = "Locked: unlock to change"
_NO_PROJECT_HINT = "No project open"


def preset_row_menu(controls: TuningControls, desc: RowDescriptor) -> ContextMenuProvider:
    """Provider for the preset row *desc*; empty once the row is gone."""

    def entries() -> tuple[ContextMenuEntry, ...]:
        return preset_row_menu_entries(controls, desc)

    return entries


def preset_row_menu_entries(
    controls: TuningControls, desc: RowDescriptor
) -> tuple[ContextMenuEntry, ...]:
    slot = desc.slot
    if slot is None or slot not in controls.session.layers:
        return ()
    if desc.kind is RowKind.TRACK_PRESET_LIST_ITEM:
        index = desc.preset_index
        presets = controls.session.layers[slot].preset_list
        if index is None or not 0 <= index < len(presets):
            return ()
        return join_groups(
            [
                (_audition_item(controls, slot, index),),
                _list_edit_items(controls, desc, slot, index),
                _list_fill_items(controls, desc, slot),
                _curate_items(controls, desc, slot),
            ]
        )
    if desc.kind is RowKind.TRACK_PRESET_DIR:
        return _jump_items(controls, desc, slot)
    if desc.kind is RowKind.TRACK_PRESET:
        return join_groups(
            [
                (_add_item(controls, desc, slot, label="Add to preset list"),),
                _curate_items(controls, desc, slot),
            ]
        )
    return ()


def _jump_items(
    controls: TuningControls, desc: RowDescriptor, slot: str
) -> tuple[ContextMenuEntry, ...]:
    """Jump to directory: a submenu of the library collections."""
    playlist = controls.session.layers[slot].playlist
    collections = playlist.catalog.collections()
    if not collections:
        return ()
    locked = section_lock_blocks_mutation(controls.session, desc)
    mutations = controls.layer_mutations
    return (
        ContextSubmenu(
            id="preset.jump",
            label="Jump to directory",
            items=tuple(
                ContextMenuItem(
                    id=f"preset.jump.{collection}",
                    label=COLLECTION_LABEL[collection],
                    run=lambda collection=collection: mutations.jump_to_collection(
                        slot, collection
                    ),
                    checked=playlist.collection == collection,
                )
                for collection in collections
            ),
            enabled=not locked,
            hint=_LOCK_HINT if locked else None,
        ),
    )


def _audition_item(controls: TuningControls, slot: str, index: int) -> ContextMenuItem:
    return ContextMenuItem(
        id="preset.audition",
        label="Audition",
        run=lambda: controls.preset_list.audition(slot, index),
        shortcut="Enter",
    )


def _list_edit_items(
    controls: TuningControls, desc: RowDescriptor, slot: str, index: int
) -> tuple[ContextMenuEntry, ...]:
    locked = section_lock_blocks_mutation(controls.session, desc)
    last = len(controls.session.layers[slot].preset_list) - 1
    preset_list = controls.preset_list

    def move_hint(at_end: bool, end_hint: str) -> str | None:
        if locked:
            return _LOCK_HINT
        return end_hint if at_end else None

    return (
        ContextMenuItem(
            id="preset.move_up",
            label="Move up",
            run=lambda: preset_list.move_item(slot, index, -1),
            enabled=not locked and index > 0,
            hint=move_hint(index <= 0, "Already the first preset"),
        ),
        ContextMenuItem(
            id="preset.move_down",
            label="Move down",
            run=lambda: preset_list.move_item(slot, index, 1),
            enabled=not locked and index < last,
            hint=move_hint(index >= last, "Already the last preset"),
        ),
        ContextMenuItem(
            id="preset.remove",
            label="Remove from list...",
            run=lambda: preset_list.prompt_delete(slot, index),
            enabled=not locked,
            shortcut="Delete",
            hint=_LOCK_HINT if locked else None,
        ),
    )


def _list_fill_items(
    controls: TuningControls, desc: RowDescriptor, slot: str
) -> tuple[ContextMenuEntry, ...]:
    hint = _fill_hint(controls, desc)
    return (
        _add_item(controls, desc, slot, label="Add current preset"),
        ContextMenuItem(
            id="preset.populate",
            label="Populate...",
            run=lambda: controls.preset_list.prompt_populate(slot),
            enabled=hint is None,
            hint=hint,
        ),
    )


def _add_item(
    controls: TuningControls, desc: RowDescriptor, slot: str, *, label: str
) -> ContextMenuItem:
    hint = _fill_hint(controls, desc)
    if hint is None and controls.session.layers[slot].preset_switching != "on":
        hint = "Turn on preset switching first"
    return ContextMenuItem(
        id="preset.add_current",
        label=label,
        run=lambda: controls.preset_list.add_current(slot),
        enabled=hint is None,
        shortcut="P",
        hint=hint,
    )


def _fill_hint(controls: TuningControls, desc: RowDescriptor) -> str | None:
    if section_lock_blocks_mutation(controls.session, desc):
        return _LOCK_HINT
    if controls.preset_list.project_dir is None:
        return _NO_PROJECT_HINT
    return None


def _curate_items(
    controls: TuningControls, desc: RowDescriptor, slot: str
) -> tuple[ContextMenuEntry, ...]:
    """Favourite, Blacklist, and Role; each one undoes itself."""
    curation = controls.preset_curation
    src = controls.preset_list.resolve_file_path(slot, desc.kind, desc)
    if section_lock_blocks_mutation(controls.session, desc):
        hint: str | None = _LOCK_HINT
    elif src is None or not src.is_file():
        hint = "Preset file not found"
    else:
        hint = None
    ready = hint is None and src is not None
    favourited = ready and curation.is_favourite(src)
    blacklisted = ready and curation.is_blacklisted(src)
    role = curation.role_of(src) if ready else None

    def act(run_with_src: Callable[[Path], None]) -> None:
        if src is not None:
            run_with_src(src)

    role_options: tuple[CueRole | None, ...] = (*CUE_ROLES, None)
    return (
        ContextMenuItem(
            id="preset.favourite",
            label="Unfavourite" if favourited else "Favourite",
            run=lambda: act(curation.toggle_favourite),
            enabled=ready,
            shortcut="F",
            hint=hint,
        ),
        ContextMenuItem(
            id="preset.blacklist",
            label="Unblacklist" if blacklisted else "Blacklist...",
            run=lambda: act(lambda path: curation.toggle_blacklist(slot, path)),
            enabled=ready,
            shortcut="B",
            hint=hint,
        ),
        ContextSubmenu(
            id="preset.role",
            label="Role",
            items=tuple(
                ContextMenuItem(
                    id=f"preset.role.{option if option is not None else 'none'}",
                    label="None" if option is None else option.capitalize(),
                    run=lambda option=option: act(
                        lambda path: curation.set_role(path, option)
                    ),
                    checked=option == role,
                )
                for option in role_options
            ),
            enabled=ready,
            shortcut="C",
            hint=hint,
        ),
    )
