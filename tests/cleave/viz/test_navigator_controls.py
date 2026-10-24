"""Navigator Enter: inspector groups and leftover headers."""

from __future__ import annotations

from cleave.viz.inspector import build_inspector_rows
from cleave.viz.navigator import layer_node_id
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.shell_focus import ShellRegion
from tests.cleave.viz.test_controls import _make_controls, _make_controls_with_manager


def test_enter_on_project_builds_inspector_groups() -> None:
    controls = _make_controls(("layer_1",))
    controls.shell_focus.selected_id = "project"
    controls.shell_focus.region = ShellRegion.NAVIGATOR
    controls.navigator.activate()
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    view = controls.build_view_state(paused=controls.playback.paused)
    rows = build_inspector_rows(view, "project", controls.shell_focus.collapsed)
    groups = tuple(
        row.descriptor.kind for row in rows if row.is_group and row.descriptor is not None
    )
    assert groups == (
        RowKind.PROJECT_MILKDROP_HEADER,
        RowKind.PROJECT_COMPOSITOR_HEADER,
        RowKind.PROJECT_RENDER_HEADER,
    )
    assert controls.shell_focus.inspector_cursor == next(
        row.descriptor for row in rows if row.navigable and row.descriptor is not None
    )


def test_enter_on_render_opens_overlays_inspector() -> None:
    controls = _make_controls(("layer_1",))
    focus = controls.shell_focus
    focus.selected_id = "render"
    focus.region = ShellRegion.NAVIGATOR
    focus.nav_expanded.discard("render")
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
    controls.navigator.activate()
    assert "render" in focus.nav_expanded
    assert focus.selected_id == "render.overlays"
    assert focus.region is ShellRegion.INSPECTOR
    view = controls.build_view_state(paused=controls.playback.paused)
    rows = build_inspector_rows(
        view, "render.overlays", focus.collapsed, focus.opened
    )
    assert focus.inspector_cursor == next(
        row.descriptor
        for row in rows
        if row.navigable and row.descriptor is not None
    )
    assert controls.focus_descriptor.kind is RowKind.RENDER_TIMELINE_HEADER


def test_enter_on_render_blocks_stays_off_the_panel() -> None:
    controls = _make_controls(("layer_1",))
    focus = controls.shell_focus
    focus.nav_expanded.add("render")
    view = controls.build_view_state(paused=controls.playback.paused)
    for node_id in ("render.overlays", "render.post_fx", "render.pattern_mask"):
        focus.selected_id = node_id
        focus.region = ShellRegion.NAVIGATOR
        controls.navigator.activate()
        assert focus.region is ShellRegion.INSPECTOR
        assert focus.selected_id == node_id
        rows = build_inspector_rows(
            view, node_id, focus.collapsed, focus.opened
        )
        assert focus.inspector_cursor == next(
            row.descriptor
            for row in rows
            if row.navigable and row.descriptor is not None
        )


def test_enter_on_song_markers_hands_off_to_leftover_panel() -> None:
    controls = _make_controls(("layer_1",))
    focus = controls.shell_focus
    focus.selected_id = "song_markers"
    focus.region = ShellRegion.NAVIGATOR
    controls.navigator.activate()
    assert focus.region is ShellRegion.PANEL
    assert focus.selected_id == "song_markers"
    assert controls.focus_descriptor.kind is RowKind.RENDER_TIMELINE_HEADER


def test_select_render_leaves_the_leftover_cursor() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
    controls.navigator.select("render")
    assert controls.shell_focus.region is ShellRegion.NAVIGATOR
    assert controls.shell_focus.selected_id == "render"
    assert controls.focus_descriptor.kind is RowKind.RENDER_TIMELINE_HEADER


def test_enter_on_layers_opens_inspector() -> None:
    controls = _make_controls(("layer_1",))
    controls.shell_focus.selected_id = "layers"
    controls.shell_focus.region = ShellRegion.NAVIGATOR
    before = controls.focus_descriptor
    controls.navigator.activate()
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    assert controls.focus_descriptor == before
    view = controls.build_view_state(paused=controls.playback.paused)
    focus = controls.shell_focus
    rows = build_inspector_rows(
        view, "layers", focus.collapsed, focus.opened
    )
    assert [row.descriptor.kind for row in rows if row.descriptor is not None] == [
        RowKind.LAYER_MANAGEMENT_COUNT,
    ]
    assert focus.inspector_command_id == "layers.add"
    assert focus.inspector_cursor is None

    controls.shell_focus.region = ShellRegion.NAVIGATOR
    controls.shell_focus.selected_id = layer_node_id("layer_1")
    controls.navigator.activate()
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    assert controls.focus_descriptor == before
    layer_rows = build_inspector_rows(
        view, layer_node_id("layer_1"), focus.collapsed, focus.opened
    )
    layer_kinds = [
        row.descriptor.kind
        for row in layer_rows
        if row.descriptor is not None
    ]
    assert RowKind.TRACK_HEADER not in layer_kinds
    assert RowKind.TRACK_PRESET in layer_kinds
    assert focus.inspector_cursor == next(
        row.descriptor
        for row in layer_rows
        if row.navigable and row.descriptor is not None
    )


def test_selecting_layers_does_not_focus_track_header() -> None:
    controls = _make_controls(("layer_1",))
    controls.navigator.select("render")
    assert controls.focus_descriptor.kind is RowKind.RENDER_OVERLAYS_HEADER
    controls.navigator.select("layers")
    assert controls.shell_focus.region is ShellRegion.NAVIGATOR
    assert controls.focus_descriptor.kind is RowKind.RENDER_OVERLAYS_HEADER
    controls.navigator.select(layer_node_id("layer_1"))
    assert controls.focus_descriptor.kind is RowKind.RENDER_OVERLAYS_HEADER


def test_quick_step_stays_on_top_level_ids() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.shell_focus.selected_id = "layers"
    controls.navigator.quick_step(1)
    assert controls.shell_focus.selected_id == "song_markers"
    controls.navigator.quick_step(1)
    assert controls.shell_focus.selected_id == "settings"
    controls.shell_focus.selected_id = layer_node_id("layer_2")
    controls.navigator.quick_step(1)
    assert controls.shell_focus.selected_id == "settings"
    controls.shell_focus.selected_id = layer_node_id("layer_2")
    controls.navigator.quick_step(-1)
    assert controls.shell_focus.selected_id == "song_markers"


def test_delete_reconciles_to_nearest_layer_sibling() -> None:
    controls, manager = _make_controls_with_manager(("layer_1", "layer_2", "layer_3"))
    controls.shell_focus.selected_id = layer_node_id("layer_2")

    def remove(slot: str) -> None:
        controls.session.layer_z_order.remove(slot)
        del controls.session.layers[slot]

    manager.remove_layer.side_effect = remove
    controls.layer_lifecycle.confirm_delete("layer_2")
    assert controls.shell_focus.selected_id == layer_node_id("layer_3")
    assert controls.layer_lifecycle.removed_layer_index is None

    controls.shell_focus.selected_id = layer_node_id("layer_3")
    controls.layer_lifecycle.confirm_delete("layer_3")
    assert controls.shell_focus.selected_id == layer_node_id("layer_1")
