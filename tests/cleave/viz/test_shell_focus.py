"""Shell focus model: Tab cycle, quick nav, and escape."""

from __future__ import annotations

from cleave.viz.navigator import TOP_LEVEL_IDS
from cleave.viz.row_kinds import RowKind
from cleave.viz.shell_focus import (
    CycleStop,
    InspectorGroupKey,
    ShellFocusState,
    ShellRegion,
    escape_region,
    next_region,
    quick_nav_id,
    reconcile_nav_id,
    tree_nav_id,
)

_OPEN = (
    CycleStop.MENU,
    CycleStop.NAVIGATOR,
    CycleStop.INSPECTOR,
    CycleStop.TIMELINE,
)
_CLOSED = (
    CycleStop.MENU,
    CycleStop.NAVIGATOR,
    CycleStop.INSPECTOR,
)


def test_tab_cycle_with_strip_open_has_four_stops() -> None:
    assert len(_OPEN) == 4
    for index, stop in enumerate(_OPEN):
        assert next_region(stop, strip_open=True, delta=1) is _OPEN[(index + 1) % 4]
        assert next_region(stop, strip_open=True, delta=-1) is _OPEN[(index - 1) % 4]
        assert next_region(stop, strip_open=True, delta=0) is stop


def test_tab_cycle_with_strip_closed_skips_timeline() -> None:
    assert len(_CLOSED) == 3
    for index, stop in enumerate(_CLOSED):
        assert next_region(stop, strip_open=False, delta=1) is _CLOSED[(index + 1) % 3]
        assert next_region(stop, strip_open=False, delta=-1) is _CLOSED[(index - 1) % 3]
        assert next_region(stop, strip_open=False, delta=0) is stop
    assert next_region(CycleStop.TIMELINE, strip_open=False, delta=1) is CycleStop.MENU
    assert next_region(CycleStop.TIMELINE, strip_open=False, delta=-1) is CycleStop.NAVIGATOR
    assert next_region(CycleStop.TIMELINE, strip_open=False, delta=0) is CycleStop.INSPECTOR


def test_quick_nav_walks_top_level_ids_and_wraps() -> None:
    ids = TOP_LEVEL_IDS
    assert len(ids) == 5
    selected = ids[0]
    for expected in ids[1:]:
        selected = quick_nav_id(ids, selected, 1)
        assert selected == expected
    assert quick_nav_id(ids, ids[-1], 1) == ids[0]
    assert quick_nav_id(ids, ids[0], -1) == ids[-1]
    selected = ids[-1]
    for expected in reversed(ids[:-1]):
        selected = quick_nav_id(ids, selected, -1)
        assert selected == expected
    assert quick_nav_id((), "settings", 1) == "settings"
    assert quick_nav_id(ids, "missing", 1) == ids[0]
    assert quick_nav_id(ids, "missing", -1) == ids[-1]


def test_escape_region() -> None:
    assert escape_region(ShellRegion.NAVIGATOR) is ShellRegion.NAVIGATOR
    assert escape_region(ShellRegion.INSPECTOR) is ShellRegion.NAVIGATOR
    assert not hasattr(ShellRegion, "PANEL")


def test_tree_nav_stops_at_the_ends() -> None:
    ids = ("a", "b", "c")
    assert tree_nav_id(ids, "a", -1) == "a"
    assert tree_nav_id(ids, "c", 1) == "c"
    assert tree_nav_id(ids, "b", 1) == "c"
    assert tree_nav_id(ids, "b", -1) == "a"
    assert tree_nav_id(ids, "b", 0) == "b"
    assert tree_nav_id(ids, "a", 5) == "c"
    assert tree_nav_id(ids, "missing", 1) == "a"
    assert tree_nav_id(ids, "missing", -1) == "c"
    assert tree_nav_id(ids, "missing", 0) == "missing"
    assert tree_nav_id((), "settings", -1) == "settings"


def test_reconcile_nav_id_repairs_a_missing_layer() -> None:
    visible = ("settings", "layers", "layer:a", "layer:c")
    order = ("a", "b", "c")
    assert reconcile_nav_id(visible, "settings", order) == "settings"
    assert reconcile_nav_id(visible, "layer:b", order) == "layer:a"
    assert (
        reconcile_nav_id(visible, "layer:b", ("a", "c"), prior_index=1) == "layer:c"
    )
    assert (
        reconcile_nav_id(("settings", "layers"), "layer:gone", (), prior_index=0)
        == "layers"
    )
    assert reconcile_nav_id(("settings",), "project", ()) == "settings"
    assert reconcile_nav_id(("settings", "layers"), "project", ()) == "layers"
    assert reconcile_nav_id((), "layer:a", ("a",)) == "layer:a"


def test_shell_focus_state_defaults() -> None:
    state = ShellFocusState()
    assert state.region is ShellRegion.NAVIGATOR
    assert state.selected_id == "settings"
    assert state.inspector_cursor is None
    assert state.collapsed == frozenset()
    assert state.opened == frozenset()
    assert state.nav_expanded == {"layers", "render"}
    other = ShellFocusState()
    state.nav_expanded.add("render.overlays")
    state.collapsed.add(InspectorGroupKey(RowKind.PROJECT_MILKDROP_HEADER))
    state.opened.add(InspectorGroupKey(RowKind.TRACK_EFFECTS_HEADER, slot="layer_1"))
    assert other.nav_expanded == {"layers", "render"}
    assert other.collapsed == frozenset()
    assert other.opened == frozenset()
