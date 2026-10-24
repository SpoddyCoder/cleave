"""Focus cursor for the shell and the timeline strip.

``TimelineFocus`` is the strip lane. ``MainFocus`` is the cursor while the
strip does not have scope. Nothing walks a list of main-list descriptors.
"""

from __future__ import annotations

from dataclasses import dataclass

from cleave.viz.row_kinds import RowDescriptor, RowKind


@dataclass(frozen=True)
class MainFocus:
    descriptor: RowDescriptor


@dataclass(frozen=True)
class TimelineFocus:
    row: int  # 0..N-1 into layer_z_order


FocusCursor = MainFocus | TimelineFocus


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
