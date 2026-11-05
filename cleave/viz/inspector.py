"""Inspector row model: the settings rows of one navigator page.

Rows are a pure function of view state and node id. This module does not draw.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.navigator import (
    LAYER_PAGE_COMPOSITING,
    LAYER_PAGE_EFFECTS,
    LAYER_PAGE_PRESET_SWITCHING,
    layer_page_of,
    layer_slot_of,
)
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_sections import (
    BEAT_BAR_GRID_SECTION,
    CURATION_LAYER_SECTION,
    LAYERS_SECTION,
    PROJECT_COMPOSITOR_SECTION,
    PROJECT_MILKDROP_SECTION,
    PROJECT_RENDER_SECTION,
    OVERLAY_CLOSING_CARD_SECTION,
    OVERLAY_OPENING_CARD_SECTION,
    OVERLAY_PAGE_SECTION,
    PATTERN_MASK_SECTION,
    POST_FX_CHROMA_BOOST_SECTION,
    POST_FX_FADE_SECTION,
    POST_FX_HIGHLIGHT_ROLLOFF_SECTION,
    POST_FX_LIMITER_SECTION,
    POST_FX_PAGE_SECTION,
    SETTINGS_EDITOR_WINDOW_SECTION,
    SETTINGS_LATENCY_COMPENSATION_SECTION,
    SETTINGS_UI_SECTION,
    SONG_MARKERS_SECTION,
    TIMELINE_CUTS_SECTION,
    TIMELINE_PAGE_SECTION,
    TIMELINE_PRESETS_SECTION,
    TRACK_COMPOSITING_SECTION,
    TRACK_EFFECTS_SECTION,
    TRACK_PRESET_SWITCHING_SECTION,
    TRACK_SECTION,
    SectionDef,
    SectionNode,
)
from cleave.viz.row_spec import row_spec

if TYPE_CHECKING:
    from cleave.viz.tuning_view_state import TuningViewState


@dataclass(frozen=True)
class InspectorRow:
    descriptor: RowDescriptor | None
    is_heading: bool
    depth: int
    navigable: bool
    command_id: str | None = None


# Appended after the page's own rows.
_PAGE_COMMANDS: dict[RowKind, str] = {
    RowKind.SETTINGS_LATENCY_COMPENSATION_HEADER: "settings.measure_latency",
    RowKind.PROJECT_RENDER_HEADER: "project.render",
}

_LEAF_COMMANDS: dict[RowKind, str] = {
    RowKind.LAYER_MANAGEMENT_ADD: "layers.add",
    RowKind.LAYER_MANAGEMENT_DELETE: "layers.delete",
    RowKind.TIMELINE_PRESETS: "timeline.apply_preset",
    RowKind.TIMELINE_RESET: "timeline.reset",
    RowKind.TIMELINE_SNAP_CUES: "timeline.snap_cues",
}

_PAGE_SECTIONS: dict[str, SectionDef] = {
    "settings.editor_window": SETTINGS_EDITOR_WINDOW_SECTION,
    "settings.ui": SETTINGS_UI_SECTION,
    "settings.latency": SETTINGS_LATENCY_COMPENSATION_SECTION,
    "project.projectm": PROJECT_MILKDROP_SECTION,
    "project.compositor": PROJECT_COMPOSITOR_SECTION,
    "project.render": PROJECT_RENDER_SECTION,
    "overlay": OVERLAY_PAGE_SECTION,
    "overlay.opening_card": OVERLAY_OPENING_CARD_SECTION,
    "overlay.closing_card": OVERLAY_CLOSING_CARD_SECTION,
    "post_fx": POST_FX_PAGE_SECTION,
    "post_fx.fade": POST_FX_FADE_SECTION,
    "post_fx.highlight_rolloff": POST_FX_HIGHLIGHT_ROLLOFF_SECTION,
    "post_fx.chroma_boost": POST_FX_CHROMA_BOOST_SECTION,
    "post_fx.limiter": POST_FX_LIMITER_SECTION,
    "pattern_mask": PATTERN_MASK_SECTION,
    "timeline": TIMELINE_PAGE_SECTION,
    "timeline.grid": BEAT_BAR_GRID_SECTION,
    "timeline.cue_fades": TIMELINE_CUTS_SECTION,
    "timeline.song_markers": SONG_MARKERS_SECTION,
    "timeline.preset": TIMELINE_PRESETS_SECTION,
    "layers": LAYERS_SECTION,
}

_LAYER_PAGE_SECTIONS: dict[str, SectionDef] = {
    LAYER_PAGE_PRESET_SWITCHING: TRACK_PRESET_SWITCHING_SECTION,
    LAYER_PAGE_COMPOSITING: TRACK_COMPOSITING_SECTION,
    LAYER_PAGE_EFFECTS: TRACK_EFFECTS_SECTION,
}


def page_section(state: TuningViewState, node_id: str) -> SectionDef | None:
    """Section behind a navigator page, or None for a page with no rows."""
    if layer_slot_of(node_id) is None:
        return _PAGE_SECTIONS.get(node_id)
    page = layer_page_of(node_id)
    if page is not None:
        return _LAYER_PAGE_SECTIONS.get(page)
    if is_preset_curation_mode(state.settings.editor_mode):
        return CURATION_LAYER_SECTION
    return TRACK_SECTION


def build_inspector_rows(
    state: TuningViewState,
    node_id: str,
) -> tuple[InspectorRow, ...]:
    """Inspector rows for a navigator node.

    Settings, Project, and an unknown id are empty.
    """
    section = page_section(state, node_id)
    if section is None:
        return ()
    rows: list[InspectorRow] = []
    _append_section_children(rows, section, state, 0, layer_slot_of(node_id))
    if section.header_kind in _PAGE_COMMANDS:
        rows.append(_command_row(_PAGE_COMMANDS[section.header_kind], 0))
    return tuple(rows)


def _inspector_row(
    kind: RowKind,
    *,
    slot: str | None,
    card: str | None,
    depth: int,
) -> InspectorRow:
    return InspectorRow(
        descriptor=RowDescriptor(kind, slot=slot, card=card),
        is_heading=False,
        depth=depth,
        navigable=row_spec(kind).navigable,
    )


def _command_row(command_id: str, depth: int) -> InspectorRow:
    return InspectorRow(
        descriptor=None,
        is_heading=False,
        depth=depth,
        navigable=True,
        command_id=command_id,
    )


def _append_section_children(
    rows: list[InspectorRow],
    section: SectionDef,
    state: TuningViewState,
    depth: int,
    slot: str | None,
) -> None:
    section_slot = slot if section.context == "per_slot" else None
    section_card = section.card
    probe = RowDescriptor(RowKind.TRACK_HEADER, slot=section_slot, card=section_card)
    _append_nodes(
        rows,
        section.children,
        state,
        depth,
        slot,
        section_slot,
        section_card,
        probe,
    )
    if section.append_dynamic_children is None:
        return
    dynamic: list[RowDescriptor] = []
    section.append_dynamic_children(dynamic, state, slot)
    for desc in dynamic:
        rows.append(
            InspectorRow(
                descriptor=desc,
                is_heading=False,
                depth=depth,
                navigable=row_spec(desc.kind).navigable,
            )
        )


def _append_subsection(
    rows: list[InspectorRow],
    section: SectionDef,
    state: TuningViewState,
    depth: int,
    slot: str | None,
) -> None:
    assert section.header_kind is not None
    rows.append(
        InspectorRow(
            descriptor=RowDescriptor(
                section.header_kind,
                slot=slot if section.context == "per_slot" else None,
                card=section.card,
            ),
            is_heading=True,
            depth=depth,
            navigable=False,
        )
    )
    _append_section_children(rows, section, state, depth + 1, slot)


def _append_nodes(
    rows: list[InspectorRow],
    nodes: tuple[SectionNode, ...],
    state: TuningViewState,
    depth: int,
    slot: str | None,
    leaf_slot: str | None,
    leaf_card: str | None,
    probe: RowDescriptor,
) -> None:
    for child in nodes:
        if child.leaf_kind is not None:
            command_id = _LEAF_COMMANDS.get(child.leaf_kind)
            if command_id is not None:
                rows.append(_command_row(command_id, depth))
                continue
            rows.append(
                _inspector_row(
                    child.leaf_kind,
                    slot=leaf_slot,
                    card=leaf_card,
                    depth=depth,
                )
            )
        elif child.subsection is not None:
            _append_subsection(rows, child.subsection, state, depth, slot)
        elif child.conditional is not None:
            gated = child.conditional
            if gated.predicate(state, probe):
                _append_nodes(
                    rows,
                    gated.children,
                    state,
                    depth + gated.child_indent_offset,
                    slot,
                    leaf_slot,
                    leaf_card,
                    probe,
                )
