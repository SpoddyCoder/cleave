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
    return tl.expanded and len(state.layer_z_order) > 0


def build_focus_ring(state: TuningViewState) -> list[FocusCursor]:
    frame = state.layout_frame
    if frame is not None:
        ring: list[FocusCursor] = [
            MainFocus(descriptor) for descriptor in frame.navigable_descriptors
        ]
    else:
        ring = [
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


def build_quick_nav_ring(state: TuningViewState) -> list[FocusCursor]:
    """Section stops for Ctrl+Up/Down: open/anchor headers, then timeline strip."""
    ring: list[FocusCursor] = [
        MainFocus(state.layout.descriptor(index))
        for index in state.layout.quick_nav_indices(state)
    ]
    if timeline_strip_in_ring(state):
        ring.append(TimelineFocus(0))
    return ring


def _timeline_section_landing(cursor: FocusCursor) -> TimelineFocus:
    if isinstance(cursor, TimelineFocus):
        return TimelineFocus(cursor.row)
    return TimelineFocus(0)


def _coerce_quick_nav_target(
    target: FocusCursor, cursor: FocusCursor
) -> FocusCursor:
    if isinstance(target, TimelineFocus):
        return _timeline_section_landing(cursor)
    return target


def move_quick_focus(
    cursor: FocusCursor, delta: int, state: TuningViewState
) -> FocusCursor:
    """Jump to the previous/next section stop, including the timeline strip."""
    ring = build_quick_nav_ring(state)
    if not ring:
        return cursor

    if isinstance(cursor, TimelineFocus):
        for index, item in enumerate(ring):
            if isinstance(item, TimelineFocus):
                return _coerce_quick_nav_target(
                    ring[(index + delta) % len(ring)], cursor
                )
        cursor = MainFocus(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))

    assert isinstance(cursor, MainFocus)
    descriptor = cursor.descriptor
    for index, item in enumerate(ring):
        if isinstance(item, MainFocus) and item.descriptor == descriptor:
            return _coerce_quick_nav_target(
                ring[(index + delta) % len(ring)], cursor
            )

    layout = state.layout
    if layout.contains_descriptor(descriptor):
        current_index = layout.find_descriptor(descriptor)
    else:
        resolved = layout.resolve_navigable(descriptor, state)
        current_index = (
            layout.find_descriptor(resolved)
            if layout.contains_descriptor(resolved)
            else -1
        )

    if delta > 0:
        after = [
            item
            for item in ring
            if isinstance(item, MainFocus)
            and layout.find_descriptor(item.descriptor) > current_index
        ]
        if after:
            return after[0]
        if timeline_strip_in_ring(state) and layout.contains_descriptor(
            RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
        ):
            timeline_header_index = layout.find_descriptor(
                RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
            )
            if current_index >= timeline_header_index:
                return _timeline_section_landing(cursor)
        return _coerce_quick_nav_target(ring[0], cursor)

    before = [
        item
        for item in ring
        if isinstance(item, MainFocus)
        and layout.find_descriptor(item.descriptor) < current_index
    ]
    if before:
        return before[-1]
    return _coerce_quick_nav_target(ring[-1], cursor)


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
