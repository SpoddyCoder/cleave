"""Inspector row model for Settings, Project, and Layers.

Rows are a pure function of view state, node id, and the group sets.
Session expand flags are not read. This module does not draw.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.navigator import LAYER_ID_PREFIX
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_sections import (
    CURATION_LAYER_SECTION,
    LAYERS_SECTION,
    PROJECT_SECTION,
    SETTINGS_SECTION,
    TRACK_SECTION,
    ExpandSectionDef,
    SectionNode,
)
from cleave.viz.row_spec import row_spec
from cleave.viz.shell_focus import InspectorGroupKey, inspector_group_is_open

if TYPE_CHECKING:
    from cleave.viz.tuning_view_state import TuningViewState


@dataclass(frozen=True)
class InspectorRow:
    descriptor: RowDescriptor | None
    is_group: bool
    depth: int
    navigable: bool
    command_id: str | None = None


# Appended after the group's own leaves. Phase 1 removed these from the tree.
_GROUP_COMMANDS: dict[RowKind, str] = {
    RowKind.SETTINGS_LATENCY_COMPENSATION_HEADER: "settings.measure_latency",
    RowKind.PROJECT_RENDER_HEADER: "project.render",
}

_LEAF_COMMANDS: dict[RowKind, str] = {
    RowKind.LAYER_MANAGEMENT_ADD: "layers.add",
    RowKind.LAYER_MANAGEMENT_DELETE: "layers.delete",
}


def build_inspector_rows(
    state: TuningViewState,
    node_id: str,
    collapsed: AbstractSet[InspectorGroupKey],
    opened: AbstractSet[InspectorGroupKey] = frozenset(),
) -> tuple[InspectorRow, ...]:
    """Inspector rows for a navigator node.

    ``settings`` and ``project`` walk those sections. ``layers`` is the count
    row and Add Layer (Add Layer is omitted in preset curation). ``layer:<slot>``
    walks that slot's track section, or the curation layer section in preset
    curation, without the section header. Every other id, including render and
    song markers, is empty.
    """
    if node_id == "settings":
        section = SETTINGS_SECTION
        slot = None
    elif node_id == "project":
        section = PROJECT_SECTION
        slot = None
    elif node_id == "layers":
        section = LAYERS_SECTION
        slot = None
    elif node_id.startswith(LAYER_ID_PREFIX):
        section = (
            CURATION_LAYER_SECTION
            if is_preset_curation_mode(state.settings.editor_mode)
            else TRACK_SECTION
        )
        slot = node_id[len(LAYER_ID_PREFIX) :]
    else:
        return ()
    return rows_for_section(state, section, collapsed, opened, slot)


def rows_for_section(
    state: TuningViewState,
    section: ExpandSectionDef,
    collapsed: AbstractSet[InspectorGroupKey],
    opened: AbstractSet[InspectorGroupKey] = frozenset(),
    slot: str | None = None,
) -> tuple[InspectorRow, ...]:
    """Child rows of *section*, omitting *section*'s own header.

    Each child expandable section is a group row. Its children, including
    dynamic ones, are included only when that group is open. Conditional rows
    are included only when their predicate accepts the section probe.
    """
    rows: list[InspectorRow] = []
    _append_section_children(
        rows, section, state, collapsed, opened, depth=0, slot=slot
    )
    return tuple(rows)


def _inspector_row(
    kind: RowKind,
    *,
    slot: str | None,
    card: str | None,
    is_group: bool,
    depth: int,
) -> InspectorRow:
    return InspectorRow(
        descriptor=RowDescriptor(kind, slot=slot, card=card),
        is_group=is_group,
        depth=depth,
        navigable=row_spec(kind).navigable,
    )


def _command_row(command_id: str, depth: int) -> InspectorRow:
    return InspectorRow(
        descriptor=None,
        is_group=False,
        depth=depth,
        navigable=True,
        command_id=command_id,
    )


def _append_section_children(
    rows: list[InspectorRow],
    section: ExpandSectionDef,
    state: TuningViewState,
    collapsed: AbstractSet[InspectorGroupKey],
    opened: AbstractSet[InspectorGroupKey],
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
        collapsed,
        opened,
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
                is_group=False,
                depth=depth,
                navigable=row_spec(desc.kind).navigable,
            )
        )


def _append_group(
    rows: list[InspectorRow],
    section: ExpandSectionDef,
    state: TuningViewState,
    collapsed: AbstractSet[InspectorGroupKey],
    opened: AbstractSet[InspectorGroupKey],
    depth: int,
    slot: str | None,
) -> None:
    if section.header_kind is None:
        _append_section_children(
            rows, section, state, collapsed, opened, depth, slot
        )
        return
    section_slot = slot if section.context == "per_slot" else None
    section_card = section.card
    rows.append(
        _inspector_row(
            section.header_kind,
            slot=section_slot,
            card=section_card,
            is_group=True,
            depth=depth,
        )
    )
    key = InspectorGroupKey(section.header_kind, section_slot, section_card)
    if not inspector_group_is_open(key, collapsed, opened):
        return
    _append_section_children(
        rows, section, state, collapsed, opened, depth + 1, slot
    )
    command_id = _GROUP_COMMANDS.get(section.header_kind)
    if command_id is not None:
        rows.append(_command_row(command_id, depth + 1))


def _append_nodes(
    rows: list[InspectorRow],
    nodes: tuple[SectionNode, ...],
    state: TuningViewState,
    collapsed: AbstractSet[InspectorGroupKey],
    opened: AbstractSet[InspectorGroupKey],
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
                    is_group=False,
                    depth=depth,
                )
            )
        elif child.expand is not None:
            _append_group(
                rows, child.expand, state, collapsed, opened, depth, slot
            )
        elif child.conditional is not None:
            gated = child.conditional
            if gated.predicate(state, probe):
                _append_nodes(
                    rows,
                    gated.children,
                    state,
                    collapsed,
                    opened,
                    depth + gated.child_indent_offset,
                    slot,
                    leaf_slot,
                    leaf_card,
                    probe,
                )
        elif child.panel_anchor is not None:
            rows.append(
                _inspector_row(
                    child.panel_anchor.header_kind,
                    slot=None,
                    card=None,
                    is_group=False,
                    depth=depth,
                )
            )
