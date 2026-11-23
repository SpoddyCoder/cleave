"""Right-click menu for a preset row in the inspector or the preset browser.

The directory row offers Browse presets and a Jump to directory submenu of the
library collections (favourites, roles, blacklisted). A preset list entry
offers Audition; Cut, Copy, a Paste submenu (over, before, after), and
Duplicate; Replace with (the browser), a Current preset submenu (replace this
entry, insert after it, add to the end of the list); Populate and Clear list
(after a confirmation); Move up and down, and Remove; then Favourite,
Blacklist, and a Role submenu. The layer's current preset row offers Browse
presets, Copy and Paste, Add to preset list, and the same curation items. A
preset in the browser offers Copy and the curation items. A right-click on the
Preset List page away from any entry (the only way in while the list is
empty) offers Paste at the end of the list, Add current preset, Populate, and
Clear list. Each item calls the same path as its key, and a disabled item
says why in its hint.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from cleave.cue_roles import CUE_ROLES, CueRole
from cleave.preset_library import COLLECTION_LABEL

from cleave.viz.commands import COPY, CUT, DUPLICATE, PASTE, PASTE_AFTER
from cleave.viz.context_menu import (
    ContextMenuEntry,
    ContextMenuItem,
    ContextMenuProvider,
    ContextSubmenu,
    join_groups,
)
from cleave.viz.preset_list_controls import EACH_CLIP_LIST_HINT
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
                _clipboard_items(controls, desc, slot, index),
                _fill_items(controls, desc, slot, index),
                _whole_list_items(controls, desc, slot),
                _list_edit_items(controls, desc, slot, index),
                _curate_items(controls, desc, slot),
            ]
        )
    if desc.kind is RowKind.TRACK_PRESET_DIR:
        return join_groups(
            [(_browse_item(controls, desc, slot),), _jump_items(controls, desc, slot)]
        )
    if desc.kind is RowKind.TRACK_PRESET:
        return join_groups(
            [
                (_browse_item(controls, desc, slot),),
                _preset_row_clipboard_items(controls, desc, slot),
                (_add_item(controls, desc, slot, label="Add to preset list"),),
                _curate_items(controls, desc, slot),
            ]
        )
    return ()


def preset_list_page_menu(
    controls: TuningControls, slot: str
) -> ContextMenuProvider:
    """Provider for the Preset List page itself, off any entry (or an empty list)."""
    # The heading row ignores the lock; an entry's kind carries the list's.
    desc = RowDescriptor(RowKind.TRACK_PRESET_LIST_ITEM, slot=slot)

    def entries() -> tuple[ContextMenuEntry, ...]:
        if slot not in controls.session.layers:
            return ()
        clipboard = controls.preset_clipboard
        if section_lock_blocks_mutation(controls.session, desc):
            paste_hint: str | None = _LOCK_HINT
        else:
            paste_hint = clipboard.paste_hint()
        return join_groups(
            [
                (
                    ContextMenuItem(
                        id="preset.paste_end",
                        label="Paste",
                        run=lambda: clipboard.paste_at_end(slot),
                        enabled=paste_hint is None,
                        hint=paste_hint,
                    ),
                ),
                (_add_item(controls, desc, slot, label="Add current preset"),),
                _whole_list_items(controls, desc, slot),
            ]
        )

    return entries


def browser_preset_menu(
    controls: TuningControls, slot: str, path: Path
) -> ContextMenuProvider:
    """Provider for a preset listed in the preset browser."""
    desc = RowDescriptor(RowKind.TRACK_PRESET, slot=slot)

    def entries() -> tuple[ContextMenuEntry, ...]:
        if slot not in controls.session.layers:
            return ()
        copy = ContextMenuItem(
            id="preset.copy",
            label="Copy",
            run=lambda: controls.preset_clipboard.copy_path(path),
            shortcut=COPY.shortcut,
        )
        return join_groups([(copy,), _curate_path_items(controls, desc, slot, path)])

    return entries


def _browse_item(
    controls: TuningControls, desc: RowDescriptor, slot: str
) -> ContextMenuItem:
    locked = section_lock_blocks_mutation(controls.session, desc)
    return ContextMenuItem(
        id="preset.browse",
        label="Browse presets…",
        run=lambda: controls.preset_browser.open(slot),
        enabled=not locked,
        hint=_LOCK_HINT if locked else None,
    )


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
            label="Remove from list",
            run=lambda: preset_list.remove(slot, index),
            enabled=not locked and _length_hint(controls, slot) is None,
            shortcut="Delete",
            hint=_LOCK_HINT if locked else _length_hint(controls, slot),
        ),
    )


def _clear_item(
    controls: TuningControls, desc: RowDescriptor, slot: str
) -> ContextMenuItem:
    if section_lock_blocks_mutation(controls.session, desc):
        hint: str | None = _LOCK_HINT
    elif not controls.session.layers[slot].preset_list:
        hint = "The list is already empty"
    else:
        hint = _length_hint(controls, slot)
    return ContextMenuItem(
        id="preset.clear",
        label="Clear list…",
        run=lambda: controls.preset_list.prompt_clear(slot),
        enabled=hint is None,
        hint=hint,
    )


def _clipboard_items(
    controls: TuningControls, desc: RowDescriptor, slot: str, index: int
) -> tuple[ContextMenuEntry, ...]:
    """Cut, Copy, a Paste submenu, and Duplicate for list entry *index*."""
    hint = _LOCK_HINT if section_lock_blocks_mutation(controls.session, desc) else None
    resize_hint = hint if hint is not None else _length_hint(controls, slot)
    clipboard = controls.preset_clipboard
    return (
        ContextMenuItem(
            id="preset.cut",
            label="Cut",
            run=lambda: clipboard.cut_entry(slot, index),
            enabled=resize_hint is None,
            shortcut=CUT.shortcut,
            hint=resize_hint,
        ),
        ContextMenuItem(
            id="preset.copy",
            label="Copy",
            run=lambda: clipboard.copy_entry(slot, index),
            shortcut=COPY.shortcut,
        ),
        _paste_submenu(controls, desc, slot, index),
        ContextMenuItem(
            id="preset.duplicate",
            label="Duplicate",
            run=lambda: controls.preset_list.duplicate(slot, index),
            enabled=resize_hint is None,
            shortcut=DUPLICATE.shortcut,
            hint=resize_hint,
        ),
    )


def _length_hint(controls: TuningControls, slot: str) -> str | None:
    """Why the list cannot gain or lose an entry: it holds one preset per clip."""
    if controls.preset_list.length_fixed(slot):
        return EACH_CLIP_LIST_HINT
    return None


def _paste_submenu(
    controls: TuningControls, desc: RowDescriptor, slot: str, index: int
) -> ContextSubmenu:
    """Paste over, before, and after list entry *index*."""
    clipboard = controls.preset_clipboard
    if section_lock_blocks_mutation(controls.session, desc):
        hint: str | None = _LOCK_HINT
    else:
        hint = clipboard.paste_hint()
    ready = hint is None
    insert_hint = _length_hint(controls, slot) if ready else hint
    can_insert = insert_hint is None
    items = (
        ContextMenuItem(
            id="preset.paste_over",
            label="Over this entry",
            run=lambda: clipboard.paste_over(slot, index),
            enabled=ready,
            shortcut=PASTE.shortcut,
            hint=hint,
        ),
        ContextMenuItem(
            id="preset.paste_before",
            label="Before this entry",
            run=lambda: clipboard.paste_before(slot, index),
            enabled=can_insert,
            hint=insert_hint,
        ),
        ContextMenuItem(
            id="preset.paste_after",
            label="After this entry",
            run=lambda: clipboard.paste_after(slot, index),
            enabled=can_insert,
            shortcut=PASTE_AFTER.shortcut,
            hint=insert_hint,
        ),
    )
    return ContextSubmenu(
        id="preset.paste", label="Paste", items=items, enabled=ready, hint=hint
    )


def _fill_items(
    controls: TuningControls, desc: RowDescriptor, slot: str, index: int
) -> tuple[ContextMenuEntry, ...]:
    """Replace with (the browser) and a Current preset submenu."""
    hint = _fill_hint(controls, desc)
    ready = hint is None
    preset_list = controls.preset_list
    current = (
        ContextMenuItem(
            id="preset.replace_current",
            label="Replace this entry",
            run=lambda: preset_list.replace_with_current(slot, index),
            enabled=ready,
            hint=hint,
        ),
        ContextMenuItem(
            id="preset.insert_current",
            label="Insert after this entry",
            run=lambda: preset_list.insert_current_after(slot, index),
            enabled=ready and _length_hint(controls, slot) is None,
            hint=_length_hint(controls, slot) if ready else hint,
        ),
        _add_item(controls, desc, slot, label="Add to end of list"),
    )
    return (
        ContextMenuItem(
            id="preset.replace_browse",
            label="Replace with…",
            run=lambda: controls.preset_browser.open(slot, replace_index=index),
            enabled=ready,
            hint=hint,
        ),
        ContextSubmenu(
            id="preset.current",
            label="Current preset",
            items=current,
            enabled=ready,
            hint=hint,
        ),
    )


def _whole_list_items(
    controls: TuningControls, desc: RowDescriptor, slot: str
) -> tuple[ContextMenuEntry, ...]:
    """Populate list and Clear list: the items that rework the whole list."""
    hint = _fill_hint(controls, desc)
    return (
        ContextMenuItem(
            id="preset.populate",
            label="Populate list…",
            run=lambda: controls.preset_list.prompt_populate(slot),
            enabled=hint is None,
            hint=hint,
        ),
        _clear_item(controls, desc, slot),
    )


def _preset_row_clipboard_items(
    controls: TuningControls, desc: RowDescriptor, slot: str
) -> tuple[ContextMenuEntry, ...]:
    """Copy the playing preset, or paste one to preview it on the layer."""
    clipboard = controls.preset_clipboard
    if section_lock_blocks_mutation(controls.session, desc):
        hint: str | None = _LOCK_HINT
    else:
        hint = clipboard.paste_hint()
    return (
        ContextMenuItem(
            id="preset.copy",
            label="Copy",
            run=lambda: clipboard.copy_current(slot),
            shortcut=COPY.shortcut,
        ),
        ContextMenuItem(
            id="preset.paste_preview",
            label="Paste",
            run=lambda: clipboard.paste_preview(slot),
            enabled=hint is None,
            shortcut=PASTE.shortcut,
            hint=hint,
        ),
    )


def _add_item(
    controls: TuningControls, desc: RowDescriptor, slot: str, *, label: str
) -> ContextMenuItem:
    hint = _fill_hint(controls, desc)
    if hint is None and controls.session.layers[slot].preset_switching != "on":
        hint = "Turn on preset switching first"
    if hint is None:
        hint = _length_hint(controls, slot)
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
    """Favourite, Blacklist, and Role for the row's preset file."""
    src = controls.preset_list.resolve_file_path(slot, desc.kind, desc)
    return _curate_path_items(controls, desc, slot, src)


def _curate_path_items(
    controls: TuningControls, desc: RowDescriptor, slot: str, src: Path | None
) -> tuple[ContextMenuEntry, ...]:
    """Favourite, Blacklist, and Role for *src*; each one undoes itself."""
    curation = controls.preset_curation
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
            label="Unblacklist" if blacklisted else "Blacklist…",
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
