"""Per-descriptor letter, Delete, and Backspace keys."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.key_repeat import (
    add_current_preset_key_pressed,
    delete_key_pressed,
    mod_ctrl,
)
from cleave.viz.navigator import LAYER_ID_PREFIX, OVERLAY_CARD_ID_PREFIX
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import (
    PRESET_FILE_ROW_KINDS,
    apply_field_toggle_enabled,
    apply_field_toggle_solo,
    row_spec,
    row_triggers_layer_delete,
    section_lock_blocks_mutation,
)

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls


_OVERLAY_CARDS = frozenset({"opening_card", "closing_card"})


def node_header_descriptor(node_id: str) -> RowDescriptor | None:
    """Header row for a navigator id, or None when that node has no header."""
    if node_id.startswith(LAYER_ID_PREFIX):
        return RowDescriptor(
            RowKind.TRACK_HEADER, slot=node_id[len(LAYER_ID_PREFIX) :]
        )
    if node_id == "render.overlays":
        return RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    if node_id == "render.post_fx":
        return RowDescriptor(RowKind.RENDER_POST_FX_HEADER)
    if node_id == "render.pattern_mask":
        return RowDescriptor(RowKind.RENDER_PATTERN_MASK_HEADER)
    if node_id == "render.timeline":
        return RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
    if node_id.startswith(OVERLAY_CARD_ID_PREFIX):
        card = node_id[len(OVERLAY_CARD_ID_PREFIX) :]
        if card not in _OVERLAY_CARDS:
            return None
        return RowDescriptor(RowKind.RENDER_OVERLAY_CARD_HEADER, card=card)
    return None


def toggle_header_locked(controls: TuningControls, desc: RowDescriptor) -> bool:
    """Toggle the section lock for a header row. False when *desc* has none."""
    kind = desc.kind
    if kind == RowKind.TRACK_HEADER:
        slot = desc.slot
        if slot is not None:
            controls.toggle_layer_locked(slot)
        return True
    if kind in (RowKind.RENDER_OVERLAYS_HEADER, RowKind.RENDER_OVERLAY_CARD_HEADER):
        controls.toggle_render_overlay_locked()
        return True
    if kind == RowKind.RENDER_POST_FX_HEADER:
        controls.toggle_render_post_fx_locked()
        return True
    if kind == RowKind.RENDER_PATTERN_MASK_HEADER:
        controls.toggle_render_pattern_mask_locked()
        return True
    if kind == RowKind.RENDER_TIMELINE_HEADER:
        controls.toggle_render_timeline_locked()
        return True
    return False


def activate_inspector_chip(
    controls: TuningControls, chip_id: str, desc: RowDescriptor
) -> None:
    """Run the header mutation for an inspector chip click."""
    if chip_id == "enabled":
        apply_field_toggle_enabled(controls, desc)
        return
    if chip_id == "solo":
        apply_field_toggle_solo(controls, desc)
        return
    if chip_id == "lock":
        toggle_header_locked(controls, desc)


def handle_row_hotkey(
    controls: TuningControls,
    desc: RowDescriptor,
    event: pygame.event.Event,
    *,
    page_desc: RowDescriptor | None = None,
) -> bool:
    """Return True when *desc* or *page_desc* consumes *event*."""
    if _hotkey_for_descriptor(controls, desc, event):
        return True
    if page_desc is not None and page_desc != desc:
        return _hotkey_for_descriptor(controls, page_desc, event)
    return False


def _hotkey_for_descriptor(
    controls: TuningControls,
    desc: RowDescriptor,
    event: pygame.event.Event,
) -> bool:
    kind = desc.kind
    if event.key == pygame.K_BACKSPACE:
        if kind == RowKind.TRACK_PRESET_DIR:
            slot = desc.slot
            if slot is not None:
                if section_lock_blocks_mutation(controls.session, desc):
                    return True
                controls.layer_mutations.parent_directory(slot)
            return True
        return False

    if delete_key_pressed(event):
        if kind == RowKind.SONG_MARKER_ITEM:
            if desc.marker_index is not None:
                if section_lock_blocks_mutation(controls.session, desc):
                    return True
                controls.song_markers.prompt_delete(desc.marker_index)
            return True
        if kind == RowKind.TRACK_PRESET_LIST_ITEM:
            slot = desc.slot
            if slot is not None and desc.preset_index is not None:
                if section_lock_blocks_mutation(controls.session, desc):
                    return True
                controls.preset_list.prompt_delete(slot, desc.preset_index)
            return True
        if row_triggers_layer_delete(kind):
            if is_preset_curation_mode(controls.session.settings.editor_mode):
                return True
            slot = desc.slot
            if slot is not None:
                controls.layer_lifecycle.prompt_delete(slot)
            return True
        return False

    if event.key == pygame.K_m:
        if kind == RowKind.TRACK_HEADER:
            slot = desc.slot
            if slot is not None:
                if (
                    controls.session.layers[slot].locked
                    and row_spec(kind).can_enter_move_mode
                ):
                    return True
                controls.layer_lifecycle.enter_move_mode(slot)
            return True
        if kind == RowKind.TRACK_PRESET_LIST_ITEM:
            slot = desc.slot
            index = desc.preset_index
            if slot is not None and index is not None:
                if section_lock_blocks_mutation(controls.session, desc):
                    return True
                controls.preset_list.enter_move_mode(slot, index)
            return True
        return False

    if event.key == pygame.K_l:
        return toggle_header_locked(controls, desc)

    if event.key == pygame.K_e:
        return apply_field_toggle_enabled(controls, desc)

    if event.key == pygame.K_s and not mod_ctrl(event.mod):
        return apply_field_toggle_solo(controls, desc)

    if add_current_preset_key_pressed(event.key, event.mod):
        slot = desc.slot
        if (
            slot is not None
            and controls.session.layers[slot].preset_switching == "on"
            and row_spec(kind).parent_group == "track"
        ):
            if section_lock_blocks_mutation(controls.session, desc):
                return True
            controls.preset_list.add_current(slot)
            return True
        return False

    if event.key in (pygame.K_f, pygame.K_b, pygame.K_r, pygame.K_c):
        slot = desc.slot
        if slot is not None and kind in PRESET_FILE_ROW_KINDS:
            if section_lock_blocks_mutation(controls.session, desc):
                return True
            src = controls.preset_list.resolve_file_path(slot, kind, desc)
            if src is None or not src.is_file():
                return True
            if event.key == pygame.K_f:
                controls.preset_curation.prompt_favourite(slot, src)
            elif event.key == pygame.K_b:
                controls.preset_curation.prompt_blacklist(
                    slot,
                    src,
                    from_user_preset=(kind == RowKind.TRACK_PRESET_LIST_ITEM),
                    user_preset_index=desc.preset_index,
                )
            elif event.key == pygame.K_c:
                controls.preset_curation.prompt_cast(slot, src)
            else:
                controls.preset_curation.prompt_restore(slot, src)
            return True
        return False

    return False
