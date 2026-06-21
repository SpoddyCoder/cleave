"""Unified focus cursor and navigation for the main tree and timeline strip."""

from __future__ import annotations

from dataclasses import dataclass

from cleave.viz.tuning_view_state import TuningViewState
from cleave.viz.row_semantics import RowDescriptor, RowKind


@dataclass(frozen=True)
class MainFocus:
    descriptor: RowDescriptor


@dataclass(frozen=True)
class TimelineFocus:
    row: int  # 0..N-1 into layer_z_order


FocusCursor = MainFocus | TimelineFocus


def timeline_strip_in_ring(state: TuningViewState) -> bool:
    tl = state.render_timeline
    return tl.expanded and tl.enabled and len(state.layer_z_order) > 0


def build_focus_ring(state: TuningViewState) -> list[FocusCursor]:
    ring: list[FocusCursor] = [
        MainFocus(descriptor)
        for descriptor in state.layout.navigable_descriptors(state)
    ]
    if timeline_strip_in_ring(state):
        ring.extend(TimelineFocus(row) for row in range(len(state.layer_z_order)))
    return ring


def resolve_cursor(
    cursor: FocusCursor,
    ring: list[FocusCursor],
    state: TuningViewState,
) -> FocusCursor:
    if not ring:
        if isinstance(cursor, MainFocus):
            return MainFocus(state.layout.resolve_navigable(cursor.descriptor, state))
        row_count = len(state.layer_z_order)
        row = 0 if row_count == 0 else max(0, min(cursor.row, row_count - 1))
        return TimelineFocus(row)

    if isinstance(cursor, MainFocus):
        resolved = MainFocus(state.layout.resolve_navigable(cursor.descriptor, state))
        for item in ring:
            if item == resolved:
                return item
        for item in ring:
            if isinstance(item, MainFocus):
                return item
        return ring[0]

    row_count = len(state.layer_z_order)
    row = 0 if row_count == 0 else max(0, min(cursor.row, row_count - 1))
    resolved = TimelineFocus(row)
    for item in ring:
        if item == resolved:
            return item
    timeline_header = RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
    for item in ring:
        if isinstance(item, MainFocus) and item.descriptor == timeline_header:
            return item
    for item in ring:
        if isinstance(item, MainFocus):
            return item
    return ring[0]


def move_focus(cursor: FocusCursor, delta: int, state: TuningViewState) -> FocusCursor:
    ring = build_focus_ring(state)
    if not ring:
        return cursor
    resolved = resolve_cursor(cursor, ring, state)
    try:
        pos = ring.index(resolved)
    except ValueError:
        pos = 0
    return ring[(pos + delta) % len(ring)]


def cursor_main_descriptor(cursor: FocusCursor) -> RowDescriptor:
    if isinstance(cursor, MainFocus):
        return cursor.descriptor
    return RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)


def cursor_timeline_submenu_focused(cursor: FocusCursor) -> bool:
    return isinstance(cursor, TimelineFocus)


def cursor_timeline_row(cursor: FocusCursor) -> int:
    if isinstance(cursor, TimelineFocus):
        return cursor.row
    return 0
