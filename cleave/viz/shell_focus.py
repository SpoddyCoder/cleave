"""Shell focus model: region, Tab cycle, and escape.

``ShellRegion`` is where focus sits, including the leftover panel.
``CycleStop`` is the Tab ring. Menu and timeline cursors stay in their
existing owners; this module only names the stops.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum, auto

from cleave.viz.row_kinds import RowDescriptor, RowKind


class ShellRegion(Enum):
    """Focus region inside the shell. PANEL is never a Tab stop."""

    NAVIGATOR = auto()
    INSPECTOR = auto()
    PANEL = auto()


class CycleStop(Enum):
    """Tab-cycle stop. Menu and timeline are still their existing cursors."""

    MENU = auto()
    NAVIGATOR = auto()
    INSPECTOR = auto()
    TIMELINE = auto()


_CYCLE_OPEN: tuple[CycleStop, ...] = (
    CycleStop.MENU,
    CycleStop.NAVIGATOR,
    CycleStop.INSPECTOR,
    CycleStop.TIMELINE,
)
_CYCLE_CLOSED: tuple[CycleStop, ...] = (
    CycleStop.MENU,
    CycleStop.NAVIGATOR,
    CycleStop.INSPECTOR,
)


@dataclass
class ShellFocusState:
    """Mutable focus owned by ``TuningControls``.

    ``collapsed`` is the inspector group set. Pure helpers in this module do
    not mutate it.
    """

    region: ShellRegion = ShellRegion.NAVIGATOR
    selected_id: str = "settings"
    inspector_cursor: RowDescriptor | None = None
    collapsed: set[RowKind] = field(default_factory=set)
    inspector_command_id: str | None = None


def next_region(current: CycleStop, *, strip_open: bool, delta: int) -> CycleStop:
    """Move *delta* steps around the Tab cycle.

    Order is Menu, Navigator, Inspector, Timeline. Timeline is skipped when
    *strip_open* is false. A closed strip treats a Timeline current stop as
    Inspector before *delta* is applied. *delta* of 0 returns that stop.
    """
    if not strip_open and current is CycleStop.TIMELINE:
        current = CycleStop.INSPECTOR
    if delta == 0:
        return current
    stops = _CYCLE_OPEN if strip_open else _CYCLE_CLOSED
    index = stops.index(current)
    return stops[(index + delta) % len(stops)]


def quick_nav_id(visible_ids: Sequence[str], selected_id: str, delta: int) -> str:
    """Previous or next id in *visible_ids*, wrapping.

    An empty list returns *selected_id*. When *selected_id* is missing, a
    positive *delta* returns the first id and a negative *delta* the last.
    """
    if not visible_ids:
        return selected_id
    ids = tuple(visible_ids)
    try:
        index = ids.index(selected_id)
    except ValueError:
        if delta > 0:
            return ids[0]
        if delta < 0:
            return ids[-1]
        return selected_id
    if delta == 0:
        return selected_id
    return ids[(index + delta) % len(ids)]


def escape_region(region: ShellRegion, *, leftover_rows: bool) -> ShellRegion:
    """Escape target for *region*.

    Inspector always returns to the navigator. The navigator returns to the
    panel only while leftover rows exist. The panel stays on the panel.
    """
    if region is ShellRegion.INSPECTOR:
        return ShellRegion.NAVIGATOR
    if region is ShellRegion.NAVIGATOR and leftover_rows:
        return ShellRegion.PANEL
    return region
