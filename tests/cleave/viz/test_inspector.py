"""Inspector row model: Settings, Project, collapse, and conditional rows."""

from __future__ import annotations

from cleave.viz.focus_nav import MainFocus
from cleave.viz.inspector import build_inspector_rows, rows_for_section
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_sections import (
    PROJECT_SECTION,
    RENDER_PATTERN_MASK_SECTION,
    SETTINGS_SECTION,
    ExpandSectionDef,
)
from cleave.viz.row_spec import row_spec
from cleave.viz.tuning_view_state import TuningViewState


def _view_state() -> TuningViewState:
    return TuningViewState(
        layer_z_order=(),
        tracks={},
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)),
        move_mode_slot=None,
    )


def _kinds(rows: tuple) -> list[RowKind]:
    return [row.descriptor.kind for row in rows if row.descriptor is not None]


def _leaf_descriptors(section: ExpandSectionDef) -> tuple[RowDescriptor, ...]:
    leaves: list[RowDescriptor] = []
    for child in section.children:
        assert child.leaf_kind is not None
        leaves.append(RowDescriptor(child.leaf_kind))
    return tuple(leaves)


def _group_leaves(rows: tuple, header: RowKind) -> tuple:
    found = False
    leaves = []
    for row in rows:
        if row.is_group and row.descriptor.kind == header:
            found = True
            continue
        if not found:
            continue
        if row.is_group:
            break
        leaves.append(row)
    assert found
    return tuple(leaves)


def test_project_builds_three_groups_matching_section_children() -> None:
    state = _view_state()
    rows = build_inspector_rows(state, "project", frozenset())
    assert rows == rows_for_section(state, PROJECT_SECTION, frozenset())

    expands = tuple(child.expand for child in PROJECT_SECTION.children)
    assert len(expands) == 3
    assert all(section is not None for section in expands)

    groups = tuple(row for row in rows if row.is_group)
    assert tuple(row.descriptor.kind for row in groups) == tuple(
        section.header_kind for section in expands if section is not None
    )
    assert all(row.depth == 0 and row.is_group for row in groups)
    for group in groups:
        assert group.navigable is row_spec(group.descriptor.kind).navigable

    for section in expands:
        assert section is not None
        leaves = _group_leaves(rows, section.header_kind)
        fields = tuple(row for row in leaves if row.descriptor is not None)
        commands = tuple(row.command_id for row in leaves if row.command_id)
        assert tuple(row.descriptor for row in fields) == _leaf_descriptors(section)
        if section.header_kind == RowKind.PROJECT_RENDER_HEADER:
            assert commands == ("project.render",)
        else:
            assert commands == ()
        assert all(row.depth == 1 and not row.is_group for row in leaves)
        for leaf in leaves:
            if leaf.descriptor is None:
                assert leaf.navigable
                continue
            assert leaf.navigable is row_spec(leaf.descriptor.kind).navigable


def test_collapsed_group_hides_children_and_keeps_header() -> None:
    state = _view_state()
    header = RowKind.PROJECT_COMPOSITOR_HEADER
    rows = build_inspector_rows(state, "project", frozenset({header}))
    kinds = _kinds(rows)

    assert header in kinds
    assert RowKind.PROJECT_COMPOSITOR_HDR not in kinds
    group = next(row for row in rows if row.descriptor.kind == header)
    assert group.is_group is True
    assert group.depth == 0
    assert RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY in kinds
    assert RowKind.PROJECT_RENDER_OUTPUT in kinds


def test_conditional_rows_follow_pattern_mask_predicate() -> None:
    state = _view_state()
    assert state.render_pattern_mask.type != "plasma"
    hidden = rows_for_section(state, RENDER_PATTERN_MASK_SECTION, frozenset())
    hidden_kinds = _kinds(hidden)
    assert RowKind.RENDER_PATTERN_MASK_SEED not in hidden_kinds
    assert RowKind.RENDER_PATTERN_MASK_TYPE in hidden_kinds

    state.render_pattern_mask.type = "plasma"
    shown = rows_for_section(state, RENDER_PATTERN_MASK_SECTION, frozenset())
    shown_kinds = _kinds(shown)
    assert RowKind.RENDER_PATTERN_MASK_SEED in shown_kinds
    assert RowKind.RENDER_PATTERN_MASK_TYPE in shown_kinds
    seed = next(row for row in shown if row.descriptor.kind == RowKind.RENDER_PATTERN_MASK_SEED)
    assert seed.is_group is False
    assert seed.navigable is row_spec(RowKind.RENDER_PATTERN_MASK_SEED).navigable


def test_settings_and_project_omit_top_headers() -> None:
    state = _view_state()
    settings = build_inspector_rows(state, "settings", frozenset())
    project = build_inspector_rows(state, "project", frozenset())

    assert settings == rows_for_section(state, SETTINGS_SECTION, frozenset())
    latency = _group_leaves(settings, RowKind.SETTINGS_LATENCY_COMPENSATION_HEADER)
    assert latency[-1].command_id == "settings.measure_latency"
    assert RowKind.SETTINGS_EDITOR_WINDOW_HEADER in _kinds(settings)
    assert RowKind.SETTINGS_UI_HEADER in _kinds(settings)
    assert RowKind.SETTINGS_LATENCY_COMPENSATION_HEADER in _kinds(settings)


def test_unmigrated_nodes_return_no_rows() -> None:
    state = _view_state()
    for node_id in ("render", "layers", "song_markers", "unknown"):
        assert build_inspector_rows(state, node_id, frozenset()) == ()
