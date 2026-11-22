"""Inspector row model: the settings rows of one navigator page.

Rows are a pure function of view state and node id. This module does not draw.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.navigator import (
    LAYER_PAGE_COMPOSITING,
    LAYER_PAGE_EFFECTS,
    LAYER_PAGE_MILKDROP_PRESET,
    LAYER_PAGE_PRESET_LIST,
    LAYER_PAGE_PRESET_SWITCHING,
    layer_page_of,
    layer_slot_of,
    timeline_row_slot_of,
)
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_sections import (
    BEAT_BAR_GRID_SECTION,
    CURATION_LAYER_SECTION,
    LAYERS_SECTION,
    PROJECT_COMPOSITOR_SECTION,
    PROJECT_MILKDROP_SECTION,
    PROJECT_RESOLUTION_SECTION,
    OVERLAY_CLOSING_CARD_SECTION,
    OVERLAY_OPENING_CARD_SECTION,
    OVERLAY_PAGE_SECTION,
    PATTERN_MASK_EDGES_SECTION,
    PATTERN_MASK_PAGE_SECTION,
    PATTERN_MASK_PATTERN_SECTION,
    POST_FX_CHROMA_BOOST_SECTION,
    POST_FX_FADE_SECTION,
    POST_FX_HIGHLIGHT_ROLLOFF_SECTION,
    POST_FX_LIMITER_SECTION,
    POST_FX_PAGE_SECTION,
    SETTINGS_LATENCY_SECTION,
    SETTINGS_PREVIEW_SECTION,
    SETTINGS_UI_SECTION,
    SETTINGS_DEV_TOOLS_SECTION,
    SONG_MARKERS_SECTION,
    TIMELINE_CUTS_SECTION,
    TIMELINE_PAGE_SECTION,
    TIMELINE_ROW_SECTION,
    TRACK_COMPOSITING_SECTION,
    TRACK_EFFECTS_SECTION,
    TRACK_MILKDROP_PRESET_SECTION,
    TRACK_PRESET_LIST_SECTION,
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
    command_ids: tuple[str, ...] = ()
    status: str | None = None
    divider: bool = False
    # Drawn in the page's button group, under the divider.
    with_commands: bool = False


# A thin rule between rows. It is not a row: no cursor, no click, and less
# than a row of height.
DIVIDER_ROW = InspectorRow(
    descriptor=None,
    is_heading=False,
    depth=0,
    navigable=False,
    divider=True,
)


_PAGE_SECTIONS: dict[str, SectionDef] = {
    "settings.preview": SETTINGS_PREVIEW_SECTION,
    "settings.ui": SETTINGS_UI_SECTION,
    "settings.latency": SETTINGS_LATENCY_SECTION,
    "settings.dev_tools": SETTINGS_DEV_TOOLS_SECTION,
    "project.projectm": PROJECT_MILKDROP_SECTION,
    "project.compositor": PROJECT_COMPOSITOR_SECTION,
    "project.resolution": PROJECT_RESOLUTION_SECTION,
    "overlay": OVERLAY_PAGE_SECTION,
    "overlay.opening_card": OVERLAY_OPENING_CARD_SECTION,
    "overlay.closing_card": OVERLAY_CLOSING_CARD_SECTION,
    "post_fx": POST_FX_PAGE_SECTION,
    "post_fx.fade": POST_FX_FADE_SECTION,
    "post_fx.highlight_rolloff": POST_FX_HIGHLIGHT_ROLLOFF_SECTION,
    "post_fx.chroma_boost": POST_FX_CHROMA_BOOST_SECTION,
    "post_fx.limiter": POST_FX_LIMITER_SECTION,
    "pattern_mask": PATTERN_MASK_PAGE_SECTION,
    "pattern_mask.pattern": PATTERN_MASK_PATTERN_SECTION,
    "pattern_mask.edges": PATTERN_MASK_EDGES_SECTION,
    "timeline": TIMELINE_PAGE_SECTION,
    "timeline.grid": BEAT_BAR_GRID_SECTION,
    "timeline.cue_fades": TIMELINE_CUTS_SECTION,
    "timeline.song_markers": SONG_MARKERS_SECTION,
    "layers": LAYERS_SECTION,
}

_LAYER_PAGE_SECTIONS: dict[str, SectionDef] = {
    LAYER_PAGE_MILKDROP_PRESET: TRACK_MILKDROP_PRESET_SECTION,
    LAYER_PAGE_PRESET_SWITCHING: TRACK_PRESET_SWITCHING_SECTION,
    LAYER_PAGE_PRESET_LIST: TRACK_PRESET_LIST_SECTION,
    LAYER_PAGE_COMPOSITING: TRACK_COMPOSITING_SECTION,
    LAYER_PAGE_EFFECTS: TRACK_EFFECTS_SECTION,
}


def page_section(state: TuningViewState, node_id: str) -> SectionDef | None:
    """Section behind a navigator page, or None for a page with no rows."""
    if timeline_row_slot_of(node_id) is not None:
        return TIMELINE_ROW_SECTION
    if layer_slot_of(node_id) is None:
        return _PAGE_SECTIONS.get(node_id)
    page = layer_page_of(node_id)
    if page is not None:
        return _LAYER_PAGE_SECTIONS.get(page)
    if is_preset_curation_mode(state.settings.editor_mode):
        return CURATION_LAYER_SECTION
    return TRACK_SECTION


def page_title_command(state: TuningViewState, node_id: str) -> str | None:
    """Command id for the button on the left of the page title's icon line, if any."""
    section = page_section(state, node_id)
    if section is None or section.title_command is None:
        return None
    if section.title_command_when is None:
        return section.title_command
    slot = layer_slot_of(node_id) or timeline_row_slot_of(node_id)
    if slot is not None and slot not in state.tracks:
        return None
    probe = RowDescriptor(RowKind.TRACK_HEADER, slot=slot, card=section.card)
    if not section.title_command_when(state, probe):
        return None
    return section.title_command


