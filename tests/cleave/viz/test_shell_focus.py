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

_BOTH = (
    CycleStop.MENU,
    CycleStop.NAVIGATOR,
    CycleStop.INSPECTOR,
    CycleStop.HELP,
    CycleStop.TIMELINE,
)
_HELP_ONLY = (
    CycleStop.MENU,
    CycleStop.NAVIGATOR,
    CycleStop.INSPECTOR,
    CycleStop.HELP,
)
_STRIP_ONLY = (
    CycleStop.MENU,
    CycleStop.NAVIGATOR,
    CycleStop.INSPECTOR,
    CycleStop.TIMELINE,
)
_NEITHER = (
    CycleStop.MENU,
    CycleStop.NAVIGATOR,
    CycleStop.INSPECTOR,
)


def _assert_cycle(
    stops: tuple[CycleStop, ...], *, strip_open: bool, help_open: bool
) -> None:
    count = len(stops)
    for index, stop in enumerate(stops):
        assert next_region(
            stop, strip_open=strip_open, help_open=help_open, delta=1
        ) is stops[(index + 1) % count]
        assert next_region(
            stop, strip_open=strip_open, help_open=help_open, delta=-1
        ) is stops[(index - 1) % count]
        assert next_region(
            stop, strip_open=strip_open, help_open=help_open, delta=0
        ) is stop


def test_tab_cycle_with_help_and_strip_open() -> None:
    assert len(_BOTH) == 5
    _assert_cycle(_BOTH, strip_open=True, help_open=True)


def test_tab_cycle_with_strip_open_skips_closed_help() -> None:
    assert len(_STRIP_ONLY) == 4
    _assert_cycle(_STRIP_ONLY, strip_open=True, help_open=False)
    assert next_region(
        CycleStop.HELP, strip_open=True, help_open=False, delta=1
    ) is CycleStop.TIMELINE
    assert next_region(
        CycleStop.HELP, strip_open=True, help_open=False, delta=-1
    ) is CycleStop.NAVIGATOR
    assert next_region(
        CycleStop.HELP, strip_open=True, help_open=False, delta=0
    ) is CycleStop.INSPECTOR


def test_tab_cycle_with_help_open_skips_closed_strip() -> None:
    assert len(_HELP_ONLY) == 4
    _assert_cycle(_HELP_ONLY, strip_open=False, help_open=True)
    assert next_region(
        CycleStop.TIMELINE, strip_open=False, help_open=True, delta=1
    ) is CycleStop.HELP
    assert next_region(
        CycleStop.TIMELINE, strip_open=False, help_open=True, delta=-1
    ) is CycleStop.NAVIGATOR
    assert next_region(
        CycleStop.TIMELINE, strip_open=False, help_open=True, delta=0
    ) is CycleStop.INSPECTOR


def test_tab_cycle_with_strip_closed_skips_timeline() -> None:
    assert len(_NEITHER) == 3
    _assert_cycle(_NEITHER, strip_open=False, help_open=False)
    assert next_region(
        CycleStop.TIMELINE, strip_open=False, help_open=False, delta=1
    ) is CycleStop.MENU
    assert next_region(
        CycleStop.TIMELINE, strip_open=False, help_open=False, delta=-1
    ) is CycleStop.NAVIGATOR
    assert next_region(
        CycleStop.TIMELINE, strip_open=False, help_open=False, delta=0
    ) is CycleStop.INSPECTOR
    assert next_region(
        CycleStop.HELP, strip_open=False, help_open=False, delta=1
    ) is CycleStop.MENU
    assert next_region(
        CycleStop.HELP, strip_open=False, help_open=False, delta=-1
    ) is CycleStop.NAVIGATOR
    assert next_region(
        CycleStop.HELP, strip_open=False, help_open=False, delta=0
    ) is CycleStop.INSPECTOR


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
    assert [region.name for region in ShellRegion] == [
        "NAVIGATOR",
        "INSPECTOR",
        "TIMELINE",
        "HELP",
    ]
    assert not hasattr(ShellRegion, "PANEL")
    assert escape_region(ShellRegion.NAVIGATOR) is ShellRegion.NAVIGATOR
    assert escape_region(ShellRegion.INSPECTOR) is ShellRegion.NAVIGATOR
    assert escape_region(ShellRegion.TIMELINE) is ShellRegion.TIMELINE
    assert escape_region(ShellRegion.HELP) is ShellRegion.HELP


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
    assert state.help_subject is CycleStop.NAVIGATOR
    assert state.selected_id == "settings"
    assert state.inspector_cursor is None
    assert state.collapsed == frozenset()
    assert state.opened == frozenset()
    assert state.nav_expanded == {"layers", "render", "timeline"}
    other = ShellFocusState()
    state.nav_expanded.add("render.overlays")
    state.collapsed.add(InspectorGroupKey(RowKind.PROJECT_MILKDROP_HEADER))
    state.opened.add(InspectorGroupKey(RowKind.TRACK_EFFECTS_HEADER, slot="layer_1"))
    assert other.nav_expanded == {"layers", "render", "timeline"}
    assert other.collapsed == frozenset()
    assert other.opened == frozenset()
