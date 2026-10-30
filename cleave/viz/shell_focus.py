"""Shell focus model: region, Tab cycle, and escape.

``ShellRegion`` is where keyboard scope sits: navigator, inspector, help,
or the timeline strip. ``CycleStop`` is the Tab ring. The menu bar stays
``menu_bar.focused`` and is not a region. ``next_region`` skips Help when
the column is closed and Timeline when the strip is closed.
"""

from __future__ import annotations

from collections.abc import Sequence, Set as AbstractSet
from dataclasses import dataclass, field
from enum import Enum, auto

from cleave.viz.navigator import LAYER_ID_PREFIX
from cleave.viz.row_kinds import RowDescriptor, RowKind


class ShellRegion(Enum):
    """Focus region that owns keyboard scope."""

    NAVIGATOR = auto()
    INSPECTOR = auto()
    TIMELINE = auto()
    HELP = auto()


class CycleStop(Enum):
    """Tab-cycle stop. Menu is the menu bar, not a ``ShellRegion``."""

    MENU = auto()
    NAVIGATOR = auto()
    INSPECTOR = auto()
    HELP = auto()
    TIMELINE = auto()


@dataclass(frozen=True)
class InspectorGroupKey:
    """Identity of one inspector group.

    A group is open unless this key is in ``ShellFocusState.collapsed``.
    Kinds in ``DEFAULT_CLOSED_INSPECTOR_GROUPS`` start closed and are open
    only while this key is in ``ShellFocusState.opened``. Toggles write those
    sets; building a page does not re-seed them, so an opened cleave-effects
    group stays open for that slot until it is closed. Settings and Project
    use ``slot=None`` and ``card=None``. Later card pages reuse ``card``.
    """

    kind: RowKind
    slot: str | None = None
    card: str | None = None


DEFAULT_CLOSED_INSPECTOR_GROUPS = frozenset(
    {
        RowKind.TRACK_EFFECTS_HEADER,
        RowKind.TIMELINE_BEAT_BAR_GRID_HEADER,
        RowKind.TIMELINE_CUTS_HEADER,
    }
)


def inspector_group_is_open(
    key: InspectorGroupKey,
    collapsed: AbstractSet[InspectorGroupKey],
    opened: AbstractSet[InspectorGroupKey],
) -> bool:
    if key.kind in DEFAULT_CLOSED_INSPECTOR_GROUPS:
        return key in opened
    return key not in collapsed


def toggle_inspector_group(
    collapsed: set[InspectorGroupKey],
    opened: set[InspectorGroupKey],
    key: InspectorGroupKey,
) -> None:
    target = opened if key.kind in DEFAULT_CLOSED_INSPECTOR_GROUPS else collapsed
    if key in target:
        target.discard(key)
    else:
        target.add(key)


@dataclass
class ShellFocusState:
    """Mutable focus owned by ``TuningControls``.

    ``collapsed`` and ``opened`` hold ``InspectorGroupKey`` values.
    ``nav_expanded`` is the set of expanded navigator ids. Pure helpers in
    this module do not mutate these sets. ``help_subject`` is the Menu,
    Navigator, Inspector, or Timeline stop restored when leaving Help.
    """

    region: ShellRegion = ShellRegion.NAVIGATOR
    help_subject: CycleStop = CycleStop.NAVIGATOR
    selected_id: str = "settings"
    inspector_cursor: RowDescriptor | None = None
    collapsed: set[InspectorGroupKey] = field(default_factory=set)
    opened: set[InspectorGroupKey] = field(default_factory=set)
    inspector_command_id: str | None = None
    nav_expanded: set[str] = field(default_factory=lambda: {"layers", "render", "timeline"})


def cycle_stops(*, help_open: bool, strip_open: bool) -> tuple[CycleStop, ...]:
    """Tab order with Help and Timeline included only while each is open."""
    stops = [CycleStop.MENU, CycleStop.NAVIGATOR, CycleStop.INSPECTOR]
    if help_open:
        stops.append(CycleStop.HELP)
    if strip_open:
        stops.append(CycleStop.TIMELINE)
    return tuple(stops)


def next_region(
    current: CycleStop,
    *,
    strip_open: bool,
    help_open: bool,
    delta: int,
) -> CycleStop:
    """Move *delta* steps around the Tab cycle.

    Order is Menu, Navigator, Inspector, Help, Timeline. Help is skipped
    when *help_open* is false. Timeline is skipped when *strip_open* is
    false. A closed column treats a Help current stop as Inspector before
    *delta* is applied, the same way a closed strip treats Timeline as
    Inspector. *delta* of 0 returns that stop.
    """
    if not help_open and current is CycleStop.HELP:
        current = CycleStop.INSPECTOR
    if not strip_open and current is CycleStop.TIMELINE:
        current = CycleStop.INSPECTOR
    if delta == 0:
        return current
    stops = cycle_stops(help_open=help_open, strip_open=strip_open)
    index = stops.index(current)
    return stops[(index + delta) % len(stops)]


def cycle_stop_for_focus(
    *,
    menu_focused: bool,
    region: ShellRegion,
    help_open: bool,
    strip_open: bool,
) -> CycleStop:
    """Active Tab stop from menu focus, the shell region, and which columns are open.

    A Help region with the column closed is Inspector, so the stop does not
    stay on Help. A closed strip does not report Timeline.
    """
    if menu_focused:
        return CycleStop.MENU
    if region is ShellRegion.HELP and help_open:
        return CycleStop.HELP
    if region is ShellRegion.TIMELINE and strip_open:
        return CycleStop.TIMELINE
    if region is ShellRegion.INSPECTOR or region is ShellRegion.HELP:
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

    A missing ``layer:<slot>`` lands on the nearest remaining layer sibling
    by z-order index, then ``layers`` when that id is visible, then the first
    visible id. An empty *visible_ids* returns *selected_id*.
    """
    if not visible_ids:
        return selected_id
    ids = tuple(visible_ids)
    if selected_id in ids:
        return selected_id
    if selected_id.startswith(LAYER_ID_PREFIX):
        slot = selected_id[len(LAYER_ID_PREFIX) :]
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
        if not node_id.startswith(LAYER_ID_PREFIX):
            continue
        child = node_id[len(LAYER_ID_PREFIX) :]
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
    closes through timeline controls. Help is not redirected here; Esc closes
    the column and restores the subject stop.
    """
    if region is ShellRegion.INSPECTOR:
        return ShellRegion.NAVIGATOR
    return region
