"""Inspector value colors and the timeline visibility icon."""

from __future__ import annotations

from functools import lru_cache

import pygame

from cleave.viz.icon_button import icon_box, ink_origin
from cleave.viz.material_icons import (
    VISIBILITY_GLYPH,
    VISIBILITY_OFF_GLYPH,
    material_font,
    visibility_icon_slot_width,
)
from cleave.viz.row_kinds import RowAffordance, RowDescriptor
from cleave.viz.row_spec import (
    FitStrategy,
    ROW_SPECS,
    RowPresentStyle,
    row_available,
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
    OVERLAY_SECTION_KINDS,
    PATTERN_MASK_SECTION_KINDS,
    POST_FX_LIMITER_KINDS,
    POST_FX_SECTION_KINDS,
    SECTION_SWITCH_KINDS,
    TIMELINE_SECTION_KINDS,
    TRACK_COMPOSITING_SECTION_KINDS,
)
from cleave.viz.theme import (
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

    if kind in SECTION_SWITCH_KINDS:
        return LOCKED if locked_blocked else VALUE

    if kind in TIMELINE_SECTION_KINDS:
        if not state.timeline.enabled or not row_available(state, desc):
            return DISABLED
        if affordance != RowAffordance.COMMAND:
            # Cue rows carry a slot, but the layer's live visibility does not
            # dim them.
            return LOCKED if locked_blocked else VALUE

    if affordance == RowAffordance.COMMAND:
        if (
            field is not None
            and field.present_style == RowPresentStyle.PATH_ICON
            and field.fit_strategy == FitStrategy.PATH
            and state.solo_active
        ):
            return DISABLED
        if locked_blocked:
            return LOCKED
        return VALUE

    stem = desc.slot

    if kind in OVERLAY_SECTION_KINDS:
        overlays = state.overlays
        if not (
            overlays.opening_card.runtime.enabled
            or overlays.closing_card.runtime.enabled
        ):
            return DISABLED
        if desc.card is not None and not getattr(overlays, desc.card).runtime.enabled:
            return DISABLED

    if (
        kind in POST_FX_SECTION_KINDS
        and kind not in POST_FX_LIMITER_KINDS
    ):
        if not state.post_fx.enabled:
            return DISABLED

    if kind in PATTERN_MASK_SECTION_KINDS:
        if not state.pattern_mask.enabled:
            return DISABLED

    if kind in TRACK_COMPOSITING_SECTION_KINDS:
        editor_mode = state.settings.editor_mode
        if (
            render_sections_active(editor_mode)
            and not layer_compositing_active(
                editor_mode,
                state.pattern_mask.enabled,
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
    spec = row_spec(desc.kind)
    full_line = spec.present_style in (RowPresentStyle.FULL_LINE, RowPresentStyle.LIST_ITEM)
    label = VALUE if full_line else LABEL
    return label, row_value_color_for(state, desc)


@lru_cache(maxsize=256)
def _glyph_ink(glyph: str, size: int) -> tuple[int, int, int, int]:
    """Painted bounds of *glyph* at font *size*, relative to its draw origin."""
    rects = pygame.mask.from_surface(
        material_font(size).render(glyph, True, (255, 255, 255))
    ).get_bounding_rects()
    if not rects:
        return 0, 0, 0, 0
    ink = rects[0].unionall(rects[1:])
    return ink.x, ink.y, ink.w, ink.h


def _icon_button_surface(
    glyph: str,
    color: tuple[int, int, int],
    line_height: int,
    bg: tuple[int, int, int] | None,
) -> pygame.Surface:
    """A square icon box on a row *line_height* tall, *bg* when lit.

    The glyph is drawn one box tall, so it never overhangs, and its ink is
    centred in the box (``ink_origin``), the same rule as the shell's buttons.
    """
    box = icon_box(0, (0, visibility_icon_slot_width(line_height)))
    side = int(box[2])
    surf = pygame.Surface((side, side), pygame.SRCALPHA)
    if bg is not None:
        surf.fill(bg)
    x, y = ink_origin(box, _glyph_ink(glyph, side))
    surf.blit(material_font(side).render(glyph, True, color), (int(x), int(y)))
    return surf


def render_header_toggle(
    glyph: str,
    *,
    color: tuple[int, int, int],
    line_height: int,
    bg: tuple[int, int, int] | None = None,
) -> pygame.Surface:
    """A timeline row header button: *glyph* centred in its square box, on *bg* when lit."""
    return _icon_button_surface(glyph, color, line_height, bg)


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
    bg = SOLO_BG if solo else OVERRIDE_BG if override else None
    return _icon_button_surface(glyph, color, line_height, bg)
