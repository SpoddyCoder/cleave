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
from cleave.viz.navigator import (
    LAYER_PAGE_COMPOSITING,
    LAYER_PAGE_EFFECTS,
    LAYER_PAGE_PRESET_SWITCHING,
    layer_page_of,
    layer_slot_of,
    root_id,
)
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


_NODE_HEADER_KINDS: dict[str, RowKind] = {
    "settings.editor_window": RowKind.SETTINGS_EDITOR_WINDOW_HEADER,
    "settings.ui": RowKind.SETTINGS_UI_HEADER,
    "settings.latency": RowKind.SETTINGS_LATENCY_COMPENSATION_HEADER,
    "project.projectm": RowKind.PROJECT_MILKDROP_HEADER,
    "project.compositor": RowKind.PROJECT_COMPOSITOR_HEADER,
    "project.render": RowKind.PROJECT_RENDER_HEADER,
    "overlay": RowKind.RENDER_OVERLAYS_HEADER,
    "post_fx": RowKind.RENDER_POST_FX_HEADER,
    "post_fx.fade": RowKind.RENDER_POST_FX_FADE_HEADER,
    "post_fx.highlight_rolloff": RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_HEADER,
    "post_fx.chroma_boost": RowKind.RENDER_POST_FX_CHROMA_BOOST_HEADER,
    "post_fx.limiter": RowKind.RENDER_POST_FX_LIMITER_HEADER,
    "pattern_mask": RowKind.RENDER_PATTERN_MASK_HEADER,
    "timeline": RowKind.RENDER_TIMELINE_HEADER,
    "timeline.grid": RowKind.TIMELINE_BEAT_BAR_GRID_HEADER,
    "timeline.cue_fades": RowKind.TIMELINE_CUTS_HEADER,
    "timeline.song_markers": RowKind.SONG_MARKERS_HEADER,
    "timeline.preset": RowKind.TIMELINE_PRESETS_HEADER,
}

_NODE_CARDS: dict[str, str] = {
    "overlay.opening_card": "opening_card",
    "overlay.closing_card": "closing_card",
}

_LAYER_PAGE_HEADER_KINDS: dict[str, RowKind] = {
    LAYER_PAGE_PRESET_SWITCHING: RowKind.TRACK_PRESET_SWITCHING,
    LAYER_PAGE_COMPOSITING: RowKind.TRACK_COMPOSITING_HEADER,
    LAYER_PAGE_EFFECTS: RowKind.TRACK_EFFECTS_HEADER,
}


def node_header_descriptor(node_id: str) -> RowDescriptor | None:
    """Header row for a navigator page, or None when that node has no header."""
    slot = layer_slot_of(node_id)
    if slot is not None:
        page = layer_page_of(node_id)
        kind = RowKind.TRACK_HEADER if page is None else _LAYER_PAGE_HEADER_KINDS[page]
        return RowDescriptor(kind, slot=slot)
    card = _NODE_CARDS.get(node_id)
    if card is not None:
        return RowDescriptor(RowKind.RENDER_OVERLAY_CARD_HEADER, card=card)
    kind = _NODE_HEADER_KINDS.get(node_id)
    return None if kind is None else RowDescriptor(kind)


def node_control_descriptor(node_id: str) -> RowDescriptor | None:
    """Header that owns the chips and E/S/L keys for a navigator page.

    A layer, a card, and a root own their own controls. Any other page uses
    the controls of its parent.
    """
    slot = layer_slot_of(node_id)
    if slot is not None:
        return RowDescriptor(RowKind.TRACK_HEADER, slot=slot)
    if node_id in _NODE_CARDS:
        return node_header_descriptor(node_id)
    return node_header_descriptor(root_id(node_id))


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
