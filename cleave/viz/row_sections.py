"""Expandable section composition for the live tuning panel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from cleave.viz.row_semantics import RowDescriptor, RowKind

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


_EXPAND_SECTION_EXPANDED: dict[RowKind, Callable[[TuningViewState, str | None], bool]] = {
    RowKind.SETTINGS_HEADER: _settings_expanded,
}


SETTINGS_SECTION = ExpandSectionDef(
    header_kind=RowKind.SETTINGS_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.SETTINGS_RENDER_MODE),
        SectionNode(leaf_kind=RowKind.SETTINGS_UI_FADE),
    ),
)

ROOT_SECTION_NODES: tuple[SectionNode, ...] = (SectionNode(expand=SETTINGS_SECTION),)


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
