"""Shell focus model: region, Tab cycle, and escape.

``ShellRegion`` is where keyboard scope sits: navigator, inspector, or the
timeline strip. ``CycleStop`` is the Tab ring. The menu bar stays
``menu_bar.focused`` and is not a region. Help is a column, not a stop.
``next_region`` skips Timeline when the strip is closed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum, auto

from cleave.viz.navigator import (
    DEFAULT_SELECTED_ID,
    LAYER_ID_PREFIX,
    expansion_path,
    layer_node_id,
    layer_page_of,
    layer_slot_of,
)
from cleave.viz.row_kinds import RowDescriptor


class ShellRegion(Enum):
    """Focus region that owns keyboard scope."""

    NAVIGATOR = auto()
    INSPECTOR = auto()
    TIMELINE = auto()


class CycleStop(Enum):
    """Tab-cycle stop. Menu is the menu bar, not a ``ShellRegion``."""

    MENU = auto()
    NAVIGATOR = auto()
    INSPECTOR = auto()
    TIMELINE = auto()


@dataclass
class ShellFocusState:
    """Mutable focus owned by ``TuningControls``.

    ``nav_expanded`` is the set of expanded navigator ids. Selecting a node
    resets it to that node's path. Pure helpers in this module do not mutate it.
    """

    region: ShellRegion = ShellRegion.NAVIGATOR
    selected_id: str = DEFAULT_SELECTED_ID
    inspector_cursor: RowDescriptor | None = None
    inspector_command_id: str | None = None
    nav_expanded: set[str] = field(
        default_factory=lambda: expansion_path(DEFAULT_SELECTED_ID)
    )


def cycle_stops(*, strip_open: bool) -> tuple[CycleStop, ...]:
    """Tab order. Timeline is included only while the strip is open."""
    stops = [CycleStop.MENU, CycleStop.NAVIGATOR, CycleStop.INSPECTOR]
    if strip_open:
        stops.append(CycleStop.TIMELINE)
    return tuple(stops)


def next_region(
    current: CycleStop,
    *,
    strip_open: bool,
    delta: int,
) -> CycleStop:
    """Move *delta* steps around the Tab cycle.

    Order is Menu, Navigator, Inspector, Timeline. Timeline is skipped when
    *strip_open* is false. A closed strip treats a Timeline current stop as
    Inspector before *delta* is applied. *delta* of 0 returns that stop.
    """
    if not strip_open and current is CycleStop.TIMELINE:
        current = CycleStop.INSPECTOR
    if delta == 0:
        return current
    stops = cycle_stops(strip_open=strip_open)
    index = stops.index(current)
    return stops[(index + delta) % len(stops)]


def cycle_stop_for_focus(
    *,
    menu_focused: bool,
    region: ShellRegion,
    strip_open: bool,
) -> CycleStop:
    """Active Tab stop from menu focus, the shell region, and whether the strip is open.

    A closed strip does not report Timeline.
    """
    if menu_focused:
        return CycleStop.MENU
    if region is ShellRegion.TIMELINE and strip_open:
        return CycleStop.TIMELINE
    if region is ShellRegion.INSPECTOR:
        return CycleStop.INSPECTOR
    return CycleStop.NAVIGATOR


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


def tree_nav_id(visible_ids: Sequence[str], selected_id: str, delta: int) -> str:
    """Move *delta* steps among *visible_ids* without wrapping.

    An empty list returns *selected_id*. When *selected_id* is missing, a
    positive *delta* returns the first id and a negative *delta* the last.
    *delta* of 0 returns *selected_id*. Once on the list, movement stops at
    the ends.
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
    next_index = index + delta
    if next_index < 0:
        next_index = 0
    elif next_index >= len(ids):
        next_index = len(ids) - 1
    return ids[next_index]


def reconcile_nav_id(
    visible_ids: Sequence[str],
    selected_id: str,
    layer_z_order: Sequence[str],
    *,
    prior_index: int | None = None,
) -> str:
    """Return *selected_id* when it is visible, otherwise a nearby stand-in.

    A missing page under a visible layer lands on that layer. A missing
    ``layer:<slot>`` or a page under a removed layer lands on the nearest
    remaining layer sibling by z-order index, then ``layers`` when that id is
    visible, then the first visible id. An empty *visible_ids* returns
    *selected_id*.
    """
    if not visible_ids:
        return selected_id
    ids = tuple(visible_ids)
    if selected_id in ids:
        return selected_id
    slot = layer_slot_of(selected_id)
    if slot is not None:
        if layer_page_of(selected_id) is not None and layer_node_id(slot) in ids:
            return layer_node_id(slot)
        sibling = _nearest_layer_id(ids, layer_z_order, slot, prior_index)
        if sibling is not None:
            return sibling
    if "layers" in ids:
        return "layers"
    return ids[0]


def _nearest_layer_id(
    visible_ids: Sequence[str],
    layer_z_order: Sequence[str],
    slot: str,
    prior_index: int | None,
) -> str | None:
    order = tuple(layer_z_order)
    if slot in order:
        anchor = order.index(slot)
    elif prior_index is not None:
        anchor = prior_index
    else:
        return None
    index_of = {name: index for index, name in enumerate(order)}
    best: str | None = None
    best_key: tuple[int, int] | None = None
    for node_id in visible_ids:
        if not node_id.startswith(LAYER_ID_PREFIX) or layer_page_of(node_id):
            continue
        child = layer_slot_of(node_id)
        if child == slot or child not in index_of:
            continue
        index = index_of[child]
        key = (abs(index - anchor), index)
        if best_key is None or key < best_key:
            best_key = key
            best = node_id
    return best


def escape_region(region: ShellRegion) -> ShellRegion:
    """Escape target for *region*.

    Inspector returns to the navigator. The navigator stays on the navigator;
    the navigator hides the UI itself. Timeline stays on Timeline; the strip
    closes through timeline controls.
    """
    if region is ShellRegion.INSPECTOR:
        return ShellRegion.NAVIGATOR
    return region