def page_command_ids(state: TuningViewState, node_id: str) -> tuple[str, ...]:
    """Every button the page shows: the title command, then its button rows."""
    ids: list[str] = []
    title = page_title_command(state, node_id)
    if title is not None:
        ids.append(title)
    for row in build_inspector_rows(state, node_id):
        ids.extend(command_id for command_id in row.command_ids if command_id not in ids)
    return tuple(ids)


def build_inspector_rows(
    state: TuningViewState,
    node_id: str,
) -> tuple[InspectorRow, ...]:
    """Inspector rows for a navigator node.

    Settings, Project, and an unknown id are empty. A layer or timeline row
    not yet in *state* (added this frame, after the view state was built) is
    empty until the next frame. Button rows, and leaf rows marked
    ``with_commands``, go to the bottom of the page in their page order, under
    a divider when other rows sit above them, unless the section sets
    ``commands_divider=False``.
    """
    section = page_section(state, node_id)
    if section is None:
        return ()
    slot = layer_slot_of(node_id) or timeline_row_slot_of(node_id)
    if slot is not None and slot not in state.tracks:
        return ()
    rows: list[InspectorRow] = []
    _append_section_children(rows, section, state, 0, slot)
    return _commands_last(rows, divider=section.commands_divider)


def _commands_last(
    rows: list[InspectorRow], *, divider: bool
) -> tuple[InspectorRow, ...]:
    fields = [row for row in rows if not _in_command_group(row)]
    commands = [replace(row, depth=0) for row in rows if _in_command_group(row)]
    if divider and fields and commands:
        return (*fields, DIVIDER_ROW, *commands)
    return (*fields, *commands)


def _in_command_group(row: InspectorRow) -> bool:
    return bool(row.command_ids) or row.with_commands


def _inspector_row(
    kind: RowKind,
    *,
    slot: str | None,
    card: str | None,
    depth: int,
    with_commands: bool = False,
) -> InspectorRow:
    return InspectorRow(
        descriptor=RowDescriptor(kind, slot=slot, card=card),
        is_heading=False,
        depth=depth,
        navigable=row_spec(kind).navigable,
        with_commands=with_commands,
    )


def _command_row(
    command_ids: tuple[str, ...],
    depth: int,
    status: str | None = None,
) -> InspectorRow:
    return InspectorRow(
        descriptor=None,
        is_heading=False,
        depth=depth,
        navigable=True,
        command_ids=command_ids,
        status=status,
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
            rows.append(
                _inspector_row(
                    child.leaf_kind,
                    slot=leaf_slot,
                    card=leaf_card,
                    depth=depth,
                    with_commands=child.with_commands,
                )
            )
        elif child.commands is not None:
            rows.append(_command_row(child.commands, depth, child.status))
        elif child.divider:
            rows.append(DIVIDER_ROW)
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
