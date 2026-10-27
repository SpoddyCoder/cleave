"""Inspector value colors and the timeline visibility icon."""

from __future__ import annotations

import pygame

from cleave.viz.material_icons import (
    VISIBILITY_GLYPH,
    VISIBILITY_OFF_GLYPH,
    VISIBILITY_ICON_PAD_X,
    render_glyph,
    visibility_icon_slot_width,
)
from cleave.viz.row_kinds import RowAffordance, RowDescriptor
from cleave.viz.row_spec import (
    FitStrategy,
    ROW_SPECS,
    RowPresentStyle,
    row_blocked_by_section_lock,
    row_spec,
    section_lock_blocks_mutation,
    section_locked,
)
from cleave.viz.editor_mode_controls import (
    layer_compositing_active,
    render_sections_active,
)
from cleave.viz.row_sections import (
    RENDER_OVERLAY_SECTION_KINDS,
    RENDER_PATTERN_MASK_SECTION_KINDS,
    RENDER_POST_FX_LIMITER_KINDS,
    RENDER_POST_FX_SECTION_KINDS,
    RENDER_TIMELINE_SECTION_KINDS,
    TRACK_COMPOSITING_SECTION_KINDS,
)
from cleave.viz.theme import (
    ACTION,
    DISABLED,
    HIGHLIGHT,
    LABEL,
    LOCKED,
    MOVE_MODE,
    OVERRIDE_BG,
    OVERRIDE_GLYPH,
    OVERRIDE_GLYPH_OFF,
    SOLO_BG,
    VALUE,
)
from cleave.viz.tuning_view_state import TuningViewState


def track_disabled(state: TuningViewState, slot: str) -> bool:
    return not state.tracks[slot].visible


def _descriptor_in_move_mode(state: TuningViewState, desc: RowDescriptor) -> bool:
    if desc.slot is not None and state.move_mode_slot == desc.slot:
        return True
    move = state.move_mode_preset
    if move is None:
        return False
    field = ROW_SPECS.get(desc.kind)
    return (
        field is not None
        and field.present_style == RowPresentStyle.PATH_ICON
        and desc.preset_index is not None
        and desc.slot == move[0]
        and desc.preset_index == move[1]
    )


def row_value_color_for(
    state: TuningViewState, desc: RowDescriptor
) -> tuple[int, int, int]:
    """VALUE-role color for *desc*. Shared by the inspector and timeline."""
    kind = desc.kind
    field = ROW_SPECS.get(kind)
    locked_blocked = section_locked(state, desc) and row_blocked_by_section_lock(kind)
    affordance = row_spec(kind).affordance

    if (
        affordance == RowAffordance.DISPLAY
        and field is not None
        and field.present_style == RowPresentStyle.LABELED_VALUE
    ):
        return LABEL

    if kind in RENDER_TIMELINE_SECTION_KINDS:
        if not state.render_timeline.enabled:
            return DISABLED

    if affordance == RowAffordance.ACTION:
        if (
            field is not None
            and field.present_style == RowPresentStyle.PATH_ICON
            and field.fit_strategy == FitStrategy.PATH
            and state.solo_active
        ):
            return DISABLED
        if field is not None and field.panel_label == "Delete Layer":
            if len(state.layer_z_order) == 1:
                return DISABLED
        if locked_blocked:
            return LOCKED
        return ACTION

    stem = desc.slot

    if kind in RENDER_OVERLAY_SECTION_KINDS:
        overlays = state.render_overlays
        if not (
            overlays.opening_card.runtime.enabled
            or overlays.closing_card.runtime.enabled
        ):
            return DISABLED

    if (
        kind in RENDER_POST_FX_SECTION_KINDS
        and kind not in RENDER_POST_FX_LIMITER_KINDS
    ):
        if not state.render_post_fx.enabled:
            return DISABLED

    if kind in RENDER_PATTERN_MASK_SECTION_KINDS:
        if not state.render_pattern_mask.enabled:
            return DISABLED

    if kind in TRACK_COMPOSITING_SECTION_KINDS:
        editor_mode = state.settings.editor_mode
        if (
            render_sections_active(editor_mode)
            and not layer_compositing_active(
                editor_mode,
                state.render_pattern_mask.enabled,
            )
        ):
            return DISABLED

    if (
        affordance == RowAffordance.PATH_PRESET
        and desc.preset_index is None
        and stem is not None
        and state.tracks[stem].preset_empty
    ):
        return DISABLED

    if _descriptor_in_move_mode(state, desc):
        return MOVE_MODE

    if locked_blocked:
        return LOCKED

    if stem is not None and track_disabled(state, stem):
        return DISABLED

    if (
        affordance == RowAffordance.PATH_PRESET
        and stem is not None
        and desc.preset_index is not None
        and state.tracks[stem].active_preset_list_index == desc.preset_index
    ):
        return HIGHLIGHT

    return VALUE


def inspector_field_colors(
    state: TuningViewState, desc: RowDescriptor
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Label and value colors. Locked blocked rows use LOCKED for both."""
    if section_lock_blocks_mutation(state, desc):
        return LOCKED, LOCKED
    label = (
        ACTION
        if row_spec(desc.kind).affordance is RowAffordance.ACTION
        else LABEL
    )
    return label, row_value_color_for(state, desc)


def render_visibility_icon(
    *,
    enabled: bool,
    solo: bool = False,
    override: bool = False,
    line_height: int,
) -> pygame.Surface:
    glyph = VISIBILITY_GLYPH if enabled else VISIBILITY_OFF_GLYPH
    if override:
        color = OVERRIDE_GLYPH if enabled else OVERRIDE_GLYPH_OFF
    elif enabled or solo:
        color = VALUE
    else:
        color = DISABLED
    glyph_surf = render_glyph(glyph, color=color, line_height=line_height)
    slot_w = visibility_icon_slot_width(line_height)
    surf = pygame.Surface((slot_w, line_height), pygame.SRCALPHA)
    if solo:
        pygame.draw.rect(surf, SOLO_BG, (0, 0, slot_w, line_height))
    elif override:
        pygame.draw.rect(surf, OVERRIDE_BG, (0, 0, slot_w, line_height))
    surf.blit(glyph_surf, (VISIBILITY_ICON_PAD_X, 0))
    return surf
