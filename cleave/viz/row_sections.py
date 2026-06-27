"""Expandable section composition for the live tuning panel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from cleave.effects.registry import effect_roster
from cleave.viz.row_semantics import PRESET_SWITCHING_SUBMENU_KINDS, RowDescriptor, RowKind

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls
    from cleave.viz.tuning_view_state import TuningViewState


def expand_arrow_glyph(expanded: bool) -> str:
    return "▼" if expanded else "▶"


ExpandToggleFn = Callable[["TuningControls", str | None, bool], None]
PanelAnchorToggleFn = Callable[["TuningControls", bool], None]


def _toggle_settings(controls: TuningControls, _slot: str | None, forward: bool) -> None:
    controls._settings.set_expanded(forward)


def _toggle_render_overlay(controls: TuningControls, _slot: str | None, forward: bool) -> None:
    controls._render_overlay.set_expanded(forward)


def _toggle_render_overlay_title(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._render_overlay.set_title_expanded(forward)


def _toggle_render_overlay_body(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._render_overlay.set_body_expanded(forward)


def _toggle_render_post_fx(controls: TuningControls, _slot: str | None, forward: bool) -> None:
    controls._render_post_fx.set_expanded(forward)


def _toggle_track_header(controls: TuningControls, slot: str | None, forward: bool) -> None:
    if slot is None:
        return
    controls._set_expanded(slot, forward)


def _toggle_preset_switching(controls: TuningControls, slot: str | None, forward: bool) -> None:
    if slot is None:
        return
    controls._set_preset_switching_expanded(slot, forward)


def _toggle_effects_header(controls: TuningControls, slot: str | None, forward: bool) -> None:
    if slot is None:
        return
    controls._set_effects_expanded(slot, forward)


EXPAND_TOGGLE_BY_HEADER: dict[RowKind, ExpandToggleFn] = {
    RowKind.SETTINGS_HEADER: _toggle_settings,
    RowKind.TRACK_HEADER: _toggle_track_header,
    RowKind.TRACK_PRESET_SWITCHING: _toggle_preset_switching,
    RowKind.TRACK_EFFECTS_HEADER: _toggle_effects_header,
    RowKind.RENDER_OVERLAY_HEADER: _toggle_render_overlay,
    RowKind.RENDER_OVERLAY_TITLE_HEADER: _toggle_render_overlay_title,
    RowKind.RENDER_OVERLAY_BODY_HEADER: _toggle_render_overlay_body,
    RowKind.RENDER_POST_FX_HEADER: _toggle_render_post_fx,
}

EXPAND_HEADER_KINDS = frozenset(EXPAND_TOGGLE_BY_HEADER)


def _open_timeline_panel(controls: TuningControls, forward: bool) -> None:
    if forward:
        controls._open_timeline_panel()
    else:
        controls.close_timeline_panel()


PANEL_ANCHOR_TOGGLE_BY_HEADER: dict[RowKind, PanelAnchorToggleFn] = {
    RowKind.RENDER_TIMELINE_HEADER: _open_timeline_panel,
}

PANEL_ANCHOR_HEADER_KINDS = frozenset(PANEL_ANCHOR_TOGGLE_BY_HEADER)


def apply_expand_toggle(
    controls: TuningControls,
    header_kind: RowKind,
    slot: str | None,
    forward: bool,
) -> bool:
    handler = EXPAND_TOGGLE_BY_HEADER.get(header_kind)
    if handler is None:
        return False
    handler(controls, slot, forward)
    return True


def apply_panel_anchor_toggle(
    controls: TuningControls,
    header_kind: RowKind,
    forward: bool,
) -> bool:
    handler = PANEL_ANCHOR_TOGGLE_BY_HEADER.get(header_kind)
    if handler is None:
        return False
    handler(controls, forward)
    return True


@dataclass(frozen=True)
class SectionNode:
    """Tree node: either a RowKind leaf or a nested ExpandSectionDef."""

    leaf_kind: RowKind | None = None
    expand: ExpandSectionDef | None = None

    def __post_init__(self) -> None:
        if self.leaf_kind is None and self.expand is None:
            raise ValueError("SectionNode requires leaf_kind or expand")
        if self.leaf_kind is not None and self.expand is not None:
            raise ValueError("SectionNode cannot set both leaf_kind and expand")


@dataclass(frozen=True)
class ExpandSectionDef:
    header_kind: RowKind
    context: Literal["global", "per_slot"]
    children: tuple[SectionNode, ...] = ()
    collapse_on_disable: bool = False


def _settings_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.settings.expanded


def _render_overlay_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.render_overlay.expanded


def _render_overlay_title_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.render_overlay.title_expanded


def _render_overlay_body_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.render_overlay.body_expanded


def _render_post_fx_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.render_post_fx.expanded


def _track_header_expanded(state: TuningViewState, slot: str | None) -> bool:
    if slot is None:
        return True
    return state.tracks[slot].expanded


def _track_preset_switching_expanded(state: TuningViewState, slot: str | None) -> bool:
    if slot is None:
        return True
    return state.tracks[slot].preset_switching_expanded


def _track_effects_expanded(state: TuningViewState, slot: str | None) -> bool:
    if slot is None:
        return True
    return state.tracks[slot].effects_expanded


_EXPAND_SECTION_EXPANDED: dict[RowKind, Callable[[TuningViewState, str | None], bool]] = {
    RowKind.SETTINGS_HEADER: _settings_expanded,
    RowKind.RENDER_OVERLAY_HEADER: _render_overlay_expanded,
    RowKind.RENDER_OVERLAY_TITLE_HEADER: _render_overlay_title_expanded,
    RowKind.RENDER_OVERLAY_BODY_HEADER: _render_overlay_body_expanded,
    RowKind.RENDER_POST_FX_HEADER: _render_post_fx_expanded,
    RowKind.TRACK_HEADER: _track_header_expanded,
    RowKind.TRACK_PRESET_SWITCHING: _track_preset_switching_expanded,
    RowKind.TRACK_EFFECTS_HEADER: _track_effects_expanded,
}


SETTINGS_SECTION = ExpandSectionDef(
    header_kind=RowKind.SETTINGS_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.SETTINGS_RENDER_MODE),
        SectionNode(leaf_kind=RowKind.SETTINGS_UI_FADE),
    ),
)

RENDER_OVERLAY_TITLE_SECTION = ExpandSectionDef(
    header_kind=RowKind.RENDER_OVERLAY_TITLE_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.RENDER_OVERLAY_TITLE_FONT),
        SectionNode(leaf_kind=RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE),
        SectionNode(leaf_kind=RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM),
    ),
)

RENDER_OVERLAY_BODY_SECTION = ExpandSectionDef(
    header_kind=RowKind.RENDER_OVERLAY_BODY_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.RENDER_OVERLAY_BODY_FONT),
        SectionNode(leaf_kind=RowKind.RENDER_OVERLAY_BODY_FONT_SIZE),
    ),
)

RENDER_OVERLAY_SECTION = ExpandSectionDef(
    header_kind=RowKind.RENDER_OVERLAY_HEADER,
    context="global",
    collapse_on_disable=True,
    children=(
        SectionNode(leaf_kind=RowKind.RENDER_OVERLAY_POSITION),
        SectionNode(leaf_kind=RowKind.RENDER_OVERLAY_OPACITY),
        SectionNode(leaf_kind=RowKind.RENDER_OVERLAY_BORDER_WIDTH),
        SectionNode(leaf_kind=RowKind.RENDER_OVERLAY_START_DELAY),
        SectionNode(leaf_kind=RowKind.RENDER_OVERLAY_DISPLAY_TIME),
        SectionNode(expand=RENDER_OVERLAY_TITLE_SECTION),
        SectionNode(expand=RENDER_OVERLAY_BODY_SECTION),
    ),
)

RENDER_POST_FX_SECTION = ExpandSectionDef(
    header_kind=RowKind.RENDER_POST_FX_HEADER,
    context="global",
    collapse_on_disable=True,
    children=(
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_FADE_IN),
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_FADE_OUT),
    ),
)

TRACK_PRESET_SWITCHING_SECTION = ExpandSectionDef(
    header_kind=RowKind.TRACK_PRESET_SWITCHING,
    context="per_slot",
    children=tuple(
        SectionNode(leaf_kind=kind) for kind in sorted(PRESET_SWITCHING_SUBMENU_KINDS, key=lambda k: k.name)
    ),
)

TRACK_EFFECTS_SECTION = ExpandSectionDef(
    header_kind=RowKind.TRACK_EFFECTS_HEADER,
    context="per_slot",
    children=(),
)

TRACK_SECTION = ExpandSectionDef(
    header_kind=RowKind.TRACK_HEADER,
    context="per_slot",
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_DIR),
        SectionNode(leaf_kind=RowKind.TRACK_PRESET),
        SectionNode(expand=TRACK_PRESET_SWITCHING_SECTION),
        SectionNode(leaf_kind=RowKind.TRACK_STEM),
        SectionNode(leaf_kind=RowKind.TRACK_BEAT),
        SectionNode(leaf_kind=RowKind.TRACK_BLEND),
        SectionNode(leaf_kind=RowKind.TRACK_OPACITY),
        SectionNode(expand=TRACK_EFFECTS_SECTION),
        SectionNode(leaf_kind=RowKind.LAYER_MANAGEMENT_DELETE),
    ),
)

ROOT_SECTION_NODES: tuple[SectionNode, ...] = (SectionNode(expand=SETTINGS_SECTION),)

RENDER_SECTION_NODES: tuple[SectionNode, ...] = (
    SectionNode(expand=RENDER_OVERLAY_SECTION),
    SectionNode(expand=RENDER_POST_FX_SECTION),
)

GLOBAL_EXPAND_SECTIONS: tuple[ExpandSectionDef, ...] = (
    SETTINGS_SECTION,
    RENDER_OVERLAY_SECTION,
    RENDER_POST_FX_SECTION,
)


def expand_section_expanded(
    state: TuningViewState,
    section: ExpandSectionDef,
    slot: str | None,
) -> bool:
    reader = _EXPAND_SECTION_EXPANDED.get(section.header_kind)
    if reader is None:
        return True
    return reader(state, slot)


def leaf_kinds_in_expand_section(section: ExpandSectionDef) -> frozenset[RowKind]:
    kinds: set[RowKind] = set()
    for child in section.children:
        if child.leaf_kind is not None:
            kinds.add(child.leaf_kind)
        if child.expand is not None:
            kinds |= leaf_kinds_in_expand_section(child.expand)
    return frozenset(kinds)


SETTINGS_SECTION_LEAF_KINDS = leaf_kinds_in_expand_section(SETTINGS_SECTION)


def _find_expand_ancestor(
    section: ExpandSectionDef,
    kind: RowKind,
) -> ExpandSectionDef | None:
    for child in section.children:
        if child.leaf_kind == kind:
            return section
        if child.expand is not None and _find_expand_ancestor(child.expand, kind) is not None:
            return child.expand
    return None


def expand_section_sub_row_visible(
    state: TuningViewState,
    desc: RowDescriptor,
    section: ExpandSectionDef,
) -> bool | None:
    kind = desc.kind
    if kind == section.header_kind:
        return True
    slot = desc.slot if section.context == "per_slot" else None
    if kind not in leaf_kinds_in_expand_section(section):
        return None
    ancestor = _find_expand_ancestor(section, kind)
    if ancestor is None:
        return None
    if not expand_section_expanded(state, section, slot):
        return False
    if ancestor is not section and not expand_section_expanded(state, ancestor, slot):
        return False
    return True


def sub_row_expand_visible(state: TuningViewState, desc: RowDescriptor) -> bool:
    for section in GLOBAL_EXPAND_SECTIONS:
        visible = expand_section_sub_row_visible(state, desc, section)
        if visible is not None:
            return visible
    if desc.slot is not None:
        visible = expand_section_sub_row_visible(state, desc, TRACK_SECTION)
        if visible is not None:
            return visible
    return True


def append_expand_section_rows(
    row_list: list[RowDescriptor],
    section: ExpandSectionDef,
    state: TuningViewState,
    slot: str | None = None,
) -> None:
    section_slot = slot if section.context == "per_slot" else None
    row_list.append(RowDescriptor(section.header_kind, slot=section_slot))
    if not expand_section_expanded(state, section, slot):
        return
    for child in section.children:
        if child.leaf_kind is not None:
            row_list.append(RowDescriptor(child.leaf_kind, slot=section_slot))
        elif child.expand is not None:
            append_expand_section_rows(row_list, child.expand, state, slot)


def append_preset_switching_section_rows(
    row_list: list[RowDescriptor],
    state: TuningViewState,
    slot: str,
) -> None:
    block = state.tracks[slot]
    row_list.append(RowDescriptor(RowKind.TRACK_PRESET_SWITCHING, slot=slot))
    if not block.preset_switching_expanded:
        return
    row_list.append(RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_MODE, slot=slot))
    if block.preset_switching != "projectm":
        return
    row_list.append(RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_SCOPE, slot=slot))
    row_list.append(RowDescriptor(RowKind.TRACK_PRESET_DURATION, slot=slot))
    row_list.append(RowDescriptor(RowKind.TRACK_SOFT_CUT_DURATION, slot=slot))
    row_list.append(RowDescriptor(RowKind.TRACK_EASTER_EGG, slot=slot))
    row_list.append(RowDescriptor(RowKind.TRACK_PRESET_START_CLEAN, slot=slot))
    row_list.append(RowDescriptor(RowKind.TRACK_HARD_CUT_ENABLED, slot=slot))
    if block.hard_cut_enabled:
        row_list.append(RowDescriptor(RowKind.TRACK_HARD_CUT_DURATION, slot=slot))
        row_list.append(RowDescriptor(RowKind.TRACK_HARD_CUT_SENSITIVITY, slot=slot))


def append_effects_section_rows(
    row_list: list[RowDescriptor],
    state: TuningViewState,
    slot: str,
) -> None:
    block = state.tracks[slot]
    row_list.append(RowDescriptor(RowKind.TRACK_EFFECTS_HEADER, slot=slot))
    if not block.effects_expanded:
        return
    for effect_def in effect_roster(block.stem):
        row_list.append(
            RowDescriptor(
                RowKind.TRACK_EFFECT,
                slot=slot,
                effect_id=effect_def.effect_id,
                driver_slug=effect_def.driver_slug,
            )
        )


def append_track_section_rows(
    row_list: list[RowDescriptor],
    state: TuningViewState,
    slot: str,
) -> None:
    block = state.tracks[slot]
    row_list.append(RowDescriptor(RowKind.TRACK_HEADER, slot=slot))
    if not block.expanded:
        return
    row_list.append(RowDescriptor(RowKind.TRACK_PRESET_DIR, slot=slot))
    row_list.append(RowDescriptor(RowKind.TRACK_PRESET, slot=slot))
    append_preset_switching_section_rows(row_list, state, slot)
    row_list.append(RowDescriptor(RowKind.TRACK_STEM, slot=slot))
    row_list.append(RowDescriptor(RowKind.TRACK_BEAT, slot=slot))
    row_list.append(RowDescriptor(RowKind.TRACK_BLEND, slot=slot))
    row_list.append(RowDescriptor(RowKind.TRACK_OPACITY, slot=slot))
    append_effects_section_rows(row_list, state, slot)
    row_list.append(RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot=slot))
